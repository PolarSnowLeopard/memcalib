#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../../../../.." && pwd)
cd "$ROOT"
STUDY_RUN=${MEMCALIB_STUDY_RUN:-evaluation/runs/memcalib-v241-local-baselines-1500-nonthinking-vllm}
ARCHIVE=${MEMCALIB_ARCHIVE:-$STUDY_RUN/memcalib-v241-local-baselines-1500-nonthinking-vllm-raw-results.tar.gz}

if [[ ! -d "$STUDY_RUN" ]]; then
  printf 'Missing study run: %s\n' "$STUDY_RUN" >&2
  exit 1
fi

mkdir -p "$(dirname "$ARCHIVE")"
items=()
for repeat in 1 2 3; do
  if [[ -d "$STUDY_RUN/repeat-$repeat/answers" ]]; then
    items+=("repeat-$repeat/answers")
  fi
  if [[ -d "$STUDY_RUN/repeat-$repeat/requests/answers" ]]; then
    items+=("repeat-$repeat/requests/answers")
  fi
  if [[ -d "$STUDY_RUN/repeat-$repeat/request-manifests" ]]; then
    items+=("repeat-$repeat/request-manifests")
  fi
  if [[ -f "$STUDY_RUN/repeat-$repeat/answer.seed" ]]; then
    items+=("repeat-$repeat/answer.seed")
  fi
done
if [[ "${#items[@]}" -eq 0 ]]; then
  printf 'No answer artifacts found under %s\n' "$STUDY_RUN" >&2
  exit 1
fi

tar -czf "$ARCHIVE" -C "$STUDY_RUN" "${items[@]}"
if command -v sha256sum >/dev/null 2>&1; then
  digest=$(sha256sum "$ARCHIVE" | awk '{print $1}')
else
  digest=$(shasum -a 256 "$ARCHIVE" | awk '{print $1}')
fi
printf '%s  %s\n' "$digest" "$(basename "$ARCHIVE")" | tee "$ARCHIVE.sha256"
printf 'Raw result archive: %s\n' "$ARCHIVE"
