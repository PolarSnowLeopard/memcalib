#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from utils import LABELS, extract_json_object, load_json, resolve_config_path, validate_candidate, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR / "config.json"


def get_params(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("passParams") or row.get("user_defined_params") or row.get("params") or {}


def get_text(row: dict[str, Any]) -> str:
    for key in ("response", "output", "content", "text", "answer"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    choices = row.get("choices")
    if isinstance(choices, list) and choices:
        msg = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(msg, dict) and isinstance(msg.get("content"), str):
            return msg["content"]
    result = row.get("result")
    if isinstance(result, dict):
        return get_text(result)
    if isinstance(result, str):
        return result
    raise ValueError("No model output text found")


def apply_verification(rec: dict[str, Any], verdict: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    issues = []
    if verdict.get("pass") is not True:
        issues.append("verifier_record_fail")
    item_rows = verdict.get("items")
    if not isinstance(item_rows, list):
        issues.append("verifier_missing_items")
        return rec, issues
    if len(item_rows) != len(rec.get("preferences", [])):
        issues.append("verifier_length_mismatch")
        return rec, issues

    for idx, item in enumerate(item_rows):
        if item.get("pass") is not True:
            issues.append(f"verifier_item_fail_{idx}")
        corrected = str(item.get("corrected_u_star", "")).strip().upper()
        if corrected in LABELS:
            rec["preferences"][idx]["u_star"] = corrected
        rec["preferences"][idx]["verify_reason"] = str(item.get("audit_reason", "")).strip()
        rec["preferences"][idx]["verify_issue"] = str(item.get("issue", "")).strip()
        rec["preferences"][idx]["boundary_case"] = str(item.get("boundary_case", "none")).strip() or "none"
    rec["verification"] = {
        "record_level_issues": verdict.get("record_level_issues", []),
        "items": item_rows,
    }
    return rec, issues


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse verifier results and keep only high-quality records.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--input", type=Path, required=True, help="Verifier crawl result JSONL.")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--rejected", type=Path)
    parser.add_argument("--keep-item-fails", action="store_true", help="Keep records where verifier corrected labels but flagged item issues.")
    args = parser.parse_args()

    cfg = load_json(args.config)
    gen_cfg = cfg["generation"]
    output_dir = resolve_config_path(args.config, str(cfg["output_dir"]))
    output = args.output or output_dir / "verified_records.jsonl"
    rejected_path = args.rejected or output_dir / "verified_rejected.jsonl"

    kept = []
    rejected = []
    with args.input.open(encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if not line.strip():
                continue
            row = json.loads(line)
            rec = get_params(row)
            try:
                verdict = extract_json_object(get_text(row))
                rec, verify_issues = apply_verification(rec, verdict)
                local_errors = validate_candidate(
                    rec,
                    gen_cfg["min_preferences"],
                    gen_cfg["max_preferences"],
                    require_a_label=gen_cfg.get("require_a_label", False),
                    require_applied_label=gen_cfg.get("require_applied_label", True),
                )
                blocking = local_errors + [x for x in verify_issues if args.keep_item_fails is False or x == "verifier_record_fail"]
                if blocking:
                    rejected.append({"row_index": idx, "errors": blocking, "record": rec})
                else:
                    kept.append(rec)
            except Exception as exc:  # noqa: BLE001
                rejected.append({"row_index": idx, "errors": [type(exc).__name__, str(exc)], "record": rec})

    write_jsonl(output, kept)
    write_jsonl(rejected_path, rejected)
    write_json(output.with_suffix(".stats.json"), {"kept": len(kept), "rejected": len(rejected)})
    print(json.dumps({"output": str(output), "kept": len(kept), "rejected": len(rejected)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
