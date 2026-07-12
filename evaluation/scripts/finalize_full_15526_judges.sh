#!/bin/zsh
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
: "${PYTHON_BIN:?Set PYTHON_BIN to a non-Conda Python 3.10+ executable}"

set -a
source .env.local
set +a

CONFIG=evaluation/configs/memcalib-ordered-v2.1-full-15526.json
RUN=evaluation/runs/memcalib-ordered-v2.1-full-15526
REQ="$RUN/requests/judges"
API="$RUN/api"
JUD="$RUN/judgments"
RELEASE=evaluation/releases/memcalib-ordered-v2.1-full-15526
mkdir -p "$JUD"

process_group() {
  local key=$1 input=$2 model=$3 expected=$4 workers=$5 rpm=$6
  local api_retry_request="$REQ/$key.retry-api1.jsonl"
  PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/prepare_missing_api_requests.py \
    --input "$REQ/$input" --result "$API/$key.jsonl" --output "$api_retry_request"
  local api_missing
  api_missing=$(wc -l < "$api_retry_request")
  if [[ "$api_missing" -gt 0 ]]; then
    cp "$API/$key.jsonl" "$API/$key.main-pass.jsonl"
    PYTHONPATH=pipeline "$PYTHON_BIN" pipeline/06_run_bailian_api.py \
      --input "$api_retry_request" --output "$API/$key.retry-api1.jsonl" \
      --failed "$API/$key.retry-api1.failed.jsonl" --invalid-output "$API/$key.retry-api1.api-invalid.jsonl" \
      --model "$model" --temperature 0 --max-tokens 8192 --extra-body-json '{"enable_thinking":false}' \
      --timeout 300 --max-retries 5 --max-workers "$workers" --rpm "$rpm" --progress-every 10
    PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/merge_api_results.py \
      --input "$API/$key.main-pass.jsonl" --input "$API/$key.retry-api1.jsonl" \
      --output "$API/$key.resolved.jsonl" --expected "$expected"
    mv "$API/$key.resolved.jsonl" "$API/$key.jsonl"
  fi

  PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/validate_api_results.py \
    --input "$REQ/$input" --output "$API/$key.jsonl" --model "$model" --report "$API/$key.validation.json"

  set +e
  PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/postprocess_judgments.py \
    --input "$REQ/$input" --result "$API/$key.jsonl" \
    --valid "$JUD/$key.initial.valid.jsonl" --invalid "$JUD/$key.initial.invalid.jsonl" \
    --summary "$JUD/$key.initial.summary.json"
  local initial_code=$?
  set -e
  local current_input="$REQ/$input"
  local current_invalid="$JUD/$key.initial.invalid.jsonl"
  local valid_inputs=("$JUD/$key.initial.valid.jsonl")
  local invalid_count
  invalid_count=$(wc -l < "$current_invalid")
  if [[ "$initial_code" -eq 0 && "$invalid_count" -eq 0 ]]; then
    cp "$JUD/$key.initial.valid.jsonl" "$JUD/$key.valid.jsonl"
    return
  fi

  local round=1
  while [[ "$invalid_count" -gt 0 && "$round" -le 3 ]]; do
    local retry_request="$REQ/$key.retry${round}.jsonl"
    local retry_api="$API/$key.retry${round}.jsonl"
    local retry_valid="$JUD/$key.retry${round}.valid.jsonl"
    local retry_invalid="$JUD/$key.retry${round}.invalid.jsonl"
    PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/prepare_judge_retry.py \
      --input "$current_input" --invalid "$current_invalid" --output "$retry_request" --round "$round"
    PYTHONPATH=pipeline "$PYTHON_BIN" pipeline/06_run_bailian_api.py \
      --input "$retry_request" --output "$retry_api" \
      --failed "$API/$key.retry${round}.failed.jsonl" \
      --invalid-output "$API/$key.retry${round}.api-invalid.jsonl" \
      --model "$model" --temperature 0 --max-tokens 4096 --extra-body-json '{"enable_thinking":false}' \
      --timeout 300 --max-retries 5 --max-workers "$workers" --rpm "$rpm" --progress-every 10
    set +e
    PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/postprocess_judgments.py \
      --input "$retry_request" --result "$retry_api" \
      --valid "$retry_valid" --invalid "$retry_invalid" \
      --summary "$JUD/$key.retry${round}.summary.json"
    set -e
    valid_inputs+=("$retry_valid")
    current_input="$retry_request"
    current_invalid="$retry_invalid"
    invalid_count=$(wc -l < "$current_invalid")
    round=$((round + 1))
  done
  if [[ "$invalid_count" -gt 0 ]]; then
    echo "$key still has $invalid_count structurally invalid judgments after 3 retries" >&2
    return 1
  fi

  local merge_args=()
  local valid_path
  for valid_path in "${valid_inputs[@]}"; do
    merge_args+=(--input "$valid_path")
  done
  PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/merge_judgments.py \
    "${merge_args[@]}" --output "$JUD/$key.valid.jsonl" --expected "$expected"
}

process_group primary primary.jsonl qwen3.7-plus 77630 80 480
process_group secondary-deepseek secondary-deepseek.jsonl deepseek-v4-pro 1500 30 180
process_group secondary-kimi secondary-kimi.jsonl kimi-k2.6 1000 20 120

PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/merge_judgments.py \
  --input "$JUD/secondary-deepseek.valid.jsonl" --input "$JUD/secondary-kimi.valid.jsonl" \
  --output "$JUD/secondary.valid.jsonl" --expected 2500

PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/finalize_judge_run.py \
  --config "$CONFIG" --run "$RUN" --request-manifest "$RELEASE/judge-request.manifest.json" \
  --manifest "$RELEASE/judge-run.manifest.json"

PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/analyze_evaluation.py \
  --primary "$JUD/primary.valid.jsonl" --secondary "$JUD/secondary.valid.jsonl" \
  --hidden evaluation/releases/memcalib-v0.1-full-15526/hidden-evaluation.jsonl \
  --metrics "$RELEASE/metrics.json" --report "$RELEASE/report.html"
