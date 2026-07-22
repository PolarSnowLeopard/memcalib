#!/bin/zsh
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
: "${PYTHON_BIN:?Set PYTHON_BIN to the required non-Conda Python executable}"

set -a
source .env.local
set +a

RUN=evaluation/runs/memcalib-v23-multidomain-500-nine-models
REQUESTS="$RUN/requests/answers/glm52/no_memory.jsonl"
BASE="$RUN/answers/glm52/no_memory"
RESCUE_REQUESTS="$BASE.retry-api3.requests.jsonl"
RESCUE_OUTPUT="$BASE.thinking-budget-rescue.jsonl"
RESCUE_LOG="$BASE.thinking-budget-rescue.log"

printf '%s\n' bounded_thinking_rescue > "$RUN/workflow.status"

PYTHONPATH=pipeline "$PYTHON_BIN" pipeline/06_run_bailian_api.py \
  --input "$RESCUE_REQUESTS" --output "$RESCUE_OUTPUT" \
  --failed "$BASE.thinking-budget-rescue.failed.jsonl" \
  --invalid-output "$BASE.thinking-budget-rescue.api-invalid.jsonl" \
  --model glm-5.2 --temperature 0 --max-tokens 16384 \
  --extra-body-json '{"enable_thinking":true,"thinking_budget":8192}' \
  --timeout 600 --hard-timeout 600 --max-retries 3 \
  --max-workers 1 --rpm 5 --progress-every 1 >> "$RESCUE_LOG" 2>&1

PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/resolve_api_results.py \
  --requests "$REQUESTS" \
  --result "$BASE.jsonl" \
  --result "$BASE.retry-api1.jsonl" \
  --result "$BASE.retry-api2.jsonl" \
  --result "$RESCUE_OUTPUT" \
  --output "$BASE.resolved.jsonl" --model glm-5.2 \
  --report "$BASE.thinking-budget-rescue.resolution.json" >> "$RESCUE_LOG" 2>&1
mv "$BASE.resolved.jsonl" "$BASE.jsonl"

PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/validate_api_results.py \
  --input "$REQUESTS" --output "$BASE.jsonl" --model glm-5.2 \
  --report "$BASE.thinking-budget-rescue.validation.json" >> "$RESCUE_LOG" 2>&1

printf '%s\n' resuming_full_workflow > "$RUN/workflow.status"
exec /bin/zsh evaluation/scripts/run_memcalib_v23_nine_models.sh
