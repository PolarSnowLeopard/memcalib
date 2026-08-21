#!/bin/bash
set -euo pipefail

if [[ "$#" -lt 3 || "$#" -gt 5 ]]; then
  printf 'Usage: %s MODEL_KEY SERVED_MODEL_NAME CHAT_COMPLETIONS_URL [DISPLAY_NAME] [CHECKPOINT_ROLE]\n' "$0" >&2
  printf 'Example: %s qwen3-8b-official med_chat http://127.0.0.1:8000/v1/chat/completions "Qwen3-8B Official" official_posttrained\n' "$0" >&2
  exit 2
fi

MODEL_KEY=$1
SERVED_MODEL_NAME=$2
CHAT_COMPLETIONS_URL=${3%/}
DISPLAY_NAME=${4:-${MEMCALIB_MODEL_DISPLAY_NAME:-$MODEL_KEY}}
CHECKPOINT_ROLE=${5:-${MEMCALIB_CHECKPOINT_ROLE:-baseline}}
MODEL_ID=${MEMCALIB_MODEL_ID:-$MODEL_KEY}
if [[ ! "$MODEL_KEY" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  printf 'Invalid model key: %s\n' "$MODEL_KEY" >&2
  printf 'Use only letters, numbers, dots, underscores, and hyphens; start with a letter or number.\n' >&2
  exit 2
fi

ROOT=$(cd "$(dirname "$0")/../../../../.." && pwd)
cd "$ROOT"
PYTHON_BIN=${PYTHON_BIN:-python3}
RUN=${MEMCALIB_RUN:-evaluation/runs/memcalib-v241-qwen3-8b-checkpoints-494-vllm}
CONFIG=${MEMCALIB_VLLM_CONFIG:-evaluation/current/v2.4.1/cluster/memcalib-v241-qwen3-8b-checkpoints-494/local-vllm-config.json}
MODEL_CONFIG=${MEMCALIB_CONFIG:-evaluation/current/v2.4.1/configs/memcalib-v241-multidomain-494-nine-models-nonthinking.json}
SAMPLE_RELEASE=${MEMCALIB_SAMPLE_RELEASE:-evaluation/current/v2.4.1/releases/memcalib-v241-multidomain-494-nine-models-nonthinking}
ANSWER_PROMPT=${MEMCALIB_ANSWER_PROMPT:-evaluation/prompts/answer-system.txt}
REQUEST_ROOT="$RUN/requests/answers/$MODEL_KEY"
OUTPUT_ROOT="$RUN/answers/$MODEL_KEY"
REQUEST_MANIFEST="$RUN/request-manifests/$MODEL_KEY.json"
WORKERS=${VLLM_EVAL_WORKERS:-128}
RPM=${VLLM_EVAL_RPM:-0}
TIMEOUT=${VLLM_EVAL_TIMEOUT:-600}
MAX_TOKENS=${VLLM_EVAL_MAX_TOKENS:-8192}
SEED=${VLLM_EVAL_SEED:-20260730}
STRICT_COMPLETENESS=${VLLM_EVAL_STRICT_COMPLETENESS:-0}
TOKEN_ENV=MEMCALIB_VLLM_TOKEN
EXTRA_BODY=$(printf '{"top_p":1.0,"seed":%s,"chat_template_kwargs":{"enable_thinking":false}}' "$SEED")

export MEMCALIB_VLLM_TOKEN=${MEMCALIB_VLLM_TOKEN:-EMPTY}
mkdir -p "$OUTPUT_ROOT"
printf '%s\n' "$SERVED_MODEL_NAME" > "$OUTPUT_ROOT/served-model-name.txt"

if [[ ! -s "$REQUEST_ROOT/smoke.jsonl" || ! -s "$REQUEST_ROOT/full_memory.jsonl" ]]; then
  printf 'Preparing requests for custom model key %s\n' "$MODEL_KEY"
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
  "$DISPLAY_NAME" "$CHECKPOINT_ROLE" "$SERVED_MODEL_NAME" <<'PY'
import json
import sys
from pathlib import Path

output, key, model, display_name, checkpoint_role, served_model_name = sys.argv[1:]
metadata = {
    "key": key,
    "model": model,
    "display_name": display_name,
    "answer_mode": "nonthinking",
    "checkpoint_role": checkpoint_role,
    "served_model_name": served_model_name,
}
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
    --temperature 0 \
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
    printf 'WARNING: %s is incomplete; preserving audits and continuing for complete-case evaluation.\n' "$name" >&2
  fi

  if [[ ! -s "$output" ]]; then
    printf 'ERROR: %s produced zero valid rows; refusing to continue to the next cell.\n' "$name" >&2
    return 1
  fi

  "$PYTHON_BIN" \
    evaluation/current/v2.4.1/cluster/memcalib-v241-qwen3-8b-checkpoints-494/validate_nonthinking.py \
    --input "$output" | tee "$base.nonthinking-validation.json"
}

run_cell smoke
run_cell full_memory

printf 'Completed %s using served model %s under %s\n' "$MODEL_KEY" "$SERVED_MODEL_NAME" "$OUTPUT_ROOT"
