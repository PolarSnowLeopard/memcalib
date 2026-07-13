#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from utils import iter_jsonl, write_json, write_jsonl


SCHEMA_VERSION = "memcalib-source-semantic-qc-resolution-v1"
VALID_STATES = {"strict_pass", "review", "reject"}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record_id(row: dict[str, Any]) -> str:
    source = row.get("source") or {}
    source_params = source.get("user_defined_params") or {}
    return str(row.get("id") or source_params.get("id") or source.get("request_id") or "")


def merge_resolution(
    original_valid: list[dict[str, Any]],
    original_invalid: list[dict[str, Any]],
    retry_valid: list[dict[str, Any]],
    retry_invalid: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    original_valid_ids = {record_id(row) for row in original_valid}
    original_invalid_ids = {record_id(row) for row in original_invalid}
    retry_valid_ids = {record_id(row) for row in retry_valid}
    retry_invalid_ids = {record_id(row) for row in retry_invalid}
    groups = {
        "original_valid": original_valid_ids,
        "original_invalid": original_invalid_ids,
        "retry_valid": retry_valid_ids,
        "retry_invalid": retry_invalid_ids,
    }
    rows_by_name = {
        "original_valid": original_valid,
        "original_invalid": original_invalid,
        "retry_valid": retry_valid,
        "retry_invalid": retry_invalid,
    }
    for name, ids in groups.items():
        rows = rows_by_name[name]
        if "" in ids or len(ids) != len(rows):
            raise ValueError(f"{name} must contain one non-empty unique ID per row")
    if original_valid_ids & original_invalid_ids:
        raise ValueError("original valid and invalid IDs overlap")
    retry_ids = retry_valid_ids | retry_invalid_ids
    if retry_valid_ids & retry_invalid_ids:
        raise ValueError("retry valid and invalid IDs overlap")
    if retry_ids != original_invalid_ids:
        missing = sorted(original_invalid_ids - retry_ids)
        extra = sorted(retry_ids - original_invalid_ids)
        raise ValueError(f"retry IDs do not resolve the original invalid set: missing={missing[:5]} extra={extra[:5]}")
    resolved = original_valid + retry_valid
    for row in resolved:
        state = str((row.get("semantic_qc") or {}).get("state") or "")
        if state not in VALID_STATES:
            raise ValueError(f"resolved row {record_id(row)} has invalid state: {state}")
    return resolved, retry_invalid


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge source semantic-QC results after one targeted retry.")
    parser.add_argument("--original-valid", type=Path, required=True)
    parser.add_argument("--original-invalid", type=Path, required=True)
    parser.add_argument("--retry-valid", type=Path, required=True)
    parser.add_argument("--retry-invalid", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--strict-pass", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--rejected", type=Path, required=True)
    parser.add_argument("--invalid", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    original_valid = list(iter_jsonl(args.original_valid))
    original_invalid = list(iter_jsonl(args.original_invalid))
    retry_valid = list(iter_jsonl(args.retry_valid))
    retry_invalid = list(iter_jsonl(args.retry_invalid))
    resolved, residual_invalid = merge_resolution(original_valid, original_invalid, retry_valid, retry_invalid)
    by_state = {
        state: [row for row in resolved if str((row.get("semantic_qc") or {}).get("state") or "") == state]
        for state in sorted(VALID_STATES)
    }
    write_jsonl(args.output, resolved)
    write_jsonl(args.strict_pass, by_state["strict_pass"])
    write_jsonl(args.review, by_state["review"])
    write_jsonl(args.rejected, by_state["reject"])
    write_jsonl(args.invalid, residual_invalid)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "counts": {
            "original_valid": len(original_valid),
            "original_invalid": len(original_invalid),
            "retry_valid": len(retry_valid),
            "residual_invalid": len(residual_invalid),
            "resolved": len(resolved),
            "strict_pass": len(by_state["strict_pass"]),
            "review": len(by_state["review"]),
            "reject": len(by_state["reject"]),
        },
        "distributions": {
            "domain": dict(sorted(Counter(str(row.get("domain") or "unknown") for row in resolved).items())),
            "topic": dict(sorted(Counter(str(row.get("topic") or "unknown") for row in resolved).items())),
        },
        "inputs": {
            "original_valid": {"path": str(args.original_valid), "sha256": file_sha256(args.original_valid)},
            "original_invalid": {"path": str(args.original_invalid), "sha256": file_sha256(args.original_invalid)},
            "retry_valid": {"path": str(args.retry_valid), "sha256": file_sha256(args.retry_valid)},
            "retry_invalid": {"path": str(args.retry_invalid), "sha256": file_sha256(args.retry_invalid)},
        },
        "output": {"path": str(args.output), "sha256": file_sha256(args.output)},
    }
    write_json(args.summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
