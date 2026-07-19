#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any

from utils import extract_json_object, iter_jsonl, norm_text, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data" / "multidomain" / "full-v2"
V21_DIR = DATA_DIR / "revision-composite-harda"
V22_DIR = DATA_DIR / "revision-longtail-blocks"
DEFAULT_BENCHMARK = (
    V21_DIR / "release" / "memcalib_v21_multidomain_benchmark_15000.jsonl"
)
DEFAULT_REQUESTS = V22_DIR / "memcalib_v22_longtail_augmentation_input_15000.jsonl"
DEFAULT_RESULTS = V22_DIR / "memcalib_v22_longtail_augmentation_result_15000.jsonl"
DEFAULT_OUTPUT = V22_DIR / "memcalib_v22_longtail_benchmark_15000.jsonl"
DEFAULT_REJECTED = V22_DIR / "memcalib_v22_longtail_benchmark_15000.rejected.jsonl"
DEFAULT_SUMMARY = V22_DIR / "memcalib_v22_longtail_benchmark_15000.summary.json"

REQUEST_SCHEMA = "memcalib-v22-longtail-augmentation-requests-v1"
AUGMENTATION_SCHEMA = "memcalib-v22-longtail-augmentation-v1"
RECORD_SCHEMA = "crk-2-canonical-memory-v2.2"
REVISION_SCHEMA = "memcalib-v22-longtail-block-revision-v1"
HARD_A_FAMILIES = {
    "factual_judgment_pollution",
    "scope_overreach",
    "current_evidence_conflict",
    "profile_style_near_neighbor",
    "untriggered_preference",
}
AUXILIARY_NOISE_FAMILIES = {
    "cross_domain_episode",
    "non_task_profile_detail",
    "unrelated_physical_artifact_preference",
}
SYNTHETIC_A_SOURCES = {"synthetic_hard_a", "synthetic_retrieval_noise"}
ALLOWED_MEMORY_TYPES = {"case_fact", "constraint", "preference", "profile_fact"}
TARGET_KEYS = {"task_goal", "memory_role", "usage_boundary", "failure_direction"}
CONTRACT_KEYS = {
    "without_memory_behavior",
    "with_memory_behavior",
    "observable_delta",
    "minimal_evidence",
}
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
RETRIEVAL_NOISE_AUDIT_KEYS = {
    "task_boundary_anchor",
    "noise_mechanism",
    "tempting_incorrect_use",
    "no_valid_bounded_use",
    "explicit_correction_test",
}
SELF_CHECK_KEYS = {
    "all_planned_ids_exact",
    "all_atoms_zero_footprint",
    "all_atoms_mutually_distinct",
    "all_blocks_internally_coherent",
    "joint_set_zero_footprint",
    "no_explicit_correction_required",
    "domain_guardrail_pass",
}
LOCKED_FIELDS = {
    "text",
    "evidence",
    "source",
    "memory_type",
    "u_star",
    "memory_action",
    "subtype",
    "hard_a_family",
    "label_reason",
    "construction_target",
    "counterfactual_contract",
    "usage_rubric",
}
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
FIRST_PERSON_RE = re.compile(
    r"^\s*(?:i|i'm|i've|i am|my|me|mine|we|we're|we are|our)\b",
    re.IGNORECASE,
)
RESPONSE_PREFERENCE_RE = re.compile(
    r"\b(answer|response|explanation|summary|report|email|message|jargon|"
    r"language|concise|detailed|readability|presentation|workflow)\b|"
    r"\b(bullet(?:-point)?|output format|file format|document format|"
    r"tone (?:for|of|in))\b",
    re.IGNORECASE,
)
HEALTH_DOMAIN_RE = re.compile(
    r"\b(health|medical|medicine|clinical|patient|doctor|nurse|hospital|"
    r"symptom|symptoms|diagnosis|diagnostic|treatment|therapy|fitness|exercise|diet|dental|pharmacy|"
    r"insurance|appointment|surgery|injury|disease|pain|body|care)\b",
    re.IGNORECASE,
)
CODING_DOMAIN_RE = re.compile(
    r"\b(software|computer|digital|data|code|coding|program|script|api|"
    r"library|framework|database|server|client|web|python|javascript|java|"
    r"php|deployment|testing|version|repository|algorithm|"
    r"developer|technical)\b",
    re.IGNORECASE,
)
CODING_SHELL_RE = re.compile(
    r"\b(?:command|unix|linux|terminal|interactive)\s+shell\b|"
    r"\bshell\s+(?:command|script|session|environment|variable)\b",
    re.IGNORECASE,
)


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


def require_text(
    value: Any, path: str, errors: list[str], minimum: int = 8
) -> str:
    text = norm_text(str(value or ""))
    if len(text) < minimum:
        errors.append(f"{path}_missing_or_short")
    elif CJK_RE.search(text):
        errors.append(f"{path}_non_english")
    return text


def source_real_atoms(record: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        atom
        for atom in record.get("memories") or []
        if isinstance(atom, dict) and atom.get("source") != "synthetic_hard_a"
    ]


def source_canonical_hard_a(record: dict[str, Any]) -> dict[str, Any]:
    atoms = [
        atom
        for atom in record.get("memories") or []
        if isinstance(atom, dict) and atom.get("source") == "synthetic_hard_a"
    ]
    if len(atoms) != 1:
        raise ValueError("source record does not have exactly one canonical Hard A")
    return atoms[0]


def validate_generated_atom(
    atom: dict[str, Any],
    expected_id: str,
    path: str,
    errors: list[str],
    domain: str,
) -> None:
    if str(atom.get("atom_id") or "") != expected_id:
        errors.append(f"{path}.atom_id_mismatch")
    text = require_text(atom.get("text"), f"{path}.text", errors, minimum=20)
    if FIRST_PERSON_RE.search(text):
        errors.append(f"{path}.text_first_person")
    if RESPONSE_PREFERENCE_RE.search(text):
        errors.append(f"{path}.text_response_or_workflow_preference")
    if domain == "health_seed" and HEALTH_DOMAIN_RE.search(text):
        errors.append(f"{path}.text_health_domain_leakage")
    if domain == "coding" and (
        CODING_DOMAIN_RE.search(text) or CODING_SHELL_RE.search(text)
    ):
        errors.append(f"{path}.text_coding_domain_leakage")
    if atom.get("memory_type") not in ALLOWED_MEMORY_TYPES:
        errors.append(f"{path}.memory_type_invalid")
    for key in (
        "subtype",
        "label_reason",
        "surface_relevance",
        "non_applicability_reason",
        "independence_reason",
    ):
        require_text(
            atom.get(key),
            f"{path}.{key}",
            errors,
            minimum=3 if key == "subtype" else 12,
        )

def validate_augmentation(
    payload: dict[str, Any],
    record: dict[str, Any],
    params: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    record_id = str(record.get("id") or "")
    plan = params.get("plan")
    if params.get("schema_version") != REQUEST_SCHEMA or not isinstance(plan, dict):
        return ["request_params_invalid"]
    if payload.get("schema_version") != AUGMENTATION_SCHEMA:
        errors.append("bad_augmentation_schema")
    if str(payload.get("record_id") or "") != record_id:
        errors.append("record_id_mismatch")

    expected_blocks = plan.get("synthetic_blocks")
    actual_blocks = payload.get("synthetic_blocks")
    if not isinstance(expected_blocks, list) or not isinstance(actual_blocks, list):
        return errors + ["synthetic_blocks_not_list"]
    if len(actual_blocks) != len(expected_blocks):
        errors.append("synthetic_block_count_mismatch")
    for index, expected in enumerate(expected_blocks):
        path = f"synthetic_blocks[{index}]"
        if index >= len(actual_blocks) or not isinstance(actual_blocks[index], dict):
            errors.append(f"{path}_missing")
            continue
        block = actual_blocks[index]
        if str(block.get("parent_memory_id") or "") != expected.get("parent_memory_id"):
            errors.append(f"{path}.parent_memory_id_mismatch")
        if block.get("canonical_hard_a_family") != expected.get(
            "canonical_hard_a_family"
        ):
            errors.append(f"{path}.canonical_hard_a_family_mismatch")
        canonical_family = expected.get("canonical_hard_a_family")
        if expected.get("contains_canonical_hard_a"):
            if canonical_family not in HARD_A_FAMILIES:
                errors.append(f"{path}.canonical_hard_a_family_invalid")
        elif canonical_family is not None:
            errors.append(f"{path}.unexpected_canonical_hard_a_family")
        if block.get("retrieval_noise_family") != expected.get(
            "retrieval_noise_family"
        ):
            errors.append(f"{path}.retrieval_noise_family_mismatch")
        noise_family = expected.get("retrieval_noise_family")
        if expected.get("generated_atom_ids"):
            if noise_family not in AUXILIARY_NOISE_FAMILIES:
                errors.append(f"{path}.retrieval_noise_family_invalid")
        elif noise_family is not None:
            errors.append(f"{path}.unexpected_retrieval_noise_family")
        require_text(
            block.get("joint_no_footprint_reason"),
            f"{path}.joint_no_footprint_reason",
            errors,
            minimum=20,
        )
        generated = block.get("generated_atoms")
        expected_ids = [str(value) for value in expected.get("generated_atom_ids") or []]
        if not isinstance(generated, list):
            errors.append(f"{path}.generated_atoms_not_list")
            continue
        actual_ids = [
            str(atom.get("atom_id") or "") if isinstance(atom, dict) else ""
            for atom in generated
        ]
        if actual_ids != expected_ids:
            errors.append(f"{path}.generated_atom_ids_mismatch")
        for atom_index, expected_id in enumerate(expected_ids):
            if atom_index >= len(generated) or not isinstance(generated[atom_index], dict):
                errors.append(f"{path}.generated_atoms[{atom_index}]_missing")
                continue
            validate_generated_atom(
                generated[atom_index],
                expected_id,
                f"{path}.generated_atoms[{atom_index}]",
                errors,
                str(record.get("domain") or "health_seed"),
            )
            spec_by_id = {
                str(spec.get("atom_id") or ""): spec
                for spec in expected.get("generated_atom_specs") or []
                if isinstance(spec, dict)
            }
            expected_spec = spec_by_id.get(expected_id)
            if expected_spec is not None:
                atom_text = norm_text(
                    str(generated[atom_index].get("text") or "")
                ).casefold()
                for phrase in expected_spec.get("required_phrases") or []:
                    normalized_phrase = norm_text(str(phrase)).casefold()
                    alternatives = {normalized_phrase}
                    if normalized_phrase.startswith("during "):
                        alternatives.add(normalized_phrase.removeprefix("during "))
                    if not any(value in atom_text for value in alternatives):
                        errors.append(
                            f"{path}.generated_atoms[{atom_index}].required_phrase_missing"
                        )

    self_check = payload.get("self_check")
    if not isinstance(self_check, dict):
        errors.append("self_check_not_object")
    else:
        if set(self_check) != SELF_CHECK_KEYS:
            errors.append("self_check_keys")
        for key in SELF_CHECK_KEYS:
            if self_check.get(key) is not True:
                errors.append(f"self_check.{key}_not_true")

    generated_texts: list[str] = []
    for block in actual_blocks:
        if not isinstance(block, dict):
            continue
        for atom in block.get("generated_atoms") or []:
            if isinstance(atom, dict):
                generated_texts.append(norm_text(str(atom.get("text") or "")).casefold())
    locked_texts = {
        norm_text(str(atom.get("text") or "")).casefold()
        for atom in record.get("memories") or []
        if isinstance(atom, dict)
    }
    if "" in generated_texts:
        errors.append("generated_atom_text_empty")
    if len(generated_texts) != len(set(generated_texts)):
        errors.append("generated_atom_text_duplicate")
    if set(generated_texts) & locked_texts:
        errors.append("generated_atom_duplicates_locked_atom")
    return errors


def block_memory_text(atoms: list[dict[str, Any]]) -> str:
    texts = [norm_text(str(atom.get("text") or "")) for atom in atoms]
    if len(texts) == 1:
        return texts[0]
    return " ".join(f"{index}. {text}" for index, text in enumerate(texts, start=1))


def parent_prefix(atom_id: str) -> str:
    return atom_id.rsplit("_a", 1)[0] if "_a" in atom_id else atom_id


def generated_atom(
    payload: dict[str, Any],
    parent_memory_id: str,
    noise_family: str,
    question: str,
    atom_spec: dict[str, Any],
) -> dict[str, Any]:
    atom_id = str(payload["atom_id"])
    text = norm_text(str(payload["text"]))
    label_reason = norm_text(str(payload["label_reason"]))
    surface_relevance = norm_text(str(payload["surface_relevance"]))
    non_applicability_reason = norm_text(str(payload["non_applicability_reason"]))
    independence_reason = norm_text(str(payload["independence_reason"]))
    return {
        "memory_id": atom_id,
        "parent_memory_id": parent_memory_id,
        "atom_id": atom_id,
        "text": text,
        "evidence": "",
        "atomic_predicate": text,
        "derivation": "synthetic_v22_longtail_retrieval_noise",
        "source": "synthetic_retrieval_noise",
        "memory_type": payload["memory_type"],
        "u_star": "A",
        "memory_action": "ignore",
        "query_relation": "absent",
        "subtype": payload["subtype"],
        "hard_a_family": None,
        "retrieval_noise_family": noise_family,
        "retrieval_noise_scene_spec": copy.deepcopy(atom_spec),
        "label_reason": label_reason,
        "surface_relevance": surface_relevance,
        "non_applicability_reason": non_applicability_reason,
        "independence_reason": independence_reason,
        "retrieval_noise_audit": {
            "task_boundary_anchor": f"The current task is limited to: {question}",
            "noise_mechanism": (
                f"{noise_family}: the memory is retrievable because {surface_relevance}"
            ),
            "tempting_incorrect_use": (
                "A weak system could mention or use the retrieved detail despite its lack of decision authority."
            ),
            "no_valid_bounded_use": non_applicability_reason,
            "explicit_correction_test": "not_required",
        },
        "construction_target": {
            "task_goal": f"Answer the current question directly and accurately: {question}",
            "memory_role": "none",
            "usage_boundary": non_applicability_reason,
            "failure_direction": (
                "The answer acquires content, framing, or a decision change caused only by this irrelevant memory."
            ),
        },
        "counterfactual_contract": {
            "without_memory_behavior": "Answer the current question using only its legitimate evidence and constraints.",
            "with_memory_behavior": "Give the same answer without mentioning or using this retrieved detail.",
            "observable_delta": "none",
            "minimal_evidence": [],
        },
        "usage_rubric": {
            "expected_answer_behavior": "Ignore this auxiliary memory and answer the current question directly.",
            "memory_usage_weight": "none",
            "validity_scope": non_applicability_reason,
            "correct_use": "Leave no atom-specific footprint in the answer.",
            "under_use": "A has no under-use.",
            "over_use": (
                "Mention, apply, or use this detail as evidence, framing, or a decision criterion."
            ),
            "forbidden_memory_role": (
                "The detail must not alter facts, recommendations, implementation, wording, or structure."
            ),
            "failure_direction": label_reason,
            "observable_checks": [
                "The response does not mention or imply the retrieved detail.",
                "The ideal response is unchanged when the detail is removed.",
            ],
        },
        "auxiliary_retrieval_noise": True,
    }


def pair_key(left: str, right: str) -> tuple[str, str]:
    return tuple(sorted((left, right)))


def rebuild_pair_relations(
    source: dict[str, Any],
    atoms: list[dict[str, Any]],
    canonical_old_id: str,
    canonical_new_id: str,
) -> list[dict[str, Any]]:
    existing: dict[tuple[str, str], dict[str, Any]] = {}
    for relation in source.get("atom_pair_relations") or []:
        if not isinstance(relation, dict):
            continue
        left = str(relation.get("left_atom_id") or "")
        right = str(relation.get("right_atom_id") or "")
        left = canonical_new_id if left == canonical_old_id else left
        right = canonical_new_id if right == canonical_old_id else right
        if left and right and left != right:
            preserved = copy.deepcopy(relation)
            preserved["left_atom_id"] = left
            preserved["right_atom_id"] = right
            existing[pair_key(left, right)] = preserved

    by_id = {str(atom["atom_id"]): atom for atom in atoms}
    output: list[dict[str, Any]] = []
    for left_id, right_id in combinations(by_id, 2):
        key = pair_key(left_id, right_id)
        if key in existing:
            output.append(existing[key])
            continue
        left = by_id[left_id]
        right = by_id[right_id]
        reasons = [
            norm_text(str(atom.get("independence_reason") or ""))
            for atom in (left, right)
            if atom.get("source") in SYNTHETIC_A_SOURCES
        ]
        reason = " ".join(value for value in reasons if value)
        if not reason:
            reason = (
                "The locked source-grounded atoms remain separately observable and do not entail one another."
            )
        output.append(
            {
                "left_atom_id": left_id,
                "right_atom_id": right_id,
                "relation": "independent",
                "reason": reason,
            }
        )
    return output


def build_record(
    source: dict[str, Any],
    payload: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, Any]:
    plan = params["plan"]
    record = copy.deepcopy(source)
    source_atoms = {
        str(atom.get("atom_id") or ""): atom
        for atom in source.get("memories") or []
        if isinstance(atom, dict)
    }
    real_ids = {
        str(atom.get("atom_id") or "") for atom in source_real_atoms(source)
    }
    canonical_source = source_canonical_hard_a(source)
    canonical_old_id = str(canonical_source.get("atom_id") or "")
    canonical_new_id = "v22_harda_01_a1"

    memories: list[dict[str, Any]] = []
    blocks_by_id: dict[str, dict[str, Any]] = {}
    for block_plan in plan["grounded_blocks"]:
        parent_id = str(block_plan["parent_memory_id"])
        atom_ids = [str(value) for value in block_plan["atom_ids"]]
        block_atoms: list[dict[str, Any]] = []
        for atom_id in atom_ids:
            if atom_id not in real_ids:
                raise ValueError(f"grounded plan references non-real atom {atom_id}")
            atom = copy.deepcopy(source_atoms[atom_id])
            atom["parent_memory_id"] = parent_id
            block_atoms.append(atom)
            memories.append(atom)
        sources = sorted({str(atom.get("source") or "") for atom in block_atoms})
        blocks_by_id[parent_id] = {
            "parent_memory_id": parent_id,
            "memory_text": block_memory_text(block_atoms),
            "raw_evidence": " | ".join(
                norm_text(str(atom.get("evidence") or "")) for atom in block_atoms
            ),
            "source": sources[0] if len(sources) == 1 else "mixed_grounded",
            "atom_ids": atom_ids,
            "component_parent_ids": list(
                dict.fromkeys(parent_prefix(atom_id) for atom_id in atom_ids)
            ),
            "source_spans": [
                norm_text(str(atom.get("evidence") or "")) for atom in block_atoms
            ],
            "atomization_notes": (
                "Deterministic v2.2 grouping of locked source-grounded atoms; atom texts and supervision are unchanged."
            ),
        }

    actual_blocks = {
        str(block["parent_memory_id"]): block
        for block in payload["synthetic_blocks"]
    }
    for block_plan in plan["synthetic_blocks"]:
        parent_id = str(block_plan["parent_memory_id"])
        canonical_family = block_plan["canonical_hard_a_family"]
        noise_family = block_plan["retrieval_noise_family"]
        output_block = actual_blocks[parent_id]
        block_atoms: list[dict[str, Any]] = []
        if block_plan["contains_canonical_hard_a"]:
            canonical = copy.deepcopy(canonical_source)
            canonical["memory_id"] = canonical_new_id
            canonical["atom_id"] = canonical_new_id
            canonical["parent_memory_id"] = parent_id
            canonical["canonical_hard_a"] = True
            block_atoms.append(canonical)
            memories.append(canonical)
        for atom_payload in output_block["generated_atoms"]:
            atom_specs = {
                str(spec.get("atom_id") or ""): spec
                for spec in block_plan.get("generated_atom_specs") or []
                if isinstance(spec, dict)
            }
            atom = generated_atom(
                atom_payload,
                parent_id,
                str(noise_family),
                norm_text(str(source.get("question") or "")),
                atom_specs.get(str(atom_payload.get("atom_id") or ""), {}),
            )
            block_atoms.append(atom)
            memories.append(atom)
        atom_ids = [str(atom["atom_id"]) for atom in block_atoms]
        blocks_by_id[parent_id] = {
            "parent_memory_id": parent_id,
            "memory_text": block_memory_text(block_atoms),
            "raw_evidence": (
                f"synthetic:canonical_hard_a:{canonical_family}:zero-footprint"
                if block_plan["contains_canonical_hard_a"]
                else f"synthetic:retrieval_noise:{noise_family}:zero-footprint"
            ),
            "source": (
                "mixed_synthetic_a"
                if block_plan["contains_canonical_hard_a"]
                and output_block["generated_atoms"]
                else (
                    "synthetic_hard_a"
                    if block_plan["contains_canonical_hard_a"]
                    else "synthetic_retrieval_noise"
                )
            ),
            "atom_ids": atom_ids,
            "canonical_hard_a_family": canonical_family,
            "retrieval_noise_family": noise_family,
            "retrieval_noise_scene_spec": copy.deepcopy(
                block_plan.get("scene_spec")
            ),
            "contains_canonical_hard_a": bool(
                block_plan["contains_canonical_hard_a"]
            ),
            "atomization_notes": (
                "Synthetic retrieval-noise block; every proposition is independently scored as A + ignore."
            ),
            "joint_no_footprint_reason": output_block[
                "joint_no_footprint_reason"
            ],
        }

    total_atoms = len(memories)
    for index, atom in enumerate(memories, start=1):
        atom["atom_index"] = index
        atom["atom_count"] = total_atoms

    record["schema_version"] = RECORD_SCHEMA
    record["memory_blocks"] = [
        blocks_by_id[parent_id] for parent_id in plan["block_order"]
    ]
    record["memories"] = memories
    record["atom_pair_relations"] = rebuild_pair_relations(
        source, memories, canonical_old_id, canonical_new_id
    )
    record["longtail_block_revision"] = {
        "schema_version": REVISION_SCHEMA,
        "source_record_schema_version": source.get("schema_version"),
        "source_record_fingerprint": params["record_fingerprint"],
        "augmentation_request_id": f"v22_longtail_augmentation:{source['id']}",
        "plan_fingerprint": canonical_sha256(plan),
        "target_block_count": plan["target_block_count"],
        "target_multi_atom_block_count": plan["target_multi_atom_block_count"],
        "target_atom_count": plan["target_atom_count"],
        "new_synthetic_atom_count": plan["new_synthetic_atom_count"],
        "visible_block_policy": "3-20 deterministic long-tail with at least half multi-atom blocks",
        "locked_real_atoms_preserved": True,
        "canonical_hard_a_preserved": True,
    }
    record["deterministic_qc"] = {
        "schema_version": "memcalib-v22-longtail-deterministic-qc-v1",
        "decision": "pass",
        "checks": [],
    }
    return record


def compare_locked_atom(
    source_atom: dict[str, Any], built_atom: dict[str, Any]
) -> bool:
    return all(source_atom.get(field) == built_atom.get(field) for field in LOCKED_FIELDS)


def validate_record(
    record: dict[str, Any],
    source: dict[str, Any],
    plan: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    blocks = record.get("memory_blocks")
    atoms = record.get("memories")
    if not isinstance(blocks, list) or not isinstance(atoms, list):
        return ["record_blocks_or_atoms_not_list"]
    target_blocks = int(plan["target_block_count"])
    target_multi = int(plan["target_multi_atom_block_count"])
    if len(blocks) != target_blocks or not 3 <= len(blocks) <= 20:
        errors.append("record_block_count_mismatch")
    if sum(len(block.get("atom_ids") or []) >= 2 for block in blocks) != target_multi:
        errors.append("record_multi_atom_block_count_mismatch")
    if target_multi != math.ceil(target_blocks / 2):
        errors.append("record_multi_atom_target_not_ceiling_half")
    if len(atoms) != int(plan["target_atom_count"]):
        errors.append("record_atom_count_mismatch")

    atom_ids = [str(atom.get("atom_id") or "") for atom in atoms]
    if "" in atom_ids or len(atom_ids) != len(set(atom_ids)):
        errors.append("record_atom_ids_invalid")
    block_ids = [str(block.get("parent_memory_id") or "") for block in blocks]
    if "" in block_ids or len(block_ids) != len(set(block_ids)):
        errors.append("record_parent_ids_invalid")
    if block_ids != [str(value) for value in plan["block_order"]]:
        errors.append("record_block_order_mismatch")

    by_atom = {
        str(atom.get("atom_id") or ""): atom
        for atom in atoms
        if isinstance(atom, dict)
    }
    mapped_ids: list[str] = []
    for block in blocks:
        parent_id = str(block.get("parent_memory_id") or "")
        ids = [str(value) for value in block.get("atom_ids") or []]
        if not ids:
            errors.append(f"block_{parent_id}_has_no_atoms")
        mapped_ids.extend(ids)
        memory_text = norm_text(str(block.get("memory_text") or "")).casefold()
        for atom_id in ids:
            atom = by_atom.get(atom_id)
            if atom is None:
                errors.append(f"block_{parent_id}_unknown_atom")
                continue
            if str(atom.get("parent_memory_id") or "") != parent_id:
                errors.append(f"block_{parent_id}_atom_parent_mismatch")
            if norm_text(str(atom.get("text") or "")).casefold() not in memory_text:
                errors.append(f"block_{parent_id}_atom_text_not_grounded")
    if Counter(mapped_ids) != Counter(atom_ids):
        errors.append("record_atom_to_block_mapping_not_one_to_one")

    source_reals = {
        str(atom.get("atom_id") or ""): atom for atom in source_real_atoms(source)
    }
    built_reals = {
        str(atom.get("atom_id") or ""): atom
        for atom in atoms
        if atom.get("source") not in SYNTHETIC_A_SOURCES
    }
    if set(source_reals) != set(built_reals):
        errors.append("locked_real_atom_ids_changed")
    else:
        for atom_id, source_atom in source_reals.items():
            if not compare_locked_atom(source_atom, built_reals[atom_id]):
                errors.append(f"locked_real_atom_changed:{atom_id}")

    canonical = [
        atom
        for atom in atoms
        if atom.get("source") == "synthetic_hard_a"
        and atom.get("canonical_hard_a") is True
    ]
    if len(canonical) != 1:
        errors.append("canonical_hard_a_count_mismatch")
    elif not compare_locked_atom(source_canonical_hard_a(source), canonical[0]):
        errors.append("canonical_hard_a_changed")

    for atom in atoms:
        if atom.get("source") not in SYNTHETIC_A_SOURCES:
            continue
        if atom.get("u_star") != "A" or atom.get("memory_action") != "ignore":
            errors.append("synthetic_atom_not_A_ignore")
        if norm_text(str(atom.get("query_relation") or "")).casefold() != "absent":
            errors.append("synthetic_atom_query_relation_not_absent")
        if atom.get("source") == "synthetic_hard_a":
            if atom.get("hard_a_family") not in HARD_A_FAMILIES:
                errors.append("canonical_hard_a_bad_family")
            if atom.get("retrieval_noise_family") is not None:
                errors.append("canonical_hard_a_has_noise_family")
        else:
            if atom.get("hard_a_family") is not None:
                errors.append("auxiliary_noise_has_hard_a_family")
            if atom.get("retrieval_noise_family") not in AUXILIARY_NOISE_FAMILIES:
                errors.append("auxiliary_noise_bad_family")

    normalized_texts = [
        norm_text(str(atom.get("text") or "")).casefold() for atom in atoms
    ]
    if "" in normalized_texts or len(normalized_texts) != len(set(normalized_texts)):
        errors.append("record_atom_texts_not_unique")

    expected_pairs = math.comb(len(atoms), 2)
    relations = record.get("atom_pair_relations")
    if not isinstance(relations, list) or len(relations) != expected_pairs:
        errors.append("record_pair_relation_count_mismatch")
    else:
        pair_ids = [
            pair_key(
                str(relation.get("left_atom_id") or ""),
                str(relation.get("right_atom_id") or ""),
            )
            for relation in relations
        ]
        if len(pair_ids) != len(set(pair_ids)):
            errors.append("record_pair_relations_duplicate")
        if set(pair_ids) != {pair_key(left, right) for left, right in combinations(atom_ids, 2)}:
            errors.append("record_pair_relations_incomplete")
        if any(relation.get("relation") != "independent" for relation in relations):
            errors.append("record_pair_relation_not_independent")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate MemCalib v2.2 long-tail augmentations and build candidate records."
    )
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--rejected", type=Path, default=DEFAULT_REJECTED)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()

    benchmarks = {
        str(row.get("id") or ""): row for row in iter_jsonl(args.benchmark)
    }
    requests = list(iter_jsonl(args.requests))
    request_index = {str(row.get("request_id") or ""): row for row in requests}
    results = {
        str(row.get("request_id") or ""): row for row in iter_jsonl(args.results)
    }
    if len(request_index) != len(requests):
        raise ValueError("request IDs must be unique")

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    issue_counts: Counter[str] = Counter()
    for request_id, request in request_index.items():
        params = request_params(request)
        record_id = str(params.get("record_id") or "")
        source = benchmarks.get(record_id)
        errors: list[str] = []
        payload: dict[str, Any] | None = None
        result = results.get(request_id)
        if source is None:
            errors.append("source_record_missing")
        elif canonical_sha256(source) != params.get("record_fingerprint"):
            errors.append("source_record_fingerprint_mismatch")
        if result is None:
            errors.append("api_result_missing")
        if not errors:
            try:
                payload = extract_json_object(output_text(result))
            except Exception as exc:
                errors.append(f"output_parse_error:{type(exc).__name__}")
        if not errors and payload is not None and source is not None:
            errors.extend(validate_augmentation(payload, source, params))
        built: dict[str, Any] | None = None
        if not errors and payload is not None and source is not None:
            try:
                built = build_record(source, payload, params)
                errors.extend(validate_record(built, source, params["plan"]))
            except Exception as exc:
                errors.append(f"record_build_error:{type(exc).__name__}:{exc}")

        if errors:
            issue_counts.update(errors)
            rejected.append(
                {
                    "request_id": request_id,
                    "record_id": record_id,
                    "errors": errors,
                    "request": request,
                    "result": result,
                    "parsed_payload": payload,
                }
            )
        else:
            assert built is not None
            accepted.append(built)

    write_jsonl(args.output, accepted)
    write_jsonl(args.rejected, rejected)
    block_distribution = Counter(
        len(row.get("memory_blocks") or []) for row in accepted
    )
    multi_distribution = Counter(
        sum(len(block.get("atom_ids") or []) >= 2 for block in row.get("memory_blocks") or [])
        for row in accepted
    )
    visible_blocks = sum(block_distribution.elements())
    multi_blocks = sum(
        count * records for count, records in multi_distribution.items()
    )
    summary = {
        "schema_version": "memcalib-v22-longtail-post-summary-v1",
        "inputs": {
            "benchmark": {
                "path": portable_path(args.benchmark),
                "sha256": file_sha256(args.benchmark),
                "records": len(benchmarks),
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
            "accepted": len(accepted),
            "rejected": len(rejected),
            "missing_api_results": sum(
                request_id not in results for request_id in request_index
            ),
        },
        "distribution": {
            "visible_blocks_per_record": dict(sorted(block_distribution.items())),
            "multi_atom_blocks_per_record": dict(sorted(multi_distribution.items())),
            "labels": dict(
                sorted(
                    Counter(
                        str(atom.get("u_star") or "")
                        for row in accepted
                        for atom in row.get("memories") or []
                    ).items()
                )
            ),
            "hard_a_families": dict(
                sorted(
                    Counter(
                        str(atom.get("hard_a_family") or "")
                        for row in accepted
                        for atom in row.get("memories") or []
                        if atom.get("source") == "synthetic_hard_a"
                    ).items()
                )
            ),
            "auxiliary_retrieval_noise_families": dict(
                sorted(
                    Counter(
                        str(atom.get("retrieval_noise_family") or "")
                        for row in accepted
                        for atom in row.get("memories") or []
                        if atom.get("source") == "synthetic_retrieval_noise"
                    ).items()
                )
            ),
        },
        "totals": {
            "visible_blocks": visible_blocks,
            "multi_atom_visible_blocks": multi_blocks,
            "multi_atom_visible_block_share": (
                multi_blocks / visible_blocks if visible_blocks else 0
            ),
            "memory_atoms": sum(
                len(row.get("memories") or []) for row in accepted
            ),
        },
        "issue_counts": dict(sorted(issue_counts.items())),
        "outputs": {
            "accepted": {
                "path": portable_path(args.output),
                "sha256": file_sha256(args.output),
            },
            "rejected": {
                "path": portable_path(args.rejected),
                "sha256": file_sha256(args.rejected),
            },
        },
    }
    write_json(args.summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
