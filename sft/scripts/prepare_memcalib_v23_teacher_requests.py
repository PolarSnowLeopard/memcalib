#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evaluation.common import display_path, iter_jsonl, sha256_file, write_json, write_jsonl


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = (
    ROOT
    / "pipeline/data/multidomain/full-v2/revision-composite-blocks-v23/release"
    / "memcalib_v23_multidomain_benchmark_15000.jsonl"
)
DEFAULT_IDS = ROOT / "sft/releases/memcalib-v23-sft-12000-1500-1500/pilot_train-ids.txt"
DEFAULT_PROMPT = ROOT / "sft/prompts/generate_memcalib_v23_sft_target.txt"
DEFAULT_RUN = ROOT / "sft/runs/memcalib-v23-sft-pilot-500"


def load_ids(path: Path) -> list[str]:
    values = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not values or len(values) != len(set(values)):
        raise ValueError("pilot ID file must contain unique nonempty IDs")
    return values


def atomic_supervision(memory: dict[str, Any]) -> dict[str, Any]:
    rubric = memory.get("usage_rubric") or {}
    return {
        "atom_id": str(memory["atom_id"]),
        "parent_memory_id": str(memory["parent_memory_id"]),
        "text": str(memory["text"]),
        "gold_usage_level": str(memory["u_star"]),
        "memory_action": str(memory["memory_action"]),
        "query_relation": str(memory.get("query_relation") or "unknown"),
        "rubric": {
            "expected_answer_behavior": str(rubric.get("expected_answer_behavior") or ""),
            "correct_use": str(rubric.get("correct_use") or ""),
            "under_use": str(rubric.get("under_use") or ""),
            "over_use": str(rubric.get("over_use") or ""),
            "forbidden_memory_role": str(rubric.get("forbidden_memory_role") or ""),
            "validity_scope": str(rubric.get("validity_scope") or ""),
            "observable_checks": list(rubric.get("observable_checks") or []),
        },
    }


def build_request(row: dict[str, Any], system_prompt: str, model: str, model_key: str) -> dict[str, Any]:
    sample_id = str(row["id"])
    payload = {
        "domain": str(row["domain"]),
        "current_query": str(row["question"]),
        "model_facing_memory": [
            {
                "parent_memory_id": str(block["parent_memory_id"]),
                "memory_text": str(block["memory_text"]),
            }
            for block in row.get("memory_blocks") or []
        ],
        "source_answer": str(row.get("source_answer") or ""),
        "atomic_supervision": [atomic_supervision(memory) for memory in row.get("memories") or []],
    }
    return {
        "request_id": f"answer:{model_key}:full_memory:{sample_id}",
        "prompt": [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
        ],
        "user_defined_params": {
            "stage": "answer",
            "sample_id": sample_id,
            "panel": str(row["domain"]),
            "condition": "full_memory",
            "model_key": model_key,
            "expected_model": model,
            "target_kind": "privileged_sft_teacher",
        },
    }


def model_facing(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "panel": str(row["domain"]),
        "domain": str(row["domain"]),
        "question": str(row["question"]),
        "memory_blocks": [
            {
                "parent_memory_id": str(block["parent_memory_id"]),
                "memory_text": str(block["memory_text"]),
            }
            for block in row.get("memory_blocks") or []
        ],
        "source_dataset": str(row.get("source_dataset") or ""),
        "source_topic": str(row.get("source_topic") or ""),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--ids", type=Path, default=DEFAULT_IDS)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--hidden-output", type=Path)
    parser.add_argument("--model-facing-output", type=Path)
    parser.add_argument("--model", default="qwen3.7-max")
    parser.add_argument("--model-key", default="qwen37max-teacher")
    args = parser.parse_args()

    requested_ids = load_ids(args.ids)
    requested_set = set(requested_ids)
    source_rows = [row for row in iter_jsonl(args.input) if str(row["id"]) in requested_set]
    source_by_id = {str(row["id"]): row for row in source_rows}
    missing = sorted(requested_set.difference(source_by_id))
    if missing or len(source_by_id) != len(requested_ids):
        raise ValueError(f"pilot IDs missing from source: {missing[:5]}")
    rows = [source_by_id[value] for value in requested_ids]
    system_prompt = args.prompt.read_text(encoding="utf-8")
    requests = [build_request(row, system_prompt, args.model, args.model_key) for row in rows]

    request_path = args.run_dir / "requests/answers" / args.model_key / "full_memory.jsonl"
    hidden_path = args.hidden_output or args.run_dir / "pilot.hidden.jsonl"
    model_facing_path = args.model_facing_output or args.run_dir / "pilot.model-facing.jsonl"
    manifest_path = args.run_dir / "teacher-request.manifest.json"
    write_jsonl(request_path, requests)
    write_jsonl(hidden_path, rows)
    write_jsonl(model_facing_path, (model_facing(row) for row in rows))

    prompt_chars = [sum(len(str(message["content"])) for message in row["prompt"]) for row in requests]
    manifest = {
        "schema_version": "memcalib-v23-sft-teacher-requests-v1",
        "requests": len(requests),
        "model": args.model,
        "model_key": args.model_key,
        "condition": "full_memory",
        "inputs": {
            "source": {"path": display_path(args.input, ROOT), "sha256": sha256_file(args.input)},
            "ids": {"path": display_path(args.ids, ROOT), "sha256": sha256_file(args.ids)},
            "prompt": {"path": display_path(args.prompt, ROOT), "sha256": sha256_file(args.prompt)},
        },
        "artifacts": {
            "requests": {
                "path": display_path(request_path, ROOT),
                "rows": len(requests),
                "sha256": sha256_file(request_path),
            },
            "hidden": {
                "path": display_path(hidden_path, ROOT),
                "rows": len(rows),
                "sha256": sha256_file(hidden_path),
            },
            "model_facing": {
                "path": display_path(model_facing_path, ROOT),
                "rows": len(rows),
                "sha256": sha256_file(model_facing_path),
            },
        },
        "prompt_chars": {
            "min": min(prompt_chars),
            "mean": sum(prompt_chars) / len(prompt_chars),
            "max": max(prompt_chars),
        },
    }
    write_json(manifest_path, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
