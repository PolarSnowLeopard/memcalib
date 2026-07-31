#!/bin/zsh
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"

export PYTHON_BIN=/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
export MEMCALIB_CONFIG=evaluation/current/v2.4.1/configs/memcalib-v241-multidomain-494-nine-models-nonthinking.json
export MEMCALIB_BENCHMARK=pipeline/data/multidomain/full-v2/revision-coding-text-observable-v24/v241/release/memcalib_v241_multidomain_benchmark_15000.jsonl
export MEMCALIB_SAMPLE_RELEASE=evaluation/current/v2.4.1/releases/memcalib-v241-multidomain-494-nine-models-nonthinking
export MEMCALIB_RELEASE="$MEMCALIB_SAMPLE_RELEASE"
export MEMCALIB_RUN=evaluation/runs/memcalib-v241-multidomain-494-nine-models-nonthinking
export MEMCALIB_ANALYSIS=evaluation/current/v2.4.1/analyses/candidate-metrics-nonthinking
export BAILIAN_ANSWER_THINKING=false
export ANSWER_REUSE_ROOT=evaluation/runs/memcalib-v24-multidomain-494-nine-models-system-v2-nonthinking/answers
export JUDGE_REUSE_ROOT=evaluation/runs/memcalib-v24-multidomain-494-nine-models-system-v2-nonthinking/api
export SKIP_SAMPLE_RELEASE=false
export SKIP_ANSWER_REQUEST_PREP=false
export SKIP_ANSWER_GENERATION=false
export CANDIDATE_STUDY_TITLE="MemCalib v2.4.1 non-thinking nine-model candidate metric study"
export CANDIDATE_STUDY_DESCRIPTION="Primary evaluation on the corrected v2.4.1 release using the exact locked 494 IDs, non-thinking Bailian answers, the unified careful-assistant system prompt, and Codex reasoning none."

exec /bin/zsh evaluation/scripts/run_memcalib_v23_nine_models.sh
