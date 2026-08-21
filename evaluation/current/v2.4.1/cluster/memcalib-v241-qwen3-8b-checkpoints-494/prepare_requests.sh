#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../../../../.." && pwd)
cd "$ROOT"

PYTHON_BIN=${PYTHON_BIN:-python3}
CONFIG=${MEMCALIB_CONFIG:-evaluation/current/v2.4.1/configs/memcalib-v241-multidomain-494-nine-models-nonthinking.json}
SAMPLE_RELEASE=${MEMCALIB_SAMPLE_RELEASE:-evaluation/current/v2.4.1/releases/memcalib-v241-multidomain-494-nine-models-nonthinking}
RUN=${MEMCALIB_RUN:-evaluation/runs/memcalib-v241-qwen3-8b-checkpoints-494-vllm}

PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/prepare_answer_requests.py \
  --config "$CONFIG" \
  --input "$SAMPLE_RELEASE/model-facing.jsonl" \
  --output-dir "$RUN/requests/answers" \
  --manifest "$RUN/answer-request.manifest.json" \
  --conditions full_memory

printf 'Prepared default-model answer requests under %s\n' "$RUN/requests/answers"
