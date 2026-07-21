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


DEFAULT_REQUESTS = V23_DIR / "memcalib_v23_semantic_repair_input.jsonl"
DEFAULT_REJECTED = V23_DIR / "memcalib_v23_semantic_repair_expansion_rejected.jsonl"
DEFAULT_OUTPUT = V23_DIR / "memcalib_v23_semantic_repair_retry1_input.jsonl"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare exact deterministic retries for v2.3 expansion outputs."
    )
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--rejected", type=Path, default=DEFAULT_REJECTED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    requests = list(iter_jsonl(args.requests))
    rejected = list(iter_jsonl(args.rejected))
    request_index = {str(row.get("request_id") or ""): row for row in requests}
    if "" in request_index or len(request_index) != len(requests):
        raise ValueError("source request IDs must be non-empty and unique")
    target_ids = [str(row.get("request_id") or "") for row in rejected]
    if "" in target_ids or len(target_ids) != len(set(target_ids)):
        raise ValueError("rejected request IDs must be non-empty and unique")
    unknown = set(target_ids) - set(request_index)
    if unknown:
        raise ValueError(f"rejected rows contain {len(unknown)} unknown request IDs")

    rejected_by_id = {str(row["request_id"]): row for row in rejected}
    selected: list[dict[str, Any]] = []
    for request in requests:
        request_id = str(request["request_id"])
        if request_id not in rejected_by_id:
            continue
        amended = copy.deepcopy(request)
        errors = [str(value) for value in rejected_by_id[request_id].get("errors") or []]
        amended["prompt"].append(
            {
                "role": "user",
                "content": (
                    "The previous response failed deterministic validation for these exact "
                    f"reasons: {'; '.join(errors)}. Return the complete JSON object again. "
                    "Copy record_id exactly and include every planned block and atom_id exactly "
                    "once in the requested order. Do not omit, rename, merge, or duplicate an "
                    "atom, and continue to satisfy every semantic requirement in the original "
                    "request."
                ),
            }
        )
        selected.append(amended)
    if len(selected) != len(rejected):
        raise AssertionError("retry selection did not exactly cover rejected rows")
    write_jsonl(args.output, selected)

    errors = Counter(
        str(error).split(":", 1)[0]
        for row in rejected
        for error in row.get("errors") or []
    )
    manifest = {
        "schema_version": "memcalib-v23-expansion-retry-requests-v1",
        "policy": "deterministic_reject_only_with_exact_failure_feedback",
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
