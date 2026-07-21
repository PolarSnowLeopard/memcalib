#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from memcalib_v23_common import V23_DIR, file_sha256, portable_path
from utils import iter_jsonl, write_json, write_jsonl


DEFAULT_REQUESTS = V23_DIR / "memcalib_v23_independent_qc_input_15000.jsonl"
DEFAULT_BASE_RESULTS = V23_DIR / "memcalib_v23_independent_qc_result_15000.jsonl"
DEFAULT_OUTPUT = V23_DIR / "memcalib_v23_independent_qc_resolved_result_15000.jsonl"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")


def unique_index(rows: list[dict], source: str) -> dict[str, dict]:
    ids = [str(row.get("request_id") or "") for row in rows]
    if "" in ids or len(ids) != len(set(ids)):
        raise ValueError(f"{source} request IDs must be non-empty and unique")
    return dict(zip(ids, rows, strict=True))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge v2.3 independent QC retries in original request order."
    )
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--base-results", type=Path, default=DEFAULT_BASE_RESULTS)
    parser.add_argument("--retry-results", type=Path, nargs="*", default=[])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    requests = list(iter_jsonl(args.requests))
    request_index = unique_index(requests, "requests")
    expected_ids = set(request_index)
    base_rows = list(iter_jsonl(args.base_results))
    resolved = unique_index(base_rows, "base results")
    unknown_base = set(resolved) - expected_ids
    if unknown_base:
        raise ValueError(f"base results contain {len(unknown_base)} unknown request IDs")

    retry_inputs = []
    overwritten_ids: set[str] = set()
    for path in args.retry_results:
        rows = list(iter_jsonl(path))
        index = unique_index(rows, str(path))
        unknown = set(index) - expected_ids
        if unknown:
            raise ValueError(f"retry results contain {len(unknown)} unknown request IDs")
        resolved.update(index)
        overwritten_ids.update(index)
        retry_inputs.append(
            {
                "path": portable_path(path),
                "sha256": file_sha256(path),
                "count": len(rows),
            }
        )

    missing = expected_ids - set(resolved)
    if missing:
        raise ValueError(f"resolved QC results are still missing {len(missing)} requests")
    output_rows = [resolved[request_id] for request_id in request_index]
    write_jsonl(args.output, output_rows)
    manifest = {
        "schema_version": "memcalib-v23-independent-qc-result-merge-v1",
        "policy": "original_request_order_retry_last",
        "inputs": {
            "requests": {
                "path": portable_path(args.requests),
                "sha256": file_sha256(args.requests),
                "count": len(requests),
            },
            "base_results": {
                "path": portable_path(args.base_results),
                "sha256": file_sha256(args.base_results),
                "count": len(base_rows),
            },
            "retry_results": retry_inputs,
        },
        "merge": {
            "overwritten_request_ids": len(overwritten_ids),
            "output_rows": len(output_rows),
            "unique_request_ids": len({row["request_id"] for row in output_rows}),
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
