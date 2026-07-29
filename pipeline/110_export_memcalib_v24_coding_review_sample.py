#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from memcalib_v23_common import file_sha256, portable_path
from memcalib_v24_coding_common import TASK_FAMILIES, V24_DIR
from utils import iter_jsonl, write_json, write_jsonl


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE = (
    V24_DIR / "release" / "memcalib_v24_multidomain_benchmark_15000.jsonl"
)
SAMPLE_DIR = REPO_ROOT / "docs" / "current" / "v2.4" / "samples"
DEFAULT_FULL = SAMPLE_DIR / "memcalib-v24-coding-review-sample-30.full.jsonl"
DEFAULT_MODEL_FACING = (
    SAMPLE_DIR / "memcalib-v24-coding-review-sample-30.model-facing.jsonl"
)
DEFAULT_MANIFEST = (
    SAMPLE_DIR / "memcalib-v24-coding-review-sample-30.manifest.json"
)


def stable_key(record: dict[str, Any], namespace: str) -> str:
    return hashlib.sha256(
        f"{namespace}:{record['id']}".encode("utf-8")
    ).hexdigest()


def select_sample(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    coding = [row for row in rows if row.get("domain") == "coding"]
    selected: list[dict[str, Any]] = []
    for family in TASK_FAMILIES:
        candidates = [
            row
            for row in coding
            if row["coding_text_observability_revision"]["task_family"] == family
        ]
        manual = [
            row
            for row in candidates
            if row.get("v24_coding_admission", {}).get("channel")
            == "manual_adjudication"
        ]
        strict = [
            row
            for row in candidates
            if row.get("v24_coding_admission", {}).get("channel")
            == "independent_qc_strict"
        ]
        manual.sort(key=lambda row: stable_key(row, "memcalib-v24-manual-review"))
        strict.sort(key=lambda row: stable_key(row, "memcalib-v24-strict-review"))
        manual_target = 1 if manual else 0
        selected.extend(manual[:manual_target])
        selected.extend(strict[: 10 - manual_target])
    if len(selected) != 30 or len({row["id"] for row in selected}) != 30:
        raise ValueError("review sample must contain 30 unique records")
    return selected


def model_facing_projection(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "domain": row["domain"],
        "source_dataset": row.get("source_dataset"),
        "task_family": row["coding_text_observability_revision"]["task_family"],
        "question": row["question"],
        "memory_blocks": row["memory_blocks"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export a deterministic 30-record MemCalib v2.4 coding sample."
    )
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--full-output", type=Path, default=DEFAULT_FULL)
    parser.add_argument(
        "--model-facing-output", type=Path, default=DEFAULT_MODEL_FACING
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    rows = list(iter_jsonl(args.release))
    selected = select_sample(rows)
    model_facing = [model_facing_projection(row) for row in selected]
    write_jsonl(args.full_output, selected)
    write_jsonl(args.model_facing_output, model_facing)
    manifest = {
        "schema_version": "memcalib-v24-coding-review-sample-v1",
        "selection": {
            "method": (
                "deterministic SHA-256 ordering within task family and admission "
                "channel; ten records per task family; one manual-adjudication "
                "record included when the family contains one"
            ),
            "records": len(selected),
            "task_family": dict(
                sorted(
                    Counter(
                        row["coding_text_observability_revision"]["task_family"]
                        for row in selected
                    ).items()
                )
            ),
            "admission_channel": dict(
                sorted(
                    Counter(
                        row["v24_coding_admission"]["channel"] for row in selected
                    ).items()
                )
            ),
            "record_ids": [row["id"] for row in selected],
        },
        "inputs": {
            "release": {
                "path": portable_path(args.release),
                "sha256": file_sha256(args.release),
                "records": len(rows),
            }
        },
        "outputs": {
            "full": {
                "path": portable_path(args.full_output),
                "sha256": file_sha256(args.full_output),
            },
            "model_facing": {
                "path": portable_path(args.model_facing_output),
                "sha256": file_sha256(args.model_facing_output),
            },
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
