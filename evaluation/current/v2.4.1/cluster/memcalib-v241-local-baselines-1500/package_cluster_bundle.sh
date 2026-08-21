#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../../../../.." && pwd)
cd "$ROOT"

OUTPUT_ROOT=${MEMCALIB_BUNDLE_OUTPUT_ROOT:-deliverables}
ARCHIVE=${MEMCALIB_CLUSTER_ARCHIVE:-$OUTPUT_ROOT/memcalib-v241-local-baselines-1500-cluster-bundle.tar.gz}

mkdir -p "$(dirname "$ARCHIVE")"
tar \
  --exclude='*/__pycache__' \
  --exclude='*.pyc' \
  -czf "$ARCHIVE" \
  evaluation/__init__.py \
  evaluation/common.py \
  evaluation/scripts/__init__.py \
  evaluation/scripts/prepare_answer_requests.py \
  evaluation/scripts/validate_api_results.py \
  evaluation/prompts/answer-system.txt \
  evaluation/current/v2.4.1/configs/memcalib-v241-benchmark1500-local-vllm-two-models-nonthinking.json \
  evaluation/current/v2.4.1/releases/memcalib-v241-benchmark-test-eval-1500/model-facing.jsonl \
  evaluation/current/v2.4.1/releases/memcalib-v241-benchmark-test-eval-1500/release-manifest.json \
  evaluation/current/v2.4.1/cluster/memcalib-v241-local-baselines-1500 \
  pipeline/06_run_bailian_api.py \
  pipeline/utils.py

if command -v sha256sum >/dev/null 2>&1; then
  digest=$(sha256sum "$ARCHIVE" | awk '{print $1}')
else
  digest=$(shasum -a 256 "$ARCHIVE" | awk '{print $1}')
fi
printf '%s  %s\n' "$digest" "$(basename "$ARCHIVE")" | tee "$ARCHIVE.sha256"
printf 'Cluster bundle: %s\n' "$ARCHIVE"
