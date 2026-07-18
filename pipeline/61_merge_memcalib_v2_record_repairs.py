#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
SCHEMA_VERSION = "memcalib-record-repair-overlay-v1"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(SCRIPT_DIR.parent))
    except ValueError:
        return str(resolved)


def main() -> None:
    parser = argparse.ArgumentParser(description="Overlay repaired MemCalib records while preserving base order.")
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--repair", type=Path, action="append", required=True)
    parser.add_argument("--expected-ids-from", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    base = list(iter_jsonl(args.base))
    base_ids = [str(row.get("id") or "") for row in base]
    if "" in base_ids or len(base_ids) != len(set(base_ids)):
        raise ValueError("base record IDs must be non-empty and unique")
    order = list(base_ids)
    resolved = {str(row["id"]): row for row in base}
    repair_inputs = []
    overlaid_ids: set[str] = set()
    appended_ids: set[str] = set()
    for path in args.repair:
        rows = list(iter_jsonl(path))
        ids = [str(row.get("id") or "") for row in rows]
        if "" in ids or len(ids) != len(set(ids)):
            raise ValueError(f"repair record IDs must be non-empty and unique: {path}")
        duplicate_overlays = overlaid_ids & set(ids)
        if duplicate_overlays:
            raise ValueError(f"records repaired more than once in the same merge: {len(duplicate_overlays)}")
        for row, record_id in zip(rows, ids):
            if record_id in resolved:
                overlaid_ids.add(record_id)
            else:
                order.append(record_id)
                appended_ids.add(record_id)
            resolved[record_id] = row
        repair_inputs.append(
            {"path": portable_path(path), "sha256": file_sha256(path), "records": len(rows)}
        )

    expected_ids: set[str] | None = None
    if args.expected_ids_from:
        expected_rows = list(iter_jsonl(args.expected_ids_from))
        expected_list = [str(row.get("id") or "") for row in expected_rows]
        if "" in expected_list or len(expected_list) != len(set(expected_list)):
            raise ValueError("expected record IDs must be non-empty and unique")
        expected_ids = set(expected_list)
        missing = expected_ids - set(resolved)
        extra = set(resolved) - expected_ids
        if missing or extra:
            raise ValueError(f"resolved coverage mismatch: missing={len(missing)} extra={len(extra)}")
        order = expected_list

    output = [resolved[record_id] for record_id in order]
    write_jsonl(args.output, output)
    manifest_path = args.manifest or args.output.with_suffix(".manifest.json")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "inputs": {
            "base": {
                "path": portable_path(args.base),
                "sha256": file_sha256(args.base),
                "records": len(base),
            },
            "repair": repair_inputs,
            "expected_ids_from": (
                {
                    "path": portable_path(args.expected_ids_from),
                    "sha256": file_sha256(args.expected_ids_from),
                    "records": len(expected_ids or set()),
                }
                if args.expected_ids_from
                else None
            ),
        },
        "counts": {
            "overlaid": len(overlaid_ids),
            "appended": len(appended_ids),
            "output": len(output),
            "unique_record_ids": len(resolved),
        },
        "output": {"path": portable_path(args.output), "sha256": file_sha256(args.output)},
    }
    write_json(manifest_path, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
