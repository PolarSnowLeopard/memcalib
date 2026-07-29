#!/bin/zsh
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
: "${PYTHON_BIN:?Set PYTHON_BIN to a non-Conda Python 3.10+ executable}"

CONFIG=evaluation/archive/configs/memcalib-ordered-v2.1-full-15526.json
ANSWER_RUN=evaluation/runs/memcalib-v0.1-full-15526
ANSWER_RELEASE=evaluation/archive/releases/memcalib-v0.1-full-15526
JUDGE_RUN=evaluation/runs/memcalib-ordered-v2.1-full-15526
JUDGE_RELEASE=evaluation/archive/releases/memcalib-ordered-v2.1-full-15526

PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/finalize_answer_run.py \
  --config "$CONFIG" \
  --requests "$ANSWER_RUN/requests/answers" \
  --results "$ANSWER_RUN/answers" \
  --manifest "$ANSWER_RELEASE/answer-run.manifest.json" \
  --conditions full_memory

PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/prepare_judge_requests.py \
  --config "$CONFIG" \
  --hidden "$ANSWER_RELEASE/hidden-evaluation.jsonl" \
  --answers "$ANSWER_RUN/answers" \
  --output-dir "$JUDGE_RUN/requests/judges" \
  --manifest "$JUDGE_RELEASE/judge-request.manifest.json" \
  --conditions full_memory
