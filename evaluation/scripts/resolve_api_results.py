#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation.common import iter_jsonl, request_fingerprint, write_json, write_jsonl


def finish_reason(row: dict[str, Any]) -> str:
    choices = (row.get("raw_response") or {}).get("choices") or []
    if choices and isinstance(choices[0], dict):
        return str(choices[0].get("finish_reason") or "")
    return ""


def complete_result(row: dict[str, Any], request: dict[str, Any], expected_model: str) -> bool:
    returned_model = str((row.get("raw_response") or {}).get("model") or "")
    return (
        row.get("input_fingerprint") == request_fingerprint(request)
        and isinstance(row.get("response"), str)
        and bool(row["response"].strip())
        and finish_reason(row) != "length"
        and not row.get("error")
        and (not returned_model or returned_model == expected_model)
    )


def resolve_rows(
    requests: list[dict[str, Any]],
    result_groups: list[list[dict[str, Any]]],
    *,
    expected_model: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    request_by_id = {str(row["request_id"]): row for row in requests}
    if len(request_by_id) != len(requests):
        raise ValueError("request IDs must be unique")
    resolved: dict[str, dict[str, Any]] = {}
    selected_group: dict[str, int] = {}
    invalid_reasons: Counter[str] = Counter()
    unexpected = 0
    for group_index, group in enumerate(result_groups):
        for row in group:
            request_id = str(row.get("request_id") or "")
            request = request_by_id.get(request_id)
            if request is None:
                unexpected += 1
                continue
            if complete_result(row, request, expected_model):
                resolved[request_id] = row
                selected_group[request_id] = group_index
            else:
                if row.get("input_fingerprint") != request_fingerprint(request):
                    invalid_reasons["fingerprint"] += 1
                elif finish_reason(row) == "length":
                    invalid_reasons["truncated"] += 1
                elif row.get("error"):
                    invalid_reasons["error"] += 1
                elif not isinstance(row.get("response"), str) or not str(row.get("response") or "").strip():
                    invalid_reasons["empty"] += 1
                else:
                    invalid_reasons["model_mismatch"] += 1
    missing = [request_id for request_id in request_by_id if request_id not in resolved]
    if unexpected or missing:
        raise ValueError(f"API resolution incomplete: unexpected={unexpected}, missing={len(missing)}")
    ordered = [resolved[str(request["request_id"])] for request in requests]
    group_counts = Counter(selected_group.values())
    return ordered, {
        "requests": len(requests),
        "resolved": len(ordered),
        "selected_result_group_counts": {str(key): group_counts[key] for key in sorted(group_counts)},
        "discarded_invalid_counts": dict(sorted(invalid_reasons.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve resumable API results by replacing incomplete rows with valid retries.")
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--result", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    requests = list(iter_jsonl(args.requests))
    groups = [list(iter_jsonl(path)) if path.exists() else [] for path in args.result]
    rows, summary = resolve_rows(requests, groups, expected_model=args.model)
    write_jsonl(args.output, rows)
    if args.report:
        write_json(args.report, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
