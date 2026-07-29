#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any

from memcalib_v23_common import canonical_sha256, file_sha256, norm_text, portable_path
from memcalib_v24_coding_common import V24_DIR, locked_supervision_fingerprint
from utils import extract_json_object, iter_jsonl, write_json, write_jsonl


DEFAULT_BENCHMARK = V24_DIR / "memcalib_v24_coding_rewrite_3750.valid.jsonl"
DEFAULT_REQUESTS = V24_DIR / "memcalib_v24_coding_independent_qc_input_3750.jsonl"
DEFAULT_RESULTS = V24_DIR / "memcalib_v24_coding_independent_qc_result_3750.jsonl"
DEFAULT_PREFIX = V24_DIR / "memcalib_v24_coding_independent_qc_3750"

QC_SCHEMA = "memcalib-v24-coding-text-independent-qc-v1"
RECORD_CHECKS = (
    "task_family_fidelity",
    "natural_language_only",
    "semantic_equivalence",
    "reference_completeness",
    "runtime_independence",
)
SELF_CHECK_KEYS = {
    "all_record_checks_exact",
    "all_atom_ids_exact_and_unique",
    "labels_rejudged_not_assumed",
    "answer_text_only_standard_applied",
}
VERDICTS = {"pass", "review", "fail"}
DECISION_ORDER = {"strict_pass": 0, "review": 1, "reject": 2}


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


def worsen(current: str, candidate: str) -> str:
    return candidate if DECISION_ORDER[candidate] > DECISION_ORDER[current] else current


def validate_qc(
    qc: dict[str, Any],
    record: dict[str, Any],
    params: dict[str, Any],
) -> tuple[list[str], str, list[str]]:
    errors: list[str] = []
    reasons: list[str] = []
    decision = "strict_pass"
    if qc.get("schema_version") != QC_SCHEMA:
        errors.append("schema_version_mismatch")
    if str(qc.get("record_id") or "") != str(record.get("id") or ""):
        errors.append("record_id_mismatch")

    record_checks = qc.get("record_checks")
    observed_record_checks: list[str] = []
    if not isinstance(record_checks, list):
        errors.append("record_checks_not_list")
        record_checks = []
    for index, check in enumerate(record_checks):
        if not isinstance(check, dict):
            errors.append(f"record_check_{index}_not_object")
            continue
        name = str(check.get("check") or "")
        observed_record_checks.append(name)
        verdict = check.get("verdict")
        reason = check.get("reason")
        if verdict not in VERDICTS:
            errors.append(f"record_check_{index}_bad_verdict")
        elif verdict == "fail":
            decision = "reject"
            reasons.append(f"{name}:fail")
        elif verdict == "review":
            decision = worsen(decision, "review")
            reasons.append(f"{name}:review")
        if not isinstance(reason, str) or len(norm_text(reason)) < 8:
            errors.append(f"record_check_{index}_reason_missing")
    if observed_record_checks != list(RECORD_CHECKS):
        errors.append("record_checks_order_or_coverage_mismatch")

    expected_atom_ids = [
        str(atom.get("atom_id") or "") for atom in record.get("memories") or []
    ]
    atom_checks = qc.get("atom_checks")
    observed_atom_ids: list[str] = []
    if not isinstance(atom_checks, list):
        errors.append("atom_checks_not_list")
        atom_checks = []
    for index, check in enumerate(atom_checks):
        if not isinstance(check, dict):
            errors.append(f"atom_check_{index}_not_object")
            continue
        atom_id = str(check.get("atom_id") or "")
        observed_atom_ids.append(atom_id)
        for key in (
            "label_action_validity",
            "answer_text_observability",
            "rubric_objectivity",
        ):
            verdict = check.get(key)
            if verdict not in VERDICTS:
                errors.append(f"atom_check_{index}_{key}_bad_verdict")
            elif verdict == "fail":
                decision = "reject"
                reasons.append(f"{atom_id}:{key}:fail")
            elif verdict == "review":
                decision = worsen(decision, "review")
                reasons.append(f"{atom_id}:{key}:review")
        value_status = check.get("query_value_status")
        if value_status not in {
            "not_supplied",
            "partially_supplied",
            "fully_supplied",
        }:
            errors.append(f"atom_check_{index}_bad_query_value_status")
        elif value_status != "not_supplied":
            decision = "reject"
            reasons.append(f"{atom_id}:query_value_status:{value_status}")
        reason = check.get("reason")
        if not isinstance(reason, str) or len(norm_text(reason)) < 8:
            errors.append(f"atom_check_{index}_reason_missing")
    if len(observed_atom_ids) != len(set(observed_atom_ids)):
        errors.append("atom_check_ids_not_unique")
    if set(observed_atom_ids) != set(expected_atom_ids):
        errors.append("atom_checks_coverage_mismatch")

    declared = qc.get("declared_decision")
    if declared not in DECISION_ORDER:
        errors.append("bad_declared_decision")
    elif DECISION_ORDER[declared] > DECISION_ORDER[decision]:
        decision = declared
        reasons.append(f"judge_declared_{declared}")
    declared_reasons = qc.get("decision_reasons")
    if not isinstance(declared_reasons, list) or any(
        not isinstance(reason, str) or len(norm_text(reason)) < 4
        for reason in declared_reasons
    ):
        errors.append("decision_reasons_invalid")

    self_check = qc.get("self_check")
    if not isinstance(self_check, dict):
        errors.append("self_check_not_object")
    else:
        if set(self_check) != SELF_CHECK_KEYS:
            errors.append("self_check_keys_mismatch")
        for key in SELF_CHECK_KEYS:
            if self_check.get(key) is not True:
                errors.append(f"self_check.{key}_not_true")
    return errors, decision, reasons


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Postprocess MemCalib v2.4 coding text-observability QC."
    )
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--prefix", type=Path, default=DEFAULT_PREFIX)
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
    outputs: dict[str, list[dict[str, Any]]] = {
        "strict_pass": [],
        "review": [],
        "reject": [],
        "invalid": [],
        "adjudicated": [],
    }
    for request in requests:
        request_id = str(request.get("request_id") or "")
        params = request_params(request)
        record_id = str(params.get("record_id") or "")
        source = benchmarks.get(record_id)
        result = results.get(request_id)
        structural_errors: list[str] = []
        if source is None:
            structural_errors.append("source_record_missing")
        else:
            if canonical_sha256(source) != params.get("record_fingerprint"):
                structural_errors.append("source_record_fingerprint_mismatch")
            if locked_supervision_fingerprint(source) != params.get(
                "locked_supervision_fingerprint"
            ):
                structural_errors.append("locked_supervision_fingerprint_mismatch")
            expected_ids = [
                str(atom.get("atom_id") or "")
                for atom in source.get("memories") or []
            ]
            if expected_ids != params.get("expected_atom_ids"):
                structural_errors.append("expected_atom_ids_mismatch")
        if result is None:
            structural_errors.append("api_result_missing")
        qc: dict[str, Any] | None = None
        if result is not None:
            if request_params(result) and request_params(result) != params:
                structural_errors.append("result_params_mismatch")
            try:
                qc = extract_json_object(output_text(result))
            except (ValueError, json.JSONDecodeError) as exc:
                structural_errors.append(f"invalid_json:{exc}")
        decision = "invalid"
        reasons: list[str] = []
        if source is not None and qc is not None and not structural_errors:
            qc_errors, decision, reasons = validate_qc(qc, source, params)
            structural_errors.extend(qc_errors)
        if structural_errors:
            outputs["invalid"].append(
                {
                    "request_id": request_id,
                    "record_id": record_id,
                    "errors": structural_errors,
                    "result_present": result is not None,
                }
            )
            continue
        assert source is not None and qc is not None
        record = copy.deepcopy(source)
        record["v24_coding_independent_qc"] = {
            "schema_version": QC_SCHEMA,
            "request_id": request_id,
            "decision": decision,
            "decision_reasons": reasons,
            "judge_output": qc,
        }
        outputs[decision].append(record)
        outputs["adjudicated"].append(record)

    paths = {
        "strict_pass": args.prefix.with_suffix(".strict.jsonl"),
        "review": args.prefix.with_suffix(".review.jsonl"),
        "reject": args.prefix.with_suffix(".reject.jsonl"),
        "invalid": args.prefix.with_suffix(".invalid.jsonl"),
        "adjudicated": args.prefix.with_suffix(".adjudicated.jsonl"),
    }
    for key, path in paths.items():
        write_jsonl(path, outputs[key])
    summary_path = args.prefix.with_suffix(".summary.json")
    summary = {
        "schema_version": "memcalib-v24-coding-text-independent-qc-summary-v1",
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
        "counts": {key: len(rows) for key, rows in outputs.items()},
        "by_task_family": {
            decision: dict(
                sorted(
                    Counter(
                        record["coding_text_observability_revision"]["task_family"]
                        for record in outputs[decision]
                    ).items()
                )
            )
            for decision in ("strict_pass", "review", "reject")
        },
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
