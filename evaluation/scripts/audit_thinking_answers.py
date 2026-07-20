#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation.common import iter_jsonl, write_json


CONDITIONS = ("full_memory", "no_memory")


def quantile(values: list[int], fraction: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reasoning_chars: list[int] = []
    reasoning_tokens: list[int] = []
    content_chars: list[int] = []
    missing_reasoning: list[str] = []
    finish_reasons: Counter[str] = Counter()
    credential_roles: Counter[str] = Counter()
    for row in rows:
        raw = row.get("raw_response") or {}
        choice = (raw.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        reasoning = message.get("reasoning_content") or ""
        content = message.get("content") or ""
        details = (raw.get("usage") or {}).get("completion_tokens_details") or {}
        if not reasoning.strip():
            missing_reasoning.append(str(row.get("request_id") or ""))
        reasoning_chars.append(len(reasoning))
        content_chars.append(len(content))
        if details.get("reasoning_tokens") is not None:
            reasoning_tokens.append(int(details["reasoning_tokens"]))
        finish_reasons[str(choice.get("finish_reason") or "unknown")] += 1
        credential_roles[str(row.get("credential_role") or "unknown")] += 1
    return {
        "rows": len(rows),
        "missing_reasoning": len(missing_reasoning),
        "missing_reasoning_request_ids": missing_reasoning,
        "finish_reasons": dict(sorted(finish_reasons.items())),
        "credential_roles": dict(sorted(credential_roles.items())),
        "reasoning_chars": {
            "min": min(reasoning_chars, default=0),
            "p50": quantile(reasoning_chars, 0.5),
            "p90": quantile(reasoning_chars, 0.9),
            "max": max(reasoning_chars, default=0),
        },
        "reasoning_tokens": {
            "reported_rows": len(reasoning_tokens),
            "sum": sum(reasoning_tokens),
            "min": min(reasoning_tokens, default=0),
            "p50": quantile(reasoning_tokens, 0.5),
            "p90": quantile(reasoning_tokens, 0.9),
            "max": max(reasoning_tokens, default=0),
        },
        "content_chars": {
            "min": min(content_chars, default=0),
            "p50": quantile(content_chars, 0.5),
            "p90": quantile(content_chars, 0.9),
            "max": max(content_chars, default=0),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit that a formal answer run actually used thinking mode.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--conditions", nargs="+", choices=CONDITIONS, default=list(CONDITIONS))
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    expected = int(config["sample_count"])
    cells: dict[str, Any] = {}
    errors: list[str] = []
    all_ids: list[str] = []
    for model in config["answer_models"]:
        key = str(model["key"])
        for condition in args.conditions:
            path = args.results / key / f"{condition}.jsonl"
            rows = list(iter_jsonl(path))
            cell = summarize(rows)
            cells[f"{key}:{condition}"] = cell
            all_ids.extend(str(row.get("request_id") or "") for row in rows)
            if len(rows) != expected:
                errors.append(f"{key}:{condition}: expected {expected} rows, found {len(rows)}")
            if cell["missing_reasoning"]:
                errors.append(f"{key}:{condition}: {cell['missing_reasoning']} rows have no reasoning_content")
            if cell["finish_reasons"] != {"stop": expected}:
                errors.append(f"{key}:{condition}: non-stop finish reasons {cell['finish_reasons']}")
    expected_total = expected * len(config["answer_models"]) * len(args.conditions)
    if len(all_ids) != expected_total or len(set(all_ids)) != expected_total:
        errors.append(
            f"expected {expected_total} globally unique request IDs, found {len(all_ids)} rows and {len(set(all_ids))} unique"
        )
    report = {
        "schema_version": "memcalib-thinking-answer-audit-v1",
        "status": "valid" if not errors else "invalid",
        "expected_answers": expected_total,
        "models": config["answer_models"],
        "conditions": args.conditions,
        "generation": config["answer_generation"],
        "errors": errors,
        "cells": dict(sorted(cells.items())),
    }
    write_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
