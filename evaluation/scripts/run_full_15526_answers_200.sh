#!/bin/zsh
set -u

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT" || exit 1
: "${PYTHON_BIN:?Set PYTHON_BIN to a non-Conda Python 3.10+ executable}"

set -a
source .env.local
set +a

REQ=evaluation/runs/memcalib-v0.1-full-15526/requests/answers
OUT=evaluation/runs/memcalib-v0.1-full-15526/answers
mkdir -p "$OUT"

run_model() {
  local key=$1
  local model=$2
  local workers=$3
  local rpm=$4
  mkdir -p "$OUT/$key"
  PYTHONPATH=pipeline "$PYTHON_BIN" pipeline/06_run_bailian_api.py \
    --input "$REQ/$key/full_memory.jsonl" \
    --output "$OUT/$key/full_memory.jsonl" \
    --failed "$OUT/$key/full_memory.failed.jsonl" \
    --invalid-output "$OUT/$key/full_memory.api-invalid.jsonl" \
    --model "$model" \
    --temperature 0 \
    --max-tokens 2048 \
    --extra-body-json '{"enable_thinking":false}' \
    --timeout 300 \
    --max-retries 5 \
    --max-workers "$workers" \
    --rpm "$rpm" \
    --progress-every 100 \
    > "$OUT/$key/full_memory.log" 2>&1
  local code=$?
  printf '%s\n' "$code" > "$OUT/$key/full_memory.exit"
  return "$code"
}

run_model qwen-max qwen3.7-max 40 240 & p1=$!
run_model qwen-flash qwen3.6-flash 40 240 & p2=$!
run_model deepseek deepseek-v4-pro 40 240 & p3=$!
run_model deepseek-flash deepseek-v4-flash 40 240 & p4=$!
run_model kimi kimi-k2.6 40 240 & p5=$!

exit_code=0
wait "$p1" || exit_code=1
wait "$p2" || exit_code=1
wait "$p3" || exit_code=1
wait "$p4" || exit_code=1
wait "$p5" || exit_code=1
exit "$exit_code"
