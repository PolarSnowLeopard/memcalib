#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evaluation.common import iter_jsonl, request_fingerprint, write_jsonl


def output_is_complete(row: dict[str, Any], expected_fingerprint: str) -> bool:
    choices = (row.get("raw_response") or {}).get("choices") or []
    finish_reason = str(choices[0].get("finish_reason") or "") if choices else ""
    return (
        row.get("input_fingerprint") == expected_fingerprint
        and isinstance(row.get("response"), str)
        and bool(row["response"].strip())
        and finish_reason != "length"
        and not row.get("error")
    )


def missing_requests(input_path: Path, result_path: Path | list[Path]) -> list[dict[str, Any]]:
    requests = list(iter_jsonl(input_path))
    expected = {str(row["request_id"]): request_fingerprint(row) for row in requests}
    result_paths = result_path if isinstance(result_path, list) else [result_path]
    done = {
        str(row.get("request_id") or "")
        for path in result_paths
        if path.exists()
        for row in iter_jsonl(path)
        if str(row.get("request_id") or "") in expected
        and output_is_complete(row, expected[str(row["request_id"])])
    }
    return [row for row in requests if str(row["request_id"]) not in done]


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare only missing or truncated resumable API requests.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--result", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = missing_requests(args.input, args.result)
    write_jsonl(args.output, rows)
    print(json.dumps({"input": str(args.input), "results": [str(path) for path in args.result], "missing": len(rows), "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
