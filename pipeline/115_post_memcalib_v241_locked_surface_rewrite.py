#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from memcalib_v23_common import canonical_sha256, file_sha256, norm_text, portable_path
from memcalib_v24_alignment import analyze_atom_alignment
from memcalib_v24_coding_common import (
    BENCHMARK_META_RE,
    CODE_FENCE_RE,
    V23_RELEASE,
    applicable_atoms,
    build_atom_supervision,
    locked_supervision_fingerprint,
    materialize_question,
    validate_revision_payload,
)
from utils import extract_json_object, iter_jsonl, write_json, write_jsonl


SURFACE_SCHEMA = "memcalib-v241-locked-surface-v1"
SELF_CHECK_KEYS = {
    "practical_goal_preserved",
    "natural_language_only",
    "all_requirement_values_unresolved",
    "primary_and_supporting_magnitude_preserved",
    "benchmark_metadata_absent",
}
BLOCKING_QUERY_REASONS = {
    "probable_query_atom_value_leakage",
    "probable_query_rubric_value_leakage",
}
TOPIC_DESCRIPTIONS = {
    "data_algorithm": "a data-design or algorithmic-behavior problem",
    "api_library": "an API, service, or library-integration problem",
    "debugging": "a software defect and its corrected behavior",
    "implementation": "a software-component implementation",
    "systems_devops": "a systems or deployment operation",
    "testing_quality": "a testing or quality-assurance workflow",
    "coding_other": "a software-engineering task",
}


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
    raise ValueError("no_model_output_text")


def sentence(value: str) -> str:
    cleaned = value.strip()
    return cleaned if cleaned.endswith((".", "!", "?")) else f"{cleaned}."


def fallback_surface(
    source: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, Any]:
    topic = TOPIC_DESCRIPTIONS.get(
        str(source.get("source_topic") or ""),
        TOPIC_DESCRIPTIONS["coding_other"],
    )
    family = str(params["task_family"])
    if family == "implementation_plan":
        stem = (
            f"A team is preparing {topic}. The request intentionally leaves the "
            "project-approved primary choices and secondary constraints unresolved. "
            "Describe a natural-language implementation plan that identifies the "
            "primary requirements needed to determine the solution and then explains "
            "the bounded supporting considerations that refine it. Cover inputs, "
            "dependencies, control flow, outputs, and failure behavior without "
            "providing executable code or assuming unstated project-specific values."
        )
    elif family == "debugging_diagnosis":
        stem = (
            f"A team is reviewing an incorrect approach to {topic}. The approach "
            "relies on generic defaults and may miss project-specific requirements. "
            "Diagnose which unresolved primary requirements determine the corrected "
            "behavior, then explain any bounded supporting considerations. State the "
            "corrected inputs, dependencies, control flow, outputs, and failure "
            "behavior in natural language without executable code or unstated "
            "project-specific values."
        )
    else:
        stem = (
            f"A team needs a behavior review for {topic}. The request intentionally "
            "leaves the project-approved primary choices and secondary constraints "
            "unresolved. Explain how the primary requirements determine the expected "
            "behavior, then state the bounded supporting considerations that refine "
            "it. Cover relevant inputs, dependencies, decision points, outputs, and "
            "failure paths in natural language without executable code or assuming "
            "unstated project-specific values."
        )
    return {
        "schema_version": SURFACE_SCHEMA,
        "record_id": params["record_id"],
        "task_family": family,
        "task_stem": stem,
        "self_check": {key: True for key in SELF_CHECK_KEYS},
    }


def build_reference(requirements: list[dict[str, Any]]) -> str:
    primary = [
        sentence(str(item))
        for requirement in requirements
        if requirement["role"] == "primary"
        for item in requirement["required_evidence"]
    ]
    supporting = [
        sentence(str(item))
        for requirement in requirements
        if requirement["role"] == "supporting"
        for item in requirement["required_evidence"]
    ]
    parts = [
        "The natural-language solution is governed by the following project requirements."
    ]
    if primary:
        parts.append("The primary requirements are: " + " ".join(primary))
    if supporting:
        parts.append(
            "The bounded supporting considerations are: " + " ".join(supporting)
        )
    parts.append(
        "No additional project-specific technology, identifier, value, or failure "
        "behavior should be inferred beyond these stated requirements."
    )
    return " ".join(parts)


def build_footprints(
    atoms: list[dict[str, Any]],
    requirements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {str(atom.get("atom_id") or ""): atom for atom in atoms}
    footprints: list[dict[str, Any]] = []
    for requirement in requirements:
        atom_id = str(requirement["atom_id"])
        atom = by_id[atom_id]
        label = str(atom.get("u_star") or "")
        action = str(atom.get("memory_action") or "")
        role = "bounded supporting" if label == "B" else "controlling"
        verb = "corrects" if action == "correct" else "states"
        footprints.append(
            {
                "atom_id": atom_id,
                "u_star": label,
                "memory_action": action,
                "required_answer_elements": [
                    str(value).strip()
                    for value in requirement["required_evidence"]
                ],
                "overuse_signals": [
                    "Any project-specific technology, identifier, value, or failure "
                    "behavior not supported by this requirement"
                ],
                "label_justification": (
                    f"This requirement has {role} influence: the answer {verb} its "
                    "own project-specific behavior while the task keeps that value "
                    "unresolved."
                ),
            }
        )
    return footprints


def validate_surface(
    surface: dict[str, Any],
    params: dict[str, Any],
    source: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if surface.get("schema_version") != SURFACE_SCHEMA:
        errors.append("schema_version_mismatch")
    if str(surface.get("record_id") or "") != str(params.get("record_id") or ""):
        errors.append("record_id_mismatch")
    if surface.get("task_family") != params.get("task_family"):
        errors.append("task_family_mismatch")
    stem = surface.get("task_stem")
    if not isinstance(stem, str) or len(norm_text(stem).split()) < 40:
        errors.append("task_stem_too_short")
        stem = ""
    if CODE_FENCE_RE.search(stem):
        errors.append("task_stem_contains_code_fence")
    if BENCHMARK_META_RE.search(stem):
        errors.append("task_stem_leaks_benchmark_metadata")
    checks = surface.get("self_check")
    if not isinstance(checks, dict) or set(checks) != SELF_CHECK_KEYS:
        errors.append("self_check_keys_mismatch")
    elif any(checks.get(key) is not True for key in SELF_CHECK_KEYS):
        errors.append("self_check_not_all_true")
    atoms = applicable_atoms(source)
    requirements = params.get("locked_requirements")
    if not isinstance(requirements, list):
        errors.append("locked_requirements_not_list")
        return errors
    expected_ids = [str(atom.get("atom_id") or "") for atom in atoms]
    observed_ids = [str(item.get("atom_id") or "") for item in requirements]
    if observed_ids != expected_ids:
        errors.append("locked_requirement_coverage_mismatch")
    for atom, requirement in zip(atoms, requirements):
        expected = " ".join(
            str(value) for value in requirement.get("required_evidence") or []
        )
        alignment = analyze_atom_alignment(atom, expected, atoms, stem)
        for reason in alignment["reasons"]:
            if reason in BLOCKING_QUERY_REASONS:
                errors.append(f"{atom.get('atom_id')}_{reason}")
    return errors


def build_record(
    source: dict[str, Any],
    surface: dict[str, Any],
    params: dict[str, Any],
    request_id: str,
    surface_mode: str = "model_rewrite",
) -> tuple[dict[str, Any], dict[str, Any]]:
    requirements = params["locked_requirements"]
    footprints = build_footprints(applicable_atoms(source), requirements)
    reference = build_reference(requirements)
    payload = {
        "schema_version": "memcalib-v24-coding-text-rewrite-payload-v1",
        "record_id": source["id"],
        "task_family": params["task_family"],
        "task_stem": surface["task_stem"],
        "reference_answer": reference,
        "applicable_atom_footprints": footprints,
        "query_isolation_audit": [
            {
                "atom_id": requirement["atom_id"],
                "query_supplies_atom_value": False,
                "reason": (
                    "The task asks for the unresolved project requirement without "
                    "stating its concrete value."
                ),
            }
            for requirement in requirements
        ],
        "self_check": {
            "all_applicable_atom_ids_exact": True,
            "locked_labels_actions_preserved": True,
            "query_does_not_restate_scored_memories": True,
            "answer_is_natural_language_only": True,
            "all_required_evidence_visible_in_reference_answer": True,
            "no_runtime_execution_needed_to_judge": True,
        },
    }
    errors = validate_revision_payload(payload, source, params)
    if errors:
        raise ValueError(";".join(errors))

    record = json.loads(json.dumps(source))
    record["question"] = materialize_question(
        str(surface["task_stem"]), str(params["task_family"])
    )
    record["source_answer"] = reference
    footprint_by_id = {row["atom_id"]: row for row in footprints}
    for atom in record.get("memories") or []:
        atom.update(
            build_atom_supervision(
                atom, footprint_by_id.get(str(atom.get("atom_id") or ""))
            )
        )
    record["schema_version"] = "crk-2-canonical-memory-v2.4.1"
    record["coding_text_observability_revision"] = {
        "schema_version": "memcalib-v241-locked-coding-surface-v1",
        "request_id": request_id,
        "task_family": params["task_family"],
        "retry_round": params.get("retry_round"),
        "source_record_fingerprint": params["source_record_fingerprint"],
        "locked_supervision_fingerprint": params[
            "locked_supervision_fingerprint"
        ],
        "memory_blocks_fingerprint": params["memory_blocks_fingerprint"],
        "question_contract": "natural_language_only_no_code_blocks",
        "labels_and_actions_locked": True,
        "memory_atoms_and_blocks_locked": True,
        "rubrics_built_deterministically_by_atom_id": True,
        "surface_mode": surface_mode,
    }
    audit = {
        "schema_version": "memcalib-v241-locked-surface-audit-v1",
        "record_id": source["id"],
        "request_id": request_id,
        "task_family": params["task_family"],
        "source_record_fingerprint": params["source_record_fingerprint"],
        "output_record_fingerprint": canonical_sha256(record),
        "original_question": source.get("question"),
        "revised_question": record["question"],
        "revised_reference_answer": reference,
        "locked_requirements": requirements,
        "applicable_atom_footprints": footprints,
        "surface_mode": surface_mode,
    }
    return record, audit


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Postprocess attribution-locked v2.4.1 coding surface rewrites."
    )
    parser.add_argument("--benchmark", type=Path, default=V23_RELEASE)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument(
        "--deterministic-fallback",
        action="store_true",
        help=(
            "Replace structurally invalid or leaking model task stems with a "
            "topic-level deterministic stem, while retaining atom-locked evidence."
        ),
    )
    args = parser.parse_args()

    benchmark = {
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
        source = benchmark.get(record_id)
        result = results.get(request_id)
        errors: list[str] = []
        if source is None:
            errors.append("source_record_missing")
        else:
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
        infrastructure_errors = list(errors)
        surface: dict[str, Any] | None = None
        if result is not None:
            if request_params(result) and request_params(result) != params:
                errors.append("result_params_mismatch")
            try:
                surface = extract_json_object(output_text(result))
            except (ValueError, json.JSONDecodeError) as exc:
                errors.append(f"invalid_json:{exc}")
        if source is not None and surface is not None and not errors:
            errors.extend(validate_surface(surface, params, source))
        surface_mode = "model_rewrite"
        if (
            args.deterministic_fallback
            and source is not None
            and not infrastructure_errors
            and errors
        ):
            surface = fallback_surface(source, params)
            errors = validate_surface(surface, params, source)
            surface_mode = "deterministic_fallback"
        if source is not None and surface is not None and not errors:
            try:
                record, audit = build_record(
                    source,
                    surface,
                    params,
                    request_id,
                    surface_mode=surface_mode,
                )
            except ValueError as exc:
                errors.extend(str(exc).split(";"))
            else:
                if record.get("memory_blocks") != source.get("memory_blocks"):
                    errors.append("memory_blocks_changed")
                if locked_supervision_fingerprint(record) != params.get(
                    "locked_supervision_fingerprint"
                ):
                    errors.append("locked_supervision_changed")
                if not errors:
                    valid.append(record)
                    audits.append(audit)
        if errors:
            invalid.append(
                {
                    "request_id": request_id,
                    "record_id": record_id,
                    "errors": errors,
                    "result_present": result is not None,
                }
            )

    paths = {
        "valid": args.prefix.with_suffix(".valid.jsonl"),
        "invalid": args.prefix.with_suffix(".invalid.jsonl"),
        "audit": args.prefix.with_suffix(".audit.jsonl"),
    }
    write_jsonl(paths["valid"], valid)
    write_jsonl(paths["invalid"], invalid)
    write_jsonl(paths["audit"], audits)
    summary = {
        "schema_version": "memcalib-v241-locked-surface-summary-v1",
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
        },
        "outputs": {
            name: {"path": portable_path(path), "sha256": file_sha256(path)}
            for name, path in paths.items()
        },
    }
    write_json(args.prefix.with_suffix(".summary.json"), summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
