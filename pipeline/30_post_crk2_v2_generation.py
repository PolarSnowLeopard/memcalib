#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any

from utils import extract_json_object, iter_jsonl, norm_text, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = SCRIPT_DIR / "data" / "crk2_v2_generation_result_100.jsonl"
DEFAULT_OUTPUT = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_100.jsonl"
DEFAULT_REJECTED = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_100.rejected.jsonl"
DEFAULT_SUMMARY = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_100.summary.json"
SCHEMA_VERSION = "crk-2-canonical-memory-v2"
ALLOWED_SOURCES = {"from_question", "from_context", "synthetic_hard_a"}
ALLOWED_LABELS = {"A", "B", "C"}
ALLOWED_ACTIONS = {"ignore", "apply", "correct"}
ALLOWED_DERIVATIONS = {"explicit", "inferred", "synthetic"}
ALLOWED_MEMORY_TYPES = {"case_fact", "constraint", "preference", "profile_fact", "safety_sensitive"}
ALLOWED_HARD_A_FAMILIES = {"scope_mismatch", "stale_context", "near_neighbor", "untriggered_preference"}
QC_KEYS = {
    "evidence_grounding_pass",
    "query_isolation_pass",
    "atomicity_pass",
    "pairwise_independence_pass",
    "counterfactual_observability_pass",
    "label_action_consistency_pass",
    "rubric_objectivity_pass",
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
TARGET_KEYS = {"task_goal", "memory_role", "usage_boundary", "failure_direction"}
CONTRACT_KEYS = {"without_memory_behavior", "with_memory_behavior", "observable_delta", "minimal_evidence"}
TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
FIRST_PERSON_RE = re.compile(r"^\s*(?:i|i'm|i've|i am|my|me|mine|we|we're|we are|our)\b", re.IGNORECASE)
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "by", "for", "from", "has", "have",
    "he", "her", "hers", "him", "his", "i", "in", "is", "it", "its", "me", "my", "of", "on", "or",
    "our", "she", "that", "the", "their", "them", "they", "this", "to", "user", "we", "with", "you", "your",
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


def content_tokens(text: Any) -> list[str]:
    return [token.casefold() for token in TOKEN_RE.findall(str(text or "")) if token.casefold() not in STOPWORDS]


def query_memory_lexical_overlap(question: Any, memory: Any) -> dict[str, Any]:
    q_tokens = content_tokens(question)
    m_tokens = content_tokens(memory)
    if not m_tokens:
        return {"flag": False, "coverage": 0.0, "shared": [], "reason": "no_content_tokens"}
    q_set = set(q_tokens)
    shared = sorted(set(m_tokens) & q_set)
    coverage = len(shared) / len(set(m_tokens))
    q_norm = " ".join(q_tokens)
    m_norm = " ".join(m_tokens)
    substring = len(m_tokens) >= 3 and m_norm in q_norm
    width = min(5, len(m_tokens))
    m_shingles = {tuple(m_tokens[i : i + width]) for i in range(len(m_tokens) - width + 1)}
    q_shingles = {tuple(q_tokens[i : i + width]) for i in range(max(0, len(q_tokens) - width + 1))}
    shingle_match = bool(m_shingles & q_shingles) if width >= 3 else False
    high_coverage = len(set(m_tokens)) >= 4 and coverage >= 0.65
    flag = substring or shingle_match or high_coverage
    reason = "substring" if substring else "shingle" if shingle_match else "high_coverage" if high_coverage else "none"
    return {"flag": flag, "coverage": round(coverage, 4), "shared": shared, "reason": reason}


def evidence_grounded(evidence: Any, source_text: Any) -> bool:
    evidence_text = norm_text(str(evidence or ""))
    source = norm_text(str(source_text or ""))
    return bool(evidence_text and source and evidence_text.casefold() in source.casefold())


def english_violations(value: Any, path: str = "") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if key in {"raw_evidence", "evidence"}:
                continue
            violations.extend(english_violations(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(english_violations(child, f"{path}[{index}]"))
    elif isinstance(value, str) and CJK_RE.search(value):
        violations.append(path)
    return violations


def validate_record(record: dict[str, Any], params: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    overlap_audit: list[dict[str, Any]] = []
    if record.get("schema_version") != SCHEMA_VERSION:
        errors.append("bad_schema_version")
    if record.get("accepted") is not True:
        errors.append("constructor_rejected")
    question = norm_text(str(record.get("question") or ""))
    if len(question) < 20:
        errors.append("question_too_short")
    if english_violations(record):
        errors.append("generated_non_english_text")

    blocks = record.get("memory_blocks")
    memories = record.get("memories")
    pairs = record.get("atom_pair_relations")
    if not isinstance(blocks, list) or not (3 <= len(blocks) <= 6):
        errors.append("parent_memory_count_out_of_range")
        blocks = blocks if isinstance(blocks, list) else []
    if not isinstance(memories, list) or not (3 <= len(memories) <= 12):
        errors.append("atomic_memory_count_out_of_range")
        memories = memories if isinstance(memories, list) else []
    if not isinstance(pairs, list):
        errors.append("missing_atom_pair_relations")
        pairs = []

    block_ids: set[str] = set()
    declared_atom_ids: set[str] = set()
    synthetic_blocks = 0
    block_source: dict[str, str] = {}
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            errors.append(f"block_{index}_not_object")
            continue
        parent_id = str(block.get("parent_memory_id") or "")
        if not parent_id or parent_id in block_ids:
            errors.append(f"block_{index}_bad_or_duplicate_id")
        block_ids.add(parent_id)
        source = str(block.get("source") or "")
        block_source[parent_id] = source
        if source not in ALLOWED_SOURCES:
            errors.append(f"block_{index}_bad_source")
        if source == "synthetic_hard_a":
            synthetic_blocks += 1
        elif not evidence_grounded(
            block.get("raw_evidence"),
            params.get("raw_question") if source == "from_question" else params.get("dialogue_context") or params.get("source_context"),
        ):
            errors.append(f"block_{index}_ungrounded_evidence")
        if FIRST_PERSON_RE.search(str(block.get("memory_text") or "")):
            errors.append(f"block_{index}_first_person_memory")
        atom_ids = block.get("atom_ids")
        if not isinstance(atom_ids, list) or not atom_ids:
            errors.append(f"block_{index}_missing_atom_ids")
        else:
            for atom_id in atom_ids:
                atom_id = str(atom_id)
                if atom_id in declared_atom_ids:
                    errors.append(f"duplicate_declared_atom_id_{atom_id}")
                declared_atom_ids.add(atom_id)
    if synthetic_blocks != 1:
        errors.append("synthetic_hard_a_parent_count_not_one")

    seen_atom_ids: set[str] = set()
    labels: Counter[str] = Counter()
    expected_weights = {"A": "none", "B": "supporting", "C": "controlling"}
    for index, memory in enumerate(memories):
        if not isinstance(memory, dict):
            errors.append(f"memory_{index}_not_object")
            continue
        atom_id = str(memory.get("atom_id") or "")
        if not atom_id or atom_id in seen_atom_ids:
            errors.append(f"memory_{index}_bad_or_duplicate_atom_id")
        seen_atom_ids.add(atom_id)
        if str(memory.get("memory_id") or "") != atom_id:
            errors.append(f"memory_{index}_memory_id_mismatch")
        parent_id = str(memory.get("parent_memory_id") or "")
        if parent_id not in block_ids:
            errors.append(f"memory_{index}_unknown_parent")
        source = str(memory.get("source") or "")
        if source not in ALLOWED_SOURCES:
            errors.append(f"memory_{index}_bad_source")
        if block_source.get(parent_id) and block_source[parent_id] != source:
            errors.append(f"memory_{index}_parent_source_mismatch")
        if source != "synthetic_hard_a" and not evidence_grounded(
            memory.get("evidence"),
            params.get("raw_question") if source == "from_question" else params.get("dialogue_context") or params.get("source_context"),
        ):
            errors.append(f"memory_{index}_ungrounded_evidence")
        if str(memory.get("derivation") or "") not in ALLOWED_DERIVATIONS:
            errors.append(f"memory_{index}_bad_derivation")
        if str(memory.get("memory_type") or "") not in ALLOWED_MEMORY_TYPES:
            errors.append(f"memory_{index}_bad_memory_type")
        if FIRST_PERSON_RE.search(str(memory.get("text") or "")):
            errors.append(f"memory_{index}_first_person_memory")

        label = str(memory.get("u_star") or "").upper()
        action = str(memory.get("memory_action") or "")
        labels[label] += 1
        if label not in ALLOWED_LABELS:
            errors.append(f"memory_{index}_bad_label")
        if action not in ALLOWED_ACTIONS:
            errors.append(f"memory_{index}_bad_action")
        if (label == "A" and action != "ignore") or (label in {"B", "C"} and action == "ignore"):
            errors.append(f"memory_{index}_label_action_mismatch")
        if str(memory.get("query_relation") or "") != "absent":
            errors.append(f"memory_{index}_query_relation_not_absent")

        hard_family = memory.get("hard_a_family")
        if source == "synthetic_hard_a":
            if label != "A" or action != "ignore" or memory.get("derivation") != "synthetic":
                errors.append(f"memory_{index}_bad_synthetic_hard_a")
            if hard_family not in ALLOWED_HARD_A_FAMILIES:
                errors.append(f"memory_{index}_bad_hard_a_family")
        elif hard_family is not None:
            errors.append(f"memory_{index}_real_memory_has_hard_a_family")

        target = memory.get("construction_target")
        if not isinstance(target, dict) or not TARGET_KEYS.issubset(target):
            errors.append(f"memory_{index}_bad_construction_target")
        rubric = memory.get("usage_rubric")
        if not isinstance(rubric, dict) or not RUBRIC_KEYS.issubset(rubric):
            errors.append(f"memory_{index}_bad_usage_rubric")
        elif rubric.get("memory_usage_weight") != expected_weights.get(label):
            errors.append(f"memory_{index}_bad_usage_weight")
        elif not isinstance(rubric.get("observable_checks"), list) or not rubric.get("observable_checks"):
            errors.append(f"memory_{index}_missing_observable_checks")

        contract = memory.get("counterfactual_contract")
        if not isinstance(contract, dict) or not CONTRACT_KEYS.issubset(contract):
            errors.append(f"memory_{index}_bad_counterfactual_contract")
        else:
            without = norm_text(str(contract.get("without_memory_behavior") or ""))
            with_memory = norm_text(str(contract.get("with_memory_behavior") or ""))
            delta = norm_text(str(contract.get("observable_delta") or ""))
            minimal = contract.get("minimal_evidence")
            if not without or not with_memory or not isinstance(minimal, list):
                errors.append(f"memory_{index}_incomplete_counterfactual_contract")
            if label == "A" and (delta.casefold() != "none" or minimal):
                errors.append(f"memory_{index}_a_has_observable_delta")
            if label in {"B", "C"} and (
                not delta or delta.casefold() == "none" or not minimal or without.casefold() == with_memory.casefold()
            ):
                errors.append(f"memory_{index}_bc_lacks_observable_delta")

        overlap = query_memory_lexical_overlap(question, memory.get("atomic_predicate") or memory.get("text"))
        overlap_audit.append({"atom_id": atom_id, **overlap})
        if overlap["flag"]:
            errors.append(f"memory_{index}_query_lexical_leakage")

    if declared_atom_ids != seen_atom_ids:
        errors.append("block_memory_atom_id_mismatch")
    if not (labels["B"] or labels["C"]):
        errors.append("missing_real_applied_memory")
    synthetic_atoms = [memory for memory in memories if isinstance(memory, dict) and memory.get("source") == "synthetic_hard_a"]
    if not synthetic_atoms:
        errors.append("missing_synthetic_hard_a_atom")

    expected_pairs = {normalized_pair(left, right) for left, right in combinations(sorted(seen_atom_ids), 2)}
    observed_pairs: set[tuple[str, str]] = set()
    for index, pair in enumerate(pairs):
        if not isinstance(pair, dict):
            errors.append(f"pair_{index}_not_object")
            continue
        left = str(pair.get("left_atom_id") or "")
        right = str(pair.get("right_atom_id") or "")
        normalized = normalized_pair(left, right)
        if left == right or left not in seen_atom_ids or right not in seen_atom_ids or normalized in observed_pairs:
            errors.append(f"pair_{index}_bad_or_duplicate_ids")
        observed_pairs.add(normalized)
        if pair.get("relation") != "independent":
            errors.append(f"pair_{index}_not_independent")
        if len(norm_text(str(pair.get("reason") or ""))) < 10:
            errors.append(f"pair_{index}_missing_reason")
    if observed_pairs != expected_pairs:
        errors.append("incomplete_atom_pair_matrix")

    qc = record.get("qc")
    if not isinstance(qc, dict):
        errors.append("missing_qc")
    else:
        for key in sorted(QC_KEYS):
            if qc.get(key) is not True:
                errors.append(f"qc_failed_{key}")
    return sorted(set(errors)), overlap_audit


def normalize_record(record: dict[str, Any], params: dict[str, Any], request_id: str, overlap_audit: list[dict[str, Any]]) -> dict[str, Any]:
    source_id = str(params.get("id") or params.get("source_raw_id") or "")
    result = dict(record)
    result.update(
        {
            "id": request_id or f"crk2_v2_{source_id}",
            "source_dataset": params.get("source_dataset", ""),
            "domain": params.get("domain", "health_seed"),
            "source_id": source_id,
            "source_split": params.get("source_split", ""),
            "source_index": params.get("source_index", ""),
            "source_license": params.get("source_license", ""),
            "source_topic": params.get("topic", ""),
            "raw_query": params.get("raw_question", ""),
            "source_context": params.get("dialogue_context") or params.get("source_context") or "",
            "source_answer": params.get("doctor_answer") or params.get("source_answer") or "",
            "raw_selection": params.get("raw_selection") or {},
            "semantic_qc": params.get("semantic_qc") or {},
            "semantic_admission": params.get("semantic_admission") or {},
            "deterministic_qc": {
                "schema_version": "crk2-deterministic-qc-v2",
                "decision": "pass",
                "query_lexical_overlap_audit": overlap_audit,
            },
        }
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse and deterministically validate CRK-2 v2 construction outputs.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--rejected", type=Path, default=DEFAULT_REJECTED)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()
    for line_number, row in enumerate(iter_jsonl(args.input), start=1):
        params = get_params(row)
        request_id = str(row.get("request_id") or row.get("id") or "")
        try:
            record = extract_json_object(get_output_text(row))
            errors, overlap_audit = validate_record(record, params)
        except Exception as exc:
            record = {}
            overlap_audit = []
            errors = [f"parse_error:{type(exc).__name__}:{exc}"]
        if errors:
            reasons.update(errors)
            rejected.append(
                {
                    "request_id": request_id,
                    "line_number": line_number,
                    "errors": errors,
                    "user_defined_params": params,
                    "parsed_record": record,
                    "query_lexical_overlap_audit": overlap_audit,
                }
            )
        else:
            accepted.append(normalize_record(record, params, request_id, overlap_audit))

    write_jsonl(args.output, accepted)
    write_jsonl(args.rejected, rejected)
    summary = {
        "schema_version": "crk2-v2-postprocess-summary-v1",
        "input": {"path": str(args.input), "sha256": file_sha256(args.input)},
        "counts": {"total": len(accepted) + len(rejected), "deterministic_pass": len(accepted), "rejected": len(rejected)},
        "rejection_reasons": dict(reasons.most_common()),
        "outputs": {
            "accepted": {"path": str(args.output), "sha256": file_sha256(args.output)},
            "rejected": {"path": str(args.rejected), "sha256": file_sha256(args.rejected)},
        },
    }
    write_json(args.summary, summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
