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
RAW_SELECTOR_PATH = SCRIPT_DIR / "15_select_crk2_raw_seeds.py"
POST_QC_PATH = SCRIPT_DIR / "19_post_source_semantic_qc.py"
SCHEMA_VERSION = "crk2-source-semantic-admission-v1"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RAW_SELECTOR = load_module(RAW_SELECTOR_PATH, "semantic_admission_raw_selector")
POST_QC = load_module(POST_QC_PATH, "semantic_admission_post_qc")


def _with_admission(row: dict[str, Any], decision: str) -> dict[str, Any]:
    output = dict(row)
    output["semantic_admission"] = {
        "schema_version": SCHEMA_VERSION,
        "decision": decision,
        "source_state": str((row.get("semantic_qc") or {}).get("state") or "invalid"),
    }
    return output


def plan_admission(
    records: list[dict[str, Any]],
    final_target: int,
    generation_successes: int,
    generation_total: int,
    seed: int,
    config: dict[str, Any],
) -> dict[str, Any]:
    admission_target = POST_QC.compute_admission_target(
        final_target=final_target,
        generation_successes=generation_successes,
        generation_total=generation_total,
    )
    strict_rows = [row for row in records if (row.get("semantic_qc") or {}).get("state") == "strict_pass"]
    review_rows = [row for row in records if (row.get("semantic_qc") or {}).get("state") == "review"]
    rejected_rows = [row for row in records if (row.get("semantic_qc") or {}).get("state") == "reject"]

    selected_strict = RAW_SELECTOR.select_stratified(
        strict_rows,
        target=min(admission_target, len(strict_rows)),
        seed=seed,
        config=config,
    )
    admitted = [_with_admission(row, "admitted_strict") for row in selected_strict]

    if len(strict_rows) >= admission_target:
        status = "strict_sufficient"
        review_candidates: list[dict[str, Any]] = []
    else:
        status = (
            "review_required"
            if len(strict_rows) + len(review_rows) >= admission_target
            else "candidate_topup_required"
        )
        ranked_review = RAW_SELECTOR.select_stratified(
            review_rows,
            target=len(review_rows),
            seed=seed + 1,
            config=config,
        )
        review_candidates = [_with_admission(row, "pending_secondary_review") for row in ranked_review]

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "final_target": final_target,
        "admission_target": admission_target,
        "generation_pilot": {
            "successes": generation_successes,
            "total": generation_total,
            "wilson_lower_95": POST_QC.wilson_lower_bound(generation_successes, generation_total),
        },
        "counts": {
            "input": len(records),
            "strict_pass": len(strict_rows),
            "review": len(review_rows),
            "reject": len(rejected_rows),
            "admitted": len(admitted),
            "secondary_review_candidates": len(review_candidates),
        },
        "admitted": admitted,
        "review_candidates": review_candidates,
    }


def distribution(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    return {
        "source_dataset": dict(sorted(Counter(str(row.get("source_dataset") or "unknown") for row in rows).items())),
        "topic": dict(sorted(Counter(str(row.get("topic") or "general_other") for row in rows).items())),
        "seed_complexity": dict(
            sorted(
                Counter(
                    str((row.get("raw_selection") or {}).get("seed_complexity") or "unknown")
                    for row in rows
                ).items()
            )
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply adaptive source semantic-QC admission policy.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--review-output", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--final-target", type=int, default=15000)
    parser.add_argument("--generation-successes", type=int, required=True)
    parser.add_argument("--generation-total", type=int, required=True)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()

    cfg = load_json(args.config)
    output_dir = resolve_config_path(args.config, str(cfg["output_dir"]))
    seed = int(args.seed if args.seed is not None else cfg.get("sampling", {}).get("seed", 42))
    selection_cfg = dict(cfg.get("raw_selection") or {})
    output_path = args.output or output_dir / "crk2_source_semantic_admitted.jsonl"
    review_path = args.review_output or output_dir / "crk2_source_semantic_secondary_review.jsonl"
    manifest_path = args.manifest or output_dir / "crk2_source_semantic_admission.manifest.json"

    records = list(iter_jsonl(args.input))
    plan = plan_admission(
        records,
        final_target=args.final_target,
        generation_successes=args.generation_successes,
        generation_total=args.generation_total,
        seed=seed,
        config=selection_cfg,
    )
    write_jsonl(output_path, plan["admitted"])
    write_jsonl(review_path, plan["review_candidates"])
    manifest = {
        key: value for key, value in plan.items() if key not in {"admitted", "review_candidates"}
    }
    manifest["parameters"] = {"seed": seed}
    manifest["input"] = {"path": str(args.input), "sha256": RAW_SELECTOR.file_sha256(args.input)}
    manifest["distributions"] = {
        "admitted": distribution(plan["admitted"]),
        "secondary_review_candidates": distribution(plan["review_candidates"]),
    }
    manifest["outputs"] = {
        "admitted": {"path": str(output_path), "sha256": RAW_SELECTOR.file_sha256(output_path)},
        "secondary_review": {"path": str(review_path), "sha256": RAW_SELECTOR.file_sha256(review_path)},
    }
    write_json(manifest_path, manifest)
    print(json.dumps({"manifest": str(manifest_path), **manifest}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
