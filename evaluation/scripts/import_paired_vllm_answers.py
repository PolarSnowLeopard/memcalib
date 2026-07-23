#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation.common import (
    display_path,
    iter_jsonl,
    request_fingerprint,
    sha256_file,
    write_json,
    write_jsonl,
)


ROOT = Path(__file__).resolve().parents[2]


def _write_jsonl_gz(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    ).encode("utf-8")
    path.write_bytes(gzip.compress(payload, compresslevel=9, mtime=0))


def _finish_reason(row: dict[str, Any]) -> str:
    choices = (row.get("raw_response") or {}).get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return ""
    return str(choices[0].get("finish_reason") or "")


def _has_reasoning_trace(row: dict[str, Any]) -> bool:
    choices = (row.get("raw_response") or {}).get("choices") or []
    message = (
        choices[0].get("message") or {}
        if choices and isinstance(choices[0], dict)
        else {}
    )
    if str(message.get("reasoning_content") or "").strip():
        return True
    response = str(row.get("response") or "").lower()
    return "<think>" in response or "</think>" in response


def validate_model_answers(
    requests: list[dict[str, Any]],
    answers: list[dict[str, Any]],
    returned_model: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    requests_by_id = {str(row["request_id"]): row for row in requests}
    if len(requests_by_id) != len(requests):
        raise ValueError("answer request IDs are not unique")

    answer_id_counts = Counter(str(row.get("request_id") or "") for row in answers)
    errors: Counter[str] = Counter()
    by_sample: dict[str, dict[str, Any]] = {}
    for row in answers:
        request_id = str(row.get("request_id") or "")
        source = requests_by_id.get(request_id)
        if source is None:
            errors["unexpected_request_id"] += 1
            continue
        if answer_id_counts[request_id] != 1:
            errors["duplicate_request_id"] += 1
            continue
        if row.get("input_fingerprint") != request_fingerprint(source):
            errors["input_fingerprint_mismatch"] += 1
        if not str(row.get("response") or "").strip():
            errors["empty_response"] += 1
        if _finish_reason(row) != "stop":
            errors["non_stop_finish_reason"] += 1
        response_model = str((row.get("raw_response") or {}).get("model") or "")
        if response_model != returned_model:
            errors["returned_model_mismatch"] += 1
        if row.get("error"):
            errors["error_field_present"] += 1
        if _has_reasoning_trace(row):
            errors["reasoning_trace_present"] += 1

        source_params = source.get("user_defined_params") or {}
        answer_params = row.get("user_defined_params") or {}
        sample_id = str(source_params.get("sample_id") or "")
        if not sample_id or sample_id != str(answer_params.get("sample_id") or ""):
            errors["sample_id_mismatch"] += 1
            continue
        if sample_id in by_sample:
            errors["duplicate_sample_id"] += 1
            continue
        by_sample[sample_id] = row

    if errors:
        raise ValueError(f"invalid answer rows: {dict(sorted(errors.items()))}")
    return by_sample, {
        "request_rows": len(requests),
        "answer_rows": len(answers),
        "unique_answer_request_ids": len(answer_id_counts),
        "unique_answer_sample_ids": len(by_sample),
        "returned_model": returned_model,
        "finish_reasons": {"stop": len(answers)},
        "reasoning_trace_rows": 0,
    }


def import_paired_answers(
    *,
    source_root: Path,
    source_release: Path,
    config_template_path: Path,
    output_run: Path,
    output_release: Path,
    output_config_path: Path,
    returned_models: dict[str, str],
    source_archive_sha256: str | None = None,
) -> dict[str, Any]:
    hidden = list(iter_jsonl(source_release / "hidden-evaluation.jsonl"))
    model_facing = list(iter_jsonl(source_release / "model-facing.jsonl"))
    hidden_by_id = {str(row["id"]): row for row in hidden}
    facing_by_id = {str(row["id"]): row for row in model_facing}
    if len(hidden_by_id) != len(hidden) or len(facing_by_id) != len(model_facing):
        raise ValueError("source release sample IDs are not unique")
    if set(hidden_by_id) != set(facing_by_id):
        raise ValueError("source hidden and model-facing sample IDs differ")

    model_answers: dict[str, dict[str, dict[str, Any]]] = {}
    model_requests: dict[str, dict[str, dict[str, Any]]] = {}
    model_summaries: dict[str, Any] = {}
    for model_key, returned_model in returned_models.items():
        request_path = source_root / "requests" / "answers" / model_key / "full_memory.jsonl"
        answer_path = source_root / "answers" / model_key / "full_memory.jsonl"
        requests = list(iter_jsonl(request_path))
        answers = list(iter_jsonl(answer_path))
        answers_by_sample, summary = validate_model_answers(requests, answers, returned_model)
        request_sample_ids = [
            str((row.get("user_defined_params") or {}).get("sample_id") or "")
            for row in requests
        ]
        if any(not sample_id for sample_id in request_sample_ids):
            raise ValueError(f"{model_key} has a request without sample_id")
        requests_by_sample = dict(zip(request_sample_ids, requests, strict=True))
        if len(requests_by_sample) != len(requests):
            raise ValueError(f"{model_key} request sample IDs are not unique")
        model_answers[model_key] = answers_by_sample
        model_requests[model_key] = requests_by_sample
        model_summaries[model_key] = {
            **summary,
            "source_request_path": f"requests/answers/{model_key}/full_memory.jsonl",
            "source_request_sha256": sha256_file(request_path),
            "source_answer_path": f"answers/{model_key}/full_memory.jsonl",
            "source_answer_sha256": sha256_file(answer_path),
        }

    common_ids = set(hidden_by_id)
    for rows in model_answers.values():
        common_ids &= set(rows)
    ordered_ids = [str(row["id"]) for row in hidden if str(row["id"]) in common_ids]
    if not ordered_ids:
        raise ValueError("models have no common completed samples")

    paired_hidden = [hidden_by_id[sample_id] for sample_id in ordered_ids]
    paired_model_facing = [facing_by_id[sample_id] for sample_id in ordered_ids]
    hidden_path = output_release / "hidden-evaluation.jsonl.gz"
    model_facing_path = output_release / "model-facing.jsonl.gz"
    _write_jsonl_gz(hidden_path, paired_hidden)
    _write_jsonl_gz(model_facing_path, paired_model_facing)
    sample_ids_path = output_release / "sample-ids.txt"
    sample_ids_path.parent.mkdir(parents=True, exist_ok=True)
    sample_ids_path.write_text("".join(f"{sample_id}\n" for sample_id in ordered_ids), encoding="utf-8")

    for model_key in returned_models:
        request_rows = [model_requests[model_key][sample_id] for sample_id in ordered_ids]
        answer_rows = [model_answers[model_key][sample_id] for sample_id in ordered_ids]
        write_jsonl(output_run / "requests" / "answers" / model_key / "full_memory.jsonl", request_rows)
        write_jsonl(output_run / "answers" / model_key / "full_memory.jsonl", answer_rows)

    config = copy.deepcopy(json.loads(config_template_path.read_text(encoding="utf-8")))
    config["schema_version"] = "memcalib-v23-vllm-sft-paired-full-only-config-v1"
    config["sample_count"] = len(ordered_ids)
    config["release"] = output_release.name
    config["evaluation_modes"]["leaderboard_required_conditions"] = ["full_memory"]
    config["evaluation_modes"]["official_research_conditions"] = ["full_memory"]
    config["evaluation_modes"]["primary_metrics_condition"] = "full_memory"
    config["evaluation_modes"].pop("counterfactual_condition", None)
    config["source_inputs"]["paired_sample_ordered_id_sha256"] = sha256_file(sample_ids_path)
    config["source_inputs"]["source_hidden_sha256"] = sha256_file(source_release / "hidden-evaluation.jsonl")
    for model in config["answer_models"]:
        model_key = str(model["key"])
        if model_key not in returned_models:
            raise ValueError(f"config contains unimported answer model: {model_key}")
        model["served_model_name"] = returned_models[model_key]
    config["secondary_judge_sampling"]["total"] = (
        int(config["secondary_judge_sampling"]["per_model_per_condition"]) * len(returned_models)
    )
    write_json(output_config_path, config)

    omitted = {
        model_key: [
            sample_id for sample_id in hidden_by_id if sample_id not in model_answers[model_key]
        ]
        for model_key in returned_models
    }
    manifest = {
        "schema_version": "memcalib-v23-vllm-paired-answer-import-v1",
        "status": "validated",
        "condition": "full_memory",
        "source_archive_sha256": source_archive_sha256,
        "source_sample_count": len(hidden),
        "paired_sample_count": len(ordered_ids),
        "model_summaries": model_summaries,
        "omitted_sample_ids_by_model": omitted,
        "common_sample_order": {
            "path": display_path(sample_ids_path, ROOT),
            "sha256": sha256_file(sample_ids_path),
        },
        "artifacts": {
            "config": {
                "path": display_path(output_config_path, ROOT),
                "sha256": sha256_file(output_config_path),
            },
            "hidden": {
                "path": display_path(hidden_path, ROOT),
                "sha256": sha256_file(hidden_path),
                "rows": len(paired_hidden),
            },
            "model_facing": {
                "path": display_path(model_facing_path, ROOT),
                "sha256": sha256_file(model_facing_path),
                "rows": len(paired_model_facing),
            },
            "answers": {
                model_key: {
                    "path": display_path(
                        output_run / "answers" / model_key / "full_memory.jsonl", ROOT
                    ),
                    "sha256": sha256_file(
                        output_run / "answers" / model_key / "full_memory.jsonl"
                    ),
                    "rows": len(ordered_ids),
                }
                for model_key in returned_models
            },
        },
    }
    write_json(output_release / "paired-answer-import.manifest.json", manifest)
    return manifest


def _parse_model(value: str) -> tuple[str, str]:
    key, separator, returned_model = value.partition("=")
    if not separator or not key or not returned_model:
        raise argparse.ArgumentTypeError("--model must use MODEL_KEY=RETURNED_MODEL")
    return key, returned_model


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate and pair imported vLLM full-memory answers."
    )
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--source-release", type=Path, required=True)
    parser.add_argument("--config-template", type=Path, required=True)
    parser.add_argument("--output-run", type=Path, required=True)
    parser.add_argument("--output-release", type=Path, required=True)
    parser.add_argument("--output-config", type=Path, required=True)
    parser.add_argument("--source-archive-sha256")
    parser.add_argument("--model", action="append", type=_parse_model, required=True)
    args = parser.parse_args()
    returned_models = dict(args.model)
    if len(returned_models) != len(args.model):
        raise ValueError("duplicate --model keys")
    manifest = import_paired_answers(
        source_root=args.source_root,
        source_release=args.source_release,
        config_template_path=args.config_template,
        output_run=args.output_run,
        output_release=args.output_release,
        output_config_path=args.output_config,
        returned_models=returned_models,
        source_archive_sha256=args.source_archive_sha256,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
