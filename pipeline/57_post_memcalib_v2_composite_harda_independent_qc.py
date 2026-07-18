#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from utils import extract_json_object, iter_jsonl, norm_text, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
REVISION_DIR = SCRIPT_DIR / "data" / "multidomain" / "full-v2" / "revision-composite-harda"
DEFAULT_BENCHMARK = REVISION_DIR / "memcalib_v21_composite_harda_benchmark_15000.jsonl"
DEFAULT_REQUESTS = REVISION_DIR / "memcalib_v21_composite_harda_independent_qc_input_15000.jsonl"
DEFAULT_RESULTS = REVISION_DIR / "memcalib_v21_composite_harda_independent_qc_result_15000.jsonl"
DEFAULT_PREFIX = REVISION_DIR / "memcalib_v21_composite_harda_independent_qc_15000"
REQUEST_SCHEMA = "memcalib-composite-harda-independent-qc-requests-v1"
QC_SCHEMA = "memcalib-composite-harda-independent-qc-v1"
QC_RECORD_SCHEMA = "memcalib-composite-harda-independent-qc-adjudication-v1"
PASS_FAIL = {"pass", "fail"}
PASS_REVIEW_FAIL = {"pass", "review", "fail"}
QUERY_RELATIONS = {"absent", "overlap", "entailed"}
INFLUENCE_LEVELS = {"none", "bounded", "direct"}
SAFETY_RELEVANCE = {"none", "possible", "direct"}
DECISIONS = {"strict_pass", "review", "reject"}


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(SCRIPT_DIR.parent))
    except ValueError:
        return str(resolved)


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


def expected_real_atom_ids(record: dict[str, Any]) -> list[str]:
    return [
        str(atom.get("atom_id") or "")
        for atom in record.get("memories") or []
        if isinstance(atom, dict) and atom.get("source") != "synthetic_hard_a"
    ]


def normalize_qc_structure(
    qc: dict[str, Any],
    expected_record_id: str,
) -> tuple[dict[str, Any], list[str]]:
    normalized = copy.deepcopy(qc)
    normalizations: list[str] = []
    if normalized.get("schema_version") != QC_SCHEMA:
        normalized["schema_version"] = QC_SCHEMA
        normalizations.append("restored_locked_qc_schema")
    if expected_record_id and normalized.get("record_id") != expected_record_id:
        normalized["record_id"] = expected_record_id
        normalizations.append("restored_locked_record_id_from_request")
    return normalized, normalizations


def validate_qc(
    qc: dict[str, Any],
    record: dict[str, Any],
    params: dict[str, Any],
) -> tuple[list[str], str, list[str]]:
    errors: list[str] = []
    reasons: list[str] = []
    computed = "strict_pass"
    record_id = str(record.get("id") or "")
    expected_ids = expected_real_atom_ids(record)
    expected_family = str(params.get("hard_a_family") or "")

    if qc.get("schema_version") != QC_SCHEMA:
        errors.append("bad_qc_schema")
    if str(qc.get("record_id") or "") != record_id:
        errors.append("record_id_mismatch")
    if params.get("schema_version") != REQUEST_SCHEMA:
        errors.append("bad_request_schema")
    if params.get("record_fingerprint") != canonical_sha256(record):
        errors.append("record_fingerprint_mismatch")
    if list(params.get("real_atom_ids") or []) != expected_ids:
        errors.append("request_real_atom_ids_mismatch")

    composite = qc.get("composite_block_check")
    if not isinstance(composite, dict):
        errors.append("composite_block_check_not_object")
    else:
        for key in ("exact_atom_coverage", "separable_into_atoms", "no_new_proposition"):
            if composite.get(key) not in PASS_FAIL:
                errors.append(f"composite_bad_{key}")
            elif composite.get(key) == "fail":
                computed = "reject"
                reasons.append(f"composite:{key}")
        if composite.get("coherence") not in PASS_REVIEW_FAIL:
            errors.append("composite_bad_coherence")
        elif composite.get("coherence") == "fail":
            computed = "reject"
            reasons.append("composite:coherence_fail")
        elif composite.get("coherence") == "review" and computed != "reject":
            computed = "review"
            reasons.append("composite:coherence_review")
        if len(norm_text(str(composite.get("reason") or ""))) < 15:
            errors.append("composite_missing_reason")

    atom_checks = qc.get("real_atom_checks")
    observed_ids: list[str] = []
    if not isinstance(atom_checks, list):
        errors.append("real_atom_checks_not_list")
    else:
        for index, check in enumerate(atom_checks):
            if not isinstance(check, dict):
                errors.append(f"real_atom_check_{index}_not_object")
                continue
            atom_id = str(check.get("atom_id") or "")
            observed_ids.append(atom_id)
            for key in ("label_action_validity", "counterfactual_observability", "rubric_judgeability"):
                value = check.get(key)
                if value not in PASS_REVIEW_FAIL:
                    errors.append(f"real_atom_check_{index}_bad_{key}")
                elif value == "fail":
                    computed = "reject"
                    reasons.append(f"{atom_id}:{key}_fail")
                elif value == "review" and computed != "reject":
                    computed = "review"
                    reasons.append(f"{atom_id}:{key}_review")
            if len(norm_text(str(check.get("reason") or ""))) < 15:
                errors.append(f"real_atom_check_{index}_missing_reason")
        if len(observed_ids) != len(set(observed_ids)):
            errors.append("real_atom_check_duplicate_id")
        if set(observed_ids) != set(expected_ids):
            errors.append("real_atom_check_coverage_mismatch")

    hard = qc.get("hard_a_check")
    if not isinstance(hard, dict):
        errors.append("hard_a_check_not_object")
    else:
        if hard.get("assigned_family") != expected_family:
            errors.append("hard_a_assigned_family_mismatch")
        for key in ("family_match", "no_decision_authority", "no_explicit_correction_required", "no_answer_footprint"):
            value = hard.get(key)
            if value not in PASS_FAIL:
                errors.append(f"hard_a_bad_{key}")
            elif value == "fail":
                computed = "reject"
                reasons.append(f"hard_a:{key}")
        for key in ("surface_relevance", "independent_of_real_atoms"):
            value = hard.get(key)
            if value not in PASS_REVIEW_FAIL:
                errors.append(f"hard_a_bad_{key}")
            elif value == "fail":
                computed = "reject"
                reasons.append(f"hard_a:{key}_fail")
            elif value == "review" and computed != "reject":
                computed = "review"
                reasons.append(f"hard_a:{key}_review")
        relation = hard.get("query_relation")
        if relation not in QUERY_RELATIONS:
            errors.append("hard_a_bad_query_relation")
        elif relation != "absent":
            computed = "reject"
            reasons.append(f"hard_a:query_relation_{relation}")
        influence = hard.get("legitimate_answer_influence")
        if influence not in INFLUENCE_LEVELS:
            errors.append("hard_a_bad_legitimate_answer_influence")
        elif influence != "none":
            computed = "reject"
            reasons.append(f"hard_a:legitimate_answer_influence_{influence}")
        if hard.get("family_boundary_valid") not in PASS_FAIL:
            errors.append("hard_a_bad_family_boundary_valid")
        elif hard.get("family_boundary_valid") == "fail":
            computed = "reject"
            reasons.append("hard_a:family_boundary_invalid")
        safety = hard.get("safety_relevance")
        if safety not in SAFETY_RELEVANCE:
            errors.append("hard_a_bad_safety_relevance")
        elif safety != "none":
            computed = "reject"
            reasons.append(f"hard_a:safety_relevance_{safety}")
        if len(norm_text(str(hard.get("reason") or ""))) < 15:
            errors.append("hard_a_missing_reason")

    if qc.get("recommended_decision") not in DECISIONS:
        errors.append("bad_recommended_decision")
    if len(norm_text(str(qc.get("decision_reason") or ""))) < 10:
        errors.append("missing_decision_reason")
    if errors:
        return sorted(set(errors)), "invalid", sorted(set(reasons))
    return [], computed, sorted(set(reasons))


def main() -> None:
    parser = argparse.ArgumentParser(description="Post-process independent QC for revised composite/Hard-A records.")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--prefix", type=Path, default=DEFAULT_PREFIX)
    args = parser.parse_args()

    benchmark = list(iter_jsonl(args.benchmark))
    benchmark_by_id = {str(row.get("id") or ""): row for row in benchmark}
    if "" in benchmark_by_id or len(benchmark_by_id) != len(benchmark):
        raise ValueError("benchmark record IDs must be non-empty and unique")
    requests = list(iter_jsonl(args.requests))
    request_by_id = {str(row.get("request_id") or ""): row for row in requests}
    if "" in request_by_id or len(request_by_id) != len(requests):
        raise ValueError("request IDs must be non-empty and unique")
    results = list(iter_jsonl(args.results))
    result_by_id = {str(row.get("request_id") or ""): row for row in results}
    if "" in result_by_id or len(result_by_id) != len(results):
        raise ValueError("result request IDs must be non-empty and unique")

    adjudicated_by_id: dict[str, dict[str, Any]] = {}
    categorized: dict[str, list[dict[str, Any]]] = {
        "strict_pass": [],
        "review": [],
        "reject": [],
        "invalid": [],
    }
    decision_reasons: Counter[str] = Counter()
    domain_decisions: dict[str, Counter[str]] = defaultdict(Counter)
    family_decisions: dict[str, Counter[str]] = defaultdict(Counter)

    for request_id, request in request_by_id.items():
        params = get_params(request)
        record_id = str(params.get("record_id") or "")
        record = benchmark_by_id.get(record_id)
        result = result_by_id.get(request_id)
        errors: list[str] = []
        qc: dict[str, Any] | None = None
        structural_normalizations: list[str] = []
        if record is None:
            errors.append("benchmark_record_missing")
        if result is None:
            errors.append("api_result_missing")
        else:
            result_params = get_params(result)
            if result_params and result_params != params:
                errors.append("result_params_mismatch")
            try:
                qc = extract_json_object(get_output_text(result))
                qc, structural_normalizations = normalize_qc_structure(qc, record_id)
            except (ValueError, json.JSONDecodeError, TypeError) as exc:
                errors.append(f"qc_parse_error:{type(exc).__name__}")

        decision = "invalid"
        reasons: list[str] = []
        if record is not None and qc is not None and not errors:
            qc_errors, decision, reasons = validate_qc(qc, record, params)
            errors.extend(qc_errors)
            if errors:
                decision = "invalid"

        audit = {
            "schema_version": QC_RECORD_SCHEMA,
            "request_id": request_id,
            "record_id": record_id,
            "domain": params.get("domain"),
            "hard_a_family": params.get("hard_a_family"),
            "computed_decision": decision,
            "computed_reasons": reasons,
            "validation_errors": sorted(set(errors)),
            "structural_normalizations": structural_normalizations,
            "judge_output": qc,
            "raw_result": result if decision == "invalid" else None,
        }
        if record is None or decision == "invalid":
            categorized["invalid"].append(audit)
        else:
            enriched = copy.deepcopy(record)
            enriched["revision_independent_qc"] = audit
            adjudicated_by_id[record_id] = enriched
            categorized[decision].append(enriched)
        for reason in reasons:
            decision_reasons[reason] += 1
        for error in sorted(set(errors)):
            decision_reasons[f"invalid:{error}"] += 1
        domain_decisions[str(params.get("domain") or "health_seed")][decision] += 1
        family_decisions[str(params.get("hard_a_family") or "")][decision] += 1

    adjudicated = [
        adjudicated_by_id[str(row.get("id") or "")]
        for row in benchmark
        if str(row.get("id") or "") in adjudicated_by_id
    ]
    paths = {
        "adjudicated": args.prefix.with_suffix(".adjudicated.jsonl"),
        "strict_pass": args.prefix.with_suffix(".strict.jsonl"),
        "review": args.prefix.with_suffix(".review.jsonl"),
        "reject": args.prefix.with_suffix(".reject.jsonl"),
        "invalid": args.prefix.with_suffix(".invalid.jsonl"),
        "summary": args.prefix.with_suffix(".summary.json"),
    }
    write_jsonl(paths["adjudicated"], adjudicated)
    for decision in ("strict_pass", "review", "reject", "invalid"):
        write_jsonl(paths[decision], categorized[decision])

    summary = {
        "schema_version": QC_RECORD_SCHEMA,
        "inputs": {
            "benchmark": {
                "path": portable_path(args.benchmark),
                "sha256": file_sha256(args.benchmark),
                "records": len(benchmark),
            },
            "requests": {
                "path": portable_path(args.requests),
                "sha256": file_sha256(args.requests),
                "records": len(requests),
            },
            "results": {
                "path": portable_path(args.results),
                "sha256": file_sha256(args.results),
                "records": len(results),
            },
        },
        "counts": {
            "requested": len(requests),
            "api_results": len(results),
            "strict_pass": len(categorized["strict_pass"]),
            "review": len(categorized["review"]),
            "reject": len(categorized["reject"]),
            "invalid": len(categorized["invalid"]),
            "adjudicated": len(adjudicated),
        },
        "decision_by_domain": {
            domain: dict(sorted(counts.items())) for domain, counts in sorted(domain_decisions.items())
        },
        "decision_by_hard_a_family": {
            family: dict(sorted(counts.items())) for family, counts in sorted(family_decisions.items())
        },
        "decision_reasons": dict(sorted(decision_reasons.items())),
        "outputs": {
            name: {
                "path": portable_path(path),
                "sha256": file_sha256(path),
                "records": (
                    len(adjudicated)
                    if name == "adjudicated"
                    else len(categorized[name])
                    if name in categorized
                    else None
                ),
            }
            for name, path in paths.items()
            if name != "summary"
        },
    }
    write_json(paths["summary"], summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
