#!/bin/zsh
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
: "${PYTHON_BIN:?Set PYTHON_BIN to the required non-Conda Python executable}"

set -a
source .env.local
set +a
if [[ -z "${DASHSCOPE_API_KEY:-${BAILIAN_API_KEY:-}}" ]]; then
  printf 'DASHSCOPE_API_KEY or BAILIAN_API_KEY is missing from .env.local\n' >&2
  exit 1
fi

CONFIG=sft/configs/memcalib-v23-sft-pilot-500.json
RUN=sft/runs/memcalib-v23-sft-pilot-500
ANSWER_REQ="$RUN/requests/answers"
ANSWER_OUT="$RUN/answers"
JUDGE_REQ="$RUN/requests/judges"
JUDGE_API="$RUN/api"
JUDGMENTS="$RUN/judgments"
mkdir -p "$ANSWER_OUT/qwen37max-teacher" "$JUDGE_REQ" "$JUDGE_API" "$JUDGMENTS"

phase() {
  printf '%s\n' "$1" > "$RUN/workflow.status"
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1"
}

run_api_complete() {
  local request_path=$1 canonical_output=$2 model=$3 max_tokens=$4
  local workers=$5 rpm=$6 progress_every=$7 extra_body_json=$8
  local base=${canonical_output%.jsonl}
  mkdir -p "$(dirname "$canonical_output")"

  set +e
  PYTHONPATH=pipeline "$PYTHON_BIN" pipeline/06_run_bailian_api.py \
    --input "$request_path" --output "$canonical_output" \
    --failed "$base.failed.jsonl" --invalid-output "$base.api-invalid.jsonl" \
    --model "$model" --temperature 0 --max-tokens "$max_tokens" \
    --extra-body-json "$extra_body_json" \
    --timeout 300 --hard-timeout 300 --max-retries 5 \
    --max-workers "$workers" --rpm "$rpm" --progress-every "$progress_every" \
    >> "$base.log" 2>&1
  local main_code=$?
  set -e
  printf '%s\n' "$main_code" > "$base.main.exit"

  local result_paths=("$canonical_output")
  local round=1 missing=0
  while [[ "$round" -le 3 ]]; do
    local missing_request="$base.retry-api${round}.requests.jsonl"
    local missing_args=()
    local result_path
    for result_path in "${result_paths[@]}"; do
      missing_args+=(--result "$result_path")
    done
    PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/prepare_missing_api_requests.py \
      --input "$request_path" "${missing_args[@]}" --output "$missing_request" \
      >> "$base.log" 2>&1
    missing=$(wc -l < "$missing_request")
    if [[ "$missing" -eq 0 ]]; then
      break
    fi
    local retry_output="$base.retry-api${round}.jsonl"
    set +e
    PYTHONPATH=pipeline "$PYTHON_BIN" pipeline/06_run_bailian_api.py \
      --input "$missing_request" --output "$retry_output" \
      --failed "$base.retry-api${round}.failed.jsonl" \
      --invalid-output "$base.retry-api${round}.api-invalid.jsonl" \
      --model "$model" --temperature 0 --max-tokens "$max_tokens" \
      --extra-body-json "$extra_body_json" \
      --timeout 300 --hard-timeout 300 --max-retries 5 \
      --max-workers "$workers" --rpm "$rpm" --progress-every 10 \
      >> "$base.log" 2>&1
    local retry_code=$?
    set -e
    printf '%s\n' "$retry_code" > "$base.retry-api${round}.exit"
    result_paths+=("$retry_output")
    round=$((round + 1))
  done

  local resolve_args=()
  local result_path
  for result_path in "${result_paths[@]}"; do
    resolve_args+=(--result "$result_path")
  done
  if [[ "${#result_paths[@]}" -gt 1 ]]; then
    cp "$canonical_output" "$base.main-pass.jsonl"
    PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/resolve_api_results.py \
      --requests "$request_path" "${resolve_args[@]}" \
      --output "$base.resolved.jsonl" --model "$model" --report "$base.resolution.json" \
      >> "$base.log" 2>&1
    mv "$base.resolved.jsonl" "$canonical_output"
  fi
  PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/validate_api_results.py \
    --input "$request_path" --output "$canonical_output" --model "$model" \
    --report "$base.validation.json" >> "$base.log" 2>&1
}

process_judgments() {
  local key=$1 request_name=$2 model=$3 workers=$4 rpm=$5
  local original_request="$JUDGE_REQ/$request_name"
  local original_api="$JUDGE_API/$key.jsonl"
  local expected
  expected=$(wc -l < "$original_request")

  set +e
  PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/postprocess_judgments.py \
    --input "$original_request" --result "$original_api" \
    --valid "$JUDGMENTS/$key.initial.valid.jsonl" \
    --invalid "$JUDGMENTS/$key.initial.invalid.jsonl" \
    --summary "$JUDGMENTS/$key.initial.summary.json"
  set -e

  local current_input="$original_request"
  local current_invalid="$JUDGMENTS/$key.initial.invalid.jsonl"
  local valid_inputs=("$JUDGMENTS/$key.initial.valid.jsonl")
  local invalid_count
  invalid_count=$(wc -l < "$current_invalid")
  local round=1
  while [[ "$invalid_count" -gt 0 && "$round" -le 3 ]]; do
    local retry_request="$JUDGE_REQ/$key.structural-retry${round}.jsonl"
    local retry_api="$JUDGE_API/$key.structural-retry${round}.jsonl"
    local retry_valid="$JUDGMENTS/$key.structural-retry${round}.valid.jsonl"
    local retry_invalid="$JUDGMENTS/$key.structural-retry${round}.invalid.jsonl"
    PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/prepare_judge_retry.py \
      --input "$current_input" --invalid "$current_invalid" --output "$retry_request" --round "$round"
    run_api_complete "$retry_request" "$retry_api" "$model" 16384 "$workers" "$rpm" 10 \
      '{"enable_thinking":false}'
    set +e
    PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/postprocess_judgments.py \
      --input "$retry_request" --result "$retry_api" \
      --valid "$retry_valid" --invalid "$retry_invalid" \
      --summary "$JUDGMENTS/$key.structural-retry${round}.summary.json"
    set -e
    valid_inputs+=("$retry_valid")
    current_input="$retry_request"
    current_invalid="$retry_invalid"
    invalid_count=$(wc -l < "$current_invalid")
    round=$((round + 1))
  done
  if [[ "$invalid_count" -gt 0 ]]; then
    printf '%s still has %s structurally invalid judgments\n' "$key" "$invalid_count" >&2
    return 1
  fi
  local merge_args=()
  local valid_path
  for valid_path in "${valid_inputs[@]}"; do
    merge_args+=(--input "$valid_path")
  done
  PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/merge_judgments.py \
    "${merge_args[@]}" --output "$JUDGMENTS/$key.valid.jsonl" --expected "$expected"
}

phase prepare
PYTHONPATH=. "$PYTHON_BIN" sft/scripts/prepare_memcalib_v23_splits.py >/dev/null
PYTHONPATH=. "$PYTHON_BIN" sft/scripts/prepare_memcalib_v23_teacher_requests.py >/dev/null

phase teacher_generation
run_api_complete \
  "$ANSWER_REQ/qwen37max-teacher/full_memory.jsonl" \
  "$ANSWER_OUT/qwen37max-teacher/full_memory.jsonl" \
  qwen3.7-max 8192 120 300 10 '{"enable_thinking":true}'

phase teacher_validation_and_judge_requests
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/finalize_answer_run.py \
  --config "$CONFIG" --requests "$ANSWER_REQ" --results "$ANSWER_OUT" \
  --manifest "$RUN/teacher-answer-run.manifest.json" --conditions full_memory
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/prepare_judge_requests.py \
  --config "$CONFIG" --hidden "$RUN/pilot.hidden.jsonl" --answers "$ANSWER_OUT" \
  --output-dir "$JUDGE_REQ" --manifest "$RUN/judge-request.manifest.json" \
  --conditions full_memory

phase judge_generation
run_api_complete \
  "$JUDGE_REQ/primary.jsonl" "$JUDGE_API/primary.jsonl" \
  qwen3.7-plus 16384 300 1200 20 '{"enable_thinking":false}' & j1=$!
run_api_complete \
  "$JUDGE_REQ/secondary-deepseek.jsonl" "$JUDGE_API/secondary-deepseek.jsonl" \
  deepseek-v4-pro 16384 120 480 20 '{"enable_thinking":false}' & j2=$!
judge_code=0
wait "$j1" || judge_code=1
wait "$j2" || judge_code=1
if [[ "$judge_code" -ne 0 ]]; then
  phase judge_generation_failed
  exit 1
fi

phase judgment_normalization
process_judgments primary primary.jsonl qwen3.7-plus 120 480
process_judgments secondary-deepseek secondary-deepseek.jsonl deepseek-v4-pro 80 240

phase sft_admission
PYTHONPATH=. "$PYTHON_BIN" sft/scripts/build_memcalib_v23_swift_sft.py
"$PYTHON_BIN" /Users/zhaofanyu/Code/qwen_med_chat/shared/skills/swift-sft-dataset-builder/scripts/validate_swift_sft.py \
  --input "$RUN/sft/swift-sft.dual-strict.jsonl" --examples 3 \
  > "$RUN/sft/swift-sft.dual-strict.validation.txt"

phase completed
date -Iseconds > "$RUN/workflow.completed"
