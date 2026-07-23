#!/bin/bash
set -euo pipefail

if [[ "$#" -ne 2 ]]; then
  printf 'Usage: %s MODEL_ALIAS CHAT_COMPLETIONS_URL\n' "$0" >&2
  printf 'Example: %s qwen35-a3b-base-vllm http://127.0.0.1:8000/v1/chat/completions\n' "$0" >&2
  exit 2
fi

MODEL_ALIAS=$1
CHAT_COMPLETIONS_URL=$2
case "$MODEL_ALIAS" in
  qwen35-a3b-base-vllm|qwen35-a3b-sft-vllm) ;;
  *)
    printf 'Unsupported model alias: %s\n' "$MODEL_ALIAS" >&2
    exit 2
    ;;
esac

ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$ROOT"

if [[ -z "${PYTHON_BIN:-}" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=python3
  else
    PYTHON_BIN=python
  fi
fi

RUN=${MEMCALIB_RUN:-evaluation/runs/memcalib-v23-sft-base-500-vllm}
REQUEST_ROOT="$RUN/requests/answers/$MODEL_ALIAS"
OUTPUT_ROOT="$RUN/answers/$MODEL_ALIAS"
WORKERS=${VLLM_EVAL_WORKERS:-128}
RPM=${VLLM_EVAL_RPM:-0}
TIMEOUT=${VLLM_EVAL_TIMEOUT:-600}
MAX_TOKENS=${VLLM_EVAL_MAX_TOKENS:-8192}
SEED=${VLLM_EVAL_SEED:-20260723}
TOKEN_ENV=MEMCALIB_VLLM_TOKEN
EXTRA_BODY=$(printf '{"top_p":1.0,"seed":%s,"chat_template_kwargs":{"enable_thinking":false}}' "$SEED")

# An unauthenticated vLLM endpoint still accepts an arbitrary bearer token.
export MEMCALIB_VLLM_TOKEN=${MEMCALIB_VLLM_TOKEN:-EMPTY}
mkdir -p "$OUTPUT_ROOT"

run_cell() {
  local name=$1
  local input="$REQUEST_ROOT/$name.jsonl"
  local output="$OUTPUT_ROOT/$name.jsonl"
  local base=${output%.jsonl}

  PYTHONPATH=pipeline "$PYTHON_BIN" pipeline/06_run_bailian_api.py \
    --input "$input" \
    --output "$output" \
    --failed "$base.failed.jsonl" \
    --invalid-output "$base.invalid.jsonl" \
    --api-key-env "$TOKEN_ENV" \
    --base-url "$CHAT_COMPLETIONS_URL" \
    --model "$MODEL_ALIAS" \
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

  PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/validate_api_results.py \
    --input "$input" \
    --output "$output" \
    --model "$MODEL_ALIAS" \
    --report "$base.validation.json"

  "$PYTHON_BIN" \
    evaluation/cluster/memcalib-v23-sft-vllm-500/validate_nonthinking.py \
    --input "$output" | tee "$base.nonthinking-validation.json"
}

run_cell smoke
run_cell full_memory
run_cell no_memory

printf 'Completed %s under %s\n' "$MODEL_ALIAS" "$OUTPUT_ROOT"
