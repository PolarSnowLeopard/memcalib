#!/bin/zsh
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"

PYTHON_BIN=${PYTHON_BIN:-/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}
ENV_FILE=${PRIMUS_CHAT_ENV_FILE:-$HOME/.config/memcalib/primus-chat.env}
WORKERS=${PRIMUS_CHAT_WORKERS_PER_MODEL:-64}
MAX_ROUNDS=${PRIMUS_CHAT_MAX_ROUNDS:-6}
RUN=evaluation/runs/memcalib-v241-benchmark1500-four-platform-models-nonthinking-full-memory-three-seeds

if [[ ! -r "$ENV_FILE" ]]; then
  printf 'missing credential file: %s\n' "$ENV_FILE" >&2
  exit 2
fi
set -a
source "$ENV_FILE"
set +a

keys=(claude-opus-5 gpt56-sol gemini35-flash)
models=(claude-opus-5 gpt-5.6-sol gemini-3.5-flash)
seeds=(42 43 44)

date -Iseconds > "$RUN/primus-chat-completion.started"
printf 'starting\n' > "$RUN/primus-chat-completion.status"
printf 'primus_chat_direct_running\n' > "$RUN/platform-completion.status"

run_one() {
  local repeat=$1 seed=$2 key=$3 model=$4
  local input="$RUN/request-template/$key/full_memory.jsonl"
  local dir="$RUN/repeat-$repeat/$key"
  local output="$dir/normalized.jsonl"
  local failed="$dir/primus-chat.failed.jsonl"
  local report="$dir/primus-chat.report.json"
  local round log
  mkdir -p "$dir"

  for round in {1..$MAX_ROUNDS}; do
    log="$dir/primus-chat.round-$round.log"
    if PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/run_primus_chat_api.py \
      --input "$input" \
      --output "$output" \
      --failed-output "$failed" \
      --report "$report" \
      --model "$model" \
      --seed "$seed" \
      --workers "$WORKERS" \
      --max-tokens 8192 \
      --timeout 300 \
      --max-retries 4 \
      --progress-every 50 \
      > "$log" 2>&1; then
      break
    fi
    if [[ "$round" -eq "$MAX_ROUNDS" ]]; then
      printf 'exhausted retries: repeat=%s model=%s\n' "$repeat" "$model" >&2
      return 1
    fi
    sleep $((round * 10))
  done

  PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/validate_api_results.py \
    --input "$input" \
    --output "$output" \
    --model "$model" \
    --report "$dir/normalized.validation.json" \
    >> "$log" 2>&1
  PYTHONPATH=. "$PYTHON_BIN" \
    evaluation/current/v2.4.1/cluster/memcalib-v241-local-baselines-1500/validate_nonthinking.py \
    --input "$output" \
    --report "$dir/nonthinking.validation.json" \
    >> "$log" 2>&1
  date -Iseconds > "$dir/primus-chat.completed"
}

for repeat in 1 2 3; do
  seed=${seeds[$repeat]}
  printf 'repeat_%s_running\n' "$repeat" > "$RUN/primus-chat-completion.status"
  pids=()
  for index in {1..3}; do
    run_one "$repeat" "$seed" "${keys[$index]}" "${models[$index]}" &
    pids+=($!)
  done
  code=0
  for pid in "${pids[@]}"; do
    wait "$pid" || code=1
  done
  if [[ "$code" -ne 0 ]]; then
    printf 'repeat_%s_failed\n' "$repeat" > "$RUN/primus-chat-completion.status"
    printf 'primus_chat_direct_failed\n' > "$RUN/platform-completion.status"
    exit 1
  fi
  printf 'repeat_%s_completed\n' "$repeat" > "$RUN/primus-chat-completion.status"
done

printf 'completed\n' > "$RUN/primus-chat-completion.status"
printf 'completed\n' > "$RUN/platform-completion.status"
date -Iseconds > "$RUN/primus-chat-completion.completed"
