#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from memcalib_v23_common import V23_DIR, file_sha256, portable_path
from utils import iter_jsonl, write_json, write_jsonl


DEFAULT_ORDER = V23_DIR / "memcalib_v23_independent_qc_15000.reject.jsonl"
DEFAULT_OUTPUT = V23_DIR / "memcalib_v23_repaired_records.jsonl"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge disjoint repaired v2.3 record sets in target order."
    )
    parser.add_argument("--order", type=Path, default=DEFAULT_ORDER)
    parser.add_argument("--inputs", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    order_rows = list(iter_jsonl(args.order))
    order_ids = [str(row.get("id") or "") for row in order_rows]
    if "" in order_ids or len(order_ids) != len(set(order_ids)):
        raise ValueError("target record IDs must be non-empty and unique")

    merged: dict[str, dict[str, Any]] = {}
    inputs: list[dict[str, Any]] = []
    for path in args.inputs:
        rows = list(iter_jsonl(path))
        for row in rows:
            record_id = str(row.get("id") or "")
            if not record_id:
                raise ValueError(f"{path} contains an empty record ID")
            if record_id in merged:
                raise ValueError(f"duplicate repaired record ID {record_id}")
            merged[record_id] = row
        inputs.append(
            {
                "path": portable_path(path),
                "sha256": file_sha256(path),
                "count": len(rows),
            }
        )

    missing = set(order_ids) - set(merged)
    extra = set(merged) - set(order_ids)
    if missing or extra:
        raise ValueError(
            f"repaired records mismatch: missing={len(missing)} extra={len(extra)}"
        )
    output_rows = [merged[record_id] for record_id in order_ids]
    write_jsonl(args.output, output_rows)
    manifest = {
        "schema_version": "memcalib-v23-repaired-record-merge-v1",
        "policy": "target_order_exact_disjoint_coverage",
        "order": {
            "path": portable_path(args.order),
            "sha256": file_sha256(args.order),
            "count": len(order_rows),
        },
        "inputs": inputs,
        "output": {
            "path": portable_path(args.output),
            "sha256": file_sha256(args.output),
            "count": len(output_rows),
            "unique_record_ids": len(merged),
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
