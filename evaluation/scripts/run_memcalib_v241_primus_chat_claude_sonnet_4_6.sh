#!/bin/zsh
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"

PYTHON_BIN=${PYTHON_BIN:-/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}
ENV_FILE=${PRIMUS_CHAT_ENV_FILE:-$HOME/.config/memcalib/primus-chat.env}
WORKERS=${PRIMUS_CHAT_SONNET_WORKERS:-24}
MAX_ROUNDS=${PRIMUS_CHAT_MAX_ROUNDS:-8}
RUN=evaluation/runs/memcalib-v241-benchmark1500-four-platform-models-nonthinking-full-memory-three-seeds
KEY=claude-sonnet-4-6
MODEL=claude-sonnet-4-6
SOURCE_KEY=claude-opus-5
SOURCE_INPUT="$RUN/request-template/$SOURCE_KEY/full_memory.jsonl"
INPUT="$RUN/request-template/$KEY/full_memory.jsonl"

if [[ ! -r "$ENV_FILE" ]]; then
  printf 'missing credential file: %s\n' "$ENV_FILE" >&2
  exit 2
fi
set -a
source "$ENV_FILE"
set +a

PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/prepare_primus_model_request_template.py \
  --input "$SOURCE_INPUT" \
  --output "$INPUT" \
  --source-key "$SOURCE_KEY" \
  --target-key "$KEY" \
  --target-model "$MODEL" \
  --expected-count 1500 \
  --report "$RUN/request-template/$KEY/template.manifest.json"

date -Iseconds > "$RUN/primus-chat-sonnet-4-6.started"
printf 'starting\n' > "$RUN/primus-chat-sonnet-4-6.status"
printf 'sonnet_4_6_running\n' > "$RUN/platform-completion.status"
seeds=(42 43 44)

run_one() {
  local repeat=$1 seed=$2
  local dir="$RUN/repeat-$repeat/$KEY"
  local output="$dir/normalized.jsonl"
  local failed="$dir/primus-chat.failed.jsonl"
  local report="$dir/primus-chat.report.json"
  local round log
  mkdir -p "$dir"

  for round in {1..$MAX_ROUNDS}; do
    log="$dir/primus-chat.resume-round-$round.log"
    if PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/run_primus_chat_api.py \
      --input "$INPUT" \
      --output "$output" \
      --failed-output "$failed" \
      --report "$report" \
      --model "$MODEL" \
      --seed "$seed" \
      --workers "$WORKERS" \
      --max-tokens 8192 \
      --timeout 300 \
      --max-retries 5 \
      --progress-every 50 \
      > "$log" 2>&1; then
      break
    fi
    if [[ "$round" -eq "$MAX_ROUNDS" ]]; then
      printf 'exhausted retries: repeat=%s model=%s\n' "$repeat" "$MODEL" >&2
      return 1
    fi
    sleep $((round * 15))
  done

  PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/validate_api_results.py \
    --input "$INPUT" \
    --output "$output" \
    --model "$MODEL" \
    --report "$dir/normalized.validation.json" \
    >> "$log" 2>&1
  PYTHONPATH=. "$PYTHON_BIN" \
    evaluation/current/v2.4.1/cluster/memcalib-v241-local-baselines-1500/validate_nonthinking.py \
    --input "$output" \
    --report "$dir/nonthinking.validation.json" \
    >> "$log" 2>&1
  cp "$report" "$dir/normalization.report.json"
  date -Iseconds > "$dir/primus-chat.completed"
}

for repeat in 1 2 3; do
  printf 'repeat_%s_running\n' "$repeat" > "$RUN/primus-chat-sonnet-4-6.status"
  if ! run_one "$repeat" "${seeds[$repeat]}"; then
    printf 'repeat_%s_failed\n' "$repeat" > "$RUN/primus-chat-sonnet-4-6.status"
    printf 'sonnet_4_6_failed\n' > "$RUN/platform-completion.status"
    exit 1
  fi
done

printf 'completed\n' > "$RUN/primus-chat-sonnet-4-6.status"
while [[ "$(cat "$RUN/primus-chat-gpt-gemini.status" 2>/dev/null || true)" != "completed" ]]; do
  printf 'waiting_for_gpt_gemini\n' > "$RUN/platform-completion.status"
  sleep 30
done
printf 'completed\n' > "$RUN/platform-completion.status"
date -Iseconds > "$RUN/primus-chat-sonnet-4-6.completed"
