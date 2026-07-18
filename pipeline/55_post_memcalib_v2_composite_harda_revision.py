#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any

from utils import extract_json_object, iter_jsonl, norm_text, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data" / "multidomain" / "full-v2"
REVISION_DIR = DATA_DIR / "revision-composite-harda"
DEFAULT_BENCHMARK = DATA_DIR / "memcalib_v02_multidomain_benchmark_15000.jsonl"
DEFAULT_REQUESTS = REVISION_DIR / "composite_harda_patch_input_15000.jsonl"
DEFAULT_RESULTS = REVISION_DIR / "composite_harda_patch_result_15000.jsonl"
DEFAULT_OUTPUT = REVISION_DIR / "memcalib_v21_composite_harda_benchmark_15000.jsonl"
DEFAULT_REJECTED = REVISION_DIR / "memcalib_v21_composite_harda_benchmark_15000.rejected.jsonl"
DEFAULT_SUMMARY = REVISION_DIR / "memcalib_v21_composite_harda_benchmark_15000.summary.json"

REQUEST_SCHEMA = "memcalib-composite-harda-patch-requests-v2"
PATCH_SCHEMA = "memcalib-composite-harda-patch-v2"
RECORD_SCHEMA = "crk-2-canonical-memory-v2.1"
REVISION_SCHEMA = "memcalib-composite-harda-revision-v1"
COMPOSITE_PARENT_ID = "v21_real_composite"
HARD_A_PARENT_ID = "v21_hard_a"
HARD_A_ATOM_ID = "v21_hard_a_a1"
HARD_A_FAMILIES = {
    "factual_judgment_pollution",
    "scope_overreach",
    "current_evidence_conflict",
    "profile_style_near_neighbor",
    "untriggered_preference",
}
ALLOWED_MEMORY_TYPES = {"case_fact", "constraint", "preference", "profile_fact", "safety_sensitive"}
TARGET_KEYS = {"task_goal", "memory_role", "usage_boundary", "failure_direction"}
CONTRACT_KEYS = {"without_memory_behavior", "with_memory_behavior", "observable_delta", "minimal_evidence"}
RUBRIC_KEYS = {
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
SELF_CHECK_KEYS = {
    "family_match",
    "surface_relevance_present",
    "no_decision_authority",
    "no_answer_footprint",
    "no_explicit_correction_required",
    "independent_of_all_real_atoms",
}
FAMILY_AUDIT_KEYS = {
    "task_boundary_anchor",
    "family_specific_mechanism",
    "tempting_incorrect_use",
    "no_valid_bounded_use",
    "explicit_correction_test",
}
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
FIRST_PERSON_RE = re.compile(r"^\s*(?:i|i'm|i've|i am|my|me|mine|we|we're|we are|our)\b", re.IGNORECASE)


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


def require_text(value: Any, path: str, errors: list[str], minimum: int = 8) -> str:
    text = norm_text(str(value or ""))
    if len(text) < minimum:
        errors.append(f"{path}_missing_or_short")
    elif CJK_RE.search(text):
        errors.append(f"{path}_non_english")
    return text


def real_atoms(record: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        atom
        for atom in record.get("memories") or []
        if isinstance(atom, dict) and atom.get("source") != "synthetic_hard_a"
    ]


def normalize_patch_structure(
    patch: dict[str, Any],
    expected_record_id: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    normalized = copy.deepcopy(patch)
    normalizations: list[str] = []
    if expected_record_id and normalized.get("record_id") != expected_record_id:
        normalized["record_id"] = expected_record_id
        normalizations.append("restored_locked_record_id_from_request")
    hard_a = normalized.get("hard_a")
    self_check = normalized.get("self_check")
    if not isinstance(hard_a, dict):
        return normalized, normalizations
    family_audit = hard_a.get("family_audit")
    if (
        isinstance(family_audit, dict)
        and set(family_audit) == FAMILY_AUDIT_KEYS - {"explicit_correction_test"}
        and isinstance(self_check, dict)
        and self_check.get("no_explicit_correction_required") is True
    ):
        family_audit["explicit_correction_test"] = "not_required"
        normalizations.append("filled_explicit_correction_test_from_true_self_check")
    target = hard_a.get("construction_target")
    if isinstance(target, dict):
        role = norm_text(str(target.get("memory_role") or "")).casefold()
        if role != "none" and "no answer role" in role and "ignore" in role:
            target["memory_role"] = "none"
            normalizations.append("canonicalized_no_answer_role_to_none")
    return normalized, normalizations


def validate_patch(
    patch: dict[str, Any],
    record: dict[str, Any],
    params: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    record_id = str(record.get("id") or "")
    family = str(params.get("hard_a_family") or "")
    expected_atom_ids = [str(atom.get("atom_id") or "") for atom in real_atoms(record)]

    if patch.get("schema_version") != PATCH_SCHEMA:
        errors.append("bad_patch_schema")
    if str(patch.get("record_id") or "") != record_id:
        errors.append("record_id_mismatch")
    if family not in HARD_A_FAMILIES or patch.get("hard_a_family") != family:
        errors.append("hard_a_family_mismatch")

    hard_a = patch.get("hard_a")
    if not isinstance(hard_a, dict):
        return errors + ["hard_a_not_object"]
    memory_text = require_text(hard_a.get("memory_text"), "hard_a.memory_text", errors, minimum=20)
    if FIRST_PERSON_RE.search(memory_text):
        errors.append("hard_a_memory_is_first_person")
    if hard_a.get("memory_type") not in ALLOWED_MEMORY_TYPES:
        errors.append("bad_hard_a_memory_type")
    for key in ("subtype", "label_reason", "surface_relevance", "non_applicability_reason"):
        require_text(hard_a.get(key), f"hard_a.{key}", errors)

    family_audit = hard_a.get("family_audit")
    if not isinstance(family_audit, dict):
        errors.append("family_audit_not_object")
    else:
        if set(family_audit) != FAMILY_AUDIT_KEYS:
            errors.append("family_audit_keys_mismatch")
        for key in FAMILY_AUDIT_KEYS - {"explicit_correction_test"}:
            require_text(family_audit.get(key), f"family_audit.{key}", errors, minimum=15)
        if norm_text(str(family_audit.get("explicit_correction_test") or "")).casefold() != "not_required":
            errors.append("family_audit_explicit_correction_not_not_required")

    target = hard_a.get("construction_target")
    if not isinstance(target, dict):
        errors.append("construction_target_not_object")
    else:
        if set(target) != TARGET_KEYS:
            errors.append("construction_target_keys_mismatch")
        for key in TARGET_KEYS - {"memory_role"}:
            require_text(target.get(key), f"construction_target.{key}", errors)
        if norm_text(str(target.get("memory_role") or "")).casefold() != "none":
            errors.append("construction_target_memory_role_not_none")

    contract = hard_a.get("counterfactual_contract")
    if not isinstance(contract, dict):
        errors.append("counterfactual_contract_not_object")
    else:
        if set(contract) != CONTRACT_KEYS:
            errors.append("counterfactual_contract_keys_mismatch")
        require_text(contract.get("without_memory_behavior"), "contract.without_memory_behavior", errors)
        require_text(contract.get("with_memory_behavior"), "contract.with_memory_behavior", errors)
        if norm_text(str(contract.get("observable_delta") or "")).casefold() != "none":
            errors.append("counterfactual_observable_delta_not_none")
        if contract.get("minimal_evidence") != []:
            errors.append("counterfactual_minimal_evidence_not_empty")

    rubric = hard_a.get("usage_rubric")
    if not isinstance(rubric, dict):
        errors.append("usage_rubric_not_object")
    else:
        if set(rubric) != RUBRIC_KEYS:
            errors.append("usage_rubric_keys_mismatch")
        for key in RUBRIC_KEYS - {"observable_checks", "memory_usage_weight"}:
            require_text(rubric.get(key), f"usage_rubric.{key}", errors)
        if norm_text(str(rubric.get("memory_usage_weight") or "")).casefold() != "none":
            errors.append("usage_rubric_weight_not_none")
        checks = rubric.get("observable_checks")
        if not isinstance(checks, list) or len(checks) < 2:
            errors.append("usage_rubric_observable_checks_too_few")
        else:
            for index, check in enumerate(checks):
                require_text(check, f"usage_rubric.observable_checks.{index}", errors)

    independence = hard_a.get("independence_from_real_atoms")
    if not isinstance(independence, list):
        errors.append("independence_not_list")
    else:
        observed: list[str] = []
        for index, item in enumerate(independence):
            if not isinstance(item, dict):
                errors.append(f"independence_{index}_not_object")
                continue
            atom_id = str(item.get("atom_id") or "")
            observed.append(atom_id)
            require_text(item.get("reason"), f"independence.{atom_id}.reason", errors, minimum=15)
        if len(observed) != len(set(observed)):
            errors.append("independence_duplicate_atom_id")
        if set(observed) != set(expected_atom_ids):
            errors.append("independence_atom_coverage_mismatch")

    self_check = patch.get("self_check")
    if not isinstance(self_check, dict):
        errors.append("self_check_not_object")
    else:
        if set(self_check) != SELF_CHECK_KEYS:
            errors.append("self_check_keys_mismatch")
        for key in SELF_CHECK_KEYS:
            if self_check.get(key) is not True:
                errors.append(f"self_check_{key}_not_true")

    real_texts = {norm_text(str(atom.get("text") or "")).casefold() for atom in real_atoms(record)}
    if memory_text.casefold() in real_texts:
        errors.append("hard_a_duplicates_real_atom")
    if len(expected_atom_ids) < 2 or "" in expected_atom_ids or len(expected_atom_ids) != len(set(expected_atom_ids)):
        errors.append("bad_real_atom_ids")
    if params.get("schema_version") != REQUEST_SCHEMA:
        errors.append("bad_request_schema")
    if params.get("record_fingerprint") != canonical_sha256(record):
        errors.append("record_fingerprint_mismatch")
    if list(params.get("real_atom_ids") or []) != expected_atom_ids:
        errors.append("request_real_atom_ids_mismatch")
    return sorted(set(errors))


def composite_memory_text(atoms: list[dict[str, Any]]) -> str:
    return " ".join(f"{index}. {norm_text(str(atom.get('text') or ''))}" for index, atom in enumerate(atoms, 1))


def rebuild_record(
    original: dict[str, Any],
    patch: dict[str, Any],
    request_id: str,
    params: dict[str, Any],
    structural_normalizations: list[str] | None = None,
) -> dict[str, Any]:
    record = copy.deepcopy(original)
    atoms = [copy.deepcopy(atom) for atom in real_atoms(original)]
    atom_count = len(atoms)
    for index, atom in enumerate(atoms, 1):
        atom["parent_memory_id"] = COMPOSITE_PARENT_ID
        atom["atom_index"] = index
        atom["atom_count"] = atom_count

    hard = patch["hard_a"]
    hard_atom = {
        "memory_id": HARD_A_ATOM_ID,
        "parent_memory_id": HARD_A_PARENT_ID,
        "atom_id": HARD_A_ATOM_ID,
        "atom_index": 1,
        "atom_count": 1,
        "text": norm_text(str(hard["memory_text"])),
        "evidence": "",
        "atomic_predicate": norm_text(str(hard["memory_text"])),
        "derivation": "synthetic",
        "source": "synthetic_hard_a",
        "memory_type": hard["memory_type"],
        "u_star": "A",
        "memory_action": "ignore",
        "query_relation": "absent",
        "subtype": norm_text(str(hard["subtype"])),
        "hard_a_family": patch["hard_a_family"],
        "label_reason": norm_text(str(hard["label_reason"])),
        "surface_relevance": norm_text(str(hard["surface_relevance"])),
        "non_applicability_reason": norm_text(str(hard["non_applicability_reason"])),
        "family_audit": copy.deepcopy(hard["family_audit"]),
        "construction_target": copy.deepcopy(hard["construction_target"]),
        "counterfactual_contract": copy.deepcopy(hard["counterfactual_contract"]),
        "usage_rubric": copy.deepcopy(hard["usage_rubric"]),
    }

    old_blocks = {
        str(block.get("parent_memory_id") or ""): block
        for block in original.get("memory_blocks") or []
        if isinstance(block, dict)
    }
    source_spans = []
    component_parent_ids = []
    raw_evidence_parts = []
    for atom in atoms:
        atom_id = str(atom.get("atom_id") or "")
        parent_id = str(next(
            (
                old_atom.get("parent_memory_id")
                for old_atom in original.get("memories") or []
                if isinstance(old_atom, dict) and str(old_atom.get("atom_id") or "") == atom_id
            ),
            "",
        ))
        component_parent_ids.append(parent_id)
        evidence = norm_text(str(atom.get("evidence") or ""))
        if evidence:
            raw_evidence_parts.append(evidence)
        source_spans.append(
            {
                "atom_id": atom_id,
                "source": atom.get("source"),
                "evidence": evidence,
                "original_parent_memory_id": parent_id,
                "original_memory_text": old_blocks.get(parent_id, {}).get("memory_text", ""),
            }
        )

    composite_block = {
        "parent_memory_id": COMPOSITE_PARENT_ID,
        "raw_evidence": "\n".join(raw_evidence_parts),
        "memory_text": composite_memory_text(atoms),
        "source": "composite_grounded",
        "atom_ids": [str(atom["atom_id"]) for atom in atoms],
        "atomization_notes": (
            "Deterministic visible composite of the locked grounded atoms. Numbered clauses map one-to-one to atom_ids "
            "and introduce no new proposition."
        ),
        "component_parent_ids": component_parent_ids,
        "source_spans": source_spans,
    }
    hard_block = {
        "parent_memory_id": HARD_A_PARENT_ID,
        "raw_evidence": "",
        "memory_text": hard_atom["text"],
        "source": "synthetic_hard_a",
        "atom_ids": [HARD_A_ATOM_ID],
        "atomization_notes": (
            f"Balanced five-family synthetic Hard A ({patch['hard_a_family']}); independently audited as A + ignore."
        ),
    }

    old_relations = {
        tuple(sorted((str(item.get("left_atom_id") or ""), str(item.get("right_atom_id") or "")))): item
        for item in original.get("atom_pair_relations") or []
        if isinstance(item, dict)
    }
    relations: list[dict[str, Any]] = []
    for left, right in combinations([str(atom["atom_id"]) for atom in atoms], 2):
        old_relation = old_relations[(min(left, right), max(left, right))]
        relations.append(copy.deepcopy(old_relation))
    independence = {
        str(item["atom_id"]): norm_text(str(item["reason"]))
        for item in hard["independence_from_real_atoms"]
    }
    for atom in atoms:
        atom_id = str(atom["atom_id"])
        relations.append(
            {
                "left_atom_id": atom_id,
                "right_atom_id": HARD_A_ATOM_ID,
                "relation": "independent",
                "reason": independence[atom_id],
            }
        )

    record["schema_version"] = RECORD_SCHEMA
    record["memory_blocks"] = [composite_block, hard_block]
    record["memories"] = atoms + [hard_atom]
    record["atom_pair_relations"] = relations
    record["accepted"] = True
    record["deterministic_qc"] = {
        "schema_version": REVISION_SCHEMA,
        "decision": "pass",
        "checks": {
            "question_locked": True,
            "real_atoms_locked": True,
            "composite_exact_atom_coverage": True,
            "composite_introduces_no_new_proposition": True,
            "hard_a_contract_valid": True,
            "pairwise_relation_coverage": True,
        },
    }
    record.pop("independent_qc", None)
    record.pop("release_admission", None)
    record["construction_revision"] = {
        "schema_version": REVISION_SCHEMA,
        "revision": "v2.1-composite-five-family-hard-a",
        "source_record_schema_version": original.get("schema_version"),
        "source_record_fingerprint": canonical_sha256(original),
        "patch_request_id": request_id,
        "patch_family": params["hard_a_family"],
        "patch_fingerprint": canonical_sha256(patch),
        "structural_normalizations": list(structural_normalizations or []),
        "question_locked": True,
        "real_atom_ids_locked": [str(atom["atom_id"]) for atom in atoms],
        "real_atom_labels_locked": {
            str(atom["atom_id"]): {
                "u_star": atom.get("u_star"),
                "memory_action": atom.get("memory_action"),
            }
            for atom in atoms
        },
        "visible_block_policy": "one grounded multi-atom composite plus one single-atom synthetic Hard A",
    }
    return record


def validate_rebuilt(record: dict[str, Any], original: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if record.get("schema_version") != RECORD_SCHEMA:
        errors.append("bad_rebuilt_schema")
    if record.get("id") != original.get("id") or record.get("question") != original.get("question"):
        errors.append("locked_identity_or_question_changed")
    blocks = record.get("memory_blocks") or []
    atoms = record.get("memories") or []
    if len(blocks) != 2:
        errors.append("rebuilt_block_count_not_two")
    if len(atoms) < 3:
        errors.append("rebuilt_atom_count_too_low")
    real = [atom for atom in atoms if atom.get("source") != "synthetic_hard_a"]
    hard = [atom for atom in atoms if atom.get("source") == "synthetic_hard_a"]
    if len(real) < 2 or len(hard) != 1:
        errors.append("rebuilt_real_or_hard_atom_count_invalid")
    old_real = real_atoms(original)
    if [
        {
            key: atom.get(key)
            for key in (
                "atom_id",
                "text",
                "evidence",
                "source",
                "memory_type",
                "u_star",
                "memory_action",
                "label_reason",
                "construction_target",
                "counterfactual_contract",
                "usage_rubric",
            )
        }
        for atom in real
    ] != [
        {
            key: atom.get(key)
            for key in (
                "atom_id",
                "text",
                "evidence",
                "source",
                "memory_type",
                "u_star",
                "memory_action",
                "label_reason",
                "construction_target",
                "counterfactual_contract",
                "usage_rubric",
            )
        }
        for atom in old_real
    ]:
        errors.append("locked_real_atom_content_changed")
    if blocks:
        if blocks[0].get("source") != "composite_grounded":
            errors.append("first_block_not_composite_grounded")
        if blocks[0].get("memory_text") != composite_memory_text(real):
            errors.append("composite_visible_text_mismatch")
        if list(blocks[0].get("atom_ids") or []) != [str(atom.get("atom_id") or "") for atom in real]:
            errors.append("composite_atom_coverage_mismatch")
        if blocks[1].get("source") != "synthetic_hard_a" or blocks[1].get("atom_ids") != [HARD_A_ATOM_ID]:
            errors.append("second_block_not_single_hard_a")
    expected_pairs = len(atoms) * (len(atoms) - 1) // 2
    relations = record.get("atom_pair_relations") or []
    observed_pairs = {
        tuple(sorted((str(item.get("left_atom_id") or ""), str(item.get("right_atom_id") or ""))))
        for item in relations
        if isinstance(item, dict)
    }
    if len(relations) != expected_pairs or len(observed_pairs) != expected_pairs:
        errors.append("pairwise_relation_coverage_mismatch")
    if hard:
        hard_atom = hard[0]
        if hard_atom.get("u_star") != "A" or hard_atom.get("memory_action") != "ignore":
            errors.append("hard_a_label_action_invalid")
        if hard_atom.get("counterfactual_contract", {}).get("observable_delta") != "none":
            errors.append("hard_a_observable_delta_invalid")
        if hard_atom.get("counterfactual_contract", {}).get("minimal_evidence") != []:
            errors.append("hard_a_minimal_evidence_invalid")
    return sorted(set(errors))


def main() -> None:
    parser = argparse.ArgumentParser(description="Post-process composite-block and balanced five-family Hard-A revisions.")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--rejected", type=Path, default=DEFAULT_REJECTED)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()

    original_rows = list(iter_jsonl(args.benchmark))
    original_by_id = {str(row.get("id") or ""): row for row in original_rows}
    requests = list(iter_jsonl(args.requests))
    request_by_id = {str(row.get("request_id") or ""): row for row in requests}
    if len(request_by_id) != len(requests) or "" in request_by_id:
        raise ValueError("request IDs must be non-empty and unique")
    result_rows = list(iter_jsonl(args.results))
    result_by_id = {str(row.get("request_id") or ""): row for row in result_rows}
    if len(result_by_id) != len(result_rows) or "" in result_by_id:
        raise ValueError("result request IDs must be non-empty and unique")

    valid_by_record_id: dict[str, dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []
    rejection_reasons: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    family_by_domain: dict[str, Counter[str]] = {}

    for request_id, request in request_by_id.items():
        request_params = get_params(request)
        record_id = str(request_params.get("record_id") or "")
        original = original_by_id.get(record_id)
        result = result_by_id.get(request_id)
        errors: list[str] = []
        patch: dict[str, Any] | None = None
        structural_normalizations: list[str] = []
        if original is None:
            errors.append("original_record_missing")
        if result is None:
            errors.append("api_result_missing")
        else:
            result_params = get_params(result)
            if result_params and result_params != request_params:
                errors.append("result_params_mismatch")
            try:
                patch = extract_json_object(get_output_text(result))
                patch, structural_normalizations = normalize_patch_structure(patch, record_id)
            except (ValueError, json.JSONDecodeError, TypeError) as exc:
                errors.append(f"patch_parse_error:{type(exc).__name__}")
        if original is not None and patch is not None:
            errors.extend(validate_patch(patch, original, request_params))
        rebuilt = None
        if not errors and original is not None and patch is not None:
            try:
                rebuilt = rebuild_record(
                    original,
                    patch,
                    request_id,
                    request_params,
                    structural_normalizations,
                )
                errors.extend(validate_rebuilt(rebuilt, original))
            except (KeyError, TypeError, ValueError) as exc:
                errors.append(f"rebuild_error:{type(exc).__name__}:{exc}")

        if errors:
            for error in sorted(set(errors)):
                rejection_reasons[error] += 1
            rejected.append(
                {
                    "request_id": request_id,
                    "record_id": record_id,
                    "domain": request_params.get("domain"),
                    "hard_a_family": request_params.get("hard_a_family"),
                    "errors": sorted(set(errors)),
                    "raw_result": result,
                }
            )
            continue
        assert rebuilt is not None
        valid_by_record_id[record_id] = rebuilt
        family = str(request_params["hard_a_family"])
        domain = str(rebuilt.get("domain") or "health_seed")
        family_counts[family] += 1
        family_by_domain.setdefault(domain, Counter())[family] += 1

    selected_record_ids = {
        str(get_params(request).get("record_id") or "")
        for request in requests
    }
    valid = [
        valid_by_record_id[str(row.get("id") or "")]
        for row in original_rows
        if str(row.get("id") or "") in selected_record_ids and str(row.get("id") or "") in valid_by_record_id
    ]
    write_jsonl(args.output, valid)
    write_jsonl(args.rejected, rejected)

    blocks = [block for row in valid for block in row.get("memory_blocks") or []]
    multi_blocks = [block for block in blocks if len(block.get("atom_ids") or []) >= 2]
    summary = {
        "schema_version": REVISION_SCHEMA,
        "inputs": {
            "benchmark": {
                "path": portable_path(args.benchmark),
                "sha256": file_sha256(args.benchmark),
                "records": len(original_rows),
            },
            "requests": {
                "path": portable_path(args.requests),
                "sha256": file_sha256(args.requests),
                "records": len(requests),
            },
            "results": {
                "path": portable_path(args.results),
                "sha256": file_sha256(args.results),
                "records": len(result_rows),
            },
        },
        "counts": {
            "requested": len(requests),
            "api_results": len(result_rows),
            "valid": len(valid),
            "rejected": len(rejected),
            "missing_api_results": len(set(request_by_id) - set(result_by_id)),
            "visible_blocks": len(blocks),
            "multi_atom_visible_blocks": len(multi_blocks),
            "multi_atom_visible_block_share": round(len(multi_blocks) / len(blocks), 6) if blocks else 0.0,
            "samples_with_multi_atom_block": sum(
                any(len(block.get("atom_ids") or []) >= 2 for block in row.get("memory_blocks") or [])
                for row in valid
            ),
        },
        "distribution": {
            "domain": dict(sorted(Counter(str(row.get("domain") or "health_seed") for row in valid).items())),
            "hard_a_family": dict(sorted(family_counts.items())),
            "hard_a_family_by_domain": {
                domain: dict(sorted(counts.items())) for domain, counts in sorted(family_by_domain.items())
            },
        },
        "rejection_reasons": dict(sorted(rejection_reasons.items())),
        "outputs": {
            "valid": {"path": portable_path(args.output), "sha256": file_sha256(args.output)},
            "rejected": {"path": portable_path(args.rejected), "sha256": file_sha256(args.rejected)},
        },
    }
    write_json(args.summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
