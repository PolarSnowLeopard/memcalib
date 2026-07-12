#!/bin/zsh
set -u

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT" || exit 1
: "${PYTHON_BIN:?Set PYTHON_BIN to a non-Conda Python 3.10+ executable}"

set -a
source .env.local
set +a

REQ=evaluation/runs/memcalib-ordered-v2.1-full-15526/requests/judges
OUT=evaluation/runs/memcalib-ordered-v2.1-full-15526/api
mkdir -p "$OUT"

run_judge() {
  local key=$1
  local input=$2
  local model=$3
  local workers=$4
  local rpm=$5
  PYTHONPATH=pipeline "$PYTHON_BIN" pipeline/06_run_bailian_api.py \
    --input "$REQ/$input" \
    --output "$OUT/$key.jsonl" \
    --failed "$OUT/$key.failed.jsonl" \
    --invalid-output "$OUT/$key.api-invalid.jsonl" \
    --model "$model" \
    --temperature 0 \
    --max-tokens 4096 \
    --extra-body-json '{"enable_thinking":false}' \
    --timeout 300 \
    --max-retries 5 \
    --max-workers "$workers" \
    --rpm "$rpm" \
    --progress-every 100 \
    > "$OUT/$key.log" 2>&1
  local code=$?
  printf '%s\n' "$code" > "$OUT/$key.exit"
  return "$code"
}

run_judge primary primary.jsonl qwen3.7-plus 170 1020 & p1=$!
run_judge secondary-deepseek secondary-deepseek.jsonl deepseek-v4-pro 18 108 & p2=$!
run_judge secondary-kimi secondary-kimi.jsonl kimi-k2.6 12 72 & p3=$!

exit_code=0
wait "$p1" || exit_code=1
wait "$p2" || exit_code=1
wait "$p3" || exit_code=1
exit "$exit_code"
