#!/bin/zsh
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"

export MEMCALIB_CONFIG=evaluation/current/v2.4/configs/memcalib-v24-multidomain-494-nine-models-complete-case.json
export MEMCALIB_BENCHMARK=pipeline/data/multidomain/full-v2/revision-coding-text-observable-v24/release/memcalib_v24_multidomain_benchmark_15000.jsonl
export MEMCALIB_SAMPLE_RELEASE=evaluation/current/v2.4/releases/memcalib-v24-multidomain-494-nine-models-complete-case
export MEMCALIB_RELEASE="$MEMCALIB_SAMPLE_RELEASE"
export MEMCALIB_RUN=evaluation/runs/memcalib-v24-multidomain-494-nine-models-complete-case
export MEMCALIB_ANALYSIS=evaluation/current/v2.4/analyses/candidate-metrics
export MEMCALIB_ANSWER_REQ="$MEMCALIB_RUN/requests/answers"
export MEMCALIB_ANSWER_OUT="$MEMCALIB_RUN/answers"
export SKIP_SAMPLE_RELEASE=true
export SKIP_ANSWER_REQUEST_PREP=true
export SKIP_ANSWER_GENERATION=true
export BAILIAN_ANSWER_THINKING=true
export CANDIDATE_STUDY_TITLE="MemCalib v2.4 nine-model complete-case candidate metric study"
export CANDIDATE_STUDY_DESCRIPTION="The common 494-sample subset of the locked v2.4 500-sample evaluation after globally excluding six GLM-5.2 no-memory length failures from every model-condition cell."

exec /bin/zsh evaluation/scripts/run_memcalib_v23_nine_models.sh
