#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any

from memcalib_v23_common import V23_DIR, file_sha256, portable_path
from utils import iter_jsonl, write_json, write_jsonl


DEFAULT_REQUESTS = V23_DIR / "memcalib_v23_surface_rewrite_input_15000.jsonl"
DEFAULT_REJECTED = V23_DIR / "memcalib_v23_surface_rewrite_rejected_15000.jsonl"
DEFAULT_OUTPUT = V23_DIR / "memcalib_v23_surface_rewrite_retry1_input.jsonl"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")


def error_family(error: Any) -> str:
    return str(error).split(":", 1)[0]


def add_retry_feedback(request: dict, errors: list[Any]) -> dict:
    amended = copy.deepcopy(request)
    prompt = amended.get("prompt")
    if not isinstance(prompt, list):
        raise ValueError(f"request {request.get('request_id')} prompt must be a list")
    error_text = "; ".join(str(error) for error in errors)
    prompt.append(
        {
            "role": "user",
            "content": (
                "The previous response failed deterministic validation for these exact reasons: "
                f"{error_text}. Redo the complete JSON response from scratch. Preserve every "
                "critical token named after a colon verbatim in the corresponding block, keep "
                "the exact record_id, and do not shorten or omit any proposition."
            ),
        }
    )
    return amended


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Select only deterministically rejected MemCalib v2.3 rewrite requests."
    )
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--rejected", type=Path, default=DEFAULT_REJECTED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--append-feedback",
        action="store_true",
        help="Append prior deterministic failure reasons to each selected request.",
    )
    args = parser.parse_args()

    requests = list(iter_jsonl(args.requests))
    rejected = list(iter_jsonl(args.rejected))
    request_ids = [str(row.get("request_id") or "") for row in requests]
    rejected_ids = [str(row.get("request_id") or "") for row in rejected]
    if "" in request_ids or len(request_ids) != len(set(request_ids)):
        raise ValueError("source request IDs must be non-empty and unique")
    if "" in rejected_ids or len(rejected_ids) != len(set(rejected_ids)):
        raise ValueError("rejected request IDs must be non-empty and unique")
    unknown = set(rejected_ids) - set(request_ids)
    if unknown:
        raise ValueError(f"rejected audit contains {len(unknown)} unknown request IDs")

    rejected_set = set(rejected_ids)
    rejected_by_id = {
        str(row["request_id"]): list(row.get("errors") or []) for row in rejected
    }
    selected = [row for row in requests if row["request_id"] in rejected_set]
    if len(selected) != len(rejected):
        raise AssertionError("retry selection did not cover every rejected request exactly once")
    if args.append_feedback:
        selected = [
            add_retry_feedback(row, rejected_by_id[str(row["request_id"])])
            for row in selected
        ]
    write_jsonl(args.output, selected)

    errors = Counter(
        error_family(error)
        for row in rejected
        for error in row.get("errors") or []
    )
    manifest = {
        "schema_version": "memcalib-v23-surface-rewrite-retry-requests-v1",
        "inputs": {
            "requests": {
                "path": portable_path(args.requests),
                "sha256": file_sha256(args.requests),
                "count": len(requests),
            },
            "rejected": {
                "path": portable_path(args.rejected),
                "sha256": file_sha256(args.rejected),
                "count": len(rejected),
            },
        },
        "selection": {
            "policy": "deterministic_reject_only",
            "prior_failure_feedback_appended": args.append_feedback,
            "requests": len(selected),
            "unique_request_ids": len({row["request_id"] for row in selected}),
            "error_families": dict(sorted(errors.items())),
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
