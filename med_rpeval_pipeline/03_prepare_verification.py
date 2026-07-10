#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from utils import iter_jsonl, load_json, resolve_config_path, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR / "config.json"
DEFAULT_PROMPT = SCRIPT_DIR / "prompts" / "verify_rpeval_record.txt"


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare verifier LLM requests for generated RPEval records.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--prompt-template", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--primus-string-prompt", action="store_true")
    args = parser.parse_args()

    cfg = load_json(args.config)
    output_dir = resolve_config_path(args.config, str(cfg["output_dir"]))
    input_path = args.input or output_dir / "generated_candidates.jsonl"
    output_path = args.output or output_dir / "crawl_verify_input.jsonl"
    template = args.prompt_template.read_text(encoding="utf-8")

    rows = []
    for rec in iter_jsonl(input_path):
        candidate_json = json.dumps(
            {
                "question": rec["question"],
                "preferences": rec["preferences"],
                "raw_question": rec.get("raw_question", ""),
            },
            ensure_ascii=False,
            indent=2,
        )
        messages = [{"role": "user", "content": template.replace("{candidate_json}", candidate_json)}]
        rows.append(
            {
                "prompt": json.dumps(messages, ensure_ascii=False) if args.primus_string_prompt else messages,
                "user_defined_params": rec,
            }
        )

    write_jsonl(output_path, rows)
    print(json.dumps({"output": str(output_path), "requests": len(rows)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
