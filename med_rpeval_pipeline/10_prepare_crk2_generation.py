#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from utils import iter_jsonl, load_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR / "config.json"
DEFAULT_PROMPT = SCRIPT_DIR / "prompts" / "generate_crk2_memory_benchmark_record.txt"
DEFAULT_OUTPUT = SCRIPT_DIR / "data" / "crk2_generation_input_100.jsonl"


def select_balanced_records(rows: list[dict[str, Any]], limit: int, seed: int) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get("topic") or "unknown")].append(row)

    for topic, topic_rows in buckets.items():
        topic_rng = random.Random(f"{seed}:{topic}")
        topic_rng.shuffle(topic_rows)

    selected = []
    topics = sorted(buckets)
    while len(selected) < limit and topics:
        next_topics = []
        for topic in topics:
            if buckets[topic] and len(selected) < limit:
                selected.append(buckets[topic].pop(0))
            if buckets[topic]:
                next_topics.append(topic)
        topics = next_topics
    return selected


def build_request(row: dict[str, Any], request_index: int, target_memory_count: str, prompt_template: str | None = None) -> dict[str, Any]:
    template = prompt_template
    if template is None:
        template = DEFAULT_PROMPT.read_text(encoding="utf-8")
    source_id = str(row.get("id") or f"row_{request_index:06d}")
    content = (
        template.replace("{source_dataset}", str(row.get("source_dataset", "")))
        .replace("{source_id}", source_id)
        .replace("{topic}", str(row.get("topic", "")))
        .replace("{raw_question}", str(row.get("raw_question", "")))
        .replace("{doctor_answer}", str(row.get("doctor_answer", "")))
    )
    content += f"\n\n目标：优先构造 {target_memory_count} 个 memory block；最终 atomic memory 数量由语义拆分决定。只允许补充 hard A。"
    params = dict(row)
    params["crk2_request_index"] = request_index
    params["target_memory_count"] = target_memory_count
    return {
        "request_id": f"crk2_{source_id}",
        "prompt": [{"role": "user", "content": content}],
        "user_defined_params": params,
    }


def collect_excluded_ids(paths: list[Path]) -> set[str]:
    excluded = set()
    for path in paths:
        for row in iter_jsonl(path):
            params = row.get("user_defined_params") or row.get("passParams") or row.get("params") or {}
            source_id = params.get("id") or params.get("source_raw_id")
            if source_id:
                excluded.add(str(source_id))
    return excluded


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare CRK-2 full LLM construction requests from raw public QA records.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--prompt-template", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--target-memory-count", default="3-6")
    parser.add_argument("--primus-string-prompt", action="store_true")
    parser.add_argument("--exclude-requests", type=Path, action="append", default=[])
    args = parser.parse_args()

    cfg = load_json(args.config)
    input_path = args.input or Path(cfg["output_dir"]) / "normalized_raw.jsonl"
    seed = args.seed if args.seed is not None else int(cfg.get("sampling", {}).get("seed", 42))
    rows = list(iter_jsonl(input_path))
    excluded_ids = collect_excluded_ids(args.exclude_requests)
    if excluded_ids:
        rows = [row for row in rows if str(row.get("id")) not in excluded_ids]
    selected = select_balanced_records(rows, args.limit, seed)
    template = args.prompt_template.read_text(encoding="utf-8")
    requests = []
    for index, row in enumerate(selected, start=1):
        request = build_request(row, index, args.target_memory_count, template)
        if args.primus_string_prompt:
            request["prompt"] = json.dumps(request["prompt"], ensure_ascii=False)
        requests.append(request)

    write_jsonl(args.output, requests)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "requests": len(requests),
                "input": str(input_path),
                "seed": seed,
                "excluded": len(excluded_ids),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
