#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from utils import iter_jsonl, load_json, resolve_config_path, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR / "config.json"
DEFAULT_PROMPT = SCRIPT_DIR / "prompts" / "verify_source_qa_semantic_quality.txt"
RAW_SELECTOR_PATH = SCRIPT_DIR / "15_select_crk2_raw_seeds.py"
SCHEMA_VERSION = "crk2-source-semantic-qc-v1"
DIMENSION_NAMES = (
    "question_completeness",
    "answer_relevance",
    "answer_substantiveness",
    "memory_extractability",
    "text_integrity",
    "safety_plausibility",
)


def load_raw_selector():
    spec = importlib.util.spec_from_file_location("semantic_qc_raw_selector", RAW_SELECTOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RAW_SELECTOR = load_raw_selector()


def select_calibration_rows(
    rows: list[dict[str, Any]], limit: int, seed: int, config: dict[str, Any]
) -> list[dict[str, Any]]:
    if limit <= 0:
        raise ValueError("limit must be positive")
    return RAW_SELECTOR.select_stratified(rows, target=min(limit, len(rows)), seed=seed, config=config)


def build_request(
    row: dict[str, Any],
    request_index: int,
    prompt_template: str | None = None,
) -> dict[str, Any]:
    template = prompt_template if prompt_template is not None else DEFAULT_PROMPT.read_text(encoding="utf-8")
    source_id = str(row.get("id") or f"row_{request_index:06d}")
    content = (
        template.replace("{schema_version}", SCHEMA_VERSION)
        .replace("{source_dataset}", str(row.get("source_dataset") or ""))
        .replace("{source_id}", source_id)
        .replace("{topic}", str(row.get("topic") or ""))
        .replace("{raw_question}", str(row.get("raw_question") or ""))
        .replace("{doctor_answer}", str(row.get("doctor_answer") or ""))
        .replace("{dimension_names}", ", ".join(DIMENSION_NAMES))
    )
    params = dict(row)
    params["semantic_qc_request_index"] = request_index
    params["semantic_qc_schema_version"] = SCHEMA_VERSION
    return {
        "request_id": f"sourceqc_{source_id}",
        "prompt": [{"role": "user", "content": content}],
        "user_defined_params": params,
    }


def distribution(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    return {
        "source_dataset": dict(sorted(Counter(str(row.get("source_dataset") or "unknown") for row in rows).items())),
        "topic": dict(sorted(Counter(str(row.get("topic") or "general_other") for row in rows).items())),
        "seed_complexity": dict(
            sorted(
                Counter(
                    str((row.get("raw_selection") or {}).get("seed_complexity") or "unknown") for row in rows
                ).items()
            )
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare grounded source-QA semantic QC requests.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--input-manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--prompt-template", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()

    cfg = load_json(args.config)
    output_dir = resolve_config_path(args.config, str(cfg["output_dir"]))
    input_path = args.input or output_dir / "crk2_source_candidate_pool_30000.jsonl"
    input_manifest_path = args.input_manifest or output_dir / "crk2_source_candidate_pool_30000.manifest.json"
    output_path = args.output or output_dir / f"crk2_source_semantic_qc_input_{args.limit}.jsonl"
    manifest_path = args.manifest or output_dir / f"crk2_source_semantic_qc_input_{args.limit}.manifest.json"
    seed = int(args.seed if args.seed is not None else cfg.get("sampling", {}).get("seed", 42))
    selection_cfg = dict(cfg.get("raw_selection") or {})

    input_manifest = load_json(input_manifest_path)
    expected_hash = str((input_manifest.get("output") or {}).get("sha256") or "")
    actual_hash = RAW_SELECTOR.file_sha256(input_path)
    if not expected_hash or expected_hash != actual_hash:
        raise ValueError("candidate pool hash does not match input manifest")

    rows = list(iter_jsonl(input_path))
    selected = select_calibration_rows(rows, args.limit, seed, selection_cfg)
    template = args.prompt_template.read_text(encoding="utf-8")
    requests = [build_request(row, index, template) for index, row in enumerate(selected, start=1)]
    write_jsonl(output_path, requests)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "input": {
            "path": str(input_path),
            "sha256": actual_hash,
            "manifest_path": str(input_manifest_path),
            "manifest_sha256": RAW_SELECTOR.file_sha256(input_manifest_path),
        },
        "prompt": {
            "path": str(args.prompt_template),
            "sha256": RAW_SELECTOR.file_sha256(args.prompt_template),
        },
        "config": {"path": str(args.config), "sha256": RAW_SELECTOR.file_sha256(args.config)},
        "parameters": {"limit": args.limit, "seed": seed, "dimensions": list(DIMENSION_NAMES)},
        "requests": len(requests),
        "distributions": distribution(selected),
        "output": {"path": str(output_path), "sha256": RAW_SELECTOR.file_sha256(output_path)},
    }
    write_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "input": str(input_path),
                "requests": len(requests),
                "output": str(output_path),
                "manifest": str(manifest_path),
                "distributions": manifest["distributions"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
