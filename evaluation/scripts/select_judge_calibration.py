#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from evaluation.common import display_path, iter_jsonl, sha256_file, stable_hash, write_json, write_jsonl


ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = ROOT / "evaluation" / "runs" / "memcalib-ordered-v2-500"
DEFAULT_PRIMARY = RUN_ROOT / "requests" / "judges" / "primary.jsonl"
DEFAULT_SECONDARY = (
    RUN_ROOT / "requests" / "judges" / "secondary-deepseek.jsonl",
    RUN_ROOT / "requests" / "judges" / "secondary-kimi.jsonl",
)
DEFAULT_OUTPUT = RUN_ROOT / "calibration" / "requests"
DEFAULT_MANIFEST = (
    ROOT / "evaluation" / "archive" / "releases" / "memcalib-ordered-v2-500" / "calibration-request.manifest.json"
)
CONDITIONS = ("full_memory", "no_memory")


def _answer_id(row: dict[str, Any]) -> str:
    return str(row["user_defined_params"]["answer_request_id"])


def select_paired_calibration_rows(
    primary: list[dict[str, Any]],
    secondary: list[dict[str, Any]],
    *,
    seed: int,
    representative_samples: int,
    diagnostic_samples: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    primary_by_answer = {_answer_id(row): row for row in primary}
    secondary_by_answer = {_answer_id(row): row for row in secondary}
    if len(primary_by_answer) != len(primary) or len(secondary_by_answer) != len(secondary):
        raise ValueError("judge calibration inputs contain duplicate answer_request_id values")

    candidates: dict[tuple[str, str, str], dict[str, str]] = defaultdict(dict)
    for answer_id, row in secondary_by_answer.items():
        params = row["user_defined_params"]
        key = (str(params["model_key"]), str(params["panel"]), str(params["sample_id"]))
        candidates[key][str(params["condition"])] = answer_id

    models = sorted({key[0] for key in candidates})
    selected_answer_ids: set[str] = set()
    for model in models:
        for panel, required in (
            ("representative", representative_samples),
            ("diagnostic", diagnostic_samples),
        ):
            complete = [
                (sample_id, condition_map)
                for (candidate_model, candidate_panel, sample_id), condition_map in candidates.items()
                if candidate_model == model
                and candidate_panel == panel
                and set(condition_map) == set(CONDITIONS)
                and all(answer_id in primary_by_answer for answer_id in condition_map.values())
            ]
            complete.sort(key=lambda item: stable_hash(seed, f"{model}:{panel}:{item[0]}"))
            if len(complete) < required:
                raise ValueError(
                    f"insufficient paired calibration samples for {(model, panel)}: {len(complete)} < {required}"
                )
            for _, condition_map in complete[:required]:
                selected_answer_ids.update(condition_map.values())

    expected = len(models) * 2 * (representative_samples + diagnostic_samples)
    if len(selected_answer_ids) != expected:
        raise ValueError(f"calibration selection count mismatch: {len(selected_answer_ids)} != {expected}")
    selected_primary = sorted(
        (primary_by_answer[answer_id] for answer_id in selected_answer_ids), key=_answer_id
    )
    selected_secondary = sorted(
        (secondary_by_answer[answer_id] for answer_id in selected_answer_ids), key=_answer_id
    )
    return selected_primary, selected_secondary


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def main() -> None:
    parser = argparse.ArgumentParser(description="Select paired ordered-usage-v2 Judge calibration requests.")
    parser.add_argument("--primary", type=Path, default=DEFAULT_PRIMARY)
    parser.add_argument("--secondary", type=Path, action="append")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--seed", type=int, default=20260714)
    parser.add_argument("--representative-samples", type=int, default=7)
    parser.add_argument("--diagnostic-samples", type=int, default=3)
    args = parser.parse_args()

    secondary_paths = tuple(args.secondary or DEFAULT_SECONDARY)
    primary = list(iter_jsonl(args.primary))
    secondary = [row for path in secondary_paths for row in iter_jsonl(path)]
    selected_primary, selected_secondary = select_paired_calibration_rows(
        primary,
        secondary,
        seed=args.seed,
        representative_samples=args.representative_samples,
        diagnostic_samples=args.diagnostic_samples,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    primary_path = args.output_dir / "primary.jsonl"
    write_jsonl(primary_path, selected_primary)
    artifacts: dict[str, Any] = {
        primary_path.name: {"rows": len(selected_primary), "sha256": sha256_file(primary_path)}
    }
    by_judge: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in selected_secondary:
        by_judge[str(row["user_defined_params"]["judge_model"])].append(row)
    for judge_model, rows in sorted(by_judge.items()):
        path = args.output_dir / f"secondary-{_slug(judge_model)}.jsonl"
        write_jsonl(path, rows)
        artifacts[path.name] = {"rows": len(rows), "sha256": sha256_file(path), "judge_model": judge_model}

    selected_ids_path = args.output_dir / "answer-ids.txt"
    selected_ids_path.write_text("".join(f"{_answer_id(row)}\n" for row in selected_primary), encoding="utf-8")
    artifacts[selected_ids_path.name] = {
        "rows": len(selected_primary),
        "sha256": sha256_file(selected_ids_path),
    }
    cells = Counter(
        (
            str(row["user_defined_params"]["model_key"]),
            str(row["user_defined_params"]["condition"]),
            str(row["user_defined_params"]["panel"]),
        )
        for row in selected_primary
    )
    manifest = {
        "schema_version": "memcalib-ordered-judge-calibration-v1",
        "seed": args.seed,
        "paired_samples_per_model": args.representative_samples + args.diagnostic_samples,
        "answer_requests": len(selected_primary),
        "primary_requests": len(selected_primary),
        "secondary_requests": len(selected_secondary),
        "cells": {"|".join(key): value for key, value in sorted(cells.items())},
        "inputs": {
            "primary": {"path": display_path(args.primary, ROOT), "sha256": sha256_file(args.primary)},
            "secondary": [
                {"path": display_path(path, ROOT), "sha256": sha256_file(path)} for path in secondary_paths
            ],
        },
        "artifacts": artifacts,
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
