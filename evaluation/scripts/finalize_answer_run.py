#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from evaluation.common import display_path, iter_jsonl, sha256_file, write_json
from evaluation.scripts.validate_api_results import validate_results


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "evaluation" / "configs" / "memcalib-v0.1-500.json"
DEFAULT_REQUESTS = ROOT / "evaluation" / "runs" / "memcalib-v0.1-500" / "requests" / "answers"
DEFAULT_RESULTS = ROOT / "evaluation" / "runs" / "memcalib-v0.1-500" / "answers"
DEFAULT_MANIFEST = ROOT / "evaluation" / "releases" / "memcalib-v0.1-500" / "answer-run.manifest.json"
CONDITIONS = ("full_memory", "no_memory")


def summarize_result_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    models: Counter[str] = Counter()
    finish_reasons: Counter[str] = Counter()
    usage: Counter[str] = Counter()
    response_chars = []
    for row in rows:
        raw = row.get("raw_response") or {}
        models[str(raw.get("model") or "unknown")] += 1
        choices = raw.get("choices") or []
        finish_reasons[str(choices[0].get("finish_reason") or "unknown") if choices else "unknown"] += 1
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            usage[key] += int((raw.get("usage") or {}).get(key) or 0)
        response_chars.append(len(str(row.get("response") or "")))
    return {
        "rows": len(rows),
        "returned_models": dict(sorted(models.items())),
        "finish_reasons": dict(sorted(finish_reasons.items())),
        "usage": dict(usage),
        "response_chars": {
            "min": min(response_chars) if response_chars else 0,
            "mean": sum(response_chars) / len(response_chars) if response_chars else 0,
            "max": max(response_chars) if response_chars else 0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and lock the MemCalib answer run.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--conditions", nargs="+", choices=CONDITIONS)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    configured_conditions = config.get("evaluation_modes", {}).get("official_research_conditions")
    conditions = tuple(args.conditions or configured_conditions or CONDITIONS)
    cells = {}
    errors = {}
    aggregate_usage: Counter[str] = Counter()
    total = 0
    for model_entry in config["answer_models"]:
        model_key = str(model_entry["key"])
        model = str(model_entry["model"])
        for condition in conditions:
            input_path = args.requests / model_key / f"{condition}.jsonl"
            output_path = args.results / model_key / f"{condition}.jsonl"
            validation = validate_results(input_path, output_path, model)
            if not validation["valid"]:
                errors[f"{model_key}:{condition}"] = validation
                continue
            rows = list(iter_jsonl(output_path))
            summary = summarize_result_rows(rows)
            for key, value in summary["usage"].items():
                aggregate_usage[key] += value
            total += len(rows)
            cells[f"{model_key}:{condition}"] = {
                "model": model,
                "condition": condition,
                "input": {"path": display_path(input_path, ROOT), "sha256": sha256_file(input_path)},
                "output": {"path": display_path(output_path, ROOT), "sha256": sha256_file(output_path)},
                "validation": validation["counts"],
                "summary": summary,
            }
    if errors:
        print(json.dumps({"status": "invalid", "errors": errors}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    manifest = {
        "schema_version": "memcalib-answer-run-v1",
        "status": "completed",
        "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "formal_answers": total,
        "models": config["answer_models"],
        "conditions": list(conditions),
        "generation": config["answer_generation"],
        "aggregate_usage": dict(aggregate_usage),
        "cells": dict(sorted(cells.items())),
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
