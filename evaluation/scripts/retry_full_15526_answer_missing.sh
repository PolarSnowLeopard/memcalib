#!/bin/zsh
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
: "${PYTHON_BIN:?Set PYTHON_BIN to a non-Conda Python 3.10+ executable}"

set -a
source .env.local
set +a

REQ=evaluation/runs/memcalib-v0.1-full-15526/requests/answers
OUT=evaluation/runs/memcalib-v0.1-full-15526/answers

retry_model() {
  local key=$1 model=$2 workers=$3 rpm=$4
  local dir="$OUT/$key"
  PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/prepare_missing_api_requests.py \
    --input "$REQ/$key/full_memory.jsonl" --result "$dir/full_memory.jsonl" \
    --output "$REQ/$key/full_memory.retry1.jsonl"
  local missing
  missing=$(wc -l < "$REQ/$key/full_memory.retry1.jsonl")
  if [[ "$missing" -eq 0 ]]; then
    return
  fi
  PYTHONPATH=pipeline "$PYTHON_BIN" pipeline/06_run_bailian_api.py \
    --input "$REQ/$key/full_memory.retry1.jsonl" \
    --output "$dir/full_memory.retry1.jsonl" --failed "$dir/full_memory.retry1.failed.jsonl" \
    --invalid-output "$dir/full_memory.retry1.api-invalid.jsonl" --model "$model" \
    --temperature 0 --max-tokens 4096 --extra-body-json '{"enable_thinking":false}' \
    --timeout 300 --max-retries 5 --max-workers "$workers" --rpm "$rpm" --progress-every 10
  PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/merge_api_results.py \
    --input "$dir/full_memory.jsonl" --input "$dir/full_memory.retry1.jsonl" \
    --output "$dir/full_memory.resolved.jsonl" --expected 15526
  PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/validate_api_results.py \
    --input "$REQ/$key/full_memory.jsonl" --output "$dir/full_memory.resolved.jsonl" --model "$model"
  mv "$dir/full_memory.resolved.jsonl" "$dir/full_memory.jsonl"
}

retry_model qwen-max qwen3.7-max 20 120
retry_model qwen-flash qwen3.6-flash 20 120
retry_model deepseek deepseek-v4-pro 20 120
retry_model deepseek-flash deepseek-v4-flash 20 120
retry_model kimi kimi-k2.6 20 120
