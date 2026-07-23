#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$ROOT"

: "${PYTHON_BIN:?Set PYTHON_BIN to a non-Conda Python 3 executable}"

CONFIG=${MEMCALIB_CONFIG:-evaluation/configs/memcalib-v23-sft-base-500-vllm.json}
RUN=${MEMCALIB_RUN:-evaluation/runs/memcalib-v23-sft-base-500-vllm}
REQUESTS="$RUN/requests/answers"
ANSWERS="$RUN/answers"
MANIFEST="$RUN/answer-run.manifest.json"
ARCHIVE=${MEMCALIB_ARCHIVE:-$RUN/memcalib-v23-sft-base-500-vllm-results.tar.gz}

PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/finalize_answer_run.py \
  --config "$CONFIG" \
  --requests "$REQUESTS" \
  --results "$ANSWERS" \
  --manifest "$MANIFEST" \
  --conditions full_memory no_memory

tar -czf "$ARCHIVE" \
  -C "$RUN" \
  answer-request.manifest.json \
  answer-run.manifest.json \
  requests/answers \
  answers

"$PYTHON_BIN" - "$ARCHIVE" <<'PY'
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

path = Path(sys.argv[1])
digest = hashlib.sha256(path.read_bytes()).hexdigest()
print(f"archive={path}")
print(f"sha256={digest}")
print(f"bytes={path.stat().st_size}")
PY
