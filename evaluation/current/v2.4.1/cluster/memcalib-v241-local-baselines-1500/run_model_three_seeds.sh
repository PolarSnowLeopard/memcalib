#!/bin/bash
set -euo pipefail

if [[ "$#" -lt 3 || "$#" -gt 6 ]]; then
  printf 'Usage: %s MODEL_KEY SERVED_MODEL_NAME CHAT_COMPLETIONS_URL [DISPLAY_NAME] [CHECKPOINT_ROLE] [REQUEST_PROFILE]\n' "$0" >&2
  exit 2
fi

ROOT=$(cd "$(dirname "$0")/../../../../.." && pwd)
cd "$ROOT"
STUDY_RUN=${MEMCALIB_STUDY_RUN:-evaluation/runs/memcalib-v241-local-baselines-1500-nonthinking-vllm}
MODEL_KEY=$1
seeds=(42 43 44)

for index in 0 1 2; do
  repeat=$((index + 1))
  seed=${seeds[$index]}
  run="$STUDY_RUN/repeat-$repeat"
  completed="$run/answers/$MODEL_KEY/completed"
  if [[ -s "$completed" ]]; then
    printf 'repeat-%s seed=%s already complete for %s; preserving outputs\n' \
      "$repeat" "$seed" "$MODEL_KEY"
    continue
  fi
  mkdir -p "$run"
  printf '%s\n' "$seed" > "$run/answer.seed"
  printf '[%s] starting %s repeat-%s seed=%s\n' \
    "$(date '+%Y-%m-%d %H:%M:%S')" "$MODEL_KEY" "$repeat" "$seed"
  env \
    MEMCALIB_RUN="$run" \
    VLLM_EVAL_SEED="$seed" \
    bash evaluation/current/v2.4.1/cluster/memcalib-v241-local-baselines-1500/run_answer_model.sh \
      "$@"
done

printf 'Completed all three seeds for %s\n' "$MODEL_KEY"
