#!/bin/zsh
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"

PYTHON_BIN=${PYTHON_BIN:-/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}
CONFIG=evaluation/current/v2.4.1/configs/memcalib-v241-benchmark1500-local-vllm-two-models-nonthinking.json
SAMPLE_RELEASE=evaluation/current/v2.4.1/releases/memcalib-v241-benchmark-test-eval-1500
STUDY_ROOT=evaluation/runs/memcalib-v241-local-baselines-1500-nonthinking-vllm
RELEASE_ROOT=evaluation/current/v2.4.1/releases/memcalib-v241-local-baselines-1500-nonthinking-vllm
ANALYSIS_ROOT=evaluation/current/v2.4.1/analyses/memcalib-v241-local-baselines-1500-nonthinking-vllm
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
  mkdir -p "$release" "$analysis"

  qwen_requests="$run/requests/answers/qwen35-35b-a3b-local-vllm/full_memory.jsonl"
  qwen_results="$run/answers/qwen35-35b-a3b-local-vllm/full_memory.jsonl"
  qwen_failed="$run/answers/qwen35-35b-a3b-local-vllm/full_memory.failed.jsonl"
  failure_audit="$run/answers/qwen35-35b-a3b-local-vllm/full_memory.inference-failure-audit.json"
  PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/materialize_inference_failures.py \
    --requests "$qwen_requests" --results "$qwen_results" --failed "$qwen_failed" \
    --served-model med_chat --audit "$failure_audit"
  PYTHONPATH=. "$PYTHON_BIN" \
    evaluation/current/v2.4.1/cluster/memcalib-v241-local-baselines-1500/validate_nonthinking.py \
    --input "$qwen_results" \
    --report "$run/answers/qwen35-35b-a3b-local-vllm/full_memory.nonthinking-validation.json"

  printf 'repeat-%s-judge-seed-%s\n' "$repeat" "$seed" > "$STUDY_ROOT/workflow.status"
  env \
    PYTHON_BIN="$PYTHON_BIN" \
    MEMCALIB_CONFIG="$CONFIG" \
    MEMCALIB_SAMPLE_RELEASE="$SAMPLE_RELEASE" \
    MEMCALIB_RELEASE="$release" \
    MEMCALIB_RUN="$run" \
    MEMCALIB_ANALYSIS="$analysis" \
    MEMCALIB_BAILIAN_CREDENTIAL_MODE=broad_only \
    SKIP_SAMPLE_RELEASE=true \
    SKIP_ANSWER_REQUEST_PREP=true \
    SKIP_ANSWER_GENERATION=true \
    MEMCALIB_CONDITIONS=full_memory \
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
    INFERENCE_FAILURE_AUDIT="$failure_audit" \
    CANDIDATE_STUDY_TITLE="MemCalib v2.4.1 local vLLM baselines, seed $seed" \
    CANDIDATE_STUDY_DESCRIPTION="Locked 1,500-record Full-memory Non-Think evaluation of two local vLLM baselines; DeepSeek-V4-Pro Judge; inference failures remain in the denominator." \
    SAMPLE_LEVEL_STUDY_TITLE="MemCalib v2.4.1 local vLLM baseline sample-level metrics, seed $seed" \
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
