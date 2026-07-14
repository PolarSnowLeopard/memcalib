#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any

from utils import extract_json_object, iter_jsonl, norm_text, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_BENCHMARK = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_100.jsonl"
DEFAULT_INPUT = SCRIPT_DIR / "data" / "crk2_v2_independent_qc_result_100.jsonl"
DEFAULT_PREFIX = SCRIPT_DIR / "data" / "crk2_v2_independent_qc_100"
ATOM_ENUMS = {
    "query_relation": {"absent", "overlap", "entailed"},
    "atomicity": {"pass", "fail"},
    "label_action_validity": {"pass", "review", "fail"},
    "counterfactual_observability": {"pass", "fail"},
    "rubric_judgeability": {"pass", "review", "fail"},
    "recommended_u_star": {"A", "B", "C"},
    "recommended_memory_action": {"ignore", "apply", "correct"},
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get_params(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("passParams") or row.get("user_defined_params") or row.get("params") or {}


def get_output_text(row: dict[str, Any]) -> str:
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


def normalized_pair(left: str, right: str) -> tuple[str, str]:
    return tuple(sorted((left, right)))


def validate_qc(qc: dict[str, Any], record: dict[str, Any]) -> tuple[list[str], str, list[str]]:
    errors: list[str] = []
    decision_reasons: list[str] = []
    record_id = str(record.get("id") or "")
    if qc.get("schema_version") != "crk-2-independent-qc-v2":
        errors.append("bad_schema_version")
    if str(qc.get("record_id") or "") != record_id:
        errors.append("record_id_mismatch")

    gold = {str(memory.get("atom_id") or ""): memory for memory in record.get("memories", [])}
    expected_ids = set(gold)
    atom_checks = qc.get("atom_checks")
    if not isinstance(atom_checks, list):
        return errors + ["atom_checks_not_list"], "invalid", decision_reasons
    observed_ids: set[str] = set()
    computed = "strict_pass"
    for index, check in enumerate(atom_checks):
        if not isinstance(check, dict):
            errors.append(f"atom_check_{index}_not_object")
            continue
        atom_id = str(check.get("atom_id") or "")
        if atom_id not in expected_ids or atom_id in observed_ids:
            errors.append(f"atom_check_{index}_bad_or_duplicate_id")
        observed_ids.add(atom_id)
        for field, allowed in ATOM_ENUMS.items():
            if check.get(field) not in allowed:
                errors.append(f"atom_check_{index}_bad_{field}")
        if len(norm_text(str(check.get("reason") or ""))) < 10:
            errors.append(f"atom_check_{index}_missing_reason")
        hard_fail = (
            check.get("query_relation") != "absent"
            or check.get("label_action_validity") == "fail"
            or check.get("counterfactual_observability") != "pass"
            or check.get("rubric_judgeability") == "fail"
        )
        if hard_fail:
            computed = "reject"
            decision_reasons.append(f"{atom_id}:hard_failure")
        elif computed != "reject" and check.get("atomicity") != "pass":
            computed = "review"
            decision_reasons.append(f"{atom_id}:atomicity_advisory")
        elif computed != "reject" and (
            check.get("label_action_validity") == "review"
            or check.get("rubric_judgeability") == "review"
            or check.get("recommended_u_star") != gold.get(atom_id, {}).get("u_star")
            or check.get("recommended_memory_action") != gold.get(atom_id, {}).get("memory_action")
        ):
            computed = "review"
            decision_reasons.append(f"{atom_id}:boundary_or_recommendation_change")
    if observed_ids != expected_ids:
        errors.append("atom_check_coverage_mismatch")

    expected_pairs = {normalized_pair(left, right) for left, right in combinations(sorted(expected_ids), 2)}
    pair_checks = qc.get("pair_checks")
    if not isinstance(pair_checks, list):
        errors.append("pair_checks_not_list")
        pair_checks = []
    observed_pairs: set[tuple[str, str]] = set()
    for index, check in enumerate(pair_checks):
        if not isinstance(check, dict):
            errors.append(f"pair_check_{index}_not_object")
            continue
        left = str(check.get("left_atom_id") or "")
        right = str(check.get("right_atom_id") or "")
        pair = normalized_pair(left, right)
        if left == right or pair not in expected_pairs or pair in observed_pairs:
            errors.append(f"pair_check_{index}_bad_or_duplicate_ids")
        observed_pairs.add(pair)
        if check.get("relation") not in {"independent", "overlap", "entails", "contradicts"}:
            errors.append(f"pair_check_{index}_bad_relation")
        elif check.get("relation") != "independent":
            left_memory = gold.get(left, {})
            right_memory = gold.get(right, {})
            same_parent = left_memory.get("parent_memory_id") == right_memory.get("parent_memory_id")
            same_usage = (
                left_memory.get("u_star") == right_memory.get("u_star")
                and left_memory.get("memory_action") == right_memory.get("memory_action")
            )
            advisory_relation = check.get("relation") in {"overlap", "entails"} and same_parent and same_usage
            if advisory_relation and computed != "reject":
                computed = "review"
                decision_reasons.append(f"{left}+{right}:{check.get('relation')}_same_parent_advisory")
            else:
                computed = "reject"
                decision_reasons.append(f"{left}+{right}:{check.get('relation')}_blocking")
        if len(norm_text(str(check.get("reason") or ""))) < 10:
            errors.append(f"pair_check_{index}_missing_reason")
    if observed_pairs != expected_pairs:
        errors.append("pair_check_coverage_mismatch")

    if errors:
        return sorted(set(errors)), "invalid", decision_reasons
    declared = str(qc.get("record_decision") or "")
    if declared not in {"strict_pass", "review", "reject"}:
        errors.append("bad_declared_decision")
        return errors, "invalid", decision_reasons
    if declared != computed:
        decision_reasons.append(f"declared_{declared}_overridden_by_{computed}")
    return [], computed, decision_reasons


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and merge independent CRK-2 v2 semantic QC.")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-prefix", type=Path, default=DEFAULT_PREFIX)
    args = parser.parse_args()

    benchmark = {str(record.get("id") or ""): record for record in iter_jsonl(args.benchmark)}
    buckets: dict[str, list[dict[str, Any]]] = {key: [] for key in ("strict_pass", "review", "reject", "invalid")}
    reason_counts: Counter[str] = Counter()
    seen_records: set[str] = set()
    for line_number, row in enumerate(iter_jsonl(args.input), start=1):
        params = get_params(row)
        record_id = str(params.get("record_id") or "")
        record = benchmark.get(record_id)
        errors: list[str] = []
        try:
            if record is None:
                raise ValueError("unknown_record_id")
            qc = extract_json_object(get_output_text(row))
            errors, decision, decision_reasons = validate_qc(qc, record)
        except Exception as exc:
            qc = {}
            decision = "invalid"
            decision_reasons = []
            errors = [f"parse_error:{type(exc).__name__}:{exc}"]
        if record_id in seen_records:
            errors.append("duplicate_record_result")
            decision = "invalid"
        seen_records.add(record_id)
        if errors:
            reason_counts.update(errors)
            buckets["invalid"].append(
                {"record_id": record_id, "line_number": line_number, "errors": sorted(set(errors)), "parsed_qc": qc}
            )
            continue
        merged = dict(record)
        merged["independent_qc"] = {
            "schema_version": "crk-2-independent-qc-v2",
            "decision": decision,
            "declared_decision": qc.get("record_decision"),
            "decision_reasons": decision_reasons,
            "atom_checks": qc.get("atom_checks"),
            "pair_checks": qc.get("pair_checks"),
            "issues": qc.get("issues") if isinstance(qc.get("issues"), list) else [],
        }
        buckets[decision].append(merged)

    missing = sorted(set(benchmark) - seen_records)
    for record_id in missing:
        buckets["invalid"].append({"record_id": record_id, "errors": ["missing_qc_result"]})
        reason_counts["missing_qc_result"] += 1

    output_paths: dict[str, dict[str, Any]] = {}
    for decision, rows in buckets.items():
        path = Path(f"{args.output_prefix}.{decision}.jsonl")
        write_jsonl(path, rows)
        output_paths[decision] = {"path": str(path), "sha256": file_sha256(path), "records": len(rows)}
    summary_path = Path(f"{args.output_prefix}.summary.json")
    summary = {
        "schema_version": "crk2-independent-qc-summary-v2",
        "benchmark": {"path": str(args.benchmark), "sha256": file_sha256(args.benchmark), "records": len(benchmark)},
        "input": {"path": str(args.input), "sha256": file_sha256(args.input)},
        "counts": {decision: len(rows) for decision, rows in buckets.items()},
        "invalid_reasons": dict(reason_counts.most_common()),
        "outputs": output_paths,
    }
    write_json(summary_path, summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
