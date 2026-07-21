#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from memcalib_v23_common import V23_DIR, file_sha256, portable_path
from utils import iter_jsonl, write_json, write_jsonl


DEFAULT_ORDER = V23_DIR / "memcalib_v23_independent_qc_15000.reject.jsonl"
DEFAULT_OUTPUT = V23_DIR / "memcalib_v23_targeted_rewrite_input_334.jsonl"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge disjoint targeted v2.3 rewrite request sets in reject order."
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
    request_ids: set[str] = set()
    inputs = []
    for path in args.inputs:
        rows = list(iter_jsonl(path))
        for row in rows:
            params = row.get("user_defined_params") or {}
            record_id = str(params.get("record_id") or "")
            request_id = str(row.get("request_id") or "")
            if not record_id or not request_id:
                raise ValueError(f"{path} contains an empty record or request ID")
            if record_id in merged or request_id in request_ids:
                raise ValueError(f"duplicate targeted rewrite request for {record_id}")
            merged[record_id] = row
            request_ids.add(request_id)
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
            f"targeted rewrite coverage mismatch: missing={len(missing)} extra={len(extra)}"
        )
    output_rows = [merged[record_id] for record_id in order_ids]
    write_jsonl(args.output, output_rows)
    manifest = {
        "schema_version": "memcalib-v23-targeted-rewrite-request-merge-v1",
        "policy": "reject_order_exact_disjoint_coverage",
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
            "unique_request_ids": len(request_ids),
            "unique_record_ids": len(merged),
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
