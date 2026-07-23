#!/bin/zsh
set -euo pipefail
setopt NULL_GLOB

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
PYTHON_BIN=/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3

set -a
source .env.local
set +a
if [[ -z "${DASHSCOPE_API_KEY:-${BAILIAN_API_KEY:-}}" ]]; then
  printf 'DASHSCOPE_API_KEY or BAILIAN_API_KEY is missing from .env.local\n' >&2
  exit 1
fi

CONFIG=sft/configs/memcalib-v23-sft-train-12000.json
TRAIN_IDS=sft/releases/memcalib-v23-sft-12000-1500-1500/train-ids.txt
RUN=sft/runs/memcalib-v23-sft-train-12000
PILOT=sft/runs/memcalib-v23-sft-pilot-500
ANSWER_REQ="$RUN/requests/answers"
ANSWER_OUT="$RUN/answers"
JUDGE_REQ="$RUN/requests/judges"
JUDGE_API="$RUN/api"
JUDGMENTS="$RUN/judgments"
mkdir -p "$ANSWER_OUT/qwen37max-teacher" "$JUDGE_REQ" "$JUDGE_API" "$JUDGMENTS"

phase() {
  printf '%s\n' "$1" > "$RUN/workflow.status"
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" | tee -a "$RUN/workflow.log"
}

add_existing_result() {
  local path=$1
  if [[ -n "$path" && -f "$path" ]]; then
    result_paths+=("$path")
  fi
}

run_api_complete() {
  local request_path=$1 canonical_output=$2 model=$3 max_tokens=$4
  local workers=$5 rpm=$6 progress_every=$7 extra_body_json=$8 seed_result=${9:-}
  local base=${canonical_output%.jsonl}
  local incremental="$base.incremental.jsonl"
  local pending="$base.pending.jsonl"
  local final_missing="$base.final-missing.requests.jsonl"
  mkdir -p "$(dirname "$canonical_output")"

  local -a result_paths
  result_paths=()
  add_existing_result "$seed_result"
  add_existing_result "$canonical_output"
  add_existing_result "$incremental"
  local existing_retry
  for existing_retry in "$base".retry-api*.jsonl; do
    [[ "$existing_retry" == *.requests.jsonl ]] && continue
    add_existing_result "$existing_retry"
  done

  local -a result_args
  result_args=()
  local result_path
  for result_path in "${result_paths[@]}"; do
    result_args+=(--result "$result_path")
  done
  if [[ "${#result_args[@]}" -eq 0 ]]; then
    : > "$incremental"
    result_paths+=("$incremental")
    result_args=(--result "$incremental")
  fi
  PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/prepare_missing_api_requests.py \
    --input "$request_path" "${result_args[@]}" --output "$pending" >> "$base.log" 2>&1
  local missing
  missing=$(wc -l < "$pending")
  printf '[%s] %s pending=%s model=%s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$request_path" "$missing" "$model" \
    | tee -a "$RUN/workflow.log"

  if [[ "$missing" -gt 0 ]]; then
    set +e
    PYTHONPATH=pipeline "$PYTHON_BIN" pipeline/06_run_bailian_api.py \
      --input "$pending" --output "$incremental" \
      --failed "$base.incremental.failed.jsonl" \
      --invalid-output "$base.incremental.api-invalid.jsonl" \
      --model "$model" --temperature 0 --max-tokens "$max_tokens" \
      --extra-body-json "$extra_body_json" \
      --timeout 300 --hard-timeout 300 --max-retries 5 \
      --max-workers "$workers" --rpm "$rpm" --progress-every "$progress_every" \
      >> "$base.log" 2>&1
    local main_code=$?
    set -e
    printf '%s\n' "$main_code" > "$base.incremental.exit"
    add_existing_result "$incremental"
  fi

  local round=1
  while [[ "$round" -le 3 ]]; do
    result_args=()
    for result_path in "${result_paths[@]}"; do
      result_args+=(--result "$result_path")
    done
    local retry_request="$base.retry-api${round}.requests.jsonl"
    PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/prepare_missing_api_requests.py \
      --input "$request_path" "${result_args[@]}" --output "$retry_request" >> "$base.log" 2>&1
    missing=$(wc -l < "$retry_request")
    [[ "$missing" -eq 0 ]] && break
    local retry_output="$base.retry-api${round}.jsonl"
    set +e
    PYTHONPATH=pipeline "$PYTHON_BIN" pipeline/06_run_bailian_api.py \
      --input "$retry_request" --output "$retry_output" \
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
    add_existing_result "$retry_output"
    round=$((round + 1))
  done

  result_args=()
  for result_path in "${result_paths[@]}"; do
    result_args+=(--result "$result_path")
  done
  PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/prepare_missing_api_requests.py \
    --input "$request_path" "${result_args[@]}" --output "$final_missing" >> "$base.log" 2>&1
  missing=$(wc -l < "$final_missing")
  if [[ "$missing" -gt 0 ]]; then
    printf '%s unresolved API requests remain for %s\n' "$missing" "$request_path" >&2
    return 1
  fi

  local resolved="$base.resolved.jsonl"
  PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/resolve_api_results.py \
    --requests "$request_path" "${result_args[@]}" \
    --output "$resolved" --model "$model" --report "$base.resolution.json" >> "$base.log" 2>&1
  mv "$resolved" "$canonical_output"
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
  local -a valid_inputs
  valid_inputs=("$JUDGMENTS/$key.initial.valid.jsonl")
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
      '{"enable_thinking":false}' ""
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
  local -a merge_args
  merge_args=()
  local valid_path
  for valid_path in "${valid_inputs[@]}"; do
    merge_args+=(--input "$valid_path")
  done
  PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/merge_judgments.py \
    "${merge_args[@]}" --output "$JUDGMENTS/$key.valid.jsonl" --expected "$expected"
}

phase prepare
PYTHONPATH=. "$PYTHON_BIN" sft/scripts/prepare_memcalib_v23_splits.py >/dev/null
PYTHONPATH=. "$PYTHON_BIN" sft/scripts/prepare_memcalib_v23_teacher_requests.py \
  --ids "$TRAIN_IDS" --run-dir "$RUN" \
  --hidden-output "$RUN/train.hidden.jsonl" \
  --model-facing-output "$RUN/train.model-facing.jsonl" >/dev/null

phase teacher_generation
run_api_complete \
  "$ANSWER_REQ/qwen37max-teacher/full_memory.jsonl" \
  "$ANSWER_OUT/qwen37max-teacher/full_memory.jsonl" \
  qwen3.7-max 8192 300 300 20 '{"enable_thinking":true}' \
  "$PILOT/answers/qwen37max-teacher/full_memory.jsonl"

phase teacher_validation_and_judge_requests
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/finalize_answer_run.py \
  --config "$CONFIG" --requests "$ANSWER_REQ" --results "$ANSWER_OUT" \
  --manifest "$RUN/teacher-answer-run.manifest.json" --conditions full_memory
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/prepare_judge_requests.py \
  --config "$CONFIG" --hidden "$RUN/train.hidden.jsonl" --answers "$ANSWER_OUT" \
  --output-dir "$JUDGE_REQ" --manifest "$RUN/judge-request.manifest.json" \
  --conditions full_memory

phase judge_generation
run_api_complete \
  "$JUDGE_REQ/primary.jsonl" "$JUDGE_API/primary.jsonl" \
  qwen3.7-plus 16384 300 1200 20 '{"enable_thinking":false}' \
  "$PILOT/api/primary.jsonl" & j1=$!
run_api_complete \
  "$JUDGE_REQ/secondary-deepseek.jsonl" "$JUDGE_API/secondary-deepseek.jsonl" \
  deepseek-v4-pro 16384 120 480 20 '{"enable_thinking":false}' \
  "$PILOT/api/secondary-deepseek.jsonl" & j2=$!
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
PYTHONPATH=. "$PYTHON_BIN" sft/scripts/build_memcalib_v23_swift_sft.py \
  --hidden "$RUN/train.hidden.jsonl" \
  --answers "$ANSWER_OUT/qwen37max-teacher/full_memory.jsonl" \
  --primary "$JUDGMENTS/primary.valid.jsonl" \
  --secondary "$JUDGMENTS/secondary-deepseek.valid.jsonl" \
  --output-dir "$RUN/sft"
"$PYTHON_BIN" /Users/zhaofanyu/Code/qwen_med_chat/shared/skills/swift-sft-dataset-builder/scripts/validate_swift_sft.py \
  --input "$RUN/sft/swift-sft.dual-strict.jsonl" --examples 3 \
  > "$RUN/sft/swift-sft.dual-strict.validation.txt"

phase completed
date -Iseconds > "$RUN/workflow.completed"
