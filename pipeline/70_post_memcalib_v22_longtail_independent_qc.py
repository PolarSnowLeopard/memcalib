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
V22_DIR = SCRIPT_DIR / "data" / "multidomain" / "full-v2" / "revision-longtail-blocks"
DEFAULT_BENCHMARK = V22_DIR / "memcalib_v22_longtail_benchmark_15000.jsonl"
DEFAULT_REQUESTS = V22_DIR / "memcalib_v22_longtail_independent_qc_input_15000.jsonl"
DEFAULT_RESULTS = V22_DIR / "memcalib_v22_longtail_independent_qc_result_15000.jsonl"
DEFAULT_PREFIX = V22_DIR / "memcalib_v22_longtail_independent_qc_15000"
REQUEST_SCHEMA = "memcalib-v22-longtail-independent-qc-requests-v1"
QC_SCHEMA = "memcalib-v22-longtail-independent-qc-v1"
AUDIT_SCHEMA = "memcalib-v22-longtail-independent-qc-adjudication-v1"
QUERY_RELATIONS = {"absent", "overlap", "entailed"}
FOOTPRINTS = {"none", "content", "presentation", "implementation", "safety"}
PASS_REVIEW_FAIL = {"pass", "review", "fail"}
CHECK_DECISIONS = {"pass", "review", "reject"}
RECORD_DECISIONS = {"strict_pass", "review", "reject"}


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(SCRIPT_DIR.parent))
    except ValueError:
        return str(resolved)


def params(row: dict[str, Any]) -> dict[str, Any]:
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
    rank = {"strict_pass": 0, "review": 1, "reject": 2}
    return candidate if rank[candidate] > rank[current] else current


def validate_qc(
    qc: dict[str, Any],
    record: dict[str, Any],
    request_params: dict[str, Any],
) -> tuple[list[str], str, list[str]]:
    errors: list[str] = []
    reasons: list[str] = []
    decision = "strict_pass"
    if qc.get("schema_version") != QC_SCHEMA:
        errors.append("bad_qc_schema")
    if str(qc.get("record_id") or "") != str(record.get("id") or ""):
        errors.append("record_id_mismatch")
    if request_params.get("schema_version") != REQUEST_SCHEMA:
        errors.append("bad_request_schema")
    if request_params.get("record_fingerprint") != canonical_sha256(record):
        errors.append("record_fingerprint_mismatch")

    expected_atoms = [str(value) for value in request_params.get("auxiliary_atom_ids") or []]
    atom_checks = qc.get("atom_checks")
    observed_atoms: list[str] = []
    if not isinstance(atom_checks, list):
        errors.append("atom_checks_not_list")
    else:
        for index, check in enumerate(atom_checks):
            if not isinstance(check, dict):
                errors.append(f"atom_check_{index}_not_object")
                continue
            atom_id = str(check.get("atom_id") or "")
            observed_atoms.append(atom_id)
            relation = check.get("query_relation")
            footprint = check.get("answer_footprint")
            atomicity = check.get("atomicity")
            plausibility = check.get("same_user_plausibility")
            declared = check.get("decision")
            if relation not in QUERY_RELATIONS:
                errors.append(f"atom_{index}_bad_query_relation")
            elif relation != "absent":
                decision = worsen(decision, "reject")
                reasons.append(f"{atom_id}:query_relation_{relation}")
            if footprint not in FOOTPRINTS:
                errors.append(f"atom_{index}_bad_answer_footprint")
            elif footprint != "none":
                decision = worsen(decision, "reject")
                reasons.append(f"{atom_id}:answer_footprint_{footprint}")
            if check.get("explicit_correction_required") not in {True, False}:
                errors.append(f"atom_{index}_bad_explicit_correction_required")
            elif check.get("explicit_correction_required") is True:
                decision = worsen(decision, "reject")
                reasons.append(f"{atom_id}:explicit_correction_required")
            if atomicity not in {"pass", "fail"}:
                errors.append(f"atom_{index}_bad_atomicity")
            elif atomicity == "fail":
                decision = worsen(decision, "reject")
                reasons.append(f"{atom_id}:atomicity_fail")
            if plausibility not in PASS_REVIEW_FAIL:
                errors.append(f"atom_{index}_bad_same_user_plausibility")
            elif plausibility == "fail":
                decision = worsen(decision, "reject")
                reasons.append(f"{atom_id}:same_user_plausibility_fail")
            elif plausibility == "review":
                decision = worsen(decision, "review")
                reasons.append(f"{atom_id}:same_user_plausibility_review")
            if declared not in CHECK_DECISIONS:
                errors.append(f"atom_{index}_bad_decision")
            elif declared == "reject":
                decision = worsen(decision, "reject")
                reasons.append(f"{atom_id}:judge_reject")
            elif declared == "review":
                decision = worsen(decision, "review")
                reasons.append(f"{atom_id}:judge_review")
            if len(norm_text(str(check.get("reason") or ""))) < 15:
                errors.append(f"atom_{index}_missing_reason")
        if len(observed_atoms) != len(set(observed_atoms)):
            errors.append("atom_checks_duplicate")
        if set(observed_atoms) != set(expected_atoms):
            errors.append("atom_checks_order_or_coverage_mismatch")

    expected_blocks = request_params.get("auxiliary_block_atom_ids") or {}
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
            footprint = check.get("joint_answer_footprint")
            coherence = check.get("coherence")
            declared = check.get("decision")
            if footprint not in FOOTPRINTS:
                errors.append(f"block_{index}_bad_joint_answer_footprint")
            elif footprint != "none":
                decision = worsen(decision, "reject")
                reasons.append(f"{parent_id}:joint_answer_footprint_{footprint}")
            if coherence not in PASS_REVIEW_FAIL:
                errors.append(f"block_{index}_bad_coherence")
            elif coherence == "fail":
                decision = worsen(decision, "reject")
                reasons.append(f"{parent_id}:coherence_fail")
            elif coherence == "review":
                decision = worsen(decision, "review")
                reasons.append(f"{parent_id}:coherence_review")
            if declared not in CHECK_DECISIONS:
                errors.append(f"block_{index}_bad_decision")
            elif declared == "reject":
                decision = worsen(decision, "reject")
                reasons.append(f"{parent_id}:judge_reject")
            elif declared == "review":
                decision = worsen(decision, "review")
                reasons.append(f"{parent_id}:judge_review")
            if len(norm_text(str(check.get("reason") or ""))) < 15:
                errors.append(f"block_{index}_missing_reason")
        if len(observed_blocks) != len(set(observed_blocks)):
            errors.append("block_checks_duplicate")
        if set(observed_blocks) != set(expected_blocks):
            errors.append("block_checks_order_or_coverage_mismatch")

    global_check = qc.get("global_check")
    if not isinstance(global_check, dict):
        errors.append("global_check_not_object")
    else:
        for key in (
            "all_auxiliary_zero_footprint",
            "no_collective_persona_influence",
            "all_locked_memories_unchanged",
        ):
            if global_check.get(key) not in {True, False}:
                errors.append(f"global_check_bad_{key}")
            elif global_check.get(key) is False:
                decision = worsen(decision, "reject")
                reasons.append(f"global:{key}_false")
        if len(norm_text(str(global_check.get("reason") or ""))) < 15:
            errors.append("global_check_missing_reason")

    if qc.get("recommended_decision") not in RECORD_DECISIONS:
        errors.append("bad_recommended_decision")
    if len(norm_text(str(qc.get("decision_reason") or ""))) < 10:
        errors.append("missing_decision_reason")
    if errors:
        return sorted(set(errors)), "invalid", sorted(set(reasons))
    return [], decision, sorted(set(reasons))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Post-process MemCalib v2.2 auxiliary retrieval-noise independent QC."
    )
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--prefix", type=Path, default=DEFAULT_PREFIX)
    args = parser.parse_args()

    benchmark = list(iter_jsonl(args.benchmark))
    benchmark_by_id = {str(row.get("id") or ""): row for row in benchmark}
    requests = list(iter_jsonl(args.requests))
    request_by_id = {str(row.get("request_id") or ""): row for row in requests}
    results = list(iter_jsonl(args.results))
    result_by_id = {str(row.get("request_id") or ""): row for row in results}
    if len(benchmark_by_id) != len(benchmark) or "" in benchmark_by_id:
        raise ValueError("benchmark record IDs must be non-empty and unique")
    if len(request_by_id) != len(requests) or "" in request_by_id:
        raise ValueError("request IDs must be non-empty and unique")
    if len(result_by_id) != len(results) or "" in result_by_id:
        raise ValueError("result request IDs must be non-empty and unique")

    categorized: dict[str, list[dict[str, Any]]] = {
        "strict_pass": [],
        "review": [],
        "reject": [],
        "invalid": [],
    }
    adjudicated_by_id: dict[str, dict[str, Any]] = {}
    reason_counts: Counter[str] = Counter()
    domain_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for request_id, request in request_by_id.items():
        request_params = params(request)
        record_id = str(request_params.get("record_id") or "")
        record = benchmark_by_id.get(record_id)
        result = result_by_id.get(request_id)
        errors: list[str] = []
        qc: dict[str, Any] | None = None
        if record is None:
            errors.append("benchmark_record_missing")
        if result is None:
            errors.append("api_result_missing")
        else:
            result_params = params(result)
            if result_params and result_params != request_params:
                errors.append("result_params_mismatch")
            try:
                qc = extract_json_object(output_text(result))
            except Exception as exc:
                errors.append(f"qc_parse_error:{type(exc).__name__}")

        decision = "invalid"
        reasons: list[str] = []
        if record is not None and qc is not None and not errors:
            qc_errors, decision, reasons = validate_qc(qc, record, request_params)
            errors.extend(qc_errors)
            if errors:
                decision = "invalid"
        audit = {
            "schema_version": AUDIT_SCHEMA,
            "request_id": request_id,
            "record_id": record_id,
            "domain": request_params.get("domain"),
            "computed_decision": decision,
            "computed_reasons": reasons,
            "validation_errors": sorted(set(errors)),
            "judge_output": qc,
            "raw_result": result if decision == "invalid" else None,
        }
        if record is None or decision == "invalid":
            categorized["invalid"].append(audit)
        else:
            enriched = copy.deepcopy(record)
            enriched["longtail_independent_qc"] = audit
            categorized[decision].append(enriched)
            adjudicated_by_id[record_id] = enriched
        for reason in reasons:
            reason_counts[reason] += 1
        for error in sorted(set(errors)):
            reason_counts[f"invalid:{error}"] += 1
        domain_counts[str(request_params.get("domain") or "health_seed")][decision] += 1

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
        "schema_version": AUDIT_SCHEMA,
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
            domain: dict(sorted(counts.items()))
            for domain, counts in sorted(domain_counts.items())
        },
        "decision_reasons": dict(sorted(reason_counts.items())),
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
