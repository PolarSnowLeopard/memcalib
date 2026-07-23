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

CONFIG=evaluation/configs/memcalib-v23-sft-base-full-only-paired.json
RELEASE=evaluation/releases/memcalib-v23-sft-base-full-only-paired
RUN=evaluation/runs/memcalib-v23-sft-base-full-only-paired
ANALYSIS=evaluation/analyses/memcalib-v23-sft-base-full-only-paired-candidate-metrics
JUDGE_REQ="$RUN/requests/judges"
JUDGE_API="$RUN/api"
JUDGMENTS="$RUN/judgments"
mkdir -p "$JUDGE_API" "$JUDGMENTS" "$ANALYSIS"

phase() {
  local name=$1
  printf '%s\n' "$name" > "$RUN/workflow.status"
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$name"
}

run_api_complete() {
  local request_path=$1 canonical_output=$2 model=$3 max_tokens=$4
  local workers=$5 rpm=$6 progress_every=$7
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
    local retry_max_tokens=$((max_tokens * (1 << round)))
    if [[ "$retry_max_tokens" -gt 32768 ]]; then
      retry_max_tokens=32768
    fi
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
    run_api_complete "$retry_request" "$retry_api" "$model" 16384 "$workers" "$rpm" 10
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

phase judge_generation
run_api_complete \
  "$JUDGE_REQ/primary.jsonl" "$JUDGE_API/primary.jsonl" \
  qwen3.7-plus 16384 300 1200 25 & primary_pid=$!
run_api_complete \
  "$JUDGE_REQ/secondary-deepseek.jsonl" "$JUDGE_API/secondary-deepseek.jsonl" \
  deepseek-v4-pro 16384 100 480 10 & secondary_pid=$!
judge_code=0
wait "$primary_pid" || judge_code=1
wait "$secondary_pid" || judge_code=1
if [[ "$judge_code" -ne 0 ]]; then
  phase judge_generation_failed
  exit 1
fi

phase judgment_normalization
process_judgments primary primary.jsonl qwen3.7-plus 100 480
process_judgments secondary-deepseek secondary-deepseek.jsonl deepseek-v4-pro 50 240
cp "$JUDGMENTS/secondary-deepseek.valid.jsonl" "$JUDGMENTS/secondary.valid.jsonl"

phase metrics_and_report
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/finalize_judge_run.py \
  --config "$CONFIG" --run "$RUN" \
  --request-manifest "$RELEASE/judge-request.manifest.json" \
  --manifest "$RELEASE/judge-run.manifest.json"
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/analyze_evaluation.py \
  --primary "$JUDGMENTS/primary.valid.jsonl" \
  --secondary "$JUDGMENTS/secondary.valid.jsonl" \
  --hidden "$RELEASE/hidden-evaluation.jsonl.gz" \
  --metrics "$RELEASE/metrics.json" --report "$RELEASE/report.html"

phase candidate_metrics
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/analyze_candidate_metrics.py \
  --primary "$JUDGMENTS/primary.valid.jsonl" \
  --output-dir "$ANALYSIS" --official-metrics "$RELEASE/metrics.json" \
  --bootstrap-replicates 2000 --seed 20260723 \
  --study-title "MemCalib v2.3 Qwen3.5-35B-A3B Base vs SFT" \
  --study-description \
  "Strictly paired Full-memory-only evaluation on the 496 locked v2.3 samples completed by both the Base and SFT checkpoints."
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/plot_candidate_metric_diagnostics.py \
  --primary "$JUDGMENTS/primary.valid.jsonl" \
  --metrics "$ANALYSIS/candidate-metrics.json" \
  --output "$ANALYSIS/candidate-metric-diagnostics.html" \
  --manifest "$ANALYSIS/candidate-metric-diagnostics.manifest.json"

phase completed
date -Iseconds > "$RUN/workflow.completed"
