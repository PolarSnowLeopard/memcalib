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
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object")
            yield value


def nonempty_reasoning(row: dict[str, Any]) -> bool:
    choices = (row.get("raw_response") or {}).get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return False
    message = choices[0].get("message") or {}
    reasoning = message.get("reasoning_content") if isinstance(message, dict) else None
    return isinstance(reasoning, str) and bool(reasoning.strip())


def visible_thinking(response: str) -> bool:
    return any(match.group(1).strip() for match in THINK_PATTERN.finditer(response))


def main() -> None:
    parser = argparse.ArgumentParser(description="Reject non-thinking answers with observable reasoning traces.")
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()

    rows = list(iter_jsonl(args.input))
    reasoning_ids = [
        str(row.get("request_id") or "")
        for row in rows
        if nonempty_reasoning(row)
    ]
    visible_ids = [
        str(row.get("request_id") or "")
        for row in rows
        if visible_thinking(str(row.get("response") or ""))
    ]
    report = {
        "input": str(args.input),
        "rows": len(rows),
        "nonempty_reasoning_content": len(reasoning_ids),
        "visible_nonempty_think_blocks": len(visible_ids),
        "valid_nonthinking": not reasoning_ids and not visible_ids,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if reasoning_ids or visible_ids:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
