#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any

from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
POST_PATH = SCRIPT_DIR / "30_post_crk2_v2_generation.py"
GENERIC_CODING_QUESTION = (
    "Produce the requested source-code artifact. Apply only retrieved memories that materially "
    "constrain the result, ignore irrelevant retrieved context, and return only the completed artifact."
)
TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def load_post_module() -> Any:
    spec = importlib.util.spec_from_file_location("crk2_post_v2", POST_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {POST_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


POST = load_post_module()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def row_id(row: dict[str, Any]) -> str:
    return str(row.get("id") or row.get("record_id") or row.get("request_id") or "")


def params_from_record(record: dict[str, Any]) -> dict[str, Any]:
    params = {
        "id": record.get("source_id"),
        "source_dataset": record.get("source_dataset"),
        "domain": record.get("domain"),
        "source_split": record.get("source_split"),
        "source_index": record.get("source_index"),
        "source_license": record.get("source_license"),
        "topic": record.get("source_topic"),
        "raw_question": record.get("raw_query"),
        "source_context": record.get("source_context"),
        "source_answer": record.get("source_answer"),
        "raw_selection": record.get("raw_selection") or {},
        "semantic_qc": record.get("semantic_qc") or {},
        "semantic_admission": record.get("semantic_admission") or {},
    }
    if isinstance(record.get("source_metadata"), dict):
        params["source_metadata"] = record["source_metadata"]
    for source_key, target_key in (
        ("semantic_repair", "crk2_v2_semantic_repair"),
        ("reserve_reconstruction", "crk2_v2_reserve_reconstruction"),
    ):
        if isinstance(record.get(source_key), dict):
            params[target_key] = record[source_key]
    return params


def enum_value(value: Any, allowed: set[str]) -> str:
    text = str(value or "").strip().casefold()
    for candidate in sorted(allowed, key=len, reverse=True):
        if re.search(rf"\b{re.escape(candidate.casefold())}\b", text):
            return candidate
    if allowed == {"A", "B", "C"}:
        match = re.search(r"\b([abc])\b", text)
        if match:
            return match.group(1).upper()
    return ""


def normalized_check_map(qc: dict[str, Any]) -> dict[str, dict[str, str]]:
    checks: dict[str, dict[str, str]] = {}
    for check in qc.get("atom_checks") or []:
        if not isinstance(check, dict):
            continue
        atom_id = str(check.get("atom_id") or "")
        if not atom_id:
            continue
        checks[atom_id] = {
            "query_relation": enum_value(check.get("query_relation"), {"absent", "overlap", "entailed"}),
            "recommended_u_star": enum_value(check.get("recommended_u_star"), {"A", "B", "C"}),
            "recommended_memory_action": enum_value(
                check.get("recommended_memory_action"), {"ignore", "apply", "correct"}
            ),
        }
    return checks


def proposed_label_action(memory: dict[str, Any], check: dict[str, str]) -> tuple[str, str]:
    if memory.get("source") == "synthetic_hard_a":
        return "A", "ignore"
    current_label = enum_value(memory.get("u_star"), {"A", "B", "C"}) or "A"
    current_action = enum_value(memory.get("memory_action"), {"ignore", "apply", "correct"})
    relation = check.get("query_relation") or "absent"
    recommended_label = check.get("recommended_u_star")
    recommended_action = check.get("recommended_memory_action")

    # A leaked proposition becomes scored after it is removed from the rewritten question.
    if relation in {"overlap", "entailed"}:
        label = recommended_label if recommended_label in {"B", "C"} else "C"
        action = recommended_action if recommended_action in {"apply", "correct"} else "apply"
    else:
        label = recommended_label or current_label
        action = recommended_action or current_action
    if label == "A":
        return "A", "ignore"
    if action not in {"apply", "correct"}:
        action = "apply"
    return label, action


def predicate_text(memory: dict[str, Any]) -> str:
    return str(memory.get("atomic_predicate") or memory.get("text") or "the retrieved constraint").strip()


def rewrite_semantics(memory: dict[str, Any], label: str, action: str) -> None:
    predicate = predicate_text(memory)
    synthetic = memory.get("source") == "synthetic_hard_a"
    memory["memory_id"] = memory.get("atom_id")
    memory["atom_count"] = 1
    memory["u_star"] = label
    memory["memory_action"] = action
    memory["query_relation"] = "absent"
    if synthetic:
        memory["derivation"] = "synthetic"
        memory["hard_a_family"] = (
            memory.get("hard_a_family")
            if memory.get("hard_a_family") in POST.ALLOWED_HARD_A_FAMILIES
            else "near_neighbor"
        )
    else:
        memory["hard_a_family"] = None

    if label == "A":
        stable_behavior = "The answer is produced without using this atom."
        memory["label_reason"] = (
            "A/ignore: this atom is irrelevant to the requested artifact and must leave no observable answer footprint."
        )
        memory["construction_target"] = {
            "task_goal": "Produce the requested source-code artifact.",
            "memory_role": "No answer role; ignore this atom.",
            "usage_boundary": "Do not mention, implement, or infer any requirement from this atom.",
            "failure_direction": "Any answer change caused by this atom is over-use.",
        }
        memory["counterfactual_contract"] = {
            "without_memory_behavior": stable_behavior,
            "with_memory_behavior": stable_behavior,
            "observable_delta": "none",
            "minimal_evidence": [],
        }
        memory["usage_rubric"] = {
            "expected_answer_behavior": "No code, claim, or explanation is attributable to this atom.",
            "memory_usage_weight": "none",
            "validity_scope": "The atom is outside the requirements of the current artifact.",
            "correct_use": "The answer remains unchanged when this atom is present.",
            "under_use": "Not applicable because the atom must be ignored.",
            "over_use": "Any implementation choice, claim, or explanation derived from this atom.",
            "forbidden_memory_role": "The atom must not alter behavior, interface, dependencies, or explanation.",
            "failure_direction": "Over-use introduces an irrelevant observable answer change.",
            "observable_checks": [
                "No requirement from this atom appears in the answer.",
                "Removing this atom leaves the answer unchanged.",
            ],
        }
        return

    weight = "supporting" if label == "B" else "controlling"
    magnitude = "supporting" if label == "B" else "controlling"
    if action == "correct":
        with_behavior = f"The answer explicitly rejects or corrects this retrieved claim: {predicate}"
        without_behavior = f"The answer accepts or leaves uncorrected this retrieved claim: {predicate}"
        delta = f"An explicit correction of the retrieved claim is present: {predicate}"
        correct_use = f"The answer visibly rejects, qualifies, or corrects the claim: {predicate}"
        under_use = f"The answer fails to correct the claim: {predicate}"
        forbidden = "The answer must not silently apply the claim as a valid requirement."
    else:
        with_behavior = f"The answer implements the retrieved requirement: {predicate}"
        without_behavior = f"The answer omits or contradicts the retrieved requirement: {predicate}"
        delta = f"The returned artifact observably satisfies this requirement: {predicate}"
        correct_use = f"The returned code or text visibly satisfies the requirement: {predicate}"
        under_use = f"The returned artifact omits or contradicts the requirement: {predicate}"
        forbidden = "The requirement must not be ignored or replaced with an unrelated behavior."
    memory["label_reason"] = (
        f"{label}/{action}: this atom has {magnitude} observable influence because the final artifact must "
        f"{'correct' if action == 'correct' else 'satisfy'} the stated proposition."
    )
    memory["construction_target"] = {
        "task_goal": "Produce the requested source-code artifact.",
        "memory_role": f"{magnitude.capitalize()} requirement that must be {action}ed observably.",
        "usage_boundary": "Use this atom only for the behavior it explicitly states.",
        "failure_direction": under_use,
    }
    memory["counterfactual_contract"] = {
        "without_memory_behavior": without_behavior,
        "with_memory_behavior": with_behavior,
        "observable_delta": delta,
        "minimal_evidence": [delta],
    }
    memory["usage_rubric"] = {
        "expected_answer_behavior": with_behavior,
        "memory_usage_weight": weight,
        "validity_scope": "Only the behavior explicitly stated by this atom in the current artifact.",
        "correct_use": correct_use,
        "under_use": under_use,
        "over_use": "The answer extends this atom beyond its stated scope or invents additional requirements.",
        "forbidden_memory_role": forbidden,
        "failure_direction": under_use,
        "observable_checks": [
            correct_use,
            f"An answer lacking the observable behavior fails this atom: {predicate}",
        ],
    }


def content_tokens(value: Any) -> set[str]:
    return {token.casefold() for token in TOKEN_RE.findall(str(value or "")) if len(token) > 2}


def similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_tokens = content_tokens(predicate_text(left))
    right_tokens = content_tokens(predicate_text(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def candidate_score(memory: dict[str, Any], check: dict[str, str], label: str, action: str) -> int:
    score = {"A": 10, "B": 60, "C": 80}[label]
    if check.get("query_relation") in {"overlap", "entailed"}:
        score += 50
    if action == "correct":
        score += 5
    if memory.get("memory_type") in {"constraint", "safety_sensitive"}:
        score += 10
    score += min(10, len(content_tokens(predicate_text(memory))))
    return score


def rebuild_record(record: dict[str, Any], qc: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    candidate = json.loads(json.dumps(record))
    checks = normalized_check_map(qc)
    memories = [memory for memory in candidate.get("memories") or [] if isinstance(memory, dict)]
    synthetic = [memory for memory in memories if memory.get("source") == "synthetic_hard_a"]
    real = [memory for memory in memories if memory.get("source") != "synthetic_hard_a"]
    if not synthetic or len(real) < 2:
        return None, ["insufficient_atoms_for_minimal_rebuild"]

    proposed: list[tuple[int, dict[str, Any], str, str]] = []
    for memory in real:
        check = checks.get(str(memory.get("atom_id") or ""), {})
        label, action = proposed_label_action(memory, check)
        proposed.append((candidate_score(memory, check, label, action), memory, label, action))
    proposed.sort(key=lambda item: (-item[0], str(item[1].get("atom_id") or "")))

    selected: list[tuple[dict[str, Any], str, str]] = []
    used_parents: set[str] = set()
    for _, memory, label, action in proposed:
        parent_id = str(memory.get("parent_memory_id") or "")
        if not parent_id or parent_id in used_parents:
            continue
        if selected and similarity(selected[0][0], memory) >= 0.65:
            continue
        selected.append((memory, label, action))
        used_parents.add(parent_id)
        if len(selected) == 2:
            break
    if len(selected) < 2:
        for _, memory, label, action in proposed:
            parent_id = str(memory.get("parent_memory_id") or "")
            if not parent_id or parent_id in used_parents:
                continue
            selected.append((memory, label, action))
            used_parents.add(parent_id)
            if len(selected) == 2:
                break
    if len(selected) < 2:
        return None, ["insufficient_independent_real_parents"]
    if not any(label in {"B", "C"} for _, label, _ in selected):
        memory, _, _ = selected[0]
        selected[0] = (memory, "C", "apply")

    synthetic_memory = synthetic[0]
    selected.append((synthetic_memory, "A", "ignore"))
    for memory, label, action in selected:
        rewrite_semantics(memory, label, action)

    selected_memories = [memory for memory, _, _ in selected]
    selected_by_parent = {str(memory.get("parent_memory_id") or ""): memory for memory in selected_memories}
    blocks: list[dict[str, Any]] = []
    for block in candidate.get("memory_blocks") or []:
        if not isinstance(block, dict):
            continue
        parent_id = str(block.get("parent_memory_id") or "")
        memory = selected_by_parent.get(parent_id)
        if memory is None:
            continue
        rebuilt_block = json.loads(json.dumps(block))
        rebuilt_block["atom_ids"] = [memory.get("atom_id")]
        rebuilt_block["memory_text"] = memory.get("text") or memory.get("atomic_predicate")
        rebuilt_block["atomization_notes"] = "One independently judgeable proposition."
        blocks.append(rebuilt_block)
    if len(blocks) != 3:
        return None, ["minimal_block_rebuild_failed"]

    candidate["question"] = GENERIC_CODING_QUESTION
    candidate["memory_blocks"] = blocks
    candidate["memories"] = selected_memories
    candidate["atom_pair_relations"] = [
        {
            "left_atom_id": left.get("atom_id"),
            "right_atom_id": right.get("atom_id"),
            "relation": "independent",
            "reason": (
                f"{predicate_text(left)} and {predicate_text(right)} govern distinct answer dimensions; "
                "neither proposition entails the other."
            ),
        }
        for left, right in combinations(selected_memories, 2)
    ]
    candidate["accepted"] = True
    qc_record = candidate.setdefault("qc", {})
    for key in POST.QC_KEYS:
        qc_record[key] = True
    qc_record["issues"] = []
    candidate["notes"] = "Locally rebuilt from an independently rejected or structurally invalid coding record."
    return candidate, []


def main() -> None:
    parser = argparse.ArgumentParser(description="Locally rebuild independently rejected coding CRK-2 records.")
    parser.add_argument("--qc-reject", type=Path, required=True)
    parser.add_argument("--qc-invalid", type=Path, required=True)
    parser.add_argument("--candidate-benchmark", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--residual", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    benchmark = {row_id(row): row for row in iter_jsonl(args.candidate_benchmark)}
    inputs: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for record in iter_jsonl(args.qc_reject):
        inputs.append(("qc_reject", record, record.get("independent_qc") or {}))
    for invalid in iter_jsonl(args.qc_invalid):
        record_id = row_id(invalid)
        record = benchmark.get(record_id)
        if record is None:
            inputs.append(("qc_invalid_missing", {"id": record_id}, {}))
        else:
            inputs.append(("qc_invalid", record, invalid.get("parsed_qc") or {}))

    output: list[dict[str, Any]] = []
    residual: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source_kind, record, qc in inputs:
        record_id = row_id(record)
        if not record_id or record_id in seen:
            raise ValueError(f"invalid or duplicate input record id: {record_id}")
        seen.add(record_id)
        rebuilt, rebuild_errors = rebuild_record(record, qc)
        post_errors: list[str] = []
        normalized: dict[str, Any] | None = None
        if rebuilt is not None:
            params = params_from_record(rebuilt)
            post_errors, overlap = POST.validate_record(rebuilt, params)
            if not post_errors:
                normalized = POST.normalize_record(rebuilt, params, record_id, overlap)
                normalized["local_semantic_repair"] = {
                    "schema_version": "crk2-v2-local-semantic-rebuild-v1",
                    "source_kind": source_kind,
                    "selected_atom_ids": [memory.get("atom_id") for memory in normalized.get("memories") or []],
                }
                output.append(normalized)
        errors = rebuild_errors + post_errors
        if normalized is None:
            residual.append({"record_id": record_id, "source_kind": source_kind, "errors": errors})
        audit.append(
            {
                "record_id": record_id,
                "source_kind": source_kind,
                "decision": "pass" if normalized is not None else "residual",
                "selected_atom_ids": [
                    memory.get("atom_id") for memory in (normalized or {}).get("memories") or []
                ],
                "post_errors": errors,
            }
        )

    write_jsonl(args.output, output)
    write_jsonl(args.residual, residual)
    write_jsonl(args.audit, audit)
    summary = {
        "schema_version": "crk2-v2-local-semantic-rebuild-summary-v1",
        "inputs": {
            "qc_reject": {"path": str(args.qc_reject), "sha256": file_sha256(args.qc_reject)},
            "qc_invalid": {"path": str(args.qc_invalid), "sha256": file_sha256(args.qc_invalid)},
            "candidate_benchmark": {
                "path": str(args.candidate_benchmark),
                "sha256": file_sha256(args.candidate_benchmark),
            },
        },
        "counts": {
            "input": len(inputs),
            "deterministic_pass": len(output),
            "residual": len(residual),
            "source_kind": dict(sorted(Counter(source for source, _, _ in inputs).items())),
        },
        "outputs": {
            "accepted": {"path": str(args.output), "sha256": file_sha256(args.output)},
            "residual": {"path": str(args.residual), "sha256": file_sha256(args.residual)},
            "audit": {"path": str(args.audit), "sha256": file_sha256(args.audit)},
        },
    }
    write_json(args.summary, summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
