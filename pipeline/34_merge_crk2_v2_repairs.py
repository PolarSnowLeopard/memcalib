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
DEFAULT_REQUESTS = SCRIPT_DIR / "data" / "crk2_v2_generation_input_100.jsonl"
DEFAULT_PRIMARY = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_100.jsonl"
DEFAULT_REPAIR = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_repair1.jsonl"
DEFAULT_OUTPUT = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_100.resolved.jsonl"
DEFAULT_MANIFEST = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_100.resolved.manifest.json"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def index_records(paths: list[Path]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for path in paths:
        for record in iter_jsonl(path):
            source_id = str(record.get("source_id") or "")
            if not source_id:
                raise ValueError(f"record in {path} has no source_id")
            if source_id in indexed:
                raise ValueError(f"duplicate resolved source_id: {source_id}")
            indexed[source_id] = record
    return indexed


def expected_order(requests_path: Path) -> list[str]:
    result: list[str] = []
    for request in iter_jsonl(requests_path):
        params = request.get("user_defined_params") or {}
        source_id = str(params.get("id") or params.get("source_raw_id") or "")
        if not source_id:
            raise ValueError("construction request has no source id")
        result.append(source_id)
    if len(result) != len(set(result)):
        raise ValueError("construction request source IDs are not unique")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge deterministic-pass CRK-2 v2 primary and repair records.")
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--primary", type=Path, default=DEFAULT_PRIMARY)
    parser.add_argument("--repair", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    repair_paths = args.repair or [DEFAULT_REPAIR]

    order = expected_order(args.requests)
    indexed = index_records([args.primary, *repair_paths])
    missing = sorted(set(order) - set(indexed))
    unexpected = sorted(set(indexed) - set(order))
    if missing or unexpected:
        raise ValueError(f"resolved coverage mismatch: missing={missing}, unexpected={unexpected}")
    resolved = [indexed[source_id] for source_id in order]
    write_jsonl(args.output, resolved)

    manifest = {
        "schema_version": "crk2-v2-resolved-benchmark-v1",
        "requests": {"path": str(args.requests), "sha256": file_sha256(args.requests), "records": len(order)},
        "primary": {"path": str(args.primary), "sha256": file_sha256(args.primary)},
        "repairs": [{"path": str(path), "sha256": file_sha256(path)} for path in repair_paths],
        "counts": {
            "resolved": len(resolved),
            "source_dataset": dict(sorted(Counter(str(row.get("source_dataset") or "") for row in resolved).items())),
        },
        "output": {"path": str(args.output), "sha256": file_sha256(args.output)},
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
