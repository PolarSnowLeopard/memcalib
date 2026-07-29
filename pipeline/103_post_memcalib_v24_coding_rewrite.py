#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any

from memcalib_v23_common import canonical_sha256, file_sha256, portable_path
from memcalib_v24_coding_common import (
    CODE_FENCE_RE,
    CONSTRUCTION_TARGET_KEYS,
    COUNTERFACTUAL_KEYS,
    QUESTION_SUFFIXES,
    REVISION_SCHEMA,
    USAGE_RUBRIC_KEYS,
    V23_RELEASE,
    V24_DIR,
    applicable_atoms,
    build_atom_supervision,
    locked_supervision_fingerprint,
    materialize_question,
    normalized_contains,
    validate_revision_payload,
)
from utils import extract_json_object, iter_jsonl, write_json, write_jsonl


DEFAULT_REQUESTS = V24_DIR / "memcalib_v24_coding_rewrite_input_3750.jsonl"
DEFAULT_RESULTS = V24_DIR / "memcalib_v24_coding_rewrite_result_3750.jsonl"
DEFAULT_PREFIX = V24_DIR / "memcalib_v24_coding_rewrite_3750"


def request_params(row: dict[str, Any]) -> dict[str, Any]:
    return (
        row.get("passParams")
        or row.get("user_defined_params")
        or row.get("params")
        or {}
    )


def output_text(row: dict[str, Any]) -> str:
    for key in ("response", "output", "content", "text", "answer"):
        if isinstance(row.get(key), str) and row[key].strip():
            return row[key]
    raw = row.get("raw_response")
    if isinstance(raw, dict):
        choices = raw.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            message = choices[0].get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
    raise ValueError("no_model_output_text")


def repair_missing_verbatim_evidence(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    repaired = copy.deepcopy(payload)
    reference = repaired.get("reference_answer")
    if not isinstance(reference, str):
        return repaired, []
    additions: list[str] = []
    for footprint in repaired.get("applicable_atom_footprints") or []:
        if not isinstance(footprint, dict):
            continue
        required = footprint.get("required_answer_elements")
        if not isinstance(required, list) or not 1 <= len(required) <= 3:
            continue
        for element in required:
            if (
                isinstance(element, str)
                and element.strip()
                and not normalized_contains(reference, element)
            ):
                additions.append(element.strip())
    additions = list(dict.fromkeys(additions))
    if additions:
        appendix = " ".join(
            f"{element.rstrip('.')}." for element in additions
        )
        repaired["reference_answer"] = (
            reference.rstrip()
            + "\n\nRequired answer evidence stated explicitly: "
            + appendix
        )
    return repaired, additions


def build_record(
    source: dict[str, Any],
    payload: dict[str, Any],
    params: dict[str, Any],
    request_id: str,
    deterministic_repairs: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    record = copy.deepcopy(source)
    original_question = str(source.get("question") or "")
    original_answer = str(source.get("source_answer") or "")
    family = str(payload["task_family"])
    record["question"] = materialize_question(str(payload["task_stem"]), family)
    record["source_answer"] = str(payload["reference_answer"]).strip()

    footprints = {
        str(item["atom_id"]): item
        for item in payload["applicable_atom_footprints"]
    }
    for atom in record.get("memories") or []:
        atom_id = str(atom.get("atom_id") or "")
        supervision = build_atom_supervision(atom, footprints.get(atom_id))
        atom.update(supervision)

    record["schema_version"] = "crk-2-canonical-memory-v2.4"
    record["coding_text_observability_revision"] = {
        "schema_version": REVISION_SCHEMA,
        "request_id": request_id,
        "task_family": family,
        "retry_round": params.get("retry_round", 0),
        "retry_feedback_fingerprint": params.get("retry_feedback_fingerprint"),
        "source_record_fingerprint": params["source_record_fingerprint"],
        "locked_supervision_fingerprint": params["locked_supervision_fingerprint"],
        "memory_blocks_fingerprint": params["memory_blocks_fingerprint"],
        "original_question_fingerprint": canonical_sha256(original_question),
        "original_reference_answer_fingerprint": canonical_sha256(original_answer),
        "question_contract": "natural_language_only_no_code_blocks",
        "labels_and_actions_locked": True,
        "memory_atoms_and_blocks_locked": True,
        "rubrics_rebuilt_for_answer_text": True,
        "deterministic_repairs": deterministic_repairs or [],
    }
    audit = {
        "schema_version": "memcalib-v24-coding-text-rewrite-audit-v1",
        "record_id": record["id"],
        "request_id": request_id,
        "task_family": family,
        "retry_round": params.get("retry_round", 0),
        "retry_feedback_fingerprint": params.get("retry_feedback_fingerprint"),
        "source_record_fingerprint": params["source_record_fingerprint"],
        "output_record_fingerprint": canonical_sha256(record),
        "original_question": original_question,
        "revised_question": record["question"],
        "original_reference_answer": original_answer,
        "revised_reference_answer": record["source_answer"],
        "applicable_atom_footprints": payload["applicable_atom_footprints"],
        "query_isolation_audit": payload["query_isolation_audit"],
        "deterministic_repairs": deterministic_repairs or [],
    }
    return record, audit


def validate_built_record(
    record: dict[str, Any],
    source: dict[str, Any],
    params: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if record.get("domain") != "coding":
        errors.append("domain_changed")
    family = params.get("task_family")
    question = str(record.get("question") or "")
    answer = str(record.get("source_answer") or "")
    if not question.endswith(QUESTION_SUFFIXES[str(family)]):
        errors.append("standard_question_contract_missing")
    if CODE_FENCE_RE.search(question):
        errors.append("question_contains_code_fence")
    if CODE_FENCE_RE.search(answer):
        errors.append("reference_answer_contains_code_fence")
    if record.get("memory_blocks") != source.get("memory_blocks"):
        errors.append("memory_blocks_changed")
    if locked_supervision_fingerprint(record) != params.get(
        "locked_supervision_fingerprint"
    ):
        errors.append("locked_supervision_changed")

    source_ids = [
        str(atom.get("atom_id") or "") for atom in source.get("memories") or []
    ]
    output_ids = [
        str(atom.get("atom_id") or "") for atom in record.get("memories") or []
    ]
    if output_ids != source_ids:
        errors.append("atom_order_or_coverage_changed")
    for index, atom in enumerate(record.get("memories") or []):
        prefix = f"atom_{index}"
        target = atom.get("construction_target")
        contract = atom.get("counterfactual_contract")
        rubric = atom.get("usage_rubric")
        if not isinstance(target, dict) or set(target) != CONSTRUCTION_TARGET_KEYS:
            errors.append(f"{prefix}_construction_target_invalid")
        if not isinstance(contract, dict) or set(contract) != COUNTERFACTUAL_KEYS:
            errors.append(f"{prefix}_counterfactual_contract_invalid")
            continue
        if not isinstance(rubric, dict) or set(rubric) != USAGE_RUBRIC_KEYS:
            errors.append(f"{prefix}_usage_rubric_invalid")
            continue
        label = atom.get("u_star")
        action = atom.get("memory_action")
        expected_weight = {"A": "none", "B": "supporting", "C": "controlling"}.get(
            label
        )
        if rubric.get("memory_usage_weight") != expected_weight:
            errors.append(f"{prefix}_rubric_weight_mismatch")
        evidence = contract.get("minimal_evidence")
        delta = str(contract.get("observable_delta") or "")
        if label == "A":
            if action != "ignore":
                errors.append(f"{prefix}_A_action_invalid")
            if delta != "none" or evidence != []:
                errors.append(f"{prefix}_A_counterfactual_invalid")
        else:
            if action not in {"apply", "correct"}:
                errors.append(f"{prefix}_BC_action_invalid")
            if delta == "none" or not isinstance(evidence, list) or not evidence:
                errors.append(f"{prefix}_BC_counterfactual_invalid")
            elif any(
                not isinstance(item, str) or not normalized_contains(answer, item)
                for item in evidence
            ):
                errors.append(f"{prefix}_minimal_evidence_not_in_reference")
        checks = rubric.get("observable_checks")
        if not isinstance(checks, list) or len(checks) < 2:
            errors.append(f"{prefix}_observable_checks_invalid")
        elif any(
            not isinstance(check, str) or "answer" not in check.casefold()
            for check in checks
        ):
            errors.append(f"{prefix}_observable_check_not_answer_text_based")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Postprocess MemCalib v2.4 coding text-observability rewrites."
    )
    parser.add_argument("--benchmark", type=Path, default=V23_RELEASE)
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--prefix", type=Path, default=DEFAULT_PREFIX)
    parser.add_argument(
        "--repair-missing-verbatim-evidence",
        action="store_true",
        help=(
            "Append model-declared required evidence that is missing verbatim from "
            "the hidden reference answer, then rerun all validators."
        ),
    )
    args = parser.parse_args()

    benchmarks = {
        str(record.get("id") or ""): record for record in iter_jsonl(args.benchmark)
    }
    requests = list(iter_jsonl(args.requests))
    result_rows = list(iter_jsonl(args.results))
    results = {
        str(result.get("request_id") or ""): result for result in result_rows
    }
    if len(results) != len(result_rows):
        raise ValueError("result request IDs must be unique")

    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for request in requests:
        request_id = str(request.get("request_id") or "")
        params = request_params(request)
        record_id = str(params.get("record_id") or "")
        source = benchmarks.get(record_id)
        result = results.get(request_id)
        errors: list[str] = []
        if source is None:
            errors.append("source_record_missing")
        else:
            if source.get("domain") != "coding":
                errors.append("source_not_coding")
            if canonical_sha256(source) != params.get("source_record_fingerprint"):
                errors.append("source_record_fingerprint_mismatch")
            if locked_supervision_fingerprint(source) != params.get(
                "locked_supervision_fingerprint"
            ):
                errors.append("locked_supervision_fingerprint_mismatch")
            if canonical_sha256(source.get("memory_blocks") or []) != params.get(
                "memory_blocks_fingerprint"
            ):
                errors.append("memory_blocks_fingerprint_mismatch")
        if result is None:
            errors.append("api_result_missing")
        payload: dict[str, Any] | None = None
        deterministic_repairs: list[str] = []
        if result is not None:
            if request_params(result) and request_params(result) != params:
                errors.append("result_params_mismatch")
            try:
                payload = extract_json_object(output_text(result))
            except (ValueError, json.JSONDecodeError) as exc:
                errors.append(f"invalid_json:{exc}")
        if (
            payload is not None
            and args.repair_missing_verbatim_evidence
            and not errors
        ):
            payload, added_evidence = repair_missing_verbatim_evidence(payload)
            deterministic_repairs.extend(
                f"reference_answer_verbatim_evidence:{evidence}"
                for evidence in added_evidence
            )
        if source is not None and payload is not None and not errors:
            errors.extend(validate_revision_payload(payload, source, params))
        record: dict[str, Any] | None = None
        audit: dict[str, Any] | None = None
        if source is not None and payload is not None and not errors:
            record, audit = build_record(
                source,
                payload,
                params,
                request_id,
                deterministic_repairs=deterministic_repairs,
            )
            errors.extend(validate_built_record(record, source, params))
        if errors:
            invalid.append(
                {
                    "request_id": request_id,
                    "record_id": record_id,
                    "errors": errors,
                    "result_present": result is not None,
                }
            )
            continue
        assert record is not None and audit is not None
        valid.append(record)
        audits.append(audit)

    paths = {
        "valid": args.prefix.with_suffix(".valid.jsonl"),
        "invalid": args.prefix.with_suffix(".invalid.jsonl"),
        "audit": args.prefix.with_suffix(".audit.jsonl"),
    }
    write_jsonl(paths["valid"], valid)
    write_jsonl(paths["invalid"], invalid)
    write_jsonl(paths["audit"], audits)
    summary_path = args.prefix.with_suffix(".summary.json")
    summary = {
        "schema_version": "memcalib-v24-coding-text-rewrite-summary-v1",
        "inputs": {
            "benchmark": {
                "path": portable_path(args.benchmark),
                "sha256": file_sha256(args.benchmark),
            },
            "requests": {
                "path": portable_path(args.requests),
                "sha256": file_sha256(args.requests),
                "count": len(requests),
            },
            "results": {
                "path": portable_path(args.results),
                "sha256": file_sha256(args.results),
                "count": len(result_rows),
            },
        },
        "counts": {
            "requests": len(requests),
            "valid": len(valid),
            "invalid": len(invalid),
            "records_with_deterministic_repairs": sum(
                bool(record["coding_text_observability_revision"].get("deterministic_repairs"))
                for record in valid
            ),
        },
        "task_family": dict(
            sorted(
                Counter(
                    record["coding_text_observability_revision"]["task_family"]
                    for record in valid
                ).items()
            )
        ),
        "outputs": {
            key: {
                "path": portable_path(path),
                "sha256": file_sha256(path),
            }
            for key, path in paths.items()
        },
    }
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
