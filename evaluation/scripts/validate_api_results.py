#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation.common import iter_jsonl, request_fingerprint, write_json


def _finish_reason(row: dict[str, Any]) -> str:
    choices = (row.get("raw_response") or {}).get("choices") or []
    if choices and isinstance(choices[0], dict):
        return str(choices[0].get("finish_reason") or "")
    return ""


def validate_results(input_path: Path, output_path: Path, expected_model: str) -> dict[str, Any]:
    inputs = list(iter_jsonl(input_path))
    outputs = list(iter_jsonl(output_path)) if output_path.exists() else []
    expected = {str(row["request_id"]): row for row in inputs}
    if len(expected) != len(inputs):
        raise ValueError("input request IDs are not unique")
    id_counts = Counter(str(row.get("request_id") or "") for row in outputs)
    errors: Counter[str] = Counter()
    valid_ids = set()
    for request_id, count in id_counts.items():
        if count > 1:
            errors["duplicate_ids"] += count - 1
    for row in outputs:
        request_id = str(row.get("request_id") or "")
        source = expected.get(request_id)
        if source is None:
            errors["unexpected_request_id"] += 1
            continue
        row_valid = id_counts[request_id] == 1
        if row.get("input_fingerprint") != request_fingerprint(source):
            errors["input_fingerprint_mismatch"] += 1
            row_valid = False
        if not isinstance(row.get("response"), str) or not row["response"].strip():
            errors["empty_response"] += 1
            row_valid = False
        if _finish_reason(row) == "length":
            errors["finish_reason_length"] += 1
            row_valid = False
        response_model = str((row.get("raw_response") or {}).get("model") or "")
        if response_model and response_model != expected_model:
            errors["model_mismatch"] += 1
            row_valid = False
        if row.get("error"):
            errors["error_field_present"] += 1
            row_valid = False
        if row_valid:
            valid_ids.add(request_id)
    missing = set(expected).difference(id_counts)
    if missing:
        errors["missing_request_ids"] += len(missing)
    counts = {
        "expected": len(inputs),
        "output_rows": len(outputs),
        "unique_output_ids": len(id_counts),
        "duplicate_ids": sum(max(count - 1, 0) for count in id_counts.values()),
        "valid": len(valid_ids),
        "missing": len(missing),
    }
    return {
        "valid": not errors and len(valid_ids) == len(inputs),
        "input": str(input_path),
        "output": str(output_path),
        "expected_model": expected_model,
        "counts": counts,
        "errors": dict(sorted(errors.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate resumable Bailian API result JSONL.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = validate_results(args.input, args.output, args.model)
    if args.report:
        write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["valid"] else 1)


if __name__ == "__main__":
    main()
