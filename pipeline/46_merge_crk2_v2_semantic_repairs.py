#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_BASE = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_deterministic_pass.jsonl"
DEFAULT_TARGETS = SCRIPT_DIR / "data" / "crk2_v2_independent_qc.reject.jsonl"
DEFAULT_OUTPUT = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_semantic_repaired.jsonl"
DEFAULT_UNRESOLVED = SCRIPT_DIR / "data" / "crk2_v2_semantic_repair_unresolved.jsonl"
DEFAULT_MANIFEST = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_semantic_repaired.manifest.json"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def index_unique(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        record_id = str(row.get("id") or "")
        if not record_id or record_id in indexed:
            raise ValueError(f"{label} has invalid or duplicate record id: {record_id}")
        indexed[record_id] = row
    return indexed


def merge_semantic_repairs(
    base: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    repaired: list[dict[str, Any]],
    additional: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base_by_id = index_unique(base, "base")
    target_by_id = index_unique(targets, "targets")
    repaired_by_id = index_unique(repaired, "repaired")
    additional_by_id = index_unique(additional or [], "additional")
    if not set(target_by_id) <= set(base_by_id):
        raise ValueError("semantic repair targets are not a subset of the base benchmark")
    if not set(repaired_by_id) <= set(target_by_id):
        raise ValueError("semantic repair output contains non-target records")
    if set(additional_by_id) & set(base_by_id):
        raise ValueError("additional records overlap the base benchmark")

    merged = []
    unresolved = []
    for original in base:
        record_id = str(original.get("id") or "")
        if record_id not in target_by_id:
            merged.append(original)
            continue
        replacement = repaired_by_id.get(record_id)
        if replacement is not None:
            if str(replacement.get("source_id") or "") != str(original.get("source_id") or ""):
                raise ValueError(f"semantic repair changed source_id for {record_id}")
            merged.append(replacement)
            continue
        merged.append(original)
        qc = target_by_id[record_id].get("independent_qc") or {}
        unresolved.append(
            {
                "record_id": record_id,
                "source_id": original.get("source_id"),
                "domain": original.get("domain"),
                "source_dataset": original.get("source_dataset"),
                "reason": "semantic_repair_not_deterministic_pass",
                "prior_independent_qc_decision_reasons": qc.get("decision_reasons") or [],
            }
        )
    merged.extend(additional_by_id.values())
    return merged, unresolved


def main() -> None:
    parser = argparse.ArgumentParser(description="Replace independent-QC rejects with deterministic-pass repairs.")
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--repair", type=Path, action="append", required=True)
    parser.add_argument("--additional", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--unresolved", type=Path, default=DEFAULT_UNRESOLVED)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    base = list(iter_jsonl(args.base))
    targets = list(iter_jsonl(args.targets))
    repaired = [row for path in args.repair for row in iter_jsonl(path)]
    additional = [row for path in args.additional for row in iter_jsonl(path)]
    merged, unresolved = merge_semantic_repairs(base, targets, repaired, additional)
    write_jsonl(args.output, merged)
    write_jsonl(args.unresolved, unresolved)
    manifest = {
        "schema_version": "crk2-v2-semantic-repair-merge-v1",
        "inputs": {
            "base": {"path": str(args.base), "sha256": file_sha256(args.base), "records": len(base)},
            "targets": {"path": str(args.targets), "sha256": file_sha256(args.targets), "records": len(targets)},
            "repairs": [
                {"path": str(path), "sha256": file_sha256(path)} for path in args.repair
            ],
            "additional": [
                {"path": str(path), "sha256": file_sha256(path)} for path in args.additional
            ],
        },
        "counts": {
            "merged": len(merged),
            "unchanged": len(base) - len(targets),
            "replaced": len(repaired),
            "unresolved": len(unresolved),
            "additional": len(additional),
            "domain": dict(sorted(Counter(str(row.get("domain") or "") for row in merged).items())),
        },
        "outputs": {
            "benchmark": {"path": str(args.output), "sha256": file_sha256(args.output)},
            "unresolved": {"path": str(args.unresolved), "sha256": file_sha256(args.unresolved)},
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
