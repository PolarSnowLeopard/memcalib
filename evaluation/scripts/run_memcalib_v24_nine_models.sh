#!/bin/zsh
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"

export MEMCALIB_CONFIG=evaluation/configs/memcalib-v24-multidomain-500-nine-models.json
export MEMCALIB_BENCHMARK=pipeline/data/multidomain/full-v2/revision-coding-text-observable-v24/release/memcalib_v24_multidomain_benchmark_15000.jsonl
export MEMCALIB_SAMPLE_RELEASE=evaluation/releases/memcalib-v24-multidomain-500-nine-models
export MEMCALIB_RELEASE="$MEMCALIB_SAMPLE_RELEASE"
export MEMCALIB_RUN=evaluation/runs/memcalib-v24-multidomain-500-nine-models
export MEMCALIB_ANALYSIS=evaluation/analyses/memcalib-v24-multidomain-500-nine-models-candidate-metrics
export BAILIAN_ANSWER_THINKING=true
export CANDIDATE_STUDY_TITLE="MemCalib v2.4 nine-model candidate metric study"
export CANDIDATE_STUDY_DESCRIPTION="The exact v2.3 locked 500 IDs projected onto MemCalib v2.4, with all 125 coding tasks revised for natural-language answer-text observability."

exec /bin/zsh evaluation/scripts/run_memcalib_v23_nine_models.sh
