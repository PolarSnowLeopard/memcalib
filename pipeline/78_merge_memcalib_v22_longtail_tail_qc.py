#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
V22_DIR = SCRIPT_DIR / "data" / "multidomain" / "full-v2" / "revision-longtail-blocks"
DEFAULT_BASE = (
    V22_DIR / "memcalib_v22_longtail_independent_qc_resolved2_15000.adjudicated.jsonl"
)
DEFAULT_REPAIRED = V22_DIR / "memcalib_v22_longtail_tail_repaired_qc_2.adjudicated.jsonl"
DEFAULT_OUTPUT = V22_DIR / "memcalib_v22_longtail_independent_qc_final_15000.adjudicated.jsonl"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")
MERGE_SCHEMA = "memcalib-v22-longtail-tail-qc-merge-v1"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(SCRIPT_DIR.parent))
    except ValueError:
        return str(resolved)


def index(rows: list[dict[str, Any]], name: str) -> dict[str, dict[str, Any]]:
    indexed = {str(row.get("id") or ""): row for row in rows}
    if "" in indexed or len(indexed) != len(rows):
        raise ValueError(f"{name} record IDs must be non-empty and unique")
    return indexed


def merge_rows(
    base_rows: list[dict[str, Any]], repaired_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    base_by_id = index(base_rows, "base")
    repaired_by_id = index(repaired_rows, "repaired")
    extra = set(repaired_by_id) - set(base_by_id)
    if extra:
        raise ValueError(f"repaired rows contain IDs absent from base: {sorted(extra)}")
    for record_id, row in repaired_by_id.items():
        decision = str(
            (row.get("longtail_independent_qc") or {}).get("computed_decision") or ""
        )
        if decision not in {"strict_pass", "review"}:
            raise ValueError(f"repaired row {record_id} has forbidden QC decision {decision}")
    return [
        repaired_by_id.get(str(row.get("id") or ""), row)
        for row in base_rows
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge independently re-QCed MemCalib v2.2 tail repairs."
    )
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--repaired", type=Path, default=DEFAULT_REPAIRED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    base_rows = list(iter_jsonl(args.base))
    repaired_rows = list(iter_jsonl(args.repaired))
    merged = merge_rows(base_rows, repaired_rows)
    write_jsonl(args.output, merged)
    decision_counts: dict[str, int] = {}
    for row in merged:
        decision = str(
            (row.get("longtail_independent_qc") or {}).get("computed_decision") or ""
        )
        decision_counts[decision] = decision_counts.get(decision, 0) + 1
    manifest = {
        "schema_version": MERGE_SCHEMA,
        "inputs": {
            "base": {
                "path": portable_path(args.base),
                "sha256": file_sha256(args.base),
                "records": len(base_rows),
            },
            "repaired": {
                "path": portable_path(args.repaired),
                "sha256": file_sha256(args.repaired),
                "records": len(repaired_rows),
            },
        },
        "counts": {
            "merged_records": len(merged),
            "unique_record_ids": len({str(row.get("id") or "") for row in merged}),
            "replaced_records": len(repaired_rows),
            "qc_decision": dict(sorted(decision_counts.items())),
        },
        "output": {
            "path": portable_path(args.output),
            "sha256": file_sha256(args.output),
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
