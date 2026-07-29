#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$ROOT"

if [[ -z "${PYTHON_BIN:-}" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=python3
  else
    PYTHON_BIN=python
  fi
fi

CONFIG=${MEMCALIB_CONFIG:-evaluation/archive/configs/memcalib-v23-sft-base-500-vllm.json}
RUN=${MEMCALIB_RUN:-evaluation/runs/memcalib-v23-sft-base-500-vllm}
REQUESTS="$RUN/requests/answers"
ANSWERS="$RUN/answers"
MANIFEST="$RUN/answer-run.manifest.json"
RUNTIME_CONFIG="$RUN/runtime-config.json"
ARCHIVE=${MEMCALIB_ARCHIVE:-$RUN/memcalib-v23-sft-base-500-vllm-results.tar.gz}

"$PYTHON_BIN" - "$CONFIG" "$ANSWERS" "$RUNTIME_CONFIG" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

config_path, answers_path, output_path = map(Path, sys.argv[1:])
config = json.loads(config_path.read_text(encoding="utf-8"))
for model in config["answer_models"]:
    key = str(model["key"])
    served_path = answers_path / key / "served-model-name.txt"
    if not served_path.exists():
        raise SystemExit(f"missing served model metadata: {served_path}")
    model["logical_model"] = model["model"]
    model["model"] = served_path.read_text(encoding="utf-8").strip()
output_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

PYTHONPATH=. "$PYTHON_BIN" evaluation/scripts/finalize_answer_run.py \
  --config "$RUNTIME_CONFIG" \
  --requests "$REQUESTS" \
  --results "$ANSWERS" \
  --manifest "$MANIFEST" \
  --conditions full_memory no_memory

tar -czf "$ARCHIVE" \
  -C "$RUN" \
  answer-request.manifest.json \
  answer-run.manifest.json \
  runtime-config.json \
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
