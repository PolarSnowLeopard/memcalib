#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evaluation.common import display_path, iter_jsonl, sha256_file, write_json, write_jsonl


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "evaluation" / "configs" / "memcalib-v0.1-500.json"
DEFAULT_INPUT = ROOT / "evaluation" / "releases" / "memcalib-v0.1-500" / "model-facing.jsonl"
DEFAULT_PROMPT = ROOT / "evaluation" / "prompts" / "answer-system.txt"
DEFAULT_OUTPUT = ROOT / "evaluation" / "runs" / "memcalib-v0.1-500" / "requests" / "answers"
DEFAULT_MANIFEST = ROOT / "evaluation" / "releases" / "memcalib-v0.1-500" / "answer-request.manifest.json"
CONDITIONS = ("full_memory", "no_memory")


def build_answer_messages(sample: dict[str, Any], condition: str, system_prompt: str) -> list[dict[str, str]]:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown answer condition: {condition}")
    question = str(sample["question"])
    if condition == "full_memory":
        blocks = sample.get("memory_blocks") or []
        memory_text = "\n".join(f"[{index}] {block['memory_text']}" for index, block in enumerate(blocks, start=1))
        user_content = f"MEMORY\n{memory_text}\n\nCURRENT QUERY\n{question}"
    else:
        user_content = f"CURRENT QUERY\n{question}"
    return [
        {"role": "system", "content": system_prompt.strip()},
        {"role": "user", "content": user_content},
    ]


def build_answer_request(
    sample: dict[str, Any], condition: str, model_key: str, model: str, system_prompt: str
) -> dict[str, Any]:
    sample_id = str(sample["id"])
    return {
        "request_id": f"answer:{model_key}:{condition}:{sample_id}",
        "prompt": build_answer_messages(sample, condition, system_prompt),
        "user_defined_params": {
            "stage": "answer",
            "sample_id": sample_id,
            "panel": str(sample["panel"]),
            "condition": condition,
            "model_key": model_key,
            "expected_model": model,
        },
    }


def prepare_answer_requests(
    samples: list[dict[str, Any]],
    config: dict[str, Any],
    system_prompt: str,
    output_dir: Path,
    *,
    conditions: tuple[str, ...] = CONDITIONS,
) -> dict[str, Any]:
    if len(samples) != 500 or len({str(row["id"]) for row in samples}) != 500:
        raise ValueError("answer request preparation requires exactly 500 unique samples")
    if not conditions or len(set(conditions)) != len(conditions) or not set(conditions).issubset(CONDITIONS):
        raise ValueError(f"conditions must be a unique nonempty subset of {CONDITIONS}")
    representative = next(row for row in samples if row["panel"] == "representative")
    diagnostic = next(row for row in samples if row["panel"] == "diagnostic")
    artifacts: dict[str, Any] = {}
    total = 0
    for model_entry in config["answer_models"]:
        model_key = str(model_entry["key"])
        model = str(model_entry["model"])
        model_dir = output_dir / model_key
        smoke_rows = []
        for condition in conditions:
            rows = [build_answer_request(row, condition, model_key, model, system_prompt) for row in samples]
            path = model_dir / f"{condition}.jsonl"
            write_jsonl(path, rows)
            artifacts[str(path.relative_to(output_dir))] = {
                "rows": len(rows),
                "sha256": sha256_file(path),
                "model": model,
                "condition": condition,
            }
            total += len(rows)
            smoke_rows.extend(
                build_answer_request(row, condition, model_key, model, system_prompt)
                for row in (representative, diagnostic)
            )
        smoke_path = model_dir / "smoke.jsonl"
        write_jsonl(smoke_path, smoke_rows)
        artifacts[str(smoke_path.relative_to(output_dir))] = {
            "rows": len(smoke_rows),
            "sha256": sha256_file(smoke_path),
            "model": model,
            "condition": "smoke",
        }
    return {
        "schema_version": "memcalib-answer-requests-v1",
        "samples": len(samples),
        "formal_requests": total,
        "smoke_requests": len(config["answer_models"]) * len(conditions) * 2,
        "models": config["answer_models"],
        "conditions": list(conditions),
        "generation": config["answer_generation"],
        "artifacts": dict(sorted(artifacts.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare paired answer requests for MemCalib evaluation.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--conditions", nargs="+", choices=CONDITIONS)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    samples = list(iter_jsonl(args.input))
    system_prompt = args.prompt.read_text(encoding="utf-8")
    configured_conditions = config.get("evaluation_modes", {}).get("official_research_conditions")
    conditions = tuple(args.conditions or configured_conditions or CONDITIONS)
    manifest = prepare_answer_requests(samples, config, system_prompt, args.output_dir, conditions=conditions)
    manifest["inputs"] = {
        "config": {"path": display_path(args.config, ROOT), "sha256": sha256_file(args.config)},
        "samples": {"path": display_path(args.input, ROOT), "sha256": sha256_file(args.input)},
        "prompt": {"path": display_path(args.prompt, ROOT), "sha256": sha256_file(args.prompt)},
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
