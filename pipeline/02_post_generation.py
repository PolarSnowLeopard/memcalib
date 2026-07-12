#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from utils import extract_json_object, load_json, norm_text, resolve_config_path, stable_id, validate_candidate, write_json, write_jsonl


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


def normalize_candidate(raw: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    prefs = []
    for item in raw.get("preferences", []):
        prefs.append(
            {
                "preference": norm_text(str(item.get("preference", ""))),
                "u_star": str(item.get("u_star", "")).strip().upper(),
                "reason": norm_text(str(item.get("reason", ""))),
                "source": norm_text(str(item.get("source", ""))),
            }
        )
    question = norm_text(str(raw.get("question", "")))
    return {
        "id": stable_id(params.get("id", ""), question, json.dumps(prefs, ensure_ascii=False), prefix="medrp"),
        "source_raw_id": params.get("id", ""),
        "source_dataset": params.get("source_dataset", ""),
        "source_split": params.get("source_split", ""),
        "source_index": params.get("source_index", ""),
        "topic": params.get("topic", ""),
        "raw_question": params.get("raw_question", ""),
        "doctor_answer": params.get("doctor_answer", ""),
        "question": question,
        "preferences": prefs,
        "generation_notes": norm_text(str(raw.get("notes", ""))),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse generated RPEval candidates and run local validation.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--input", type=Path, required=True, help="LLM crawl result JSONL.")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--rejected", type=Path)
    args = parser.parse_args()

    cfg = load_json(args.config)
    gen_cfg = cfg["generation"]
    output_dir = resolve_config_path(args.config, str(cfg["output_dir"]))
    output = args.output or output_dir / "generated_candidates.jsonl"
    rejected_path = args.rejected or output_dir / "generated_rejected.jsonl"

    kept = []
    rejected = []
    with args.input.open(encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if not line.strip():
                continue
            row = json.loads(line)
            params = get_params(row)
            try:
                raw = extract_json_object(get_text(row))
                rec = normalize_candidate(raw, params)
                errors = validate_candidate(
                    rec,
                    gen_cfg["min_preferences"],
                    gen_cfg["max_preferences"],
                    require_a_label=gen_cfg.get("require_a_label", False),
                    require_applied_label=gen_cfg.get("require_applied_label", True),
                )
                if errors:
                    rejected.append({"row_index": idx, "errors": errors, "record": rec})
                else:
                    kept.append(rec)
            except Exception as exc:  # noqa: BLE001
                rejected.append({"row_index": idx, "errors": [type(exc).__name__, str(exc)], "params": params})

    write_jsonl(output, kept)
    write_jsonl(rejected_path, rejected)
    write_json(output.with_suffix(".stats.json"), {"kept": len(kept), "rejected": len(rejected)})
    print(json.dumps({"output": str(output), "kept": len(kept), "rejected": len(rejected)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
