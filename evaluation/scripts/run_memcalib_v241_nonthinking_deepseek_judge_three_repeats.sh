#!/bin/zsh
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"

PYTHON_BIN=${PYTHON_BIN:-/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}
CONFIG=evaluation/current/v2.4.1/configs/memcalib-v241-multidomain-494-nine-models-nonthinking-deepseek-v4-pro-judge.json
SAMPLE_RELEASE=evaluation/current/v2.4.1/releases/memcalib-v241-multidomain-494-nine-models-nonthinking
STUDY_ROOT=evaluation/runs/memcalib-v241-nonthinking-nine-models-deepseek-v4-pro-judge-three-repeats
RELEASE_ROOT=evaluation/current/v2.4.1/releases/memcalib-v241-nonthinking-nine-models-deepseek-v4-pro-judge-three-repeats
ANALYSIS_ROOT=evaluation/current/v2.4.1/analyses/memcalib-v241-nonthinking-nine-models-deepseek-v4-pro-judge-three-repeats
mkdir -p "$STUDY_ROOT" "$RELEASE_ROOT" "$ANALYSIS_ROOT"

printf 'starting\n' > "$STUDY_ROOT/workflow.status"
date -Iseconds > "$STUDY_ROOT/workflow.started"

for repeat in 1 2 3; do
  run="$STUDY_ROOT/repeat-$repeat"
  release="$RELEASE_ROOT/repeat-$repeat"
  analysis="$ANALYSIS_ROOT/repeat-$repeat"
  if [[ -s "$run/workflow.completed" ]]; then
    printf '[%s] repeat-%s already complete; preserving outputs\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$repeat"
    continue
  fi
  mkdir -p "$run" "$release" "$analysis"
  printf 'repeat-%s\n' "$repeat" > "$STUDY_ROOT/workflow.status"
  printf '[%s] starting repeat-%s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$repeat"
  env \
    PYTHON_BIN="$PYTHON_BIN" \
    MEMCALIB_CONFIG="$CONFIG" \
    MEMCALIB_SAMPLE_RELEASE="$SAMPLE_RELEASE" \
    MEMCALIB_RELEASE="$release" \
    MEMCALIB_RUN="$run" \
    MEMCALIB_ANALYSIS="$analysis" \
    MEMCALIB_BAILIAN_CREDENTIAL_MODE=broad_only \
    SKIP_SAMPLE_RELEASE=true \
    BAILIAN_ANSWER_THINKING=false \
    CODEX_ANSWER_WORKERS=12 \
    PRIMARY_JUDGE_MODEL=deepseek-v4-pro \
    PRIMARY_JUDGE_WORKERS=300 \
    PRIMARY_JUDGE_RPM=480 \
    SECONDARY_DEFAULT_JUDGE_MODEL=deepseek-v4-pro \
    SECONDARY_DEFAULT_JUDGE_WORKERS=100 \
    SECONDARY_DEFAULT_JUDGE_RPM=240 \
    SECONDARY_DEEPSEEK_JUDGE_MODEL=deepseek-v4-pro \
    SECONDARY_DEEPSEEK_JUDGE_WORKERS=100 \
    SECONDARY_DEEPSEEK_JUDGE_RPM=240 \
    CANDIDATE_STUDY_TITLE="MemCalib v2.4.1 Non-Think DeepSeek-V4-Pro Judge repeat $repeat" \
    CANDIDATE_STUDY_DESCRIPTION="Locked 494-record, nine-model, paired full-memory/no-memory evaluation; independent answer repeat $repeat of 3; all primary judgments by DeepSeek-V4-Pro using the broad Bailian credential." \
    SAMPLE_LEVEL_STUDY_TITLE="MemCalib v2.4.1 Non-Think sample-level metrics, DeepSeek-V4-Pro Judge, repeat $repeat" \
    zsh evaluation/scripts/run_memcalib_v23_nine_models.sh \
    >> "$run/workflow.log" 2>&1
done

printf 'aggregating\n' > "$STUDY_ROOT/workflow.status"
PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/aggregate_repeated_evaluations.py \
  --repeat "repeat-1=$RELEASE_ROOT/repeat-1/metrics.json,$ANALYSIS_ROOT/repeat-1/sample-level/sample-level-metrics.json" \
  --repeat "repeat-2=$RELEASE_ROOT/repeat-2/metrics.json,$ANALYSIS_ROOT/repeat-2/sample-level/sample-level-metrics.json" \
  --repeat "repeat-3=$RELEASE_ROOT/repeat-3/metrics.json,$ANALYSIS_ROOT/repeat-3/sample-level/sample-level-metrics.json" \
  --output-dir "$ANALYSIS_ROOT/aggregate"

printf 'completed\n' > "$STUDY_ROOT/workflow.status"
date -Iseconds > "$STUDY_ROOT/workflow.completed"
