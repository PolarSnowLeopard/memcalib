#!/bin/bash
set -euo pipefail

if [[ "$#" -lt 3 || "$#" -gt 6 ]]; then
  printf 'Usage: %s MODEL_KEY SERVED_MODEL_NAME CHAT_COMPLETIONS_URL [DISPLAY_NAME] [CHECKPOINT_ROLE] [REQUEST_PROFILE]\n' "$0" >&2
  printf 'REQUEST_PROFILE: qwen_nonthinking or standard_nonthinking\n' >&2
  exit 2
fi

MODEL_KEY=$1
SERVED_MODEL_NAME=$2
CHAT_COMPLETIONS_URL=${3%/}
DISPLAY_NAME=${4:-${MEMCALIB_MODEL_DISPLAY_NAME:-$MODEL_KEY}}
CHECKPOINT_ROLE=${5:-${MEMCALIB_CHECKPOINT_ROLE:-external_local_baseline}}
REQUEST_PROFILE=${6:-${VLLM_EVAL_REQUEST_PROFILE:-standard_nonthinking}}
MODEL_ID=${MEMCALIB_MODEL_ID:-$MODEL_KEY}
MODEL_PATH=${MEMCALIB_MODEL_PATH:-}

if [[ ! "$MODEL_KEY" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  printf 'Invalid model key: %s\n' "$MODEL_KEY" >&2
  exit 2
fi
if [[ "$REQUEST_PROFILE" != "qwen_nonthinking" && "$REQUEST_PROFILE" != "standard_nonthinking" ]]; then
  printf 'Invalid request profile: %s\n' "$REQUEST_PROFILE" >&2
  exit 2
fi

ROOT=$(cd "$(dirname "$0")/../../../../.." && pwd)
cd "$ROOT"
PYTHON_BIN=${PYTHON_BIN:-python3}
RUN=${MEMCALIB_RUN:-evaluation/runs/memcalib-v241-local-baselines-1500-nonthinking-vllm/repeat-1}
CONFIG=${MEMCALIB_VLLM_CONFIG:-evaluation/current/v2.4.1/cluster/memcalib-v241-local-baselines-1500/local-vllm-config.json}
MODEL_CONFIG=${MEMCALIB_CONFIG:-evaluation/current/v2.4.1/configs/memcalib-v241-benchmark1500-local-vllm-two-models-nonthinking.json}
SAMPLE_RELEASE=${MEMCALIB_SAMPLE_RELEASE:-evaluation/current/v2.4.1/releases/memcalib-v241-benchmark-test-eval-1500}
ANSWER_PROMPT=${MEMCALIB_ANSWER_PROMPT:-evaluation/prompts/answer-system.txt}
REQUEST_ROOT="$RUN/requests/answers/$MODEL_KEY"
OUTPUT_ROOT="$RUN/answers/$MODEL_KEY"
REQUEST_MANIFEST="$RUN/request-manifests/$MODEL_KEY.json"
WORKERS=${VLLM_EVAL_WORKERS:-128}
RPM=${VLLM_EVAL_RPM:-0}
TIMEOUT=${VLLM_EVAL_TIMEOUT:-600}
MAX_TOKENS=${VLLM_EVAL_MAX_TOKENS:-8192}
SEED=${VLLM_EVAL_SEED:-42}
STRICT_COMPLETENESS=${VLLM_EVAL_STRICT_COMPLETENESS:-1}
TOKEN_ENV=MEMCALIB_VLLM_TOKEN

case "$REQUEST_PROFILE" in
  qwen_nonthinking)
    EXTRA_BODY=$(printf '{"top_p":1.0,"top_k":-1,"seed":%s,"n":1,"chat_template_kwargs":{"enable_thinking":false}}' "$SEED")
    ;;
  standard_nonthinking)
    EXTRA_BODY=$(printf '{"top_p":1.0,"top_k":-1,"seed":%s,"n":1}' "$SEED")
    ;;
esac

export MEMCALIB_VLLM_TOKEN=${MEMCALIB_VLLM_TOKEN:-EMPTY}
mkdir -p "$OUTPUT_ROOT" "$RUN/request-manifests"
printf '%s\n' "$SERVED_MODEL_NAME" > "$OUTPUT_ROOT/served-model-name.txt"
printf '%s\n' "$SEED" > "$OUTPUT_ROOT/answer-seed.txt"

if [[ ! -s "$REQUEST_ROOT/smoke.jsonl" || ! -s "$REQUEST_ROOT/full_memory.jsonl" ]]; then
  PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/prepare_answer_requests.py \
    --config "$MODEL_CONFIG" \
    --input "$SAMPLE_RELEASE/model-facing.jsonl" \
    --prompt "$ANSWER_PROMPT" \
    --output-dir "$RUN/requests/answers" \
    --manifest "$REQUEST_MANIFEST" \
    --conditions full_memory \
    --model-key "$MODEL_KEY" \
    --model "$MODEL_ID" \
    --display-name "$DISPLAY_NAME" \
    --checkpoint-role "$CHECKPOINT_ROLE"
fi

"$PYTHON_BIN" - "$OUTPUT_ROOT/model-metadata.json" "$MODEL_KEY" "$MODEL_ID" \
  "$DISPLAY_NAME" "$CHECKPOINT_ROLE" "$SERVED_MODEL_NAME" "$MODEL_PATH" \
  "$REQUEST_PROFILE" "$SEED" "$MAX_TOKENS" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

(
    output,
    key,
    model,
    display_name,
    checkpoint_role,
    served_model_name,
    model_path,
    request_profile,
    seed,
    max_tokens,
) = sys.argv[1:]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


metadata = {
    "key": key,
    "model": model,
    "display_name": display_name,
    "answer_mode": "nonthinking",
    "checkpoint_role": checkpoint_role,
    "served_model_name": served_model_name,
    "model_path": model_path or None,
    "request_profile": request_profile,
    "generation": {
        "do_sample": True,
        "temperature": 1.0,
        "top_p": 1.0,
        "top_k": -1,
        "n": 1,
        "seed": int(seed),
        "max_tokens": int(max_tokens),
    },
    "model_file_hashes": {},
}
if model_path:
    root = Path(model_path)
    for name in ("config.json", "generation_config.json", "tokenizer_config.json"):
        path = root / name
        if path.is_file():
            metadata["model_file_hashes"][name] = sha256(path)
Path(output).write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

run_cell() {
  local name=$1
  local input="$REQUEST_ROOT/$name.jsonl"
  local output="$OUTPUT_ROOT/$name.jsonl"
  local base=${output%.jsonl}

  PYTHONPATH=pipeline "$PYTHON_BIN" pipeline/06_run_bailian_api.py \
    --config "$CONFIG" \
    --input "$input" \
    --output "$output" \
    --failed "$base.failed.jsonl" \
    --invalid-output "$base.invalid.jsonl" \
    --api-key-env "$TOKEN_ENV" \
    --base-url "$CHAT_COMPLETIONS_URL" \
    --model "$SERVED_MODEL_NAME" \
    --temperature 1.0 \
    --max-tokens "$MAX_TOKENS" \
    --extra-body-json "$EXTRA_BODY" \
    --timeout "$TIMEOUT" \
    --hard-timeout "$TIMEOUT" \
    --max-retries 3 \
    --max-workers "$WORKERS" \
    --rpm "$RPM" \
    --progress-every 10 \
    2>&1 | tee -a "$base.log"

  if ! PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/validate_api_results.py \
    --input "$input" \
    --output "$output" \
    --model "$SERVED_MODEL_NAME" \
    --report "$base.validation.json"; then
    if [[ "$STRICT_COMPLETENESS" == "1" ]]; then
      return 1
    fi
    printf 'WARNING: %s is incomplete; preserving all audits.\n' "$name" >&2
  fi

  if [[ ! -s "$output" ]]; then
    printf 'ERROR: %s produced zero valid rows.\n' "$name" >&2
    return 1
  fi

  PYTHONPATH=. "$PYTHON_BIN" \
    evaluation/current/v2.4.1/cluster/memcalib-v241-local-baselines-1500/validate_nonthinking.py \
    --input "$output" \
    --report "$base.nonthinking-validation.json"

}

run_cell smoke
run_cell full_memory
date -Iseconds > "$OUTPUT_ROOT/completed"
printf 'Completed %s with served model %s, seed %s, under %s\n' \
  "$MODEL_KEY" "$SERVED_MODEL_NAME" "$SEED" "$OUTPUT_ROOT"
