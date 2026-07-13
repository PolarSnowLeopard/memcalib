#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from utils import extract_json_object, norm_text, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = SCRIPT_DIR / "data" / "crk2_memory_benchmark_100.jsonl"
DEFAULT_SUMMARY = SCRIPT_DIR / "data" / "crk2_memory_benchmark_100.summary.json"
DEFAULT_HTML = SCRIPT_DIR / "data" / "crk2_memory_benchmark_100.html"

COMMON_RUBRIC_KEYS = {
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
LABEL_SPECIFIC_RUBRIC_KEYS = {
    "A": {"contamination_signals"},
    "B": {"allowed_memory_use", "maximum_footprint"},
    "C": {"controlling_factor", "missing_memory_failure"},
}
MEMORY_REQUIRED_KEYS = {
    "memory_id",
    "parent_memory_id",
    "atom_id",
    "atom_index",
    "atom_count",
    "text",
    "evidence",
    "atomic_predicate",
    "derivation",
    "source",
    "memory_type",
    "u_star",
    "subtype",
    "hard_a_family",
    "label_reason",
    "construction_target",
    "usage_rubric",
}
BLOCK_REQUIRED_KEYS = {"parent_memory_id", "raw_evidence", "memory_text", "source", "u_star", "atom_ids"}
TARGET_REQUIRED_KEYS = {"task_goal", "memory_role", "usage_boundary", "failure_direction"}
FIRST_PERSON_EN = re.compile(r"^\s*(?:i|i'm|i’ve|i've|i am|my|me|mine|we|we're|we are|our)\b", re.IGNORECASE)
FIRST_PERSON_CN_PREFIXES = ("我", "我的", "本人", "我们", "咱们")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
CODE_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|[^\s\w]")
ENGLISH_SCHEMA_LITERAL_REPLACEMENTS = {
    "影响结论": "changes the conclusion",
    "改变排序": "changes prioritization",
    "污染证据权重": "distorts evidence weighting",
}
LABEL_ORDER = ("A", "B", "C")
ALLOWED_SOURCES = {"from_context", "from_question", "from_answer", "synthetic_hard_a"}
ALLOWED_MEMORY_TYPES = {"case_fact", "constraint", "preference", "profile_fact", "safety_sensitive"}
ALLOWED_DERIVATIONS = {"explicit", "inferred", "synthetic"}
ALLOWED_HARD_A_FAMILIES = {
    "fact_judgment_pollution",
    "scope_overreach",
    "evidence_conflict",
    "profile_style_near_neighbor",
    "untriggered_preference",
}


def effective_usage_rubric(memory: dict[str, Any]) -> dict[str, Any]:
    """Return judge rubric after normalizing common model field-placement drift."""
    rubric = memory.get("usage_rubric") if isinstance(memory.get("usage_rubric"), dict) else {}
    merged = dict(rubric)
    label = str(memory.get("u_star", "")).strip().upper()
    for key in LABEL_SPECIFIC_RUBRIC_KEYS.get(label, set()):
        if key not in merged and key in memory:
            merged[key] = memory[key]
    return merged


def is_first_person_stored_memory(text: Any) -> bool:
    normalized = norm_text(str(text or ""))
    if not normalized:
        return False
    return normalized.startswith(FIRST_PERSON_CN_PREFIXES) or bool(FIRST_PERSON_EN.match(normalized))


def canonicalize_english_schema_literals(value: Any) -> int:
    """Replace only fixed Chinese literals copied from the former English schema example."""
    repairs = 0
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(child, str) and child in ENGLISH_SCHEMA_LITERAL_REPLACEMENTS:
                value[key] = ENGLISH_SCHEMA_LITERAL_REPLACEMENTS[child]
                repairs += 1
            else:
                repairs += canonicalize_english_schema_literals(child)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, str) and child in ENGLISH_SCHEMA_LITERAL_REPLACEMENTS:
                value[index] = ENGLISH_SCHEMA_LITERAL_REPLACEMENTS[child]
                repairs += 1
            else:
                repairs += canonicalize_english_schema_literals(child)
    return repairs


def english_language_violations(value: Any, path: str = "") -> list[str]:
    """Return generated-field paths containing CJK, excluding retained source evidence."""
    violations: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if key in {"raw_evidence", "evidence"}:
                continue
            violations.extend(english_language_violations(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(english_language_violations(child, f"{path}[{index}]"))
    elif isinstance(value, str) and CJK_RE.search(value):
        violations.append(path)
    return violations


def validate_memory_enum_values(memory: dict[str, Any], memory_index: int) -> list[str]:
    errors: list[str] = []
    if memory.get("source") not in ALLOWED_SOURCES:
        errors.append(f"memory_{memory_index}_bad_source")
    if memory.get("memory_type") not in ALLOWED_MEMORY_TYPES:
        errors.append(f"memory_{memory_index}_bad_memory_type")
    if memory.get("derivation") not in ALLOWED_DERIVATIONS:
        errors.append(f"memory_{memory_index}_bad_derivation")
    if str(memory.get("u_star", "")).strip().upper() not in set(LABEL_ORDER):
        errors.append(f"memory_{memory_index}_bad_label")
    hard_a_family = memory.get("hard_a_family")
    if hard_a_family is not None and hard_a_family not in ALLOWED_HARD_A_FAMILIES:
        errors.append(f"memory_{memory_index}_bad_hard_a_family")
    return errors


def ordered_label_set(labels: list[str]) -> list[str]:
    present = set(labels)
    return [label for label in LABEL_ORDER if label in present]


def add_parent_label_metadata(blocks: list[dict[str, Any]], memories: list[dict[str, Any]]) -> dict[str, Any]:
    labels_by_parent: dict[str, list[str]] = {}
    for memory in memories:
        labels_by_parent.setdefault(str(memory.get("parent_memory_id", "")), []).append(str(memory.get("u_star", "")))

    label_set_counts: Counter = Counter()
    mode_counts: Counter = Counter()
    for block in blocks:
        labels = ordered_label_set(labels_by_parent.get(str(block.get("parent_memory_id", "")), []))
        mode = "mixed" if len(labels) > 1 else "homogeneous"
        label_set_key = "+".join(labels) if labels else "none"
        block["parent_label_set"] = labels
        block["parent_label_mode"] = mode
        label_set_counts[label_set_key] += 1
        mode_counts[mode] += 1

    return {
        "mixed_parent_count": mode_counts["mixed"],
        "homogeneous_parent_count": mode_counts["homogeneous"],
        "parent_label_set_counts": dict(label_set_counts),
        "parent_label_mode_counts": dict(mode_counts),
    }


def load_rubric_builder():
    path = SCRIPT_DIR / "09_build_memory_abc_rubric_dataset.py"
    spec = importlib.util.spec_from_file_location("memory_abc_rubric_dataset", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def get_params(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("passParams") or row.get("user_defined_params") or row.get("params") or {}


def get_text(row: dict[str, Any]) -> str:
    for key in ("response", "output", "content", "text", "answer"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    raw = row.get("raw_response")
    if isinstance(raw, dict):
        choices = raw.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
    raise ValueError("No model output text found")


def normalize_bool(value: Any) -> bool:
    return value is True or str(value).strip().lower() == "true"


def normalize_block(block: dict[str, Any], index: int) -> dict[str, Any]:
    parent_id = norm_text(str(block.get("parent_memory_id") or f"p{index}"))
    atom_ids = block.get("atom_ids") if isinstance(block.get("atom_ids"), list) else []
    memory_text = norm_text(str(block.get("memory_text") or block.get("text", "")))
    raw_evidence = norm_text(str(block.get("raw_evidence") or block.get("evidence") or block.get("text", "")))
    return {
        "parent_memory_id": parent_id,
        "raw_evidence": raw_evidence,
        "memory_text": memory_text,
        "text": memory_text,
        "source": norm_text(str(block.get("source", ""))),
        "u_star": str(block.get("u_star", "")).strip().upper(),
        "label_reason": norm_text(str(block.get("label_reason", ""))),
        "atom_count": int(block.get("atom_count") or len(atom_ids) or 0),
        "atom_ids": [str(atom_id) for atom_id in atom_ids],
        "atomization_notes": norm_text(str(block.get("atomization_notes", ""))),
        "hard_a_family": block.get("hard_a_family"),
    }


def normalize_memory(memory: dict[str, Any], index: int) -> dict[str, Any]:
    label = str(memory.get("u_star", "")).strip().upper()
    target = memory.get("construction_target") if isinstance(memory.get("construction_target"), dict) else {}
    rubric = effective_usage_rubric(memory)
    normalized = {
        "memory_id": norm_text(str(memory.get("memory_id") or f"m{index}")),
        "parent_memory_id": norm_text(str(memory.get("parent_memory_id", ""))),
        "atom_id": norm_text(str(memory.get("atom_id", ""))),
        "atom_index": int(memory.get("atom_index") or index),
        "atom_count": int(memory.get("atom_count") or 1),
        "text": norm_text(str(memory.get("text") or memory.get("atomic_predicate") or "")),
        "evidence": norm_text(str(memory.get("evidence", ""))),
        "atomic_predicate": norm_text(str(memory.get("atomic_predicate") or memory.get("text") or "")),
        "derivation": norm_text(str(memory.get("derivation", ""))),
        "source": norm_text(str(memory.get("source", ""))),
        "memory_type": norm_text(str(memory.get("memory_type", ""))),
        "u_star": label,
        "subtype": norm_text(str(memory.get("subtype", ""))),
        "hard_a_family": memory.get("hard_a_family"),
        "label_reason": norm_text(str(memory.get("label_reason", ""))),
        "verifier_reason": norm_text(str(memory.get("verifier_reason", ""))),
        "overlap_group": memory.get("overlap_group"),
        "overlap_note": norm_text(str(memory.get("overlap_note", ""))),
        "construction_target": {
            "task_goal": norm_text(str(target.get("task_goal", ""))),
            "memory_role": norm_text(str(target.get("memory_role", ""))),
            "usage_boundary": norm_text(str(target.get("usage_boundary", ""))),
            "failure_direction": norm_text(str(target.get("failure_direction", ""))),
        },
        "usage_rubric": dict(rubric),
        "judge_trace": memory.get("judge_trace", {}),
    }
    return normalized


def _evidence_is_grounded(evidence: Any, source_text: Any) -> bool:
    evidence_text = norm_text(str(evidence or ""))
    source = norm_text(str(source_text or ""))
    return bool(evidence_text and source and evidence_text.casefold() in source.casefold())


def _answer_ngram_containment(question: str, answer: str, width: int = 10) -> float:
    question_tokens = CODE_TOKEN_RE.findall((question or "").casefold())
    answer_tokens = CODE_TOKEN_RE.findall((answer or "").casefold())
    if len(answer_tokens) < width:
        return 0.0
    question_ngrams = {
        tuple(question_tokens[index : index + width])
        for index in range(max(0, len(question_tokens) - width + 1))
    }
    answer_ngrams = {
        tuple(answer_tokens[index : index + width])
        for index in range(len(answer_tokens) - width + 1)
    }
    return len(question_ngrams & answer_ngrams) / len(answer_ngrams) if answer_ngrams else 0.0


def validate_evidence_grounding(rec: dict[str, Any], params: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    source_fields = {
        "from_question": params.get("raw_question", ""),
        "from_context": params.get("source_context", ""),
        "from_answer": params.get("source_answer") or params.get("doctor_answer") or "",
    }
    domain = str(params.get("domain") or "health_seed")
    if domain == "coding":
        containment = _answer_ngram_containment(
            str(params.get("raw_question") or ""),
            str(params.get("source_answer") or params.get("doctor_answer") or ""),
        )
        if containment >= 0.8:
            errors.append("coding_question_contains_reference_solution")
    blocks = rec.get("memory_blocks") if isinstance(rec.get("memory_blocks"), list) else []
    block_sources: dict[str, str] = {}
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue
        source = str(block.get("source") or "")
        parent_id = str(block.get("parent_memory_id") or "")
        block_sources[parent_id] = source
        if domain != "health_seed" and source == "from_answer":
            errors.append(f"block_{index}_reference_answer_source_forbidden")
        if source in source_fields and not _evidence_is_grounded(block.get("raw_evidence"), source_fields[source]):
            errors.append(f"block_{index}_ungrounded_raw_evidence")

    memories = rec.get("memories") if isinstance(rec.get("memories"), list) else []
    for index, memory in enumerate(memories):
        if not isinstance(memory, dict):
            continue
        source = str(memory.get("source") or "")
        if domain != "health_seed" and source == "from_answer":
            errors.append(f"memory_{index}_reference_answer_source_forbidden")
        if source in source_fields and not _evidence_is_grounded(memory.get("evidence"), source_fields[source]):
            errors.append(f"memory_{index}_ungrounded_evidence")
        parent_source = block_sources.get(str(memory.get("parent_memory_id") or ""))
        if parent_source and source != parent_source:
            errors.append(f"memory_{index}_parent_source_mismatch")
        if source == "synthetic_hard_a":
            if str(memory.get("u_star") or "").upper() != "A":
                errors.append(f"memory_{index}_synthetic_non_a")
            if str(memory.get("derivation") or "") != "synthetic":
                errors.append(f"memory_{index}_synthetic_bad_derivation")
    return errors


def validate_model_record(rec: dict[str, Any], params: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    if rec.get("accepted") is False:
        errors.append("model_rejected_record")
    if len(norm_text(str(rec.get("question", "")))) < 10:
        errors.append("question_too_short")

    blocks = rec.get("memory_blocks")
    memories = rec.get("memories")
    if not isinstance(blocks, list) or not blocks:
        errors.append("missing_required_memory_blocks")
        blocks = []
    if not isinstance(memories, list) or not memories:
        errors.append("missing_required_memories")
        memories = []

    for block_index, block in enumerate(blocks):
        if not isinstance(block, dict):
            errors.append(f"bad_block_{block_index}")
            continue
        missing = BLOCK_REQUIRED_KEYS - set(block)
        if missing:
            errors.append(f"block_{block_index}_missing_{','.join(sorted(missing))}")
        if block.get("source") not in ALLOWED_SOURCES:
            errors.append(f"block_{block_index}_bad_source")
        if str(block.get("u_star", "")).strip().upper() not in set(LABEL_ORDER):
            errors.append(f"block_{block_index}_bad_label")
        if is_first_person_stored_memory(block.get("memory_text")):
            errors.append(f"block_{block_index}_first_person_memory_text")

    block_atom_ids = {
        str(atom_id)
        for block in blocks
        if isinstance(block, dict) and isinstance(block.get("atom_ids"), list)
        for atom_id in block.get("atom_ids", [])
    }
    memory_atom_ids = set()
    labels = []
    for memory_index, memory in enumerate(memories):
        if not isinstance(memory, dict):
            errors.append(f"bad_memory_{memory_index}")
            continue
        missing = MEMORY_REQUIRED_KEYS - set(memory)
        if missing:
            errors.append(f"memory_{memory_index}_missing_{','.join(sorted(missing))}")
        errors.extend(validate_memory_enum_values(memory, memory_index))
        label = str(memory.get("u_star", "")).strip().upper()
        labels.append(label)
        atom_id = str(memory.get("atom_id", ""))
        if atom_id:
            memory_atom_ids.add(atom_id)
        if is_first_person_stored_memory(memory.get("text")):
            errors.append(f"memory_{memory_index}_first_person_text")
        target = memory.get("construction_target") if isinstance(memory.get("construction_target"), dict) else {}
        if not TARGET_REQUIRED_KEYS.issubset(target):
            errors.append(f"memory_{memory_index}_bad_construction_target")
        rubric = effective_usage_rubric(memory)
        if not COMMON_RUBRIC_KEYS.issubset(rubric):
            errors.append(f"memory_{memory_index}_bad_common_rubric")
        specific = LABEL_SPECIFIC_RUBRIC_KEYS.get(label, set())
        if not specific.issubset(rubric):
            errors.append(f"memory_{memory_index}_bad_label_specific_rubric")
        expected_weight = {"A": "none", "B": "supporting", "C": "controlling"}.get(label)
        if expected_weight and rubric.get("memory_usage_weight") != expected_weight:
            errors.append(f"memory_{memory_index}_bad_usage_weight")

    if block_atom_ids and memory_atom_ids and block_atom_ids != memory_atom_ids:
        errors.append("block_memory_atom_id_mismatch")
    if not any(label in {"B", "C"} for label in labels):
        errors.append("missing_applied_label")
    if not any(
        str(memory.get("u_star", "")).strip().upper() == "A" and memory.get("source") == "synthetic_hard_a"
        for memory in memories
        if isinstance(memory, dict)
    ):
        errors.append("missing_synthetic_hard_a")
    if params is not None:
        errors.extend(validate_evidence_grounding(rec, params))
    return errors


def normalize_model_record(raw: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    source_id = str(params.get("id") or params.get("source_raw_id") or "")
    source_answer = params.get("source_answer") or params.get("doctor_answer") or ""
    blocks = [normalize_block(block, index + 1) for index, block in enumerate(raw.get("memory_blocks", []))]
    memories = [normalize_memory(memory, index + 1) for index, memory in enumerate(raw.get("memories", []))]
    parent_label_metadata = add_parent_label_metadata(blocks, memories)
    qc = raw.get("qc") if isinstance(raw.get("qc"), dict) else {}
    audit = raw.get("construction_audit") if isinstance(raw.get("construction_audit"), dict) else {}
    split = str(audit.get("quality_subset") or "clean")
    return {
        "id": f"crk2_{source_id}",
        "domain": params.get("domain") or "health_seed",
        "source_dataset": params.get("source_dataset", ""),
        "source_id": source_id,
        "source_record_id": source_id,
        "source_split": params.get("source_split", ""),
        "source_index": params.get("source_index", ""),
        "source_topic": params.get("topic", ""),
        "source_license": params.get("source_license", ""),
        "source_metadata": params.get("source_metadata", {}),
        "source_context": params.get("source_context", ""),
        "raw_query": params.get("raw_question", ""),
        "source_answer": source_answer,
        "doctor_answer": params.get("doctor_answer", source_answer),
        "question": norm_text(str(raw.get("question", ""))),
        "memory_blocks": blocks,
        "memories": memories,
        "composition": {
            "memory_count": len(memories),
            "parent_memory_count": len(blocks),
            "label_counts": {
                label: sum(1 for memory in memories if memory.get("u_star") == label)
                for label in ("A", "B", "C")
            },
            "has_synthetic_hard_a": any(memory.get("source") == "synthetic_hard_a" for memory in memories),
            "hard_a_families": sorted({memory.get("hard_a_family") for memory in memories if memory.get("hard_a_family")}),
            **parent_label_metadata,
        },
        "qc": {
            "atomicity_pass": normalize_bool(qc.get("atomicity_pass")),
            "duplicate_pass": normalize_bool(qc.get("duplicate_pass")),
            "question_memory_leakage_pass": normalize_bool(qc.get("question_memory_leakage_pass")),
            "hard_a_target_consistency_pass": normalize_bool(qc.get("hard_a_target_consistency_pass")),
            "rubric_objectivity_pass": normalize_bool(qc.get("rubric_objectivity_pass")),
            "evidence_grounding_pass": True,
            "counterfactual_pass": qc.get("counterfactual_pass", "pending_model_test"),
            "manual_audit": qc.get("manual_audit", "not_sampled"),
            "overlap_groups": qc.get("overlap_groups", []),
            "question_memory_leakage_issues": qc.get("question_memory_leakage_issues", []),
        },
        "construction_audit": audit or {"schema_version": "crk-2-canonical-memory-v1", "quality_subset": split, "pipeline_steps": []},
        "split": split,
        "prototype_notes": norm_text(str(raw.get("notes", ""))),
        "lineage": {
            "raw_selection": params.get("raw_selection", {}),
            "semantic_qc": params.get("semantic_qc", {}),
            "semantic_admission": params.get("semantic_admission", {}),
            "generation_repair_round": int(params.get("generation_repair_round") or 0),
            "generation_repair_errors": list(params.get("generation_repair_errors") or []),
        },
    }


def new_summary_state() -> dict[str, Any]:
    return {
        "total_samples": 0,
        "total_memories": 0,
        "total_parent_memories": 0,
        "samples_with_overlap_groups": 0,
        "english_schema_literal_repairs": 0,
        "label_counts": Counter(),
        "memory_source_counts": Counter(),
        "topic_counts": Counter(),
        "subtype_counts": Counter(),
        "memory_type_counts": Counter(),
        "hard_a_family_counts": Counter(),
        "rubric_weight_counts": Counter(),
        "derivation_counts": Counter(),
        "quality_subset_counts": Counter(),
        "qc_pass_counts": Counter(),
        "parent_label_mode_counts": Counter(),
        "parent_label_set_counts": Counter(),
        "generation_repair_round_counts": Counter(),
    }


def update_summary_state(state: dict[str, Any], sample: dict[str, Any]) -> None:
    state["total_samples"] += 1
    state["topic_counts"][sample.get("source_topic", "unknown")] += 1
    state["quality_subset_counts"][sample.get("split", "unknown")] += 1
    state["generation_repair_round_counts"][str((sample.get("lineage") or {}).get("generation_repair_round", 0))] += 1
    blocks = sample.get("memory_blocks", [])
    state["total_parent_memories"] += len(blocks)
    state["samples_with_overlap_groups"] += int(bool(sample.get("qc", {}).get("overlap_groups")))
    state["english_schema_literal_repairs"] += int(
        (sample.get("construction_audit") or {}).get("english_schema_literal_repairs") or 0
    )
    for qc_key in (
        "atomicity_pass",
        "duplicate_pass",
        "question_memory_leakage_pass",
        "hard_a_target_consistency_pass",
        "rubric_objectivity_pass",
        "evidence_grounding_pass",
    ):
        if sample.get("qc", {}).get(qc_key) is True:
            state["qc_pass_counts"][qc_key] += 1
    for block in blocks:
        mode = block.get("parent_label_mode", "unknown")
        labels = block.get("parent_label_set", [])
        label_set = "+".join(labels) if isinstance(labels, list) else str(labels or "unknown")
        state["parent_label_mode_counts"][mode] += 1
        state["parent_label_set_counts"][label_set or "none"] += 1
    for memory in sample.get("memories", []):
        state["total_memories"] += 1
        state["label_counts"][memory["u_star"]] += 1
        state["memory_source_counts"][memory["source"]] += 1
        state["subtype_counts"][memory["subtype"]] += 1
        state["memory_type_counts"][memory["memory_type"]] += 1
        state["derivation_counts"][memory.get("derivation", "unknown")] += 1
        if memory.get("hard_a_family"):
            state["hard_a_family_counts"][memory["hard_a_family"]] += 1
        state["rubric_weight_counts"][memory["usage_rubric"]["memory_usage_weight"]] += 1


def finalize_summary_state(state: dict[str, Any]) -> dict[str, Any]:
    total_samples = state["total_samples"]
    total_memories = state["total_memories"]
    total_parent = state["total_parent_memories"]
    parent_modes = state["parent_label_mode_counts"]
    return {
        "total_samples": total_samples,
        "total_memories": total_memories,
        "total_parent_memories": total_parent,
        "avg_memories_per_sample": total_memories / total_samples if total_samples else 0,
        "avg_atoms_per_parent_memory": total_memories / total_parent if total_parent else 0,
        "label_counts": dict(sorted(state["label_counts"].items())),
        "memory_source_counts": dict(sorted(state["memory_source_counts"].items())),
        "subtype_counts": dict(sorted(state["subtype_counts"].items())),
        "memory_type_counts": dict(sorted(state["memory_type_counts"].items())),
        "hard_a_family_counts": dict(sorted(state["hard_a_family_counts"].items())),
        "rubric_weight_counts": dict(sorted(state["rubric_weight_counts"].items())),
        "derivation_counts": dict(sorted(state["derivation_counts"].items())),
        "quality_subset_counts": dict(sorted(state["quality_subset_counts"].items())),
        "qc_pass_counts": dict(sorted(state["qc_pass_counts"].items())),
        "samples_with_overlap_groups": state["samples_with_overlap_groups"],
        "topic_counts": dict(sorted(state["topic_counts"].items())),
        "parent_label_mode_counts": dict(sorted(parent_modes.items())),
        "parent_label_set_counts": dict(sorted(state["parent_label_set_counts"].items())),
        "mixed_parent_count": parent_modes.get("mixed", 0),
        "mixed_parent_rate": parent_modes.get("mixed", 0) / total_parent if total_parent else 0,
        "english_schema_literal_repairs": state["english_schema_literal_repairs"],
        "generation_repair_round_counts": dict(sorted(state["generation_repair_round_counts"].items())),
        "pipeline": "crk2_llm_generation",
    }


def summarize_and_render(
    samples: list[dict[str, Any]],
    summary_path: Path,
    html_path: Path,
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    builder = load_rubric_builder()
    if summary is None:
        state = new_summary_state()
        for sample in samples:
            update_summary_state(state, sample)
        summary = finalize_summary_state(state)
    summary["html_preview_samples"] = len(samples)
    summary["prototype_limitations"] = [
        "This preview is generated by the CRK-2 canonical-memory prompt from normalized public QA seed records.",
        "Raw evidence is retained for audit, while stored memories are third-person canonical summaries used for A/B/C labeling and judge rubrics.",
        "Domain coverage remains limited to the currently configured source datasets and should be expanded before the final release.",
        "Counterfactual answer tests, cross-model judge calibration, and manual audit sampling are not run yet.",
    ]
    write_json(summary_path, summary)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html = "\n".join(line.rstrip() for line in builder.build_html(samples, summary).splitlines()) + "\n"
    html_path.write_text(html, encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse CRK-2 full LLM construction results into benchmark JSONL and HTML.")
    parser.add_argument("--input", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--rejected", type=Path)
    parser.add_argument("--target", type=int, default=100)
    parser.add_argument("--html-limit", type=int, default=100)
    args = parser.parse_args()

    rejected_path = args.rejected or args.output.with_name(args.output.stem + ".rejected.jsonl")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rejected_path.parent.mkdir(parents=True, exist_ok=True)
    preview: list[dict[str, Any]] = []
    summary_state = new_summary_state()
    rejected_count = 0
    stop = False
    with args.output.open("w", encoding="utf-8") as output_handle, rejected_path.open("w", encoding="utf-8") as rejected_handle:
        for input_path in args.input:
            with input_path.open(encoding="utf-8") as input_handle:
                for row_index, line in enumerate(input_handle):
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    params = get_params(row)
                    try:
                        raw = extract_json_object(get_text(row))
                        output_language = str(params.get("output_language") or "")
                        literal_repairs = canonicalize_english_schema_literals(raw) if output_language == "en" else 0
                        errors = validate_model_record(raw, params)
                        language_violations = english_language_violations(raw) if output_language == "en" else []
                        if language_violations:
                            errors.append("english_language_violation")
                        if errors:
                            rejected = {
                                "input": str(input_path),
                                "row_index": row_index,
                                "errors": errors,
                                "language_violations": language_violations,
                                "params": params,
                                "raw": raw,
                            }
                            rejected_handle.write(json.dumps(rejected, ensure_ascii=False) + "\n")
                            rejected_count += 1
                            continue
                        normalized = normalize_model_record(raw, params)
                        if literal_repairs:
                            normalized["construction_audit"]["english_schema_literal_repairs"] = literal_repairs
                        output_handle.write(json.dumps(normalized, ensure_ascii=False) + "\n")
                        update_summary_state(summary_state, normalized)
                        if args.html_limit <= 0 or len(preview) < args.html_limit:
                            preview.append(normalized)
                        if args.target and summary_state["total_samples"] >= args.target:
                            stop = True
                            break
                    except Exception as exc:  # noqa: BLE001
                        rejected = {
                            "input": str(input_path),
                            "row_index": row_index,
                            "errors": [type(exc).__name__, str(exc)],
                            "params": params,
                        }
                        rejected_handle.write(json.dumps(rejected, ensure_ascii=False) + "\n")
                        rejected_count += 1
            if stop:
                break

    summary = finalize_summary_state(summary_state)
    if summary["total_samples"]:
        summary = summarize_and_render(preview, args.summary, args.html, summary)
    else:
        write_json(args.summary, summary)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "input": [str(path) for path in args.input],
                "summary": str(args.summary),
                "html": str(args.html),
                "rejected": str(rejected_path),
                "kept": summary["total_samples"],
                "rejected_count": rejected_count,
                **summary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
