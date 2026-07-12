#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evaluation.common import iter_jsonl, write_jsonl


def build_retry_request(original: dict[str, Any], errors: list[str], *, retry_round: int) -> dict[str, Any]:
    protocol = str((original.get("user_defined_params") or {}).get("judge_protocol") or "verdict-v1")
    if protocol == "ordered-usage-v2":
        contract = (
            "Preserve every requested atom exactly once, copy each u_star label, and return atom_judgments as an array. "
            "For each atom provide predicted_usage_level, scorable, contradiction, evidence_quote, reason, and confidence. "
            "When scorable=false, predicted_usage_level must be null."
        )
    else:
        contract = "Preserve every requested atom exactly once, copy each u_star label, and use only the verdicts allowed for that label."
    feedback = (
        "Your previous output failed structural validation. Return a corrected JSON object only. "
        + contract
        + "\n\nVALIDATION ERRORS\n- "
        + "\n- ".join(str(error) for error in errors)
    )
    return {
        "request_id": f"{original['request_id']}:retry{retry_round}",
        "prompt": list(original["prompt"]) + [{"role": "user", "content": feedback}],
        "user_defined_params": original["user_defined_params"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare targeted retry requests for invalid MemCalib judgments.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--invalid", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--round", type=int, default=1)
    args = parser.parse_args()
    requests = {str(row["request_id"]): row for row in iter_jsonl(args.input)}
    retry_rows = []
    missing = []
    for invalid in iter_jsonl(args.invalid):
        request_id = str(invalid["request_id"])
        original = requests.get(request_id)
        if original is None:
            missing.append(request_id)
            continue
        retry_rows.append(build_retry_request(original, list(invalid.get("errors") or []), retry_round=args.round))
    if missing:
        raise SystemExit(f"invalid request IDs are absent from original input: {len(missing)}")
    write_jsonl(args.output, retry_rows)
    print(json.dumps({"input": str(args.input), "invalid": len(retry_rows), "output": str(args.output), "round": args.round}, indent=2))


if __name__ == "__main__":
    main()
