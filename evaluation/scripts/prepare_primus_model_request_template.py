#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON at {path}:{line_number}: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"expected object at {path}:{line_number}")
            rows.append(row)
    return rows


def convert_rows(
    rows: list[dict[str, Any]],
    *,
    source_key: str,
    target_key: str,
    target_model: str,
) -> list[dict[str, Any]]:
    source_prefix = f"answer:{source_key}:"
    target_prefix = f"answer:{target_key}:"
    converted: list[dict[str, Any]] = []
    request_ids: set[str] = set()
    sample_ids: set[str] = set()

    for index, source_row in enumerate(rows, start=1):
        row = json.loads(json.dumps(source_row, ensure_ascii=False))
        request_id = row.get("request_id")
        if not isinstance(request_id, str) or not request_id.startswith(source_prefix):
            raise ValueError(f"row {index} has unexpected request_id: {request_id!r}")
        row["request_id"] = target_prefix + request_id[len(source_prefix) :]

        params = row.get("user_defined_params")
        if not isinstance(params, dict):
            raise ValueError(f"row {index} has no user_defined_params object")
        sample_id = params.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id:
            raise ValueError(f"row {index} has invalid sample_id")
        params["expected_model"] = target_model
        params["model_key"] = target_key

        if row["request_id"] in request_ids:
            raise ValueError(f"duplicate request_id: {row['request_id']}")
        if sample_id in sample_ids:
            raise ValueError(f"duplicate sample_id: {sample_id}")
        request_ids.add(row["request_id"])
        sample_ids.add(sample_id)
        converted.append(row)

    return converted


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clone a locked Primus request template under a distinct model identity."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-key", required=True)
    parser.add_argument("--target-key", required=True)
    parser.add_argument("--target-model", required=True)
    parser.add_argument("--expected-count", type=int)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    source_rows = load_rows(args.input)
    if args.expected_count is not None and len(source_rows) != args.expected_count:
        raise ValueError(
            f"expected {args.expected_count} source rows, found {len(source_rows)}"
        )
    converted = convert_rows(
        source_rows,
        source_key=args.source_key,
        target_key=args.target_key,
        target_model=args.target_model,
    )

    for source, target in zip(source_rows, converted, strict=True):
        if source.get("prompt") != target.get("prompt"):
            raise ValueError("prompt changed during model-identity conversion")

    write_jsonl(args.output, converted)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(
            {
                "input": str(args.input),
                "input_sha256": sha256_file(args.input),
                "output": str(args.output),
                "output_sha256": sha256_file(args.output),
                "rows": len(converted),
                "source_key": args.source_key,
                "target_key": args.target_key,
                "target_model": args.target_model,
                "prompts_unchanged": True,
                "unique_request_ids": len({row["request_id"] for row in converted}),
                "unique_sample_ids": len(
                    {row["user_defined_params"]["sample_id"] for row in converted}
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
