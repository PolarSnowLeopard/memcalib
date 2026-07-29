#!/bin/zsh
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
: "${PYTHON_BIN:?Set PYTHON_BIN to a non-Conda Python 3.10+ executable}"

set -a
source .env.local
set +a
if [[ -z "${DASHSCOPE_API_KEY:-${BAILIAN_API_KEY:-}}" ]]; then
  printf 'DASHSCOPE_API_KEY or BAILIAN_API_KEY is missing from .env.local\n' >&2
  exit 1
fi

CONFIG=evaluation/archive/configs/memcalib-v2-multidomain-500-qwen35.json
BASE_RELEASE=evaluation/archive/releases/memcalib-v2-multidomain-500
BASE_RUN=evaluation/runs/memcalib-v2-multidomain-500
RELEASE=evaluation/archive/releases/memcalib-v2-multidomain-500-qwen35
COMBINED_RELEASE=evaluation/archive/releases/memcalib-v2-multidomain-500-six-models
RUN=evaluation/runs/memcalib-v2-multidomain-500-qwen35
COMBINED_RUN=evaluation/runs/memcalib-v2-multidomain-500-six-models
ANSWER_REQ="$RUN/requests/answers"
ANSWER_OUT="$RUN/answers"
JUDGE_REQ="$RUN/requests/judges"
JUDGE_API="$RUN/api"
JUDGMENTS="$RUN/judgments"
mkdir -p "$RELEASE" "$COMBINED_RELEASE" "$ANSWER_REQ" "$ANSWER_OUT" \
  "$JUDGE_REQ" "$JUDGE_API" "$JUDGMENTS" "$COMBINED_RUN/judgments"

if [[ ! -s "$BASE_RELEASE/model-facing.jsonl" || ! -s "$BASE_RELEASE/hidden-evaluation.jsonl" ]]; then
  printf 'Base v2 sample JSONL files are missing; restore them from their gzip artifacts first.\n' >&2
  exit 1
fi
if [[ ! -s "$BASE_RUN/judgments/primary.valid.jsonl" || ! -s "$BASE_RUN/judgments/secondary.valid.jsonl" ]]; then
  printf 'Base five-model judgments are missing; they are required for the combined report.\n' >&2
  exit 1
fi

phase() {
  local name=$1
  printf '%s\n' "$name" > "$RUN/workflow.status"
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$name"
}

run_api_complete() {
  local request_path=$1
  local canonical_output=$2
  local model=$3
  local max_tokens=$4
  local workers=$5
  local rpm=$6
  local progress_every=$7
  local base=${canonical_output%.jsonl}
  mkdir -p "$(dirname "$canonical_output")"

  set +e
  PYTHONPATH=pipeline "$PYTHON_BIN" pipeline/06_run_bailian_api.py \
    --input "$request_path" --output "$canonical_output" \
    --failed "$base.failed.jsonl" --invalid-output "$base.api-invalid.jsonl" \
    --model "$model" --temperature 0 --max-tokens "$max_tokens" \
    --extra-body-json '{"enable_thinking":false}' \
    --timeout 300 --hard-timeout 300 --max-retries 5 \
    --max-workers "$workers" --rpm "$rpm" --progress-every "$progress_every" \
    >> "$base.log" 2>&1
  local main_code=$?
  set -e
  printf '%s\n' "$main_code" > "$base.main.exit"

  local result_paths=("$canonical_output")
  local round=1
  local missing=0
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
    local retry_max_tokens=$((max_tokens * (1 << round)))
    set +e
    PYTHONPATH=pipeline "$PYTHON_BIN" pipeline/06_run_bailian_api.py \
      --input "$missing_request" --output "$retry_output" \
      --failed "$base.retry-api${round}.failed.jsonl" \
      --invalid-output "$base.retry-api${round}.api-invalid.jsonl" \
      --model "$model" --temperature 0 --max-tokens "$retry_max_tokens" \
      --extra-body-json '{"enable_thinking":false}' \
      --timeout 300 --hard-timeout 300 --max-retries 5 \
      --max-workers "$workers" --rpm "$rpm" --progress-every 10 \
      >> "$base.log" 2>&1
    local retry_code=$?
    set -e
    printf '%s\n' "$retry_code" > "$base.retry-api${round}.exit"
    result_paths+=("$retry_output")
    round=$((round + 1))
  done

  local final_missing_request="$base.final-missing.requests.jsonl"
  local final_missing_args=()
  local result_path
  for result_path in "${result_paths[@]}"; do
    final_missing_args+=(--result "$result_path")
  done
  PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/prepare_missing_api_requests.py \
    --input "$request_path" "${final_missing_args[@]}" --output "$final_missing_request" \
    >> "$base.log" 2>&1
  missing=$(wc -l < "$final_missing_request")
  if [[ "$missing" -gt 0 ]]; then
    printf 'unresolved API rows for %s: %s\n' "$request_path" "$missing" >&2
    return 1
  fi

  if [[ "${#result_paths[@]}" -gt 1 ]]; then
    if [[ ! -e "$base.main-pass.jsonl" ]]; then
      cp "$canonical_output" "$base.main-pass.jsonl"
    fi
    local resolve_args=()
    for result_path in "${result_paths[@]}"; do
      resolve_args+=(--result "$result_path")
    done
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

run_answer_model() {
  local key=$1 model=$2
  local condition
  mkdir -p "$ANSWER_OUT/$key"
  for condition in full_memory no_memory; do
    run_api_complete \
      "$ANSWER_REQ/$key/$condition.jsonl" "$ANSWER_OUT/$key/$condition.jsonl" \
      "$model" 2048 100 90 20
  done
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
      --input "$current_input" --invalid "$current_invalid" \
      --output "$retry_request" --round "$round"
    run_api_complete "$retry_request" "$retry_api" "$model" 4096 "$workers" "$rpm" 10
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

phase answer_requests
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/prepare_answer_requests.py \
  --config "$CONFIG" --input "$BASE_RELEASE/model-facing.jsonl" \
  --output-dir "$ANSWER_REQ" --manifest "$RELEASE/answer-request.manifest.json" \
  --conditions full_memory no_memory

phase answer_generation
run_answer_model qwen35-35b-a3b qwen3.5-35b-a3b

phase answer_validation_and_judge_requests
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/finalize_answer_run.py \
  --config "$CONFIG" --requests "$ANSWER_REQ" --results "$ANSWER_OUT" \
  --manifest "$RELEASE/answer-run.manifest.json" --conditions full_memory no_memory
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/prepare_judge_requests.py \
  --config "$CONFIG" --hidden "$BASE_RELEASE/hidden-evaluation.jsonl" --answers "$ANSWER_OUT" \
  --output-dir "$JUDGE_REQ" --manifest "$RELEASE/judge-request.manifest.json" \
  --conditions full_memory no_memory

phase judge_generation
run_api_complete "$JUDGE_REQ/primary.jsonl" "$JUDGE_API/primary.jsonl" qwen3.7-plus 4096 140 840 25 & j1=$!
run_api_complete "$JUDGE_REQ/secondary-deepseek.jsonl" "$JUDGE_API/secondary-deepseek.jsonl" deepseek-v4-pro 4096 40 240 20 & j2=$!
judge_code=0
wait "$j1" || judge_code=1
wait "$j2" || judge_code=1
if [[ "$judge_code" -ne 0 ]]; then
  phase judge_generation_failed
  exit 1
fi

phase judgment_normalization
process_judgments primary primary.jsonl qwen3.7-plus 80 480
process_judgments secondary-deepseek secondary-deepseek.jsonl deepseek-v4-pro 30 180
secondary_expected=$(wc -l < "$JUDGE_REQ/secondary-deepseek.jsonl")
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/merge_judgments.py \
  --input "$JUDGMENTS/secondary-deepseek.valid.jsonl" \
  --output "$JUDGMENTS/secondary.valid.jsonl" --expected "$secondary_expected"

phase extension_metrics
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/finalize_judge_run.py \
  --config "$CONFIG" --run "$RUN" --request-manifest "$RELEASE/judge-request.manifest.json" \
  --manifest "$RELEASE/judge-run.manifest.json"
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/analyze_evaluation.py \
  --primary "$JUDGMENTS/primary.valid.jsonl" --secondary "$JUDGMENTS/secondary.valid.jsonl" \
  --hidden "$BASE_RELEASE/hidden-evaluation.jsonl" \
  --metrics "$RELEASE/metrics.json" --report "$RELEASE/report.html"

phase combined_six_model_metrics
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/merge_judgments.py \
  --input "$BASE_RUN/judgments/primary.valid.jsonl" \
  --input "$JUDGMENTS/primary.valid.jsonl" \
  --output "$COMBINED_RUN/judgments/primary.valid.jsonl" --expected 6000
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/merge_judgments.py \
  --input "$BASE_RUN/judgments/secondary.valid.jsonl" \
  --input "$JUDGMENTS/secondary.valid.jsonl" \
  --output "$COMBINED_RUN/judgments/secondary.valid.jsonl" --expected 300
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/analyze_evaluation.py \
  --primary "$COMBINED_RUN/judgments/primary.valid.jsonl" \
  --secondary "$COMBINED_RUN/judgments/secondary.valid.jsonl" \
  --hidden "$BASE_RELEASE/hidden-evaluation.jsonl" \
  --metrics "$COMBINED_RELEASE/metrics.json" --report "$COMBINED_RELEASE/report.html"

phase completed
date -Iseconds > "$RUN/workflow.completed"
