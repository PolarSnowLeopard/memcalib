#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../../../../.." && pwd)
cd "$ROOT"
STUDY_RUN=${MEMCALIB_STUDY_RUN:-evaluation/runs/memcalib-v241-local-baselines-1500-nonthinking-vllm}

count_rows() {
  local path=$1
  if [[ -f "$path" ]]; then
    wc -l < "$path" | tr -d ' '
  else
    printf '0'
  fi
}

printf '%-9s %-36s %11s %11s %8s %10s\n' REPEAT MODEL SMOKE FULL FAILED NONTHINK
for repeat in 1 2 3; do
  run="$STUDY_RUN/repeat-$repeat"
  request_root="$run/requests/answers"
  [[ -d "$request_root" ]] || continue
  while IFS= read -r request_dir; do
    model=$(basename "$request_dir")
    answer_root="$run/answers/$model"
    smoke=$(count_rows "$answer_root/smoke.jsonl")
    full=$(count_rows "$answer_root/full_memory.jsonl")
    smoke_expected=$(count_rows "$request_dir/smoke.jsonl")
    full_expected=$(count_rows "$request_dir/full_memory.jsonl")
    failed=$(( \
      $(count_rows "$answer_root/smoke.failed.jsonl") + \
      $(count_rows "$answer_root/full_memory.failed.jsonl") \
    ))
    nonthink=no
    if [[ -s "$answer_root/full_memory.nonthinking-validation.json" ]] && \
       "${PYTHON_BIN:-python3}" -c \
         'import json,sys; raise SystemExit(0 if json.load(open(sys.argv[1]))["valid_nonthinking"] else 1)' \
         "$answer_root/full_memory.nonthinking-validation.json"; then
      nonthink=yes
    fi
    printf 'repeat-%-2s %-36s %5s/%-5s %5s/%-5s %8s %10s\n' \
      "$repeat" "$model" "$smoke" "$smoke_expected" \
      "$full" "$full_expected" "$failed" "$nonthink"
  done < <(find "$request_root" -mindepth 1 -maxdepth 1 -type d | sort)
done
