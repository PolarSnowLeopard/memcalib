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

CONFIG=${MEMCALIB_CONFIG:-evaluation/configs/memcalib-v23-multidomain-500-nine-models.json}
BENCHMARK=pipeline/data/multidomain/full-v2/revision-composite-blocks-v23/release/memcalib_v23_multidomain_benchmark_15000.jsonl
SAMPLE_RELEASE=${MEMCALIB_SAMPLE_RELEASE:-evaluation/releases/memcalib-v23-multidomain-500-nine-models}
RELEASE=${MEMCALIB_RELEASE:-$SAMPLE_RELEASE}
RUN=${MEMCALIB_RUN:-evaluation/runs/memcalib-v23-multidomain-500-nine-models}
ANALYSIS=${MEMCALIB_ANALYSIS:-evaluation/analyses/memcalib-v23-multidomain-500-nine-models-candidate-metrics}
BAILIAN_ANSWER_THINKING=${BAILIAN_ANSWER_THINKING:-true}
CODEX_REUSE_ROOT=${CODEX_REUSE_ROOT:-}
JUDGE_GATE_PATTERN=${JUDGE_GATE_PATTERN:-}
ANSWER_REQ="$RUN/requests/answers"
ANSWER_OUT="$RUN/answers"
JUDGE_REQ="$RUN/requests/judges"
JUDGE_API="$RUN/api"
JUDGMENTS="$RUN/judgments"
mkdir -p "$RELEASE" "$ANSWER_REQ" "$ANSWER_OUT" "$JUDGE_REQ" "$JUDGE_API" "$JUDGMENTS" "$ANALYSIS"

phase() {
  local name=$1
  printf '%s\n' "$name" > "$RUN/workflow.status"
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$name"
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
  local key=$1 model=$2 workers=$3 rpm=$4
  local body="{\"enable_thinking\":${BAILIAN_ANSWER_THINKING}}"
  if [[ "$model" == "qwen3-8b" && "$BAILIAN_ANSWER_THINKING" == "true" ]]; then
    body='{"enable_thinking":true,"stream":true,"stream_options":{"include_usage":true}}'
  fi
  local condition
  mkdir -p "$ANSWER_OUT/$key"
  for condition in full_memory no_memory; do
    run_api_complete \
      "$ANSWER_REQ/$key/$condition.jsonl" "$ANSWER_OUT/$key/$condition.jsonl" \
      "$model" 8192 "$workers" "$rpm" 20 "$body"
  done
}

run_codex_condition() {
  local condition=$1
  local output="$ANSWER_OUT/codex-gpt56-sol/$condition.jsonl"
  local base=${output%.jsonl}
  if [[ -n "$CODEX_REUSE_ROOT" ]]; then
    mkdir -p "$(dirname "$output")"
    PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/resolve_api_results.py \
      --requests "$ANSWER_REQ/codex-gpt56-sol/$condition.jsonl" \
      --result "$CODEX_REUSE_ROOT/codex-gpt56-sol/$condition.jsonl" \
      --output "$output" --model gpt-5.6-sol --report "$base.reuse-resolution.json" \
      >> "$base.log" 2>&1
    PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/validate_api_results.py \
      --input "$ANSWER_REQ/codex-gpt56-sol/$condition.jsonl" \
      --output "$output" --model gpt-5.6-sol --report "$base.validation.json" \
      >> "$base.log" 2>&1
    return
  fi
  local round=1 code=1
  mkdir -p "$(dirname "$output")"
  while [[ "$round" -le 4 ]]; do
    set +e
    PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/run_codex_answers.py \
      --input "$ANSWER_REQ/codex-gpt56-sol/$condition.jsonl" \
      --output "$output" --failed "$base.failed.jsonl" --report "$base.report.json" \
      --model gpt-5.6-sol --reasoning-effort none --max-workers 12 \
      --timeout 600 --progress-every 10 >> "$base.log" 2>&1
    code=$?
    set -e
    printf '%s\n' "$code" > "$base.round${round}.exit"
    if [[ "$code" -eq 0 ]]; then
      break
    fi
    round=$((round + 1))
  done
  if [[ "$code" -ne 0 ]]; then
    return 1
  fi
  PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/validate_api_results.py \
    --input "$ANSWER_REQ/codex-gpt56-sol/$condition.jsonl" \
    --output "$output" --model gpt-5.6-sol --report "$base.validation.json" \
    >> "$base.log" 2>&1
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
    run_api_complete \
      "$retry_request" "$retry_api" "$model" 16384 "$workers" "$rpm" 10 \
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

phase release_and_requests
if [[ "${SKIP_SAMPLE_RELEASE:-false}" != "true" ]]; then
  PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/release_memcalib_v2_sample.py \
    --input "$BENCHMARK" --config "$CONFIG" --output-dir "$SAMPLE_RELEASE"
fi
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/prepare_answer_requests.py \
  --config "$CONFIG" --input "$SAMPLE_RELEASE/model-facing.jsonl" \
  --output-dir "$ANSWER_REQ" --manifest "$RELEASE/answer-request.manifest.json" \
  --conditions full_memory no_memory

phase answer_generation
run_answer_model qwen-max qwen3.7-max 120 300 & p1=$!
run_answer_model qwen-flash qwen3.6-flash 120 300 & p2=$!
run_answer_model deepseek deepseek-v4-pro 120 240 & p3=$!
run_answer_model deepseek-flash deepseek-v4-flash 120 300 & p4=$!
run_answer_model kimi kimi-k2.6 120 240 & p5=$!
run_answer_model qwen35-35b-a3b qwen3.5-35b-a3b 120 90 & p6=$!
run_answer_model qwen3-8b qwen3-8b 120 90 & p7=$!
run_answer_model glm52 glm-5.2 120 90 & p8=$!
run_codex_condition full_memory & p9=$!
run_codex_condition no_memory & p10=$!
answer_code=0
for pid in "$p1" "$p2" "$p3" "$p4" "$p5" "$p6" "$p7" "$p8" "$p9" "$p10"; do
  wait "$pid" || answer_code=1
done
if [[ "$answer_code" -ne 0 ]]; then
  phase answer_generation_failed
  exit 1
fi

phase answer_validation_and_judge_requests
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/finalize_answer_run.py \
  --config "$CONFIG" --requests "$ANSWER_REQ" --results "$ANSWER_OUT" \
  --manifest "$RELEASE/answer-run.manifest.json" --conditions full_memory no_memory
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/prepare_judge_requests.py \
  --config "$CONFIG" --hidden "$SAMPLE_RELEASE/hidden-evaluation.jsonl" --answers "$ANSWER_OUT" \
  --output-dir "$JUDGE_REQ" --manifest "$RELEASE/judge-request.manifest.json" \
  --conditions full_memory no_memory

if [[ -n "$JUDGE_GATE_PATTERN" ]]; then
  phase waiting_for_judge_capacity
  while pgrep -f "$JUDGE_GATE_PATTERN" >/dev/null 2>&1; do
    sleep 30
  done
fi

phase judge_generation
run_api_complete \
  "$JUDGE_REQ/primary.jsonl" "$JUDGE_API/primary.jsonl" \
  qwen3.7-plus 16384 300 1200 25 '{"enable_thinking":false}' & j1=$!
run_api_complete \
  "$JUDGE_REQ/secondary-deepseek.jsonl" "$JUDGE_API/secondary-deepseek.jsonl" \
  deepseek-v4-pro 16384 100 480 20 '{"enable_thinking":false}' & j2=$!
run_api_complete \
  "$JUDGE_REQ/secondary-kimi.jsonl" "$JUDGE_API/secondary-kimi.jsonl" \
  kimi-k2.6 16384 80 360 20 '{"enable_thinking":false}' & j3=$!
judge_code=0
for pid in "$j1" "$j2" "$j3"; do
  wait "$pid" || judge_code=1
done
if [[ "$judge_code" -ne 0 ]]; then
  phase judge_generation_failed
  exit 1
fi

phase judgment_normalization
process_judgments primary primary.jsonl qwen3.7-plus 100 480
process_judgments secondary-deepseek secondary-deepseek.jsonl deepseek-v4-pro 50 240
process_judgments secondary-kimi secondary-kimi.jsonl kimi-k2.6 40 180
secondary_expected=$(($(wc -l < "$JUDGE_REQ/secondary-deepseek.jsonl") + $(wc -l < "$JUDGE_REQ/secondary-kimi.jsonl")))
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/merge_judgments.py \
  --input "$JUDGMENTS/secondary-deepseek.valid.jsonl" \
  --input "$JUDGMENTS/secondary-kimi.valid.jsonl" \
  --output "$JUDGMENTS/secondary.valid.jsonl" --expected "$secondary_expected"

phase metrics_and_report
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/finalize_judge_run.py \
  --config "$CONFIG" --run "$RUN" --request-manifest "$RELEASE/judge-request.manifest.json" \
  --manifest "$RELEASE/judge-run.manifest.json"
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/analyze_evaluation.py \
  --primary "$JUDGMENTS/primary.valid.jsonl" --secondary "$JUDGMENTS/secondary.valid.jsonl" \
  --hidden "$SAMPLE_RELEASE/hidden-evaluation.jsonl" \
  --metrics "$RELEASE/metrics.json" --report "$RELEASE/report.html"
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/analyze_candidate_metrics.py \
  --primary "$JUDGMENTS/primary.valid.jsonl" --output-dir "$ANALYSIS" \
  --official-metrics "$RELEASE/metrics.json" --bootstrap-replicates 2000 --seed 20260722 \
  --study-title "${CANDIDATE_STUDY_TITLE:-MemCalib v2.3 nine-model candidate metric study}" \
  --study-description "${CANDIDATE_STUDY_DESCRIPTION:-Locked 500-record, nine-model, paired full-memory/no-memory evaluation on MemCalib v2.3.}"
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/plot_candidate_metric_diagnostics.py \
  --primary "$JUDGMENTS/primary.valid.jsonl" \
  --metrics "$ANALYSIS/candidate-metrics.json" \
  --output "$ANALYSIS/candidate-metric-diagnostics.html" \
  --manifest "$ANALYSIS/candidate-metric-diagnostics.manifest.json"

phase completed
date -Iseconds > "$RUN/workflow.completed"
