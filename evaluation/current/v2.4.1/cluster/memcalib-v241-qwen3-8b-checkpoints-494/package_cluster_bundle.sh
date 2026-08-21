#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../../../../.." && pwd)
cd "$ROOT"

RUN=${MEMCALIB_RUN:-evaluation/runs/memcalib-v241-qwen3-8b-checkpoints-494-vllm}
ARCHIVE=${MEMCALIB_CLUSTER_ARCHIVE:-$RUN/memcalib-v241-qwen3-8b-checkpoints-494-cluster-bundle.tar.gz}

mkdir -p "$(dirname "$ARCHIVE")"
tar \
  --exclude='*/__pycache__' \
  --exclude='*.pyc' \
  -czf "$ARCHIVE" \
  evaluation/__init__.py \
  evaluation/common.py \
  evaluation/scripts/__init__.py \
  evaluation/scripts/prepare_answer_requests.py \
  evaluation/scripts/build_vllm_runtime_config.py \
  evaluation/scripts/validate_api_results.py \
  evaluation/scripts/finalize_answer_run.py \
  evaluation/prompts/answer-system.txt \
  evaluation/current/v2.4.1/configs/memcalib-v241-multidomain-494-nine-models-nonthinking.json \
  evaluation/current/v2.4.1/releases/memcalib-v241-multidomain-494-nine-models-nonthinking/model-facing.jsonl \
  evaluation/current/v2.4.1/cluster/memcalib-v241-qwen3-8b-checkpoints-494 \
  pipeline/06_run_bailian_api.py \
  pipeline/utils.py

if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$ARCHIVE" | tee "$ARCHIVE.sha256"
else
  shasum -a 256 "$ARCHIVE" | tee "$ARCHIVE.sha256"
fi
printf 'Cluster bundle: %s\n' "$ARCHIVE"
