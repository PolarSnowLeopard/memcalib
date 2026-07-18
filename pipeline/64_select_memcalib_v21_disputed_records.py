#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
SCHEMA_VERSION = "memcalib-v21-disputed-record-selection-v1"


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
    parser = argparse.ArgumentParser(description="Select disputed v2.1 records by audited record_id.")
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    benchmark = list(iter_jsonl(args.benchmark))
    ids = [str(row.get("id") or "") for row in benchmark]
    if "" in ids or len(ids) != len(set(ids)):
        raise ValueError("benchmark record IDs must be non-empty and unique")
    audit = list(iter_jsonl(args.audit))
    audit_ids = [str(row.get("record_id") or "") for row in audit]
    if "" in audit_ids or len(audit_ids) != len(set(audit_ids)):
        raise ValueError("audit record IDs must be non-empty and unique")
    requested = set(audit_ids)
    missing = requested - set(ids)
    if missing:
        raise ValueError(f"{len(missing)} audited record IDs are missing from benchmark")

    selected = [row for row in benchmark if str(row.get("id") or "") in requested]
    if len(selected) != len(audit):
        raise ValueError("selected record count does not match audit")
    write_jsonl(args.output, selected)

    reasons: Counter[str] = Counter()
    for row in audit:
        for reason in row.get("remaining_non_hard_a_reasons") or row.get("computed_reasons") or []:
            if not str(reason).startswith("hard_a:"):
                reasons[str(reason)] += 1
    manifest_path = args.manifest or args.output.with_suffix(".manifest.json")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "inputs": {
            "benchmark": {
                "path": portable_path(args.benchmark),
                "sha256": file_sha256(args.benchmark),
                "records": len(benchmark),
            },
            "audit": {
                "path": portable_path(args.audit),
                "sha256": file_sha256(args.audit),
                "records": len(audit),
            },
        },
        "counts": {
            "selected": len(selected),
            "unique_record_ids": len({str(row["id"]) for row in selected}),
        },
        "non_hard_a_reasons": dict(sorted(reasons.items())),
        "output": {
            "path": portable_path(args.output),
            "sha256": file_sha256(args.output),
        },
    }
    write_json(manifest_path, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
