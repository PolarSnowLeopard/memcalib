#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../../../../.." && pwd)
cd "$ROOT"

RUN=${MEMCALIB_RUN:-evaluation/runs/memcalib-v241-qwen3-8b-checkpoints-494-vllm}
ARCHIVE=${MEMCALIB_ARCHIVE:-$RUN/memcalib-v241-qwen3-8b-checkpoints-494-raw-results.tar.gz}

if [[ ! -d "$RUN/requests/answers" || ! -d "$RUN/answers" ]]; then
  printf 'Missing request or answer directory under %s\n' "$RUN" >&2
  exit 1
fi

archive_items=(
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
printf 'Raw result archive: %s\n' "$ARCHIVE"
