#!/bin/zsh
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"

PYTHON_BIN=${PYTHON_BIN:-/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}
CONFIG=evaluation/current/v2.4.1/configs/memcalib-v241-benchmark1500-six-models-nonthinking.json
SAMPLE_RELEASE=evaluation/current/v2.4.1/releases/memcalib-v241-benchmark-test-eval-1500
STUDY_ROOT=evaluation/runs/memcalib-v241-benchmark1500-six-models-nonthinking-full-memory-three-seeds
RELEASE_ROOT=evaluation/current/v2.4.1/releases/memcalib-v241-benchmark1500-six-models-nonthinking-full-memory-three-seeds
ANALYSIS_ROOT=evaluation/current/v2.4.1/analyses/memcalib-v241-benchmark1500-six-models-nonthinking-full-memory-three-seeds
PRIOR_STUDY_ROOT=evaluation/runs/memcalib-v241-benchmark1500-six-models-nonthinking-three-seeds
mkdir -p "$STUDY_ROOT" "$RELEASE_ROOT" "$ANALYSIS_ROOT"

printf 'starting\n' > "$STUDY_ROOT/workflow.status"
date -Iseconds > "$STUDY_ROOT/workflow.started"

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
  mkdir -p "$run" "$release" "$analysis"
  printf '%s\n' "$seed" > "$run/answer.seed"
  printf 'repeat-%s-answer-seed-%s\n' "$repeat" "$seed" > "$STUDY_ROOT/workflow.status"
  printf '[%s] starting repeat-%s answer seed=%s\n' \
    "$(date '+%Y-%m-%d %H:%M:%S')" "$repeat" "$seed"
  env \
    PYTHON_BIN="$PYTHON_BIN" \
    MEMCALIB_CONFIG="$CONFIG" \
    MEMCALIB_SAMPLE_RELEASE="$SAMPLE_RELEASE" \
    MEMCALIB_RELEASE="$release" \
    MEMCALIB_RUN="$run" \
    MEMCALIB_ANALYSIS="$analysis" \
    MEMCALIB_BAILIAN_CREDENTIAL_MODE=broad_only \
    SKIP_SAMPLE_RELEASE=true \
    ANSWER_MODEL_SET=v241_benchmark_six \
    MEMCALIB_CONDITIONS=full_memory \
    ANSWER_REUSE_ROOT="$PRIOR_STUDY_ROOT/repeat-$repeat/answers" \
    JUDGE_REUSE_ROOT="$PRIOR_STUDY_ROOT/repeat-$repeat/api" \
    BAILIAN_ANSWER_THINKING=false \
    ANSWER_TEMPERATURE=1.0 \
    ANSWER_EXTRA_BODY_JSON="{\"enable_thinking\":false,\"do_sample\":true,\"top_p\":1.0,\"seed\":$seed,\"n\":1}" \
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
    CANDIDATE_STUDY_TITLE="MemCalib v2.4.1 benchmark-1500 six-model Non-Think Full-memory seed $seed" \
    CANDIDATE_STUDY_DESCRIPTION="Locked 1,500-record, six-model Full-memory evaluation; stochastic answer seed $seed; DeepSeek-V4-Pro deterministic Judge; broad Bailian credential only." \
    SAMPLE_LEVEL_STUDY_TITLE="MemCalib v2.4.1 benchmark-1500 sample-level metrics, answer seed $seed" \
    zsh evaluation/scripts/run_memcalib_v23_nine_models.sh \
    >> "$run/workflow.log" 2>&1
done

printf 'aggregating\n' > "$STUDY_ROOT/workflow.status"
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/aggregate_repeated_evaluations.py \
  --repeat "seed-42=$RELEASE_ROOT/repeat-1/metrics.json,$ANALYSIS_ROOT/repeat-1/sample-level/sample-level-metrics.json" \
  --repeat "seed-43=$RELEASE_ROOT/repeat-2/metrics.json,$ANALYSIS_ROOT/repeat-2/sample-level/sample-level-metrics.json" \
  --repeat "seed-44=$RELEASE_ROOT/repeat-3/metrics.json,$ANALYSIS_ROOT/repeat-3/sample-level/sample-level-metrics.json" \
  --output-dir "$ANALYSIS_ROOT/aggregate"

printf 'completed\n' > "$STUDY_ROOT/workflow.status"
date -Iseconds > "$STUDY_ROOT/workflow.completed"
