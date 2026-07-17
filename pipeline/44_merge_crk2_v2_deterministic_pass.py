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
DEFAULT_REQUESTS = SCRIPT_DIR / "data" / "crk2_v2_generation_input_18000.jsonl"
DEFAULT_OUTPUT = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_deterministic_pass.jsonl"
DEFAULT_EXCLUDED = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_deterministic_excluded.jsonl"
DEFAULT_MANIFEST = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_deterministic_pass.manifest.json"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def merge_in_request_order(
    requests: list[dict[str, Any]], pass_records: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    request_by_source: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for request in requests:
        params = request.get("user_defined_params") or {}
        source_id = str(params.get("id") or params.get("source_raw_id") or "")
        if not source_id or source_id in request_by_source:
            raise ValueError(f"invalid or duplicate request source_id: {source_id}")
        request_by_source[source_id] = request
        order.append(source_id)

    indexed: dict[str, dict[str, Any]] = {}
    for record in pass_records:
        source_id = str(record.get("source_id") or "")
        if not source_id or source_id in indexed:
            raise ValueError(f"invalid or duplicate pass source_id: {source_id}")
        indexed[source_id] = record
    unexpected = sorted(set(indexed) - set(request_by_source))
    if unexpected:
        raise ValueError(f"pass records not present in requests: {unexpected}")

    resolved = [indexed[source_id] for source_id in order if source_id in indexed]
    excluded = []
    for source_id in order:
        if source_id in indexed:
            continue
        params = request_by_source[source_id].get("user_defined_params") or {}
        excluded.append(
            {
                "source_id": source_id,
                "request_id": request_by_source[source_id].get("request_id"),
                "domain": params.get("domain"),
                "source_dataset": params.get("source_dataset"),
                "exclusion_reason": "deterministic_reject",
            }
        )
    return resolved, excluded


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge all deterministic-pass CRK-2 v2 construction records.")
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--pass-file", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--excluded", type=Path, default=DEFAULT_EXCLUDED)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    requests = list(iter_jsonl(args.requests))
    pass_records = [row for path in args.pass_file for row in iter_jsonl(path)]
    resolved, excluded = merge_in_request_order(requests, pass_records)
    write_jsonl(args.output, resolved)
    write_jsonl(args.excluded, excluded)
    manifest = {
        "schema_version": "crk2-v2-deterministic-pass-merge-v1",
        "requests": {"path": str(args.requests), "sha256": file_sha256(args.requests), "records": len(requests)},
        "pass_inputs": [
            {"path": str(path), "sha256": file_sha256(path)} for path in args.pass_file
        ],
        "counts": {
            "deterministic_pass": len(resolved),
            "deterministic_excluded": len(excluded),
            "domain": dict(sorted(Counter(str(row.get("domain") or "") for row in resolved).items())),
            "source_dataset": dict(
                sorted(Counter(str(row.get("source_dataset") or "") for row in resolved).items())
            ),
        },
        "outputs": {
            "benchmark": {"path": str(args.output), "sha256": file_sha256(args.output)},
            "excluded": {"path": str(args.excluded), "sha256": file_sha256(args.excluded)},
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
