#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from memcalib_v23_common import V23_DIR, file_sha256, portable_path
from utils import iter_jsonl, write_json, write_jsonl


DEFAULT_REQUESTS = V23_DIR / "memcalib_v23_independent_qc_input_15000.jsonl"
DEFAULT_OUTPUT = V23_DIR / "memcalib_v23_independent_qc_retry_input.jsonl"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare targeted retries for failed or structurally invalid v2.3 QC requests."
    )
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--targets", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--append-structural-feedback", action="store_true")
    args = parser.parse_args()

    requests = list(iter_jsonl(args.requests))
    request_ids = [str(row.get("request_id") or "") for row in requests]
    if "" in request_ids or len(request_ids) != len(set(request_ids)):
        raise ValueError("request IDs must be non-empty and unique")

    target_rows = [row for path in args.targets for row in iter_jsonl(path)]
    target_ids = [str(row.get("request_id") or "") for row in target_rows]
    if "" in target_ids or len(target_ids) != len(set(target_ids)):
        raise ValueError("target request IDs must be non-empty and unique")
    target_by_id = dict(zip(target_ids, target_rows, strict=True))
    unknown = set(target_ids) - set(request_ids)
    if unknown:
        raise ValueError(f"retry targets contain {len(unknown)} unknown request IDs")

    selected = [copy.deepcopy(row) for row in requests if row["request_id"] in target_by_id]
    if len(selected) != len(target_rows):
        raise AssertionError("retry selection did not cover every target exactly once")
    feedback_count = 0
    if args.append_structural_feedback:
        for row in selected:
            errors = target_by_id[row["request_id"]].get("errors") or []
            if not errors:
                continue
            prompt = row.get("prompt")
            if not isinstance(prompt, list):
                raise ValueError(f"request {row['request_id']} prompt must be a list")
            prompt.append(
                {
                    "role": "user",
                    "content": (
                        "The previous response was structurally invalid for these reasons: "
                        + "; ".join(str(error) for error in errors)
                        + ". Return a complete corrected JSON object matching the requested schema."
                    ),
                }
            )
            feedback_count += 1
    write_jsonl(args.output, selected)

    manifest = {
        "schema_version": "memcalib-v23-independent-qc-retry-requests-v1",
        "policy": "failed_or_structurally_invalid_only",
        "inputs": {
            "requests": {
                "path": portable_path(args.requests),
                "sha256": file_sha256(args.requests),
                "count": len(requests),
            },
            "targets": [
                {
                    "path": portable_path(path),
                    "sha256": file_sha256(path),
                }
                for path in args.targets
            ],
        },
        "selection": {
            "requests": len(selected),
            "unique_request_ids": len({row["request_id"] for row in selected}),
            "structural_feedback_appended": feedback_count,
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
