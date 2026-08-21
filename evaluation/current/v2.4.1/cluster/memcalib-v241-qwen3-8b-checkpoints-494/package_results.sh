#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../../../../.." && pwd)
cd "$ROOT"
PYTHON_BIN=${PYTHON_BIN:-python3}
CONFIG=${MEMCALIB_CONFIG:-evaluation/current/v2.4.1/configs/memcalib-v241-multidomain-494-nine-models-nonthinking.json}
RUN=${MEMCALIB_RUN:-evaluation/runs/memcalib-v241-qwen3-8b-checkpoints-494-vllm}
REQUESTS="$RUN/requests/answers"
ANSWERS="$RUN/answers"
RUNTIME_CONFIG="$RUN/runtime-config.json"
ARCHIVE=${MEMCALIB_ARCHIVE:-$RUN/memcalib-v241-qwen3-8b-checkpoints-494-vllm-results.tar.gz}

PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/build_vllm_runtime_config.py \
  --config "$CONFIG" \
  --answers "$ANSWERS" \
  --output "$RUNTIME_CONFIG"

PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/finalize_answer_run.py \
  --config "$RUNTIME_CONFIG" \
  --requests "$REQUESTS" \
  --results "$ANSWERS" \
  --manifest "$RUN/answer-run.manifest.json" \
  --conditions full_memory

archive_items=(
  answer-run.manifest.json
  runtime-config.json
  requests/answers
  answers
)
if [[ -f "$RUN/answer-request.manifest.json" ]]; then
  archive_items+=(answer-request.manifest.json)
fi
if [[ -d "$RUN/request-manifests" ]]; then
  archive_items+=(request-manifests)
fi
tar -czf "$ARCHIVE" -C "$RUN" "${archive_items[@]}"

if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$ARCHIVE" | tee "$ARCHIVE.sha256"
else
  shasum -a 256 "$ARCHIVE" | tee "$ARCHIVE.sha256"
fi
printf 'Result archive: %s\n' "$ARCHIVE"
