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


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def row_id(row: dict[str, Any]) -> str:
    return str(row.get("id") or row.get("record_id") or "")


def index_unique(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        record_id = row_id(row)
        if not record_id or record_id in indexed:
            raise ValueError(f"{label} has invalid or duplicate record id: {record_id}")
        indexed[record_id] = row
    return indexed


def build_candidates(
    benchmark: list[dict[str, Any]],
    repaired: list[dict[str, Any]],
    prior_invalid: list[dict[str, Any]],
    additional: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    benchmark_by_id = index_unique(benchmark, "benchmark")
    repaired_by_id = index_unique(repaired, "repaired")
    invalid_by_id = index_unique(prior_invalid, "prior invalid")
    additional_by_id = index_unique(additional or [], "additional")
    if not set(repaired_by_id) <= set(benchmark_by_id):
        raise ValueError("repaired records are not a subset of the benchmark")
    if not set(invalid_by_id) <= set(benchmark_by_id):
        raise ValueError("prior invalid records are not a subset of the benchmark")
    if set(repaired_by_id) & set(invalid_by_id):
        raise ValueError("repaired and prior-invalid record IDs must be disjoint")
    if set(additional_by_id) & set(benchmark_by_id):
        raise ValueError("additional QC candidates overlap the benchmark")

    candidates = []
    for original in benchmark:
        record_id = str(original.get("id") or "")
        if record_id in repaired_by_id:
            replacement = repaired_by_id[record_id]
            if str(replacement.get("source_id") or "") != str(original.get("source_id") or ""):
                raise ValueError(f"semantic repair changed source_id for {record_id}")
            candidates.append(replacement)
        elif record_id in invalid_by_id:
            candidates.append(original)
    candidates.extend(additional_by_id.values())
    return candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the minimal independent-QC retry benchmark.")
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--repaired", type=Path, required=True)
    parser.add_argument("--prior-invalid", type=Path, required=True)
    parser.add_argument("--additional", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    benchmark = list(iter_jsonl(args.benchmark))
    repaired = list(iter_jsonl(args.repaired))
    prior_invalid = list(iter_jsonl(args.prior_invalid))
    additional = [row for path in args.additional for row in iter_jsonl(path)]
    candidates = build_candidates(benchmark, repaired, prior_invalid, additional)
    write_jsonl(args.output, candidates)
    manifest = {
        "schema_version": "crk2-v2-semantic-qc-candidates-v1",
        "inputs": {
            "benchmark": {
                "path": str(args.benchmark),
                "sha256": file_sha256(args.benchmark),
                "records": len(benchmark),
            },
            "repaired": {"path": str(args.repaired), "sha256": file_sha256(args.repaired), "records": len(repaired)},
            "prior_invalid": {
                "path": str(args.prior_invalid),
                "sha256": file_sha256(args.prior_invalid),
                "records": len(prior_invalid),
            },
            "additional": [
                {"path": str(path), "sha256": file_sha256(path)} for path in args.additional
            ],
        },
        "counts": {
            "candidates": len(candidates),
            "domain": dict(sorted(Counter(str(row.get("domain") or "") for row in candidates).items())),
        },
        "output": {"path": str(args.output), "sha256": file_sha256(args.output)},
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
