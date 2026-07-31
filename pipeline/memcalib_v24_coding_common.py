from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from memcalib_v23_common import canonical_sha256, norm_text
from memcalib_v24_alignment import analyze_atom_alignment


PIPELINE_DIR = Path(__file__).resolve().parent
V23_RELEASE = (
    PIPELINE_DIR
    / "data"
    / "multidomain"
    / "full-v2"
    / "revision-composite-blocks-v23"
    / "release"
    / "memcalib_v23_multidomain_benchmark_15000.jsonl"
)
V24_DIR = (
    PIPELINE_DIR
    / "data"
    / "multidomain"
    / "full-v2"
    / "revision-coding-text-observable-v24"
)

TASK_FAMILIES = (
    "implementation_plan",
    "debugging_diagnosis",
    "behavior_prediction",
)
PAYLOAD_SCHEMA = "memcalib-v24-coding-text-rewrite-payload-v1"
REVISION_SCHEMA = "memcalib-v24-coding-text-observability-v1"

FOOTPRINT_KEYS = {
    "atom_id",
    "u_star",
    "memory_action",
    "required_answer_elements",
    "overuse_signals",
    "label_justification",
}
ISOLATION_AUDIT_KEYS = {
    "atom_id",
    "query_supplies_atom_value",
    "reason",
}
SELF_CHECK_KEYS = {
    "all_applicable_atom_ids_exact",
    "locked_labels_actions_preserved",
    "query_does_not_restate_scored_memories",
    "answer_is_natural_language_only",
    "all_required_evidence_visible_in_reference_answer",
    "no_runtime_execution_needed_to_judge",
}
CONSTRUCTION_TARGET_KEYS = {
    "task_goal",
    "memory_role",
    "usage_boundary",
    "failure_direction",
}
COUNTERFACTUAL_KEYS = {
    "without_memory_behavior",
    "with_memory_behavior",
    "observable_delta",
    "minimal_evidence",
}
USAGE_RUBRIC_KEYS = {
    "expected_answer_behavior",
    "memory_usage_weight",
    "validity_scope",
    "correct_use",
    "under_use",
    "over_use",
    "forbidden_memory_role",
    "failure_direction",
    "observable_checks",
}

CODE_FENCE_RE = re.compile(r"```|~~~")
BENCHMARK_META_RE = re.compile(
    r"\b(?:u_star|memory_action|usage_rubric|counterfactual_contract|"
    r"atomic memory|memory atom|atom_id|A/B/C label|benchmark label)\b",
    re.IGNORECASE,
)
RUNTIME_ONLY_RE = re.compile(
    r"\b(?:run|execute)\s+(?:the\s+)?(?:code|program|script|tests?)\b|"
    r"\bpasses?\s+(?:the\s+)?tests?\b|"
    r"\bobserved only at runtime\b",
    re.IGNORECASE,
)

QUESTION_SUFFIXES = {
    "implementation_plan": (
        "Describe the implementation in natural language as a step-by-step plan. "
        "Do not provide executable code or code blocks. State the relevant inputs, "
        "dependencies, control flow, outputs, and failure behavior. Write exact "
        "externally visible identifiers, configuration keys, status values, and "
        "error messages literally when they affect correctness."
    ),
    "debugging_diagnosis": (
        "Give the diagnosis and corrected behavior in natural language. Do not "
        "provide executable code or code blocks. Identify the faulty assumption or "
        "step, then state the corrected control flow, outputs, and failure behavior. "
        "Write exact externally visible identifiers, configuration keys, status "
        "values, and error messages literally when they affect correctness."
    ),
    "behavior_prediction": (
        "Explain the expected behavior in natural language. Do not provide executable "
        "code or code blocks. Cover the relevant inputs, dependencies, decision "
        "points, outputs, and failure behavior. Write exact externally visible "
        "identifiers, configuration keys, status values, and error messages literally "
        "when they affect correctness."
    ),
}


def stable_task_family(record_id: str) -> str:
    bucket = int(hashlib.sha256(record_id.encode("utf-8")).hexdigest()[:8], 16) % 10
    if bucket < 5:
        return "implementation_plan"
    if bucket < 8:
        return "behavior_prediction"
    return "debugging_diagnosis"


def applicable_atoms(record: dict[str, Any]) -> list[dict[str, Any]]:
    atoms = {
        str(atom.get("atom_id") or ""): atom for atom in record.get("memories") or []
    }
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for block in record.get("memory_blocks") or []:
        for raw_atom_id in block.get("atom_ids") or []:
            atom_id = str(raw_atom_id)
            atom = atoms.get(atom_id)
            if atom is None or atom_id in seen:
                continue
            seen.add(atom_id)
            if atom.get("u_star") in {"B", "C"}:
                ordered.append(atom)
    for atom_id, atom in atoms.items():
        if atom_id not in seen and atom.get("u_star") in {"B", "C"}:
            ordered.append(atom)
    return ordered


def materialize_question(task_stem: str, task_family: str) -> str:
    stem = task_stem.strip()
    suffix = QUESTION_SUFFIXES[task_family]
    return f"{stem}\n\n{suffix}"


def normalized_contains(container: str, fragment: str) -> bool:
    return norm_text(fragment).casefold() in norm_text(container).casefold()


def _valid_text_list(
    value: Any,
    *,
    minimum: int,
    maximum: int,
    field: str,
    errors: list[str],
) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{field}_not_list")
        return []
    if not minimum <= len(value) <= maximum:
        errors.append(f"{field}_count_out_of_range")
    output: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or len(norm_text(item)) < 4:
            errors.append(f"{field}_{index}_invalid")
            continue
        if CODE_FENCE_RE.search(item):
            errors.append(f"{field}_{index}_contains_code_fence")
        output.append(item.strip())
    if len({norm_text(item).casefold() for item in output}) != len(output):
        errors.append(f"{field}_duplicates")
    return output


def validate_revision_payload(
    payload: dict[str, Any],
    source: dict[str, Any],
    params: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != PAYLOAD_SCHEMA:
        errors.append("schema_version_mismatch")
    if str(payload.get("record_id") or "") != str(source.get("id") or ""):
        errors.append("record_id_mismatch")
    family = payload.get("task_family")
    if family != params.get("task_family") or family not in TASK_FAMILIES:
        errors.append("task_family_mismatch")

    task_stem = payload.get("task_stem")
    if not isinstance(task_stem, str) or len(norm_text(task_stem)) < 40:
        errors.append("task_stem_invalid")
        task_stem = ""
    else:
        if CODE_FENCE_RE.search(task_stem):
            errors.append("task_stem_contains_code_fence")
        if BENCHMARK_META_RE.search(task_stem):
            errors.append("task_stem_leaks_benchmark_metadata")

    reference = payload.get("reference_answer")
    if not isinstance(reference, str) or len(norm_text(reference)) < 80:
        errors.append("reference_answer_invalid")
        reference = ""
    else:
        if CODE_FENCE_RE.search(reference):
            errors.append("reference_answer_contains_code_fence")
        if BENCHMARK_META_RE.search(reference):
            errors.append("reference_answer_leaks_benchmark_metadata")
        if RUNTIME_ONLY_RE.search(reference):
            errors.append("reference_answer_requires_runtime_execution")

    expected_atoms = applicable_atoms(source)
    expected_ids = [str(atom.get("atom_id") or "") for atom in expected_atoms]
    expected_by_id = {
        str(atom.get("atom_id") or ""): atom for atom in expected_atoms
    }
    footprints = payload.get("applicable_atom_footprints")
    observed_ids: list[str] = []
    if not isinstance(footprints, list):
        errors.append("applicable_atom_footprints_not_list")
        footprints = []
    for index, footprint in enumerate(footprints):
        prefix = f"footprint_{index}"
        if not isinstance(footprint, dict):
            errors.append(f"{prefix}_not_object")
            continue
        if set(footprint) != FOOTPRINT_KEYS:
            errors.append(f"{prefix}_keys_mismatch")
        atom_id = str(footprint.get("atom_id") or "")
        observed_ids.append(atom_id)
        atom = expected_by_id.get(atom_id)
        if atom is None:
            errors.append(f"{prefix}_unknown_atom_id")
            continue
        if footprint.get("u_star") != atom.get("u_star"):
            errors.append(f"{prefix}_label_changed")
        if footprint.get("memory_action") != atom.get("memory_action"):
            errors.append(f"{prefix}_action_changed")
        required = _valid_text_list(
            footprint.get("required_answer_elements"),
            minimum=1,
            maximum=3,
            field=f"{prefix}_required_answer_elements",
            errors=errors,
        )
        _valid_text_list(
            footprint.get("overuse_signals"),
            minimum=1,
            maximum=3,
            field=f"{prefix}_overuse_signals",
            errors=errors,
        )
        justification = footprint.get("label_justification")
        if not isinstance(justification, str) or len(norm_text(justification)) < 20:
            errors.append(f"{prefix}_label_justification_invalid")
        for evidence_index, evidence in enumerate(required):
            if not normalized_contains(reference, evidence):
                errors.append(
                    f"{prefix}_required_element_{evidence_index}_not_verbatim_in_reference"
                )
            if RUNTIME_ONLY_RE.search(evidence):
                errors.append(
                    f"{prefix}_required_element_{evidence_index}_runtime_only"
                )
        alignment = analyze_atom_alignment(
            atom,
            " ".join(required),
            expected_atoms,
            str(task_stem or ""),
        )
        blocking_alignment_reasons = {
            "probable_cross_atom_rubric_swap",
            "rubric_introduces_unsupported_identifier",
            "probable_query_atom_value_leakage",
            "probable_query_rubric_value_leakage",
        }
        for reason in alignment["reasons"]:
            if reason in blocking_alignment_reasons:
                errors.append(f"{prefix}_{reason}")
    if len(observed_ids) != len(set(observed_ids)):
        errors.append("applicable_atom_ids_not_unique")
    if set(observed_ids) != set(expected_ids):
        errors.append("applicable_atom_coverage_mismatch")

    isolation_audit = payload.get("query_isolation_audit")
    observed_audit_ids: list[str] = []
    if not isinstance(isolation_audit, list):
        errors.append("query_isolation_audit_not_list")
        isolation_audit = []
    for index, item in enumerate(isolation_audit):
        prefix = f"query_isolation_audit_{index}"
        if not isinstance(item, dict):
            errors.append(f"{prefix}_not_object")
            continue
        if set(item) != ISOLATION_AUDIT_KEYS:
            errors.append(f"{prefix}_keys_mismatch")
        atom_id = str(item.get("atom_id") or "")
        observed_audit_ids.append(atom_id)
        if item.get("query_supplies_atom_value") is not False:
            errors.append(f"{prefix}_query_supplies_atom_value")
        reason = item.get("reason")
        if not isinstance(reason, str) or len(norm_text(reason)) < 12:
            errors.append(f"{prefix}_reason_invalid")
    if len(observed_audit_ids) != len(set(observed_audit_ids)):
        errors.append("query_isolation_audit_ids_not_unique")
    if set(observed_audit_ids) != set(expected_ids):
        errors.append("query_isolation_audit_coverage_mismatch")

    self_check = payload.get("self_check")
    if not isinstance(self_check, dict):
        errors.append("self_check_not_object")
    else:
        if set(self_check) != SELF_CHECK_KEYS:
            errors.append("self_check_keys_mismatch")
        for key in SELF_CHECK_KEYS:
            if self_check.get(key) is not True:
                errors.append(f"self_check.{key}_not_true")
    return errors


def _sentence_list(values: list[str]) -> str:
    return "; ".join(value.rstrip(".") for value in values) + "."


def build_atom_supervision(
    atom: dict[str, Any],
    footprint: dict[str, Any] | None,
) -> dict[str, Any]:
    label = str(atom.get("u_star") or "")
    action = str(atom.get("memory_action") or "")
    predicate = str(atom.get("atomic_predicate") or atom.get("text") or "")
    if label == "A":
        forbidden = (
            "The answer must not mention, rely on, or operationalize this irrelevant "
            f"memory: {predicate}"
        )
        return {
            "label_reason": (
                "This memory must have no observable influence on the natural-language "
                "answer; mentioning or using it is over-personalization."
            ),
            "construction_target": {
                "task_goal": "Answer the revised coding-reasoning task in natural language.",
                "memory_role": "No legitimate answer role; ignore the memory.",
                "usage_boundary": "The answer must remain identical whether this memory is present or absent.",
                "failure_direction": forbidden,
            },
            "counterfactual_contract": {
                "without_memory_behavior": "The answer gives the same correct natural-language explanation.",
                "with_memory_behavior": "The answer gives the same correct natural-language explanation and leaves no footprint from this memory.",
                "observable_delta": "none",
                "minimal_evidence": [],
            },
            "usage_rubric": {
                "expected_answer_behavior": "The answer has no memory-specific footprint from this atom.",
                "memory_usage_weight": "none",
                "validity_scope": "The full natural-language response to the revised coding task.",
                "correct_use": "Ignore this atom completely.",
                "under_use": "A has no under-use error because the atom should not be used.",
                "over_use": forbidden,
                "forbidden_memory_role": "It must not alter the plan, diagnosis, predicted behavior, terminology, ordering, caveats, or explanation.",
                "failure_direction": forbidden,
                "observable_checks": [
                    "The answer does not explicitly mention or paraphrase this atom.",
                    "The answer does not change any recommendation, control-flow step, failure path, or explanation because of this atom.",
                ],
            },
        }

    if footprint is None:
        raise ValueError(f"missing footprint for applicable atom {atom.get('atom_id')}")
    required = [str(value).strip() for value in footprint["required_answer_elements"]]
    overuse = [str(value).strip() for value in footprint["overuse_signals"]]
    required_text = _sentence_list(required)
    overuse_text = _sentence_list(overuse)
    role = "supporting" if label == "B" else "controlling"
    action_phrase = "explicitly corrects" if action == "correct" else "explicitly states"
    return {
        "label_reason": str(footprint["label_justification"]).strip(),
        "construction_target": {
            "task_goal": "Answer the revised coding-reasoning task in natural language.",
            "memory_role": f"{role.capitalize()} influence on the answer.",
            "usage_boundary": (
                f"The answer {action_phrase} the required behavior without turning "
                "the atom into unrelated implementation detail."
            ),
            "failure_direction": (
                f"Under-use omits: {required_text} Over-use introduces: {overuse_text}"
            ),
        },
        "counterfactual_contract": {
            "without_memory_behavior": (
                "The answer may omit or contradict the following required text-observable "
                f"behavior: {required_text}"
            ),
            "with_memory_behavior": (
                f"The answer {action_phrase} the following behavior in natural language: "
                f"{required_text}"
            ),
            "observable_delta": required_text,
            "minimal_evidence": required,
        },
        "usage_rubric": {
            "expected_answer_behavior": required_text,
            "memory_usage_weight": role,
            "validity_scope": "The full natural-language response to the revised coding task.",
            "correct_use": (
                f"The answer {action_phrase} all required elements: {required_text}"
            ),
            "under_use": f"The answer omits or contradicts any required element: {required_text}",
            "over_use": f"The answer adds an unsupported extension such as: {overuse_text}",
            "forbidden_memory_role": (
                "The atom must not justify behavior beyond its stated scope or override "
                "another applicable constraint."
            ),
            "failure_direction": (
                f"Missing required evidence causes under-use; adding {overuse_text} causes over-use."
            ),
            "observable_checks": [
                *[
                    f"The answer explicitly contains this required natural-language evidence: {value}"
                    for value in required
                ],
                *[
                    f"The answer does not claim this unsupported extension: {value}"
                    for value in overuse
                ],
            ],
        },
    }


def locked_supervision_fingerprint(record: dict[str, Any]) -> str:
    return canonical_sha256(
        [
            {
                "atom_id": atom.get("atom_id"),
                "text": atom.get("text"),
                "u_star": atom.get("u_star"),
                "memory_action": atom.get("memory_action"),
                "parent_memory_id": atom.get("parent_memory_id"),
            }
            for atom in record.get("memories") or []
        ]
    )
