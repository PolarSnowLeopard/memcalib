#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from memcalib_v23_common import V23_DIR, file_sha256, portable_path
from utils import iter_jsonl, write_json, write_jsonl


DEFAULT_ORDER = V23_DIR / "memcalib_v23_rewritten_benchmark_15000.jsonl"
DEFAULT_STRICT = V23_DIR / "memcalib_v23_independent_qc_15000.strict.jsonl"
DEFAULT_REVIEW = V23_DIR / "memcalib_v23_independent_qc_15000.review.jsonl"
DEFAULT_OUTPUT = V23_DIR / "memcalib_v23_release_candidates_15000.jsonl"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replace original v2.3 rejects with repaired strict/review records."
    )
    parser.add_argument("--order", type=Path, default=DEFAULT_ORDER)
    parser.add_argument("--base-strict", type=Path, default=DEFAULT_STRICT)
    parser.add_argument("--base-review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--repair-strict", type=Path, required=True)
    parser.add_argument("--repair-review", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    order_rows = list(iter_jsonl(args.order))
    order_ids = [str(row.get("id") or "") for row in order_rows]
    if "" in order_ids or len(order_ids) != len(set(order_ids)):
        raise ValueError("release order IDs must be non-empty and unique")

    sources = [
        ("base_strict", args.base_strict),
        ("base_review", args.base_review),
        ("repair_strict", args.repair_strict),
        ("repair_review", args.repair_review),
    ]
    merged: dict[str, dict[str, Any]] = {}
    origins: Counter[str] = Counter()
    input_manifest: list[dict[str, Any]] = []
    for origin, path in sources:
        rows = list(iter_jsonl(path))
        for row in rows:
            record_id = str(row.get("id") or "")
            if not record_id:
                raise ValueError(f"{path} contains an empty record ID")
            if record_id in merged:
                raise ValueError(f"duplicate release candidate {record_id}")
            decision = (row.get("v23_independent_qc") or {}).get("decision")
            expected = "strict_pass" if origin.endswith("strict") else "review"
            if decision != expected:
                raise ValueError(
                    f"{record_id} decision {decision!r} does not match {origin}"
                )
            merged[record_id] = row
            origins[origin] += 1
        input_manifest.append(
            {
                "role": origin,
                "path": portable_path(path),
                "sha256": file_sha256(path),
                "count": len(rows),
            }
        )

    missing = set(order_ids) - set(merged)
    extra = set(merged) - set(order_ids)
    if missing or extra:
        raise ValueError(
            f"release candidate coverage mismatch: missing={len(missing)} extra={len(extra)}"
        )
    output_rows = [merged[record_id] for record_id in order_ids]
    write_jsonl(args.output, output_rows)
    manifest = {
        "schema_version": "memcalib-v23-release-candidate-merge-v1",
        "policy": "original_order_strict_or_review_only_exact_coverage",
        "order": {
            "path": portable_path(args.order),
            "sha256": file_sha256(args.order),
            "count": len(order_rows),
        },
        "inputs": input_manifest,
        "composition": dict(sorted(origins.items())),
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
