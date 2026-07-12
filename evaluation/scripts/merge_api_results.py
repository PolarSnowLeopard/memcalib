#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evaluation.common import iter_jsonl, write_jsonl


def merge_api_rows(groups: list[list[dict[str, Any]]], expected: int) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for group in groups:
        for row in group:
            request_id = str(row.get("request_id") or "")
            if not request_id:
                raise ValueError("API result row is missing request_id")
            if request_id in merged:
                raise ValueError(f"duplicate API result request_id: {request_id}")
            merged[request_id] = row
    if len(merged) != expected:
        raise ValueError(f"API result count mismatch: {len(merged)} != {expected}")
    return [merged[key] for key in sorted(merged)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge disjoint resumable API result files.")
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected", type=int, required=True)
    args = parser.parse_args()
    rows = merge_api_rows([list(iter_jsonl(path)) for path in args.input], args.expected)
    write_jsonl(args.output, rows)
    print(json.dumps({"inputs": [str(path) for path in args.input], "output": str(args.output), "rows": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
