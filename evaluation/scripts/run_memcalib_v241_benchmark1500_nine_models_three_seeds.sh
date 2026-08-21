#!/bin/zsh
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"

PYTHON_BIN=${PYTHON_BIN:-/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}
CONFIG=evaluation/current/v2.4.1/configs/memcalib-v241-benchmark1500-nine-models-nonthinking.json
SAMPLE_RELEASE=evaluation/current/v2.4.1/releases/memcalib-v241-benchmark-test-eval-1500
SIX_RUN=evaluation/runs/memcalib-v241-benchmark1500-six-models-nonthinking-full-memory-three-seeds
PLATFORM_RUN=evaluation/runs/memcalib-v241-benchmark1500-four-platform-models-nonthinking-full-memory-three-seeds
STUDY_ROOT=evaluation/runs/memcalib-v241-benchmark1500-nine-models-nonthinking-full-memory-three-seeds
RELEASE_ROOT=evaluation/current/v2.4.1/releases/memcalib-v241-benchmark1500-nine-models-nonthinking-full-memory-three-seeds
ANALYSIS_ROOT=evaluation/current/v2.4.1/analyses/memcalib-v241-benchmark1500-nine-models-nonthinking-full-memory-three-seeds
mkdir -p "$STUDY_ROOT" "$RELEASE_ROOT" "$ANALYSIS_ROOT"

printf 'waiting_for_answers\n' > "$STUDY_ROOT/workflow.status"
date -Iseconds > "$STUDY_ROOT/workflow.started"
while true; do
  six_status=$(cat "$SIX_RUN/workflow.status" 2>/dev/null || printf 'missing')
  platform_status=$(cat "$PLATFORM_RUN/platform-completion.status" 2>/dev/null || printf 'missing')
  if [[ "$six_status" == "completed" && "$platform_status" == "completed" ]]; then
    break
  fi
  if [[ "$platform_status" == *failed* || "$platform_status" == residual_missing_* ]]; then
    printf 'platform_completion_failed\n' > "$STUDY_ROOT/workflow.status"
    exit 1
  fi
  printf '[%s] waiting: six=%s platform=%s\n' \
    "$(date '+%Y-%m-%d %H:%M:%S')" "$six_status" "$platform_status"
  sleep 30
done

six_keys=(qwen38-max kimi-k26 deepseek-flash-0731 glm52 qwen35-35b-a3b qwen3-8b)
platform_keys=(claude-sonnet-4-6 gpt56-sol gemini35-flash)
platform_models=(claude-sonnet-4-6 gpt-5.6-sol gemini-3.5-flash)
seeds=(42 43 44)

for repeat in 1 2 3; do
  seed=${seeds[$repeat]}
  run="$STUDY_ROOT/repeat-$repeat"
  release="$RELEASE_ROOT/repeat-$repeat"
  analysis="$ANALYSIS_ROOT/repeat-$repeat"
  if [[ -s "$run/workflow.completed" ]]; then
    printf '[%s] repeat-%s seed=%s already complete; preserving outputs\n' \
      "$(date '+%Y-%m-%d %H:%M:%S')" "$repeat" "$seed"
    continue
  fi
  mkdir -p "$run/answers" "$release" "$analysis"
  printf '%s\n' "$seed" > "$run/answer.seed"
  printf 'repeat-%s-normalizing-answers\n' "$repeat" > "$STUDY_ROOT/workflow.status"

  for key in "${six_keys[@]}"; do
    mkdir -p "$run/answers/$key"
    cp "$SIX_RUN/repeat-$repeat/answers/$key/full_memory.jsonl" \
      "$run/answers/$key/full_memory.jsonl"
  done

  for index in {1..3}; do
    key=${platform_keys[$index]}
    model=${platform_models[$index]}
    source_dir="$PLATFORM_RUN/repeat-$repeat/$key"
    request_file="$PLATFORM_RUN/request-template/$key/full_memory.jsonl"
    output_dir="$run/answers/$key"
    mkdir -p "$output_dir"
    cp "$source_dir/normalized.jsonl" "$output_dir/full_memory.jsonl"
    if [[ -s "$source_dir/normalization.report.json" ]]; then
      cp "$source_dir/normalization.report.json" \
        "$output_dir/full_memory.normalization.json"
    else
      cp "$source_dir/primus-chat.report.json" \
        "$output_dir/full_memory.normalization.json"
    fi
    PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/validate_api_results.py \
      --input "$request_file" \
      --output "$output_dir/full_memory.jsonl" \
      --model "$model" \
      --report "$output_dir/full_memory.validation.json" \
      >> "$run/workflow.log" 2>&1
  done

  printf 'repeat-%s-judge-and-analysis\n' "$repeat" > "$STUDY_ROOT/workflow.status"
  env \
    PYTHON_BIN="$PYTHON_BIN" \
    MEMCALIB_CONFIG="$CONFIG" \
    MEMCALIB_SAMPLE_RELEASE="$SAMPLE_RELEASE" \
    MEMCALIB_RELEASE="$release" \
    MEMCALIB_RUN="$run" \
    MEMCALIB_ANALYSIS="$analysis" \
    MEMCALIB_BAILIAN_CREDENTIAL_MODE=broad_only \
    SKIP_SAMPLE_RELEASE=true \
    SKIP_ANSWER_GENERATION=true \
    MEMCALIB_CONDITIONS=full_memory \
    JUDGE_REUSE_ROOT="$SIX_RUN/repeat-$repeat/api" \
    PRIMARY_JUDGE_MODEL=deepseek-v4-pro \
    PRIMARY_JUDGE_WORKERS=80 \
    PRIMARY_JUDGE_RPM=88 \
    SECONDARY_DEFAULT_JUDGE_MODEL=deepseek-v4-pro \
    SECONDARY_DEFAULT_JUDGE_WORKERS=32 \
    SECONDARY_DEFAULT_JUDGE_RPM=45 \
    SECONDARY_DEEPSEEK_JUDGE_MODEL=deepseek-v4-pro \
    SECONDARY_DEEPSEEK_JUDGE_WORKERS=32 \
    SECONDARY_DEEPSEEK_JUDGE_RPM=45 \
    JUDGE_EXECUTION_MODE=primary_then_secondary \
    CANDIDATE_STUDY_TITLE="MemCalib v2.4.1 benchmark-1500 nine-model Non-Think Full-memory seed $seed" \
    CANDIDATE_STUDY_DESCRIPTION="Locked 1,500-record, nine-model Full-memory evaluation; stochastic answer seed $seed; DeepSeek-V4-Pro deterministic Judge; Bailian and company crawl-platform answer channels." \
    SAMPLE_LEVEL_STUDY_TITLE="MemCalib v2.4.1 benchmark-1500 nine-model sample-level metrics, answer seed $seed" \
    zsh evaluation/scripts/run_memcalib_v23_nine_models.sh \
    >> "$run/workflow.log" 2>&1
done

printf 'aggregating\n' > "$STUDY_ROOT/workflow.status"
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/aggregate_repeated_evaluations.py \
  --repeat "seed-42=$RELEASE_ROOT/repeat-1/metrics.json,$ANALYSIS_ROOT/repeat-1/sample-level/sample-level-metrics.json" \
  --repeat "seed-43=$RELEASE_ROOT/repeat-2/metrics.json,$ANALYSIS_ROOT/repeat-2/sample-level/sample-level-metrics.json" \
  --repeat "seed-44=$RELEASE_ROOT/repeat-3/metrics.json,$ANALYSIS_ROOT/repeat-3/sample-level/sample-level-metrics.json" \
  --output-dir "$ANALYSIS_ROOT/aggregate"
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/aggregate_repeated_candidate_metrics.py \
  --repeat "seed-42=$ANALYSIS_ROOT/repeat-1/candidate-metrics.json" \
  --repeat "seed-43=$ANALYSIS_ROOT/repeat-2/candidate-metrics.json" \
  --repeat "seed-44=$ANALYSIS_ROOT/repeat-3/candidate-metrics.json" \
  --output-dir "$ANALYSIS_ROOT/aggregate"

printf 'completed\n' > "$STUDY_ROOT/workflow.status"
date -Iseconds > "$STUDY_ROOT/workflow.completed"
