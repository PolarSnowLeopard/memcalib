#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from evaluation.common import iter_jsonl, request_fingerprint, sha256_file, write_json, write_jsonl


DEFAULT_CONDITIONS = ("full_memory", "no_memory")


def finish_reason(row: dict[str, Any]) -> str:
    choices = (row.get("raw_response") or {}).get("choices") or []
    if choices and isinstance(choices[0], dict):
        return str(choices[0].get("finish_reason") or "")
    return ""


def is_complete(
    row: dict[str, Any], request: dict[str, Any], expected_model: str
) -> bool:
    returned_model = str((row.get("raw_response") or {}).get("model") or "")
    return (
        row.get("input_fingerprint") == request_fingerprint(request)
        and isinstance(row.get("response"), str)
        and bool(str(row["response"]).strip())
        and finish_reason(row) == "stop"
        and not row.get("error")
        and (not returned_model or returned_model == expected_model)
    )


def result_paths(root: Path, model_key: str, condition: str) -> list[Path]:
    model_root = root / model_key
    canonical = model_root / f"{condition}.jsonl"
    retries = sorted(model_root.glob(f"{condition}.retry-api[0-9]*.jsonl"))
    return [canonical, *retries]


def write_gzip(source: Path) -> Path:
    target = source.with_suffix(source.suffix + ".gz")
    with source.open("rb") as src, gzip.open(target, "wb", compresslevel=9) as dst:
        while chunk := src.read(1024 * 1024):
            dst.write(chunk)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a fully paired complete-case answer run without new API calls."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--sample-release", type=Path, required=True)
    parser.add_argument("--output-config", type=Path, required=True)
    parser.add_argument("--output-requests", type=Path, required=True)
    parser.add_argument("--output-results", type=Path, required=True)
    parser.add_argument("--output-sample-release", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    configured_conditions = config.get("evaluation_modes", {}).get(
        "official_research_conditions"
    )
    conditions = tuple(configured_conditions or DEFAULT_CONDITIONS)
    unknown_conditions = set(conditions) - set(DEFAULT_CONDITIONS)
    if not conditions or unknown_conditions:
        raise ValueError(f"invalid evaluation conditions: {conditions}")
    cell_requests: dict[tuple[str, str], list[dict[str, Any]]] = {}
    cell_results: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    cell_sample_ids: dict[tuple[str, str], set[str]] = {}
    missing_by_cell: dict[str, list[str]] = {}

    for model_entry in config["answer_models"]:
        model_key = str(model_entry["key"])
        expected_model = str(model_entry.get("served_model_name") or model_entry["model"])
        for condition in conditions:
            cell = (model_key, condition)
            request_path = args.requests / model_key / f"{condition}.jsonl"
            requests = list(iter_jsonl(request_path))
            request_by_id = {str(row["request_id"]): row for row in requests}
            if len(request_by_id) != len(requests):
                raise ValueError(f"duplicate request IDs in {request_path}")
            selected: dict[str, dict[str, Any]] = {}
            for path in result_paths(args.results, model_key, condition):
                if not path.exists():
                    continue
                for row in iter_jsonl(path):
                    request_id = str(row.get("request_id") or "")
                    request = request_by_id.get(request_id)
                    if request is not None and is_complete(row, request, expected_model):
                        selected[request_id] = row
            valid_samples = {
                str((request_by_id[request_id].get("user_defined_params") or {})["sample_id"])
                for request_id in selected
            }
            missing_samples = sorted(
                str((request.get("user_defined_params") or {})["sample_id"])
                for request_id, request in request_by_id.items()
                if request_id not in selected
            )
            cell_requests[cell] = requests
            cell_results[cell] = selected
            cell_sample_ids[cell] = valid_samples
            missing_by_cell[f"{model_key}:{condition}"] = missing_samples

    common_sample_ids = set.intersection(*cell_sample_ids.values())
    if not common_sample_ids:
        raise ValueError("complete-case intersection is empty")

    sample_rows = list(iter_jsonl(args.sample_release / "model-facing.jsonl"))
    sample_order = [str(row["id"]) for row in sample_rows]
    common_order = [sample_id for sample_id in sample_order if sample_id in common_sample_ids]
    if len(common_order) != len(common_sample_ids):
        raise ValueError("complete-case sample IDs are not fully represented in sample release")
    excluded = [sample_id for sample_id in sample_order if sample_id not in common_sample_ids]

    artifacts: dict[str, dict[str, Any]] = {}
    for (model_key, condition), requests in sorted(cell_requests.items()):
        output_requests = []
        output_results = []
        selected = cell_results[(model_key, condition)]
        for request in requests:
            params = request.get("user_defined_params") or {}
            sample_id = str(params["sample_id"])
            if sample_id not in common_sample_ids:
                continue
            request_id = str(request["request_id"])
            result = selected.get(request_id)
            if result is None:
                raise ValueError(f"missing complete result for retained request {request_id}")
            output_requests.append(request)
            output_results.append(result)
        if len(output_requests) != len(common_order):
            raise ValueError(
                f"complete-case cell mismatch for {model_key}:{condition}: "
                f"{len(output_requests)} != {len(common_order)}"
            )
        request_path = args.output_requests / model_key / f"{condition}.jsonl"
        result_path = args.output_results / model_key / f"{condition}.jsonl"
        write_jsonl(request_path, output_requests)
        write_jsonl(result_path, output_results)
        artifacts[f"requests/{model_key}/{condition}.jsonl"] = {
            "rows": len(output_requests),
            "sha256": sha256_file(request_path),
        }
        artifacts[f"answers/{model_key}/{condition}.jsonl"] = {
            "rows": len(output_results),
            "sha256": sha256_file(result_path),
        }

    for name in ("model-facing.jsonl", "hidden-evaluation.jsonl"):
        source_rows = list(iter_jsonl(args.sample_release / name))
        filtered = [row for row in source_rows if str(row["id"]) in common_sample_ids]
        output_path = args.output_sample_release / name
        write_jsonl(output_path, filtered)
        gzip_path = write_gzip(output_path)
        artifacts[name] = {"rows": len(filtered), "sha256": sha256_file(output_path)}
        artifacts[gzip_path.name] = {
            "bytes": gzip_path.stat().st_size,
            "sha256": sha256_file(gzip_path),
        }

    sample_ids_path = args.output_sample_release / "sample-ids.txt"
    sample_ids_path.parent.mkdir(parents=True, exist_ok=True)
    sample_ids_path.write_text("".join(f"{sample_id}\n" for sample_id in common_order), encoding="utf-8")
    excluded_path = args.output_sample_release / "excluded-sample-ids.txt"
    excluded_path.write_text("".join(f"{sample_id}\n" for sample_id in excluded), encoding="utf-8")
    artifacts[sample_ids_path.name] = {
        "rows": len(common_order),
        "sha256": sha256_file(sample_ids_path),
    }
    artifacts[excluded_path.name] = {
        "rows": len(excluded),
        "sha256": sha256_file(excluded_path),
    }

    complete_config = dict(config)
    complete_config["schema_version"] = (
        "memcalib-v24-multidomain-complete-case-sample-evaluation-config-v1"
    )
    complete_config["sample_count"] = len(common_order)
    complete_config["release"] = args.output_sample_release.name
    complete_config["sampling"] = {
        **dict(config.get("sampling") or {}),
        "complete_case_policy": (
            "intersection of valid answer sample IDs across every model-condition cell"
        ),
        "locked_parent_sample_count": len(sample_order),
        "excluded_sample_count": len(excluded),
        "exclusion_audit": str(excluded_path),
    }
    write_json(args.output_config, complete_config)

    manifest = {
        "schema_version": "memcalib-complete-case-answer-run-v1",
        "status": "completed",
        "policy": (
            "Globally exclude any sample missing from at least one model-condition cell; "
            "do not impute or regenerate answers."
        ),
        "locked_parent_samples": len(sample_order),
        "complete_case_samples": len(common_order),
        "excluded_samples": len(excluded),
        "model_condition_cells": len(cell_requests),
        "formal_answers": len(common_order) * len(cell_requests),
        "missing_by_cell": {
            key: values for key, values in sorted(missing_by_cell.items()) if values
        },
        "excluded_sample_ids": excluded,
        "artifacts": dict(sorted(artifacts.items())),
    }
    write_json(args.manifest, manifest)
    release_manifest = {
        **manifest,
        "source_release": str(args.sample_release),
        "config": {
            "path": str(args.output_config),
            "sha256": sha256_file(args.output_config),
        },
    }
    write_json(args.output_sample_release / "complete-case.manifest.json", release_manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
