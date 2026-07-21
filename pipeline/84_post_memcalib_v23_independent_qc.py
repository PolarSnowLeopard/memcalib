#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any

from memcalib_v23_common import (
    V23_DIR,
    atom_index,
    canonical_sha256,
    file_sha256,
    norm_text,
    portable_path,
)
from utils import extract_json_object, iter_jsonl, write_json, write_jsonl


DEFAULT_BENCHMARK = V23_DIR / "memcalib_v23_rewritten_benchmark_15000.jsonl"
DEFAULT_REQUESTS = V23_DIR / "memcalib_v23_independent_qc_input_15000.jsonl"
DEFAULT_RESULTS = V23_DIR / "memcalib_v23_independent_qc_result_15000.jsonl"
DEFAULT_PREFIX = V23_DIR / "memcalib_v23_independent_qc_15000"

QC_SCHEMA = "memcalib-v23-composite-independent-qc-v1"
SELF_CHECK_KEYS = {
    "all_added_atom_ids_exact",
    "all_block_ids_exact",
    "all_block_atom_coverage_exact",
    "locked_supervision_not_rejudged",
}
DECISION_ORDER = {"strict_pass": 0, "review": 1, "reject": 2}


def request_params(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("passParams") or row.get("user_defined_params") or row.get("params") or {}


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
    qc: dict[str, Any], record: dict[str, Any], params: dict[str, Any]
) -> tuple[list[str], str, list[str]]:
    errors: list[str] = []
    reasons: list[str] = []
    decision = "strict_pass"
    if qc.get("schema_version") != QC_SCHEMA:
        errors.append("schema_version_mismatch")
    if str(qc.get("record_id") or "") != str(record.get("id") or ""):
        errors.append("record_id_mismatch")

    expected_added = [str(atom_id) for atom_id in params.get("added_atom_ids") or []]
    checks = qc.get("added_atom_checks")
    observed_added: list[str] = []
    if not isinstance(checks, list):
        errors.append("added_atom_checks_not_list")
    else:
        for index, check in enumerate(checks):
            if not isinstance(check, dict):
                errors.append(f"added_atom_check_{index}_not_object")
                continue
            atom_id = str(check.get("atom_id") or "")
            observed_added.append(atom_id)
            atomicity = check.get("atomicity")
            plausibility = check.get("same_user_plausibility")
            relation = check.get("query_relation")
            footprint = check.get("answer_footprint")
            correction = check.get("explicit_correction_required")
            distinct = check.get("distinct_from_block_atoms")
            coherence = check.get("block_coherence")
            if atomicity not in {"pass", "fail"}:
                errors.append(f"atom_{index}_bad_atomicity")
            elif atomicity == "fail":
                decision = "reject"
                reasons.append(f"{atom_id}:atomicity_fail")
            for key, value in (
                ("same_user_plausibility", plausibility),
                ("distinct_from_block_atoms", distinct),
                ("block_coherence", coherence),
            ):
                if value not in {"pass", "review", "fail"}:
                    errors.append(f"atom_{index}_bad_{key}")
                elif value == "fail":
                    decision = "reject"
                    reasons.append(f"{atom_id}:{key}_fail")
                elif value == "review":
                    decision = worsen(decision, "review")
                    reasons.append(f"{atom_id}:{key}_review")
            if relation not in {"absent", "overlap", "entailed"}:
                errors.append(f"atom_{index}_bad_query_relation")
            elif relation != "absent":
                decision = "reject"
                reasons.append(f"{atom_id}:query_relation_{relation}")
            if footprint not in {"none", "bounded", "controlling"}:
                errors.append(f"atom_{index}_bad_answer_footprint")
            elif footprint != "none":
                decision = "reject"
                reasons.append(f"{atom_id}:answer_footprint_{footprint}")
            if correction not in {True, False}:
                errors.append(f"atom_{index}_bad_explicit_correction_required")
            elif correction:
                decision = "reject"
                reasons.append(f"{atom_id}:explicit_correction_required")
            if len(norm_text(check.get("reason"))) < 8:
                errors.append(f"atom_{index}_reason_missing")
    if observed_added != expected_added:
        errors.append("added_atom_checks_order_or_coverage_mismatch")

    expected_blocks = params.get("expected_blocks") or []
    block_checks = qc.get("block_checks")
    observed_blocks: list[str] = []
    if not isinstance(block_checks, list):
        errors.append("block_checks_not_list")
    else:
        for index, check in enumerate(block_checks):
            if not isinstance(check, dict):
                errors.append(f"block_check_{index}_not_object")
                continue
            parent_id = str(check.get("parent_memory_id") or "")
            observed_blocks.append(parent_id)
            expected_atom_ids = (
                [str(atom_id) for atom_id in expected_blocks[index]["atom_ids"]]
                if index < len(expected_blocks)
                else []
            )
            coverage = check.get("atom_coverage")
            observed_atom_ids: list[str] = []
            if not isinstance(coverage, list):
                errors.append(f"block_{index}_atom_coverage_not_list")
            else:
                for coverage_index, atom_check in enumerate(coverage):
                    if not isinstance(atom_check, dict):
                        errors.append(
                            f"block_{index}_coverage_{coverage_index}_not_object"
                        )
                        continue
                    atom_id = str(atom_check.get("atom_id") or "")
                    observed_atom_ids.append(atom_id)
                    entailed = atom_check.get("entailed_by_memory_text")
                    if entailed not in {"pass", "review", "fail"}:
                        errors.append(
                            f"block_{index}_coverage_{coverage_index}_bad_entailment"
                        )
                    elif entailed == "fail":
                        decision = "reject"
                        reasons.append(f"{parent_id}:{atom_id}:not_entailed")
                    elif entailed == "review":
                        decision = worsen(decision, "review")
                        reasons.append(f"{parent_id}:{atom_id}:entailment_review")
                    if len(norm_text(atom_check.get("fidelity_reason"))) < 8:
                        errors.append(
                            f"block_{index}_coverage_{coverage_index}_reason_missing"
                        )
            if observed_atom_ids != expected_atom_ids:
                errors.append(f"block_{index}_atom_coverage_mismatch")
            for key in ("critical_value_fidelity", "natural_paragraph"):
                value = check.get(key)
                if value not in {"pass", "review", "fail"}:
                    errors.append(f"block_{index}_bad_{key}")
                elif value == "fail":
                    decision = "reject"
                    reasons.append(f"{parent_id}:{key}_fail")
                elif value == "review":
                    decision = worsen(decision, "review")
                    reasons.append(f"{parent_id}:{key}_review")
            extras = check.get("extra_propositions")
            if extras not in {"none", "review", "present"}:
                errors.append(f"block_{index}_bad_extra_propositions")
            elif extras == "present":
                decision = "reject"
                reasons.append(f"{parent_id}:extra_propositions_present")
            elif extras == "review":
                decision = worsen(decision, "review")
                reasons.append(f"{parent_id}:extra_propositions_review")
            contamination = check.get("cross_block_contamination")
            boundaries = check.get("visible_atom_boundaries")
            if contamination not in {True, False}:
                errors.append(f"block_{index}_bad_cross_block_contamination")
            elif contamination:
                decision = "reject"
                reasons.append(f"{parent_id}:cross_block_contamination")
            if boundaries not in {True, False}:
                errors.append(f"block_{index}_bad_visible_atom_boundaries")
            elif boundaries:
                decision = "reject"
                reasons.append(f"{parent_id}:visible_atom_boundaries")
            if len(norm_text(check.get("reason"))) < 8:
                errors.append(f"block_{index}_reason_missing")
    expected_parent_ids = [
        str(block.get("parent_memory_id") or "") for block in expected_blocks
    ]
    if observed_blocks != expected_parent_ids:
        errors.append("block_checks_order_or_coverage_mismatch")

    declared = qc.get("declared_decision")
    if declared not in DECISION_ORDER:
        errors.append("bad_declared_decision")
    elif DECISION_ORDER[declared] > DECISION_ORDER[decision]:
        decision = declared
        reasons.append(f"judge_declared_{declared}")
    declared_reasons = qc.get("decision_reasons")
    if not isinstance(declared_reasons, list) or any(
        len(norm_text(reason)) < 4 for reason in declared_reasons
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
        description="Postprocess MemCalib v2.3 composite-block independent QC."
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
    results = {
        str(result.get("request_id") or ""): result for result in iter_jsonl(args.results)
    }
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
        elif canonical_sha256(source) != params.get("record_fingerprint"):
            structural_errors.append("source_record_fingerprint_mismatch")
        elif canonical_sha256(
            {
                atom_id: atom_index(source)[atom_id].get("text")
                for atom_id in sorted(atom_index(source))
            }
        ) != params.get("all_atom_fingerprint"):
            structural_errors.append("all_atom_fingerprint_mismatch")
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
        record["v23_independent_qc"] = {
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
        "schema_version": "memcalib-v23-composite-independent-qc-summary-v1",
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
                "count": len(results),
            },
        },
        "counts": {key: len(outputs[key]) for key in outputs},
        "by_difficulty": {
            decision: dict(
                sorted(
                    Counter(
                        record["composite_block_revision"]["difficulty_level"]
                        for record in outputs[decision]
                        if isinstance(record, dict)
                        and "composite_block_revision" in record
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
