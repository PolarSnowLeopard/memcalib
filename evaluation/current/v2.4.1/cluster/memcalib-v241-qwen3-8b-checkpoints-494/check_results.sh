#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../../../../.." && pwd)
cd "$ROOT"

RUN=${MEMCALIB_RUN:-evaluation/runs/memcalib-v241-qwen3-8b-checkpoints-494-vllm}
REQUEST_ROOT="$RUN/requests/answers"

count_rows() {
  local path=$1
  if [[ -f "$path" ]]; then
    wc -l < "$path" | tr -d ' '
  else
    printf '0'
  fi
}

if [[ ! -d "$REQUEST_ROOT" ]]; then
  printf 'No prepared model requests under %s\n' "$REQUEST_ROOT" >&2
  exit 1
fi

models=()
while IFS= read -r path; do
  models+=("$(basename "$path")")
done < <(find "$REQUEST_ROOT" -mindepth 1 -maxdepth 1 -type d | sort)
if [[ "${#models[@]}" -eq 0 ]]; then
  printf 'No prepared model requests under %s\n' "$REQUEST_ROOT" >&2
  exit 1
fi

printf '%-36s %11s %11s %8s\n' MODEL SMOKE FULL FAILED
for model in "${models[@]}"; do
  root="$RUN/answers/$model"
  smoke=$(count_rows "$root/smoke.jsonl")
  full=$(count_rows "$root/full_memory.jsonl")
  smoke_expected=$(count_rows "$REQUEST_ROOT/$model/smoke.jsonl")
  full_expected=$(count_rows "$REQUEST_ROOT/$model/full_memory.jsonl")
  failed=$(( \
    $(count_rows "$root/smoke.failed.jsonl") + \
    $(count_rows "$root/full_memory.failed.jsonl") \
  ))
  printf '%-36s %5s/%-5s %5s/%-5s %8s\n' \
    "$model" "$smoke" "$smoke_expected" "$full" "$full_expected" "$failed"
done

printf '\nEach cell is shown as completed/expected. Models are discovered from prepared request directories.\n'
