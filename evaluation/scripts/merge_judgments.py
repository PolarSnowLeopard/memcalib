#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evaluation.common import iter_jsonl, write_jsonl


def merge_judgment_rows(groups: list[list[dict[str, Any]]], *, expected: int) -> list[dict[str, Any]]:
    merged = []
    seen = set()
    for group in groups:
        for row in group:
            answer_id = str(row["answer_request_id"])
            if answer_id in seen:
                raise ValueError(f"duplicate judgment for answer_request_id: {answer_id}")
            seen.add(answer_id)
            merged.append(row)
    if len(merged) != expected:
        raise ValueError(f"judgment count mismatch: {len(merged)} != {expected}")
    return sorted(merged, key=lambda row: str(row["answer_request_id"]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge validated MemCalib judgment JSONL files.")
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected", type=int, required=True)
    args = parser.parse_args()
    groups = [list(iter_jsonl(path)) for path in args.input]
    merged = merge_judgment_rows(groups, expected=args.expected)
    write_jsonl(args.output, merged)
    print(json.dumps({"inputs": [str(path) for path in args.input], "output": str(args.output), "rows": len(merged)}, indent=2))


if __name__ == "__main__":
    main()
