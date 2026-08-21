#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterator


THINK_PATTERN = re.compile(r"<think>(.*?)</think>", re.IGNORECASE | re.DOTALL)


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object")
            yield record


def response_message(record: dict[str, Any]) -> dict[str, Any]:
    response = record.get("raw_response")
    if not isinstance(response, dict):
        return {}
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return {}
    first = choices[0]
    if not isinstance(first, dict):
        return {}
    message = first.get("message")
    return message if isinstance(message, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail if a supposedly Non-Think answer contains a reasoning trace."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    rows = 0
    nonempty_reasoning = 0
    visible_thinking = 0
    reasoning_request_ids: list[str] = []
    visible_request_ids: list[str] = []

    for record in iter_jsonl(args.input):
        rows += 1
        request_id = str(record.get("request_id", ""))
        message = response_message(record)
        if any(str(message.get(field) or "").strip() for field in ("reasoning_content", "reasoning")):
            nonempty_reasoning += 1
            reasoning_request_ids.append(request_id)
        content = str(message.get("content", ""))
        if any(match.strip() for match in THINK_PATTERN.findall(content)):
            visible_thinking += 1
            visible_request_ids.append(request_id)

    report = {
        "input": str(args.input),
        "rows": rows,
        "nonempty_reasoning_content": nonempty_reasoning,
        "visible_nonempty_think_blocks": visible_thinking,
        "reasoning_request_ids": reasoning_request_ids,
        "visible_think_request_ids": visible_request_ids,
        "valid_nonthinking": nonempty_reasoning == 0 and visible_thinking == 0,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if not report["valid_nonthinking"]:
        print(json.dumps(report, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
