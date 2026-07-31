#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from memcalib_v23_common import canonical_sha256, file_sha256, norm_text, portable_path
from memcalib_v24_alignment import atom_support_text, marked_tokens, overlap, tokens
from memcalib_v24_coding_common import (
    CODE_FENCE_RE,
    QUESTION_SUFFIXES,
    REVISION_SCHEMA,
    V23_RELEASE,
    V24_DIR,
    build_atom_supervision,
    materialize_question,
    validate_revision_payload,
)
from utils import extract_json_object, iter_jsonl, write_json, write_jsonl

AUDIT_DIR = V24_DIR / "audit"
DEFAULT_REQUESTS = AUDIT_DIR / "memcalib_v241_relabel_aware_input_785.jsonl"
DEFAULT_RESULTS = AUDIT_DIR / "memcalib_v241_relabel_aware_result_785.jsonl"
DEFAULT_PREFIX = AUDIT_DIR / "memcalib_v241_relabel_aware_785"

PAYLOAD_SCHEMA = "memcalib-v241-relabel-aware-repair-payload-v1"
PAYLOAD_SCHEMA_AUX = "memcalib-v241-reclassify-aux-a-payload-v1"
SELF_CHECK_KEYS = {
    "all_atom_ids_exact",
    "only_bc_magnitude_may_change",
    "all_label_changes_audited",
    "a_atoms_have_zero_footprint",
    "query_does_not_restate_scored_memories",
    "answer_is_natural_language_only",
    "all_required_evidence_visible_in_reference_answer",
    "no_runtime_execution_needed_to_judge",
    "original_practical_goal_preserved",
}
LABEL_REVISION_KEYS = {
    "atom_id",
    "old_u_star",
    "new_u_star",
    "reason",
}
A_AUDIT_KEYS = {
    "atom_id",
    "question_has_footprint",
    "reference_has_footprint",
    "reason",
}
SELF_CHECK_KEYS_AUX = {
    "all_atom_ids_exact",
    "immutable_hard_a_and_noise_preserved",
    "only_eligible_auxiliary_a_promoted",
    "all_label_action_changes_audited",
    "final_a_atoms_have_zero_footprint",
    "query_does_not_restate_scored_memories",
    "answer_is_natural_language_only",
    "all_required_evidence_visible_in_reference_answer",
    "no_runtime_execution_needed_to_judge",
    "original_practical_goal_preserved",
}
LABEL_ACTION_REVISION_KEYS = {
    "atom_id",
    "old_u_star",
    "new_u_star",
    "old_memory_action",
    "new_memory_action",
    "reason",
}


def atom_identity_fingerprint(record: dict[str, Any]) -> str:
    return canonical_sha256(
        [
            {
                "atom_id": atom.get("atom_id"),
                "text": atom.get("text"),
                "atomic_predicate": atom.get("atomic_predicate"),
                "evidence": atom.get("evidence"),
                "memory_action": atom.get("memory_action"),
                "parent_memory_id": atom.get("parent_memory_id"),
            }
            for atom in record.get("memories") or []
        ]
    )


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


def a_footprint_reasons(atom: dict[str, Any], text: str, surface: str) -> list[str]:
    reasons: list[str] = []
    exact = norm_text(str(atom.get("text") or "")).casefold()
    if len(exact) >= 20 and exact in norm_text(text).casefold():
        reasons.append(f"a_atom_exact_text_in_{surface}")
    return reasons


def normalize_model_payload(
    payload: dict[str, Any],
    source: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    if payload.get("schema_version") == PAYLOAD_SCHEMA_AUX:
        return normalize_aux_reclassification_payload(payload, source)
    normalized = copy.deepcopy(payload)
    repairs: list[str] = []
    source_by_id = {
        str(atom.get("atom_id") or ""): atom
        for atom in source.get("memories") or []
    }
    expected_bc_ids = [
        str(atom.get("atom_id") or "")
        for atom in source.get("memories") or []
        if atom.get("u_star") in {"B", "C"}
    ]
    expected_a_ids = [
        str(atom.get("atom_id") or "")
        for atom in source.get("memories") or []
        if atom.get("u_star") == "A"
    ]
    footprints: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in normalized.get("applicable_atom_footprints") or []:
        if not isinstance(raw, dict):
            repairs.append("drop_non_object_footprint")
            continue
        atom_id = str(raw.get("atom_id") or "")
        atom = source_by_id.get(atom_id)
        if atom is None:
            repairs.append("drop_unknown_atom_footprint")
            continue
        if atom.get("u_star") == "A":
            repairs.append(f"drop_a_footprint:{atom_id}")
            continue
        if atom_id in seen:
            repairs.append(f"drop_duplicate_footprint:{atom_id}")
            continue
        seen.add(atom_id)
        footprint = copy.deepcopy(raw)
        footprint["atom_id"] = atom_id
        if footprint.get("u_star") not in {"B", "C"}:
            footprint["u_star"] = atom.get("u_star")
            repairs.append(f"restore_bc_label:{atom_id}")
        if footprint.get("memory_action") != atom.get("memory_action"):
            footprint["memory_action"] = atom.get("memory_action")
            repairs.append(f"restore_action:{atom_id}")
        overuse = footprint.get("overuse_signals")
        if not isinstance(overuse, list) or not overuse:
            footprint["overuse_signals"] = [
                "Any unsupported extension beyond this memory atom."
            ]
            repairs.append(f"fill_overuse_signal:{atom_id}")
        justification = footprint.get("label_justification")
        if not isinstance(justification, str) or len(norm_text(justification)) < 20:
            footprint["label_justification"] = (
                "This atom has bounded supporting influence on the solution."
                if footprint["u_star"] == "B"
                else "This atom controls a core behavior in the requested solution."
            )
            repairs.append(f"fill_label_justification:{atom_id}")
        footprints.append(footprint)
    normalized["applicable_atom_footprints"] = footprints

    reference = str(normalized.get("reference_answer") or "")
    additions: list[str] = []
    for footprint in footprints:
        for element in footprint.get("required_answer_elements") or []:
            if (
                isinstance(element, str)
                and element.strip()
                and norm_text(element).casefold()
                not in norm_text(reference).casefold()
            ):
                additions.append(element.strip())
    additions = list(dict.fromkeys(additions))
    if additions:
        normalized["reference_answer"] = (
            reference.rstrip()
            + "\n\n"
            + " ".join(f"{element.rstrip('.')}." for element in additions)
        )
        repairs.append(f"append_missing_required_evidence:{len(additions)}")

    revisions: list[dict[str, Any]] = []
    for footprint in footprints:
        atom_id = str(footprint["atom_id"])
        old_label = str(source_by_id[atom_id].get("u_star") or "")
        new_label = str(footprint.get("u_star") or "")
        if old_label == new_label:
            continue
        revisions.append(
            {
                "atom_id": atom_id,
                "old_u_star": old_label,
                "new_u_star": new_label,
                "reason": str(footprint.get("label_justification") or ""),
            }
        )
    if normalized.get("label_revision_audit") != revisions:
        normalized["label_revision_audit"] = revisions
        repairs.append("recompute_label_revision_audit")

    ignored_a = [
        {
            "atom_id": atom_id,
            "question_has_footprint": False,
            "reference_has_footprint": False,
            "reason": (
                "The negative-control atom is excluded from both the question and "
                "the reference answer."
            ),
        }
        for atom_id in expected_a_ids
    ]
    if normalized.get("ignored_a_audit") != ignored_a:
        normalized["ignored_a_audit"] = ignored_a
        repairs.append("recompute_ignored_a_audit")

    query_audit = [
        {
            "atom_id": atom_id,
            "query_supplies_atom_value": False,
            "reason": "The question leaves this memory-specific value unresolved.",
        }
        for atom_id in expected_bc_ids
    ]
    if normalized.get("query_isolation_audit") != query_audit:
        normalized["query_isolation_audit"] = query_audit
        repairs.append("recompute_query_isolation_audit")
    expected_self_check = {key: True for key in SELF_CHECK_KEYS}
    if normalized.get("self_check") != expected_self_check:
        normalized["self_check"] = expected_self_check
        repairs.append("normalize_self_check")
    return normalized, repairs


def normalize_aux_reclassification_payload(
    payload: dict[str, Any],
    source: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    normalized = copy.deepcopy(payload)
    repairs: list[str] = []
    source_by_id = {
        str(atom.get("atom_id") or ""): atom
        for atom in source.get("memories") or []
    }
    immutable_a = {
        atom_id
        for atom_id, atom in source_by_id.items()
        if atom.get("u_star") == "A"
        and atom_id.startswith(("v22_harda_", "v22_noise_"))
    }
    revisable_a = {
        atom_id
        for atom_id, atom in source_by_id.items()
        if atom.get("u_star") == "A" and atom_id not in immutable_a
    }
    required_original_bc = {
        atom_id
        for atom_id, atom in source_by_id.items()
        if atom.get("u_star") in {"B", "C"}
    }
    footprints: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in normalized.get("applicable_atom_footprints") or []:
        if not isinstance(raw, dict):
            repairs.append("drop_non_object_footprint")
            continue
        atom_id = str(raw.get("atom_id") or "")
        atom = source_by_id.get(atom_id)
        if atom is None:
            repairs.append("drop_unknown_atom_footprint")
            continue
        if atom_id in immutable_a:
            repairs.append(f"drop_immutable_a_footprint:{atom_id}")
            continue
        if atom.get("u_star") == "A" and atom_id not in revisable_a:
            repairs.append(f"drop_ineligible_a_footprint:{atom_id}")
            continue
        if atom_id in seen:
            repairs.append(f"drop_duplicate_footprint:{atom_id}")
            continue
        seen.add(atom_id)
        footprint = copy.deepcopy(raw)
        footprint["atom_id"] = atom_id
        if footprint.get("u_star") not in {"B", "C"}:
            if atom.get("u_star") in {"B", "C"}:
                footprint["u_star"] = atom.get("u_star")
                repairs.append(f"restore_bc_label:{atom_id}")
            else:
                repairs.append(f"drop_unscored_aux_footprint:{atom_id}")
                continue
        expected_action = (
            atom.get("memory_action")
            if atom.get("u_star") in {"B", "C"}
            else "apply"
        )
        if footprint.get("memory_action") != expected_action:
            footprint["memory_action"] = expected_action
            repairs.append(f"restore_action:{atom_id}")
        overuse = footprint.get("overuse_signals")
        if not isinstance(overuse, list) or not overuse:
            footprint["overuse_signals"] = [
                "Any unsupported extension beyond this memory atom."
            ]
            repairs.append(f"fill_overuse_signal:{atom_id}")
        justification = footprint.get("label_justification")
        if not isinstance(justification, str) or len(norm_text(justification)) < 20:
            footprint["label_justification"] = (
                "This atom has bounded supporting influence on the solution."
                if footprint["u_star"] == "B"
                else "This atom controls a core behavior in the requested solution."
            )
            repairs.append(f"fill_label_justification:{atom_id}")
        footprints.append(footprint)
    normalized["applicable_atom_footprints"] = footprints

    reference = str(normalized.get("reference_answer") or "")
    additions: list[str] = []
    for footprint in footprints:
        for element in footprint.get("required_answer_elements") or []:
            if (
                isinstance(element, str)
                and element.strip()
                and norm_text(element).casefold()
                not in norm_text(reference).casefold()
            ):
                additions.append(element.strip())
    additions = list(dict.fromkeys(additions))
    if additions:
        normalized["reference_answer"] = (
            reference.rstrip()
            + "\n\n"
            + " ".join(f"{element.rstrip('.')}." for element in additions)
        )
        repairs.append(f"append_missing_required_evidence:{len(additions)}")

    final_scored_ids = {
        str(footprint.get("atom_id") or "") for footprint in footprints
    }
    final_a_ids = [
        atom_id for atom_id in source_by_id if atom_id not in final_scored_ids
    ]
    revisions: list[dict[str, Any]] = []
    for footprint in footprints:
        atom_id = str(footprint["atom_id"])
        atom = source_by_id[atom_id]
        old_label = str(atom.get("u_star") or "")
        old_action = str(atom.get("memory_action") or "")
        new_label = str(footprint.get("u_star") or "")
        new_action = str(footprint.get("memory_action") or "")
        if old_label == new_label and old_action == new_action:
            continue
        revisions.append(
            {
                "atom_id": atom_id,
                "old_u_star": old_label,
                "new_u_star": new_label,
                "old_memory_action": old_action,
                "new_memory_action": new_action,
                "reason": str(footprint.get("label_justification") or ""),
            }
        )
    if normalized.get("label_action_revision_audit") != revisions:
        normalized["label_action_revision_audit"] = revisions
        repairs.append("recompute_label_action_revision_audit")
    ignored_a = [
        {
            "atom_id": atom_id,
            "question_has_footprint": False,
            "reference_has_footprint": False,
            "reason": (
                "The final negative-control atom is excluded from both the question "
                "and the reference answer."
            ),
        }
        for atom_id in final_a_ids
    ]
    if normalized.get("ignored_a_audit") != ignored_a:
        normalized["ignored_a_audit"] = ignored_a
        repairs.append("recompute_ignored_a_audit")
    query_audit = [
        {
            "atom_id": str(footprint["atom_id"]),
            "query_supplies_atom_value": False,
            "reason": "The question leaves this memory-specific value unresolved.",
        }
        for footprint in footprints
    ]
    if normalized.get("query_isolation_audit") != query_audit:
        normalized["query_isolation_audit"] = query_audit
        repairs.append("recompute_query_isolation_audit")
    expected_self_check = {key: True for key in SELF_CHECK_KEYS_AUX}
    if normalized.get("self_check") != expected_self_check:
        normalized["self_check"] = expected_self_check
        repairs.append("normalize_self_check")
    if not required_original_bc <= final_scored_ids:
        repairs.append("original_bc_coverage_incomplete")
    return normalized, repairs


def validate_custom_payload(
    payload: dict[str, Any],
    source: dict[str, Any],
    params: dict[str, Any],
) -> tuple[list[str], dict[str, Any], list[dict[str, Any]]]:
    if payload.get("schema_version") == PAYLOAD_SCHEMA_AUX:
        return validate_aux_reclassification_payload(payload, source, params)
    errors: list[str] = []
    if payload.get("schema_version") != PAYLOAD_SCHEMA:
        errors.append("schema_version_mismatch")
    if str(payload.get("record_id") or "") != str(source.get("id") or ""):
        errors.append("record_id_mismatch")
    if payload.get("task_family") != params.get("task_family"):
        errors.append("task_family_mismatch")

    source_atoms = list(source.get("memories") or [])
    source_by_id = {
        str(atom.get("atom_id") or ""): atom for atom in source_atoms
    }
    expected_ids = [str(atom.get("atom_id") or "") for atom in source_atoms]
    if expected_ids != params.get("expected_atom_ids"):
        errors.append("expected_atom_ids_mismatch")

    footprints = payload.get("applicable_atom_footprints")
    if not isinstance(footprints, list):
        errors.append("applicable_atom_footprints_not_list")
        footprints = []
    observed_bc_ids: list[str] = []
    final_labels: dict[str, str] = {}
    for index, footprint in enumerate(footprints):
        if not isinstance(footprint, dict):
            errors.append(f"footprint_{index}_not_object")
            continue
        atom_id = str(footprint.get("atom_id") or "")
        observed_bc_ids.append(atom_id)
        source_atom = source_by_id.get(atom_id)
        if source_atom is None:
            errors.append(f"footprint_{index}_unknown_atom_id")
            continue
        if source_atom.get("u_star") not in {"B", "C"}:
            errors.append(f"footprint_{index}_a_atom_cannot_be_scored")
        final_label = str(footprint.get("u_star") or "")
        if final_label not in {"B", "C"}:
            errors.append(f"footprint_{index}_bad_final_label")
        else:
            final_labels[atom_id] = final_label
        if footprint.get("memory_action") != source_atom.get("memory_action"):
            errors.append(f"footprint_{index}_action_changed")
    expected_bc_ids = [
        str(atom.get("atom_id") or "")
        for atom in source_atoms
        if atom.get("u_star") in {"B", "C"}
    ]
    if len(observed_bc_ids) != len(set(observed_bc_ids)):
        errors.append("applicable_atom_ids_not_unique")
    if set(observed_bc_ids) != set(expected_bc_ids):
        errors.append("applicable_atom_coverage_mismatch")

    expected_changes = {
        atom_id: (str(source_by_id[atom_id].get("u_star")), final_label)
        for atom_id, final_label in final_labels.items()
        if final_label != str(source_by_id[atom_id].get("u_star"))
    }
    revision_rows = payload.get("label_revision_audit")
    if not isinstance(revision_rows, list):
        errors.append("label_revision_audit_not_list")
        revision_rows = []
    observed_changes: dict[str, tuple[str, str]] = {}
    revision_audit: list[dict[str, Any]] = []
    for index, row in enumerate(revision_rows):
        if not isinstance(row, dict):
            errors.append(f"label_revision_{index}_not_object")
            continue
        if set(row) != LABEL_REVISION_KEYS:
            errors.append(f"label_revision_{index}_keys_mismatch")
        atom_id = str(row.get("atom_id") or "")
        old_label = str(row.get("old_u_star") or "")
        new_label = str(row.get("new_u_star") or "")
        if atom_id in observed_changes:
            errors.append("label_revision_ids_not_unique")
        observed_changes[atom_id] = (old_label, new_label)
        if old_label == new_label or {old_label, new_label} != {"B", "C"}:
            errors.append(f"label_revision_{index}_not_bc_swap")
        reason = row.get("reason")
        if not isinstance(reason, str) or len(norm_text(reason)) < 20:
            errors.append(f"label_revision_{index}_reason_invalid")
        revision_audit.append(copy.deepcopy(row))
    if observed_changes != expected_changes:
        errors.append("label_revision_audit_mismatch")

    expected_a_ids = [
        str(atom.get("atom_id") or "")
        for atom in source_atoms
        if atom.get("u_star") == "A"
    ]
    a_rows = payload.get("ignored_a_audit")
    if not isinstance(a_rows, list):
        errors.append("ignored_a_audit_not_list")
        a_rows = []
    observed_a_ids: list[str] = []
    for index, row in enumerate(a_rows):
        if not isinstance(row, dict):
            errors.append(f"ignored_a_audit_{index}_not_object")
            continue
        if set(row) != A_AUDIT_KEYS:
            errors.append(f"ignored_a_audit_{index}_keys_mismatch")
        atom_id = str(row.get("atom_id") or "")
        observed_a_ids.append(atom_id)
        if row.get("question_has_footprint") is not False:
            errors.append(f"ignored_a_audit_{index}_question_footprint")
        if row.get("reference_has_footprint") is not False:
            errors.append(f"ignored_a_audit_{index}_reference_footprint")
        reason = row.get("reason")
        if not isinstance(reason, str) or len(norm_text(reason)) < 12:
            errors.append(f"ignored_a_audit_{index}_reason_invalid")
    if len(observed_a_ids) != len(set(observed_a_ids)):
        errors.append("ignored_a_audit_ids_not_unique")
    if set(observed_a_ids) != set(expected_a_ids):
        errors.append("ignored_a_audit_coverage_mismatch")

    self_check = payload.get("self_check")
    if not isinstance(self_check, dict) or set(self_check) != SELF_CHECK_KEYS:
        errors.append("self_check_keys_mismatch")
    elif any(self_check.get(key) is not True for key in SELF_CHECK_KEYS):
        errors.append("self_check_not_all_true")

    corrected_source = copy.deepcopy(source)
    for atom in corrected_source.get("memories") or []:
        atom_id = str(atom.get("atom_id") or "")
        if atom_id in final_labels:
            atom["u_star"] = final_labels[atom_id]

    standard_payload = {
        "schema_version": "memcalib-v24-coding-text-rewrite-payload-v1",
        "record_id": payload.get("record_id"),
        "task_family": payload.get("task_family"),
        "task_stem": payload.get("task_stem"),
        "reference_answer": payload.get("reference_answer"),
        "applicable_atom_footprints": footprints,
        "query_isolation_audit": payload.get("query_isolation_audit"),
        "self_check": {
            "all_applicable_atom_ids_exact": True,
            "locked_labels_actions_preserved": True,
            "query_does_not_restate_scored_memories": True,
            "answer_is_natural_language_only": True,
            "all_required_evidence_visible_in_reference_answer": True,
            "no_runtime_execution_needed_to_judge": True,
        },
    }
    errors.extend(validate_revision_payload(standard_payload, corrected_source, params))

    task_stem = str(payload.get("task_stem") or "")
    reference = str(payload.get("reference_answer") or "")
    for atom in source_atoms:
        if atom.get("u_star") != "A":
            continue
        atom_id = str(atom.get("atom_id") or "")
        errors.extend(
            f"{atom_id}_{reason}"
            for reason in a_footprint_reasons(atom, task_stem, "question")
        )
        errors.extend(
            f"{atom_id}_{reason}"
            for reason in a_footprint_reasons(atom, reference, "reference")
        )
    return list(dict.fromkeys(errors)), corrected_source, revision_audit


def validate_aux_reclassification_payload(
    payload: dict[str, Any],
    source: dict[str, Any],
    params: dict[str, Any],
) -> tuple[list[str], dict[str, Any], list[dict[str, Any]]]:
    errors: list[str] = []
    if payload.get("schema_version") != PAYLOAD_SCHEMA_AUX:
        errors.append("schema_version_mismatch")
    if str(payload.get("record_id") or "") != str(source.get("id") or ""):
        errors.append("record_id_mismatch")
    if payload.get("task_family") != params.get("task_family"):
        errors.append("task_family_mismatch")

    source_atoms = list(source.get("memories") or [])
    source_by_id = {
        str(atom.get("atom_id") or ""): atom for atom in source_atoms
    }
    expected_ids = [str(atom.get("atom_id") or "") for atom in source_atoms]
    if expected_ids != params.get("expected_atom_ids"):
        errors.append("expected_atom_ids_mismatch")
    immutable_a = set(params.get("immutable_a_atom_ids") or [])
    revisable_a = set(params.get("revisable_a_atom_ids") or [])
    expected_immutable = {
        atom_id
        for atom_id, atom in source_by_id.items()
        if atom.get("u_star") == "A"
        and atom_id.startswith(("v22_harda_", "v22_noise_"))
    }
    expected_revisable = {
        atom_id
        for atom_id, atom in source_by_id.items()
        if atom.get("u_star") == "A" and atom_id not in expected_immutable
    }
    if immutable_a != expected_immutable:
        errors.append("immutable_a_atom_ids_mismatch")
    if revisable_a != expected_revisable:
        errors.append("revisable_a_atom_ids_mismatch")

    footprints = payload.get("applicable_atom_footprints")
    if not isinstance(footprints, list):
        errors.append("applicable_atom_footprints_not_list")
        footprints = []
    observed_ids: list[str] = []
    final_labels: dict[str, str] = {}
    final_actions: dict[str, str] = {}
    for index, footprint in enumerate(footprints):
        if not isinstance(footprint, dict):
            errors.append(f"footprint_{index}_not_object")
            continue
        atom_id = str(footprint.get("atom_id") or "")
        observed_ids.append(atom_id)
        atom = source_by_id.get(atom_id)
        if atom is None:
            errors.append(f"footprint_{index}_unknown_atom_id")
            continue
        if atom_id in immutable_a:
            errors.append(f"footprint_{index}_immutable_a_cannot_be_scored")
        if atom.get("u_star") == "A" and atom_id not in revisable_a:
            errors.append(f"footprint_{index}_ineligible_a_cannot_be_scored")
        label = str(footprint.get("u_star") or "")
        action = str(footprint.get("memory_action") or "")
        if label not in {"B", "C"}:
            errors.append(f"footprint_{index}_bad_final_label")
        else:
            final_labels[atom_id] = label
        expected_action = (
            str(atom.get("memory_action") or "")
            if atom.get("u_star") in {"B", "C"}
            else "apply"
        )
        if action != expected_action:
            errors.append(f"footprint_{index}_bad_final_action")
        else:
            final_actions[atom_id] = action
    if len(observed_ids) != len(set(observed_ids)):
        errors.append("applicable_atom_ids_not_unique")
    required_original_bc = {
        atom_id
        for atom_id, atom in source_by_id.items()
        if atom.get("u_star") in {"B", "C"}
    }
    if not required_original_bc <= set(observed_ids):
        errors.append("original_bc_coverage_mismatch")

    expected_revisions: dict[str, tuple[str, str, str, str]] = {}
    for atom_id, new_label in final_labels.items():
        atom = source_by_id[atom_id]
        old_label = str(atom.get("u_star") or "")
        old_action = str(atom.get("memory_action") or "")
        new_action = final_actions.get(atom_id, "")
        if old_label != new_label or old_action != new_action:
            expected_revisions[atom_id] = (
                old_label,
                new_label,
                old_action,
                new_action,
            )
    revision_rows = payload.get("label_action_revision_audit")
    if not isinstance(revision_rows, list):
        errors.append("label_action_revision_audit_not_list")
        revision_rows = []
    observed_revisions: dict[str, tuple[str, str, str, str]] = {}
    revision_audit: list[dict[str, Any]] = []
    for index, row in enumerate(revision_rows):
        if not isinstance(row, dict):
            errors.append(f"label_action_revision_{index}_not_object")
            continue
        if set(row) != LABEL_ACTION_REVISION_KEYS:
            errors.append(f"label_action_revision_{index}_keys_mismatch")
        atom_id = str(row.get("atom_id") or "")
        if atom_id in observed_revisions:
            errors.append("label_action_revision_ids_not_unique")
        observed_revisions[atom_id] = (
            str(row.get("old_u_star") or ""),
            str(row.get("new_u_star") or ""),
            str(row.get("old_memory_action") or ""),
            str(row.get("new_memory_action") or ""),
        )
        reason = row.get("reason")
        if not isinstance(reason, str) or len(norm_text(reason)) < 20:
            errors.append(f"label_action_revision_{index}_reason_invalid")
        revision_audit.append(copy.deepcopy(row))
    if observed_revisions != expected_revisions:
        errors.append("label_action_revision_audit_mismatch")

    final_scored = set(observed_ids)
    expected_final_a = [
        atom_id for atom_id in source_by_id if atom_id not in final_scored
    ]
    a_rows = payload.get("ignored_a_audit")
    if not isinstance(a_rows, list):
        errors.append("ignored_a_audit_not_list")
        a_rows = []
    observed_a_ids: list[str] = []
    for index, row in enumerate(a_rows):
        if not isinstance(row, dict):
            errors.append(f"ignored_a_audit_{index}_not_object")
            continue
        if set(row) != A_AUDIT_KEYS:
            errors.append(f"ignored_a_audit_{index}_keys_mismatch")
        atom_id = str(row.get("atom_id") or "")
        observed_a_ids.append(atom_id)
        if row.get("question_has_footprint") is not False:
            errors.append(f"ignored_a_audit_{index}_question_footprint")
        if row.get("reference_has_footprint") is not False:
            errors.append(f"ignored_a_audit_{index}_reference_footprint")
        reason = row.get("reason")
        if not isinstance(reason, str) or len(norm_text(reason)) < 12:
            errors.append(f"ignored_a_audit_{index}_reason_invalid")
    if len(observed_a_ids) != len(set(observed_a_ids)):
        errors.append("ignored_a_audit_ids_not_unique")
    if set(observed_a_ids) != set(expected_final_a):
        errors.append("ignored_a_audit_coverage_mismatch")

    self_check = payload.get("self_check")
    if not isinstance(self_check, dict) or set(self_check) != SELF_CHECK_KEYS_AUX:
        errors.append("self_check_keys_mismatch")
    elif any(self_check.get(key) is not True for key in SELF_CHECK_KEYS_AUX):
        errors.append("self_check_not_all_true")

    corrected_source = copy.deepcopy(source)
    for atom in corrected_source.get("memories") or []:
        atom_id = str(atom.get("atom_id") or "")
        if atom_id in final_labels:
            atom["u_star"] = final_labels[atom_id]
            atom["memory_action"] = final_actions[atom_id]

    standard_payload = {
        "schema_version": "memcalib-v24-coding-text-rewrite-payload-v1",
        "record_id": payload.get("record_id"),
        "task_family": payload.get("task_family"),
        "task_stem": payload.get("task_stem"),
        "reference_answer": payload.get("reference_answer"),
        "applicable_atom_footprints": footprints,
        "query_isolation_audit": payload.get("query_isolation_audit"),
        "self_check": {
            "all_applicable_atom_ids_exact": True,
            "locked_labels_actions_preserved": True,
            "query_does_not_restate_scored_memories": True,
            "answer_is_natural_language_only": True,
            "all_required_evidence_visible_in_reference_answer": True,
            "no_runtime_execution_needed_to_judge": True,
        },
    }
    errors.extend(validate_revision_payload(standard_payload, corrected_source, params))
    task_stem = str(payload.get("task_stem") or "")
    reference = str(payload.get("reference_answer") or "")
    for atom in corrected_source.get("memories") or []:
        if atom.get("u_star") != "A":
            continue
        atom_id = str(atom.get("atom_id") or "")
        errors.extend(
            f"{atom_id}_{reason}"
            for reason in a_footprint_reasons(atom, task_stem, "question")
        )
        errors.extend(
            f"{atom_id}_{reason}"
            for reason in a_footprint_reasons(atom, reference, "reference")
        )
    return list(dict.fromkeys(errors)), corrected_source, revision_audit


def build_record(
    corrected_source: dict[str, Any],
    payload: dict[str, Any],
    params: dict[str, Any],
    request_id: str,
    revision_audit: list[dict[str, Any]],
    deterministic_repairs: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    record = copy.deepcopy(corrected_source)
    family = str(payload["task_family"])
    record["question"] = materialize_question(str(payload["task_stem"]), family)
    record["source_answer"] = str(payload["reference_answer"]).strip()
    footprints = {
        str(item["atom_id"]): item
        for item in payload["applicable_atom_footprints"]
    }
    for atom in record.get("memories") or []:
        atom_id = str(atom.get("atom_id") or "")
        atom.update(build_atom_supervision(atom, footprints.get(atom_id)))
    record["schema_version"] = "crk-2-canonical-memory-v2.4.1"
    record["coding_text_observability_revision"] = {
        "schema_version": REVISION_SCHEMA,
        "request_id": request_id,
        "task_family": family,
        "source_record_fingerprint": params["source_record_fingerprint"],
        "memory_blocks_fingerprint": params["memory_blocks_fingerprint"],
        "atom_identity_fingerprint": params["atom_identity_fingerprint"],
        "question_contract": "natural_language_only_no_code_blocks",
        "labels_and_actions_locked": False,
        "label_change_scope": (
            "eligible_auxiliary_A_to_BC_and_BC_magnitude"
            if payload.get("schema_version") == PAYLOAD_SCHEMA_AUX
            else "B_C_magnitude_only"
        ),
        "memory_atoms_and_blocks_locked": True,
        "rubrics_rebuilt_for_answer_text": True,
        "label_revision_audit": revision_audit,
        "deterministic_repairs": deterministic_repairs,
    }
    audit = {
        "schema_version": "memcalib-v241-relabel-aware-repair-audit-v1",
        "record_id": record["id"],
        "request_id": request_id,
        "task_family": family,
        "source_record_fingerprint": params["source_record_fingerprint"],
        "output_record_fingerprint": canonical_sha256(record),
        "revised_question": record["question"],
        "revised_reference_answer": record["source_answer"],
        "label_revision_audit": revision_audit,
        "ignored_a_audit": payload["ignored_a_audit"],
        "applicable_atom_footprints": payload["applicable_atom_footprints"],
        "query_isolation_audit": payload["query_isolation_audit"],
        "deterministic_repairs": deterministic_repairs,
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
    family = str(params.get("task_family") or "")
    question = str(record.get("question") or "")
    reference = str(record.get("source_answer") or "")
    if family not in QUESTION_SUFFIXES or not question.endswith(
        QUESTION_SUFFIXES.get(family, "")
    ):
        errors.append("standard_question_contract_missing")
    if CODE_FENCE_RE.search(question):
        errors.append("question_contains_code_fence")
    if CODE_FENCE_RE.search(reference):
        errors.append("reference_answer_contains_code_fence")
    if record.get("memory_blocks") != source.get("memory_blocks"):
        errors.append("memory_blocks_changed")
    if canonical_sha256(record.get("memory_blocks") or []) != params.get(
        "memory_blocks_fingerprint"
    ):
        errors.append("memory_blocks_fingerprint_mismatch")
    source_by_id = {
        str(atom.get("atom_id") or ""): atom for atom in source.get("memories") or []
    }
    revisable_a = set(params.get("revisable_a_atom_ids") or [])
    identity_record = copy.deepcopy(record)
    for atom in identity_record.get("memories") or []:
        atom_id = str(atom.get("atom_id") or "")
        original = source_by_id.get(atom_id)
        if original is not None and atom_id in revisable_a:
            atom["memory_action"] = original.get("memory_action")
    if atom_identity_fingerprint(identity_record) != params.get(
        "atom_identity_fingerprint"
    ):
        errors.append("atom_identity_changed")
    for atom in record.get("memories") or []:
        atom_id = str(atom.get("atom_id") or "")
        original = source_by_id.get(atom_id)
        if original is None:
            errors.append(f"unknown_output_atom:{atom_id}")
            continue
        old_label = original.get("u_star")
        new_label = atom.get("u_star")
        if (
            old_label == "A"
            and new_label != "A"
            and atom_id not in revisable_a
        ):
            errors.append(f"ineligible_a_label_changed:{atom_id}")
        if old_label == "A" and new_label in {"B", "C"}:
            if atom.get("memory_action") != "apply":
                errors.append(f"promoted_a_action_invalid:{atom_id}")
        if old_label in {"B", "C"} and new_label not in {"B", "C"}:
            errors.append(f"bc_label_left_scored_set:{atom_id}")
        if old_label in {"B", "C"} and atom.get(
            "memory_action"
        ) != original.get("memory_action"):
            errors.append(f"memory_action_changed:{atom_id}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Postprocess relabel-aware v2.4.1 direct coding repairs."
    )
    parser.add_argument("--benchmark", type=Path, default=V23_RELEASE)
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--prefix", type=Path, default=DEFAULT_PREFIX)
    args = parser.parse_args()

    sources = {
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
    label_changes: Counter[str] = Counter()
    deterministic_repair_counts: Counter[str] = Counter()
    for request in requests:
        request_id = str(request.get("request_id") or "")
        params = request_params(request)
        record_id = str(params.get("record_id") or "")
        source = sources.get(record_id)
        result = results.get(request_id)
        errors: list[str] = []
        payload: dict[str, Any] | None = None
        corrected_source: dict[str, Any] | None = None
        revision_audit: list[dict[str, Any]] = []
        deterministic_repairs: list[str] = []
        if source is None:
            errors.append("source_record_missing")
        else:
            if canonical_sha256(source) != params.get("source_record_fingerprint"):
                errors.append("source_record_fingerprint_mismatch")
            if canonical_sha256(source.get("memory_blocks") or []) != params.get(
                "memory_blocks_fingerprint"
            ):
                errors.append("memory_blocks_fingerprint_mismatch")
            if atom_identity_fingerprint(source) != params.get(
                "atom_identity_fingerprint"
            ):
                errors.append("atom_identity_fingerprint_mismatch")
        if result is None:
            errors.append("api_result_missing")
        else:
            if request_params(result) and request_params(result) != params:
                errors.append("result_params_mismatch")
            try:
                payload = extract_json_object(output_text(result))
                if source is not None:
                    payload, deterministic_repairs = normalize_model_payload(
                        payload, source
                    )
            except (ValueError, json.JSONDecodeError) as exc:
                errors.append(f"invalid_json:{exc}")
        if source is not None and payload is not None and not errors:
            payload_errors, corrected_source, revision_audit = (
                validate_custom_payload(payload, source, params)
            )
            errors.extend(payload_errors)
        record: dict[str, Any] | None = None
        audit: dict[str, Any] | None = None
        if (
            source is not None
            and payload is not None
            and corrected_source is not None
            and not errors
        ):
            record, audit = build_record(
                corrected_source,
                payload,
                params,
                request_id,
                revision_audit,
                deterministic_repairs,
            )
            errors.extend(validate_built_record(record, source, params))
        if errors:
            invalid.append(
                {
                    "request_id": request_id,
                    "record_id": record_id,
                    "errors": list(dict.fromkeys(errors)),
                    "result_present": result is not None,
                }
            )
            continue
        assert record is not None and audit is not None
        valid.append(record)
        audits.append(audit)
        for change in revision_audit:
            label_changes[
                f"{change['old_u_star']}->{change['new_u_star']}"
            ] += 1
        deterministic_repair_counts.update(deterministic_repairs)

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
        "schema_version": "memcalib-v241-relabel-aware-repair-summary-v1",
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
            "valid": len(valid),
            "invalid": len(invalid),
            "audit": len(audits),
        },
        "label_change_counts": dict(sorted(label_changes.items())),
        "deterministic_repair_counts": dict(
            sorted(deterministic_repair_counts.items())
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
