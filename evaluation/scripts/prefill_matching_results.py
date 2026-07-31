#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evaluation.common import iter_jsonl, request_fingerprint, write_json, write_jsonl


def finish_reason(row: dict[str, Any]) -> str:
    choices = (row.get("raw_response") or {}).get("choices") or []
    if choices and isinstance(choices[0], dict):
        return str(choices[0].get("finish_reason") or "")
    return ""


def reusable(
    row: dict[str, Any],
    request: dict[str, Any],
    expected_model: str,
) -> bool:
    returned_model = str((row.get("raw_response") or {}).get("model") or "")
    return (
        row.get("input_fingerprint") == request_fingerprint(request)
        and isinstance(row.get("response"), str)
        and bool(str(row.get("response") or "").strip())
        and finish_reason(row) == "stop"
        and not row.get("error")
        and (not returned_model or returned_model == expected_model)
    )


def select_matching(
    requests: list[dict[str, Any]],
    prior_results: list[dict[str, Any]],
    *,
    expected_model: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prior = {
        str(row.get("request_id") or ""): row for row in prior_results
    }
    if "" in prior or len(prior) != len(prior_results):
        raise ValueError("prior result request IDs must be non-empty and unique")
    selected: list[dict[str, Any]] = []
    mismatch = 0
    missing = 0
    for request in requests:
        request_id = str(request.get("request_id") or "")
        row = prior.get(request_id)
        if row is None:
            missing += 1
        elif reusable(row, request, expected_model):
            selected.append(row)
        else:
            mismatch += 1
    return selected, {
        "requests": len(requests),
        "prior_results": len(prior_results),
        "reused": len(selected),
        "fingerprint_or_completion_mismatch": mismatch,
        "missing_prior_request_id": missing,
        "pending": len(requests) - len(selected),
        "expected_model": expected_model,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prefill only exact request-fingerprint matches from a prior run."
    )
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--prior-results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    requests = list(iter_jsonl(args.requests))
    prior = list(iter_jsonl(args.prior_results))
    selected, summary = select_matching(
        requests, prior, expected_model=args.model
    )
    write_jsonl(args.output, selected)
    if args.report:
        write_json(args.report, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
