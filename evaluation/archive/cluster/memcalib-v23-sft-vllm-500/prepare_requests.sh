#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$ROOT"

if [[ -z "${PYTHON_BIN:-}" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=python3
  else
    PYTHON_BIN=python
  fi
fi

CONFIG=${MEMCALIB_CONFIG:-evaluation/archive/configs/memcalib-v23-sft-base-500-vllm.json}
SAMPLE_RELEASE=${MEMCALIB_SAMPLE_RELEASE:-evaluation/archive/releases/memcalib-v23-multidomain-500-nine-models}
RUN=${MEMCALIB_RUN:-evaluation/runs/memcalib-v23-sft-base-500-vllm}
REQUESTS="$RUN/requests/answers"
MANIFEST="$RUN/answer-request.manifest.json"

PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/prepare_answer_requests.py \
  --config "$CONFIG" \
  --input "$SAMPLE_RELEASE/model-facing.jsonl" \
  --output-dir "$REQUESTS" \
  --manifest "$MANIFEST" \
  --conditions full_memory no_memory

printf 'Prepared cluster requests under %s\n' "$REQUESTS"
