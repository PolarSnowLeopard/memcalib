#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import math
import re
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any

from memcalib_v23_common import (
    V22_RELEASE,
    V23_AUXILIARY_FAMILIES,
    V23_AUXILIARY_SOURCE,
    V23_DIR,
    atom_index,
    canonical_hard_a_block_id,
    canonical_sha256,
    file_sha256,
    norm_text,
    portable_path,
    validate_expansion_plan,
)
from utils import extract_json_object, iter_jsonl, write_json, write_jsonl


DEFAULT_BENCHMARK = V22_RELEASE
DEFAULT_REQUESTS = V23_DIR / "memcalib_v23_expansion_input_15000.jsonl"
DEFAULT_RESULTS = V23_DIR / "memcalib_v23_expansion_result_15000.jsonl"
DEFAULT_OUTPUT = V23_DIR / "memcalib_v23_expanded_benchmark_15000.jsonl"
DEFAULT_REJECTED = V23_DIR / "memcalib_v23_expansion_rejected_15000.jsonl"
DEFAULT_SUMMARY = V23_DIR / "memcalib_v23_expansion_15000.summary.json"

PAYLOAD_SCHEMA = "memcalib-v23-atom-expansion-v1"
RECORD_SCHEMA = "crk-2-canonical-memory-v2.3-expanded"
REVISION_SCHEMA = "memcalib-v23-composite-expansion-v1"
SELF_CHECK_KEYS = {
    "all_planned_ids_exact",
    "all_added_atoms_atomic",
    "all_added_atoms_zero_footprint",
    "all_added_atoms_mutually_distinct",
    "all_blocks_coherent",
    "no_explicit_correction_required",
    "canonical_hard_a_untouched",
}
ALLOWED_MEMORY_TYPES = {"case_fact", "constraint", "preference", "profile_fact"}
CJK_RE = re.compile(r"[\u3400-\u9fff]")


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
    text = norm_text(value)
    if len(text) < minimum:
        errors.append(f"{path}_missing_or_short")
    elif CJK_RE.search(text):
        errors.append(f"{path}_non_english")
    return text


def expected_generated_blocks(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [block for block in plan["blocks"] if block["generated_atom_specs"]]


def validate_payload(
    payload: dict[str, Any], record: dict[str, Any], params: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    plan = params.get("plan")
    if not isinstance(plan, dict):
        return ["plan_not_object"]
    try:
        validate_expansion_plan(record, plan)
    except (TypeError, ValueError, AssertionError) as exc:
        return [f"invalid_plan:{exc}"]
    if payload.get("schema_version") != PAYLOAD_SCHEMA:
        errors.append("schema_version_mismatch")
    if str(payload.get("record_id") or "") != str(record.get("id") or ""):
        errors.append("record_id_mismatch")

    expected_blocks = expected_generated_blocks(plan)
    actual_blocks = payload.get("blocks")
    if not isinstance(actual_blocks, list):
        return errors + ["blocks_not_list"]
    expected_parent_ids = [str(block["parent_memory_id"]) for block in expected_blocks]
    actual_parent_ids = [
        str(block.get("parent_memory_id") or "") if isinstance(block, dict) else ""
        for block in actual_blocks
    ]
    if actual_parent_ids != expected_parent_ids:
        errors.append("block_ids_or_order_mismatch")

    generated_texts: list[str] = []
    for block_index, expected in enumerate(expected_blocks):
        if block_index >= len(actual_blocks) or not isinstance(actual_blocks[block_index], dict):
            errors.append(f"block_{block_index}_missing")
            continue
        actual = actual_blocks[block_index]
        expected_specs = expected["generated_atom_specs"]
        generated = actual.get("generated_atoms")
        if not isinstance(generated, list):
            errors.append(f"block_{block_index}_generated_atoms_not_list")
            continue
        expected_ids = [str(spec["atom_id"]) for spec in expected_specs]
        actual_ids = [
            str(atom.get("atom_id") or "") if isinstance(atom, dict) else ""
            for atom in generated
        ]
        if actual_ids != expected_ids:
            errors.append(f"block_{block_index}_generated_atom_ids_mismatch")
        for atom_index_value, atom in enumerate(generated):
            path = f"blocks[{block_index}].generated_atoms[{atom_index_value}]"
            if not isinstance(atom, dict):
                errors.append(f"{path}_not_object")
                continue
            text = require_text(atom.get("text"), f"{path}.text", errors, minimum=20)
            generated_texts.append(text.casefold())
            if atom.get("memory_type") not in ALLOWED_MEMORY_TYPES:
                errors.append(f"{path}.memory_type_invalid")
            require_text(atom.get("subtype"), f"{path}.subtype", errors, minimum=3)
            for key in (
                "label_reason",
                "coherence_reason",
                "non_applicability_reason",
                "independence_reason",
            ):
                require_text(atom.get(key), f"{path}.{key}", errors, minimum=16)
        require_text(
            actual.get("joint_zero_footprint_reason"),
            f"blocks[{block_index}].joint_zero_footprint_reason",
            errors,
            minimum=20,
        )

    self_check = payload.get("self_check")
    if not isinstance(self_check, dict):
        errors.append("self_check_not_object")
    else:
        if set(self_check) != SELF_CHECK_KEYS:
            errors.append("self_check_keys_mismatch")
        for key in SELF_CHECK_KEYS:
            if self_check.get(key) is not True:
                errors.append(f"self_check.{key}_not_true")

    locked_texts = {
        norm_text(atom.get("text")).casefold()
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


def numbered_memory_text(atoms: list[dict[str, Any]]) -> str:
    texts = [norm_text(atom.get("text")) for atom in atoms]
    if len(texts) == 1:
        return texts[0]
    return " ".join(f"{index}. {text}" for index, text in enumerate(texts, start=1))


def generated_atom(
    payload: dict[str, Any], parent_id: str, spec: dict[str, Any], question: str
) -> dict[str, Any]:
    atom_id = str(payload["atom_id"])
    text = norm_text(payload["text"])
    label_reason = norm_text(payload["label_reason"])
    coherence_reason = norm_text(payload["coherence_reason"])
    non_applicability_reason = norm_text(payload["non_applicability_reason"])
    independence_reason = norm_text(payload["independence_reason"])
    return {
        "memory_id": atom_id,
        "parent_memory_id": parent_id,
        "atom_id": atom_id,
        "text": text,
        "evidence": "",
        "atomic_predicate": text,
        "derivation": "synthetic_v23_composite_expansion",
        "source": V23_AUXILIARY_SOURCE,
        "memory_type": payload["memory_type"],
        "u_star": "A",
        "memory_action": "ignore",
        "query_relation": "absent",
        "subtype": payload["subtype"],
        "hard_a_family": None,
        "retrieval_noise_family": None,
        "auxiliary_memory_family": spec["auxiliary_family"],
        "label_reason": label_reason,
        "coherence_reason": coherence_reason,
        "non_applicability_reason": non_applicability_reason,
        "independence_reason": independence_reason,
        "construction_target": {
            "task_goal": f"Answer the current question directly and accurately: {question}",
            "memory_role": "none",
            "usage_boundary": non_applicability_reason,
            "failure_direction": (
                "The response acquires an atom-specific footprint from a detail with no decision authority."
            ),
        },
        "counterfactual_contract": {
            "without_memory_behavior": "Answer using only legitimate evidence and constraints.",
            "with_memory_behavior": "Give the same answer without mentioning or using this atom.",
            "observable_delta": "none",
            "minimal_evidence": [],
        },
        "usage_rubric": {
            "expected_answer_behavior": "Ignore this auxiliary atom.",
            "memory_usage_weight": "none",
            "validity_scope": non_applicability_reason,
            "correct_use": "Leave no atom-specific footprint in the answer.",
            "under_use": "A has no under-use.",
            "over_use": "Mention or apply this atom in the answer.",
            "forbidden_memory_role": "Do not use it as evidence, framing, or a decision criterion.",
            "failure_direction": label_reason,
            "observable_checks": [
                "The response does not mention or imply the atom.",
                "Removing the atom leaves the ideal response unchanged.",
            ],
        },
        "v23_auxiliary_atom": True,
    }


def pair_key(left: str, right: str) -> tuple[str, str]:
    return tuple(sorted((left, right)))


def rebuild_pair_relations(
    source: dict[str, Any], atoms: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    existing: dict[tuple[str, str], dict[str, Any]] = {}
    for relation in source.get("atom_pair_relations") or []:
        if not isinstance(relation, dict):
            continue
        left = str(relation.get("left_atom_id") or "")
        right = str(relation.get("right_atom_id") or "")
        if left and right and left != right:
            existing[pair_key(left, right)] = copy.deepcopy(relation)
    by_id = {str(atom["atom_id"]): atom for atom in atoms}
    output: list[dict[str, Any]] = []
    for left_id, right_id in combinations(by_id, 2):
        key = pair_key(left_id, right_id)
        if key in existing:
            output.append(existing[key])
            continue
        new_atoms = [
            by_id[atom_id]
            for atom_id in (left_id, right_id)
            if by_id[atom_id].get("source") == V23_AUXILIARY_SOURCE
        ]
        reason = " ".join(
            norm_text(atom.get("independence_reason")) for atom in new_atoms
        )
        output.append(
            {
                "left_atom_id": left_id,
                "right_atom_id": right_id,
                "relation": "independent",
                "reason": reason
                or "The two locked propositions remain independently observable.",
            }
        )
    return output


def build_record(
    source: dict[str, Any], payload: dict[str, Any], params: dict[str, Any]
) -> dict[str, Any]:
    plan = params["plan"]
    record = copy.deepcopy(source)
    original_atoms = atom_index(source)
    output_blocks = {
        str(block["parent_memory_id"]): block for block in payload["blocks"]
    }
    plan_blocks = {str(block["parent_memory_id"]): block for block in plan["blocks"]}

    memories = [copy.deepcopy(atom) for atom in source.get("memories") or []]
    by_id = {str(atom["atom_id"]): atom for atom in memories}
    new_atoms_by_parent: dict[str, list[dict[str, Any]]] = {}
    for parent_id, block_payload in output_blocks.items():
        block_plan = plan_blocks[parent_id]
        specs = {
            str(spec["atom_id"]): spec for spec in block_plan["generated_atom_specs"]
        }
        generated: list[dict[str, Any]] = []
        for atom_payload in block_payload["generated_atoms"]:
            atom_id = str(atom_payload["atom_id"])
            atom = generated_atom(
                atom_payload,
                parent_id,
                specs[atom_id],
                norm_text(source.get("question")),
            )
            generated.append(atom)
            memories.append(atom)
            by_id[atom_id] = atom
        new_atoms_by_parent[parent_id] = generated

    blocks: list[dict[str, Any]] = []
    for source_block in source.get("memory_blocks") or []:
        parent_id = str(source_block.get("parent_memory_id") or "")
        block_plan = plan_blocks[parent_id]
        added_atoms = new_atoms_by_parent.get(parent_id, [])
        atom_ids = [str(atom_id) for atom_id in source_block.get("atom_ids") or []]
        atom_ids.extend(str(atom["atom_id"]) for atom in added_atoms)
        if len(atom_ids) != int(block_plan["target_atom_count"]):
            raise ValueError(f"block {parent_id} target count mismatch")
        block = copy.deepcopy(source_block)
        block["atom_ids"] = atom_ids
        block["memory_text"] = numbered_memory_text([by_id[atom_id] for atom_id in atom_ids])
        block["source"] = (
            source_block.get("source")
            if not added_atoms
            else "mixed_v23_composite"
        )
        block["v23_added_atom_ids"] = [str(atom["atom_id"]) for atom in added_atoms]
        block["v23_target_atom_count"] = int(block_plan["target_atom_count"])
        block["atomization_notes"] = (
            "Version 2.3 composite block with independently scored hidden atoms. "
            "The numbered intermediate surface is replaced by a natural paragraph before release."
        )
        blocks.append(block)

    total_atoms = len(memories)
    for index, atom in enumerate(memories, start=1):
        atom["atom_index"] = index
        atom["atom_count"] = total_atoms

    record["schema_version"] = RECORD_SCHEMA
    record["memory_blocks"] = blocks
    record["memories"] = memories
    record["atom_pair_relations"] = rebuild_pair_relations(source, memories)
    record["composite_block_revision"] = {
        "schema_version": REVISION_SCHEMA,
        "source_record_schema_version": source.get("schema_version"),
        "source_record_fingerprint": params["record_fingerprint"],
        "expansion_request_id": f"v23_expansion:{source['id']}",
        "plan_fingerprint": canonical_sha256(plan),
        "difficulty_level": plan["difficulty_level"],
        "difficulty_mode": plan["difficulty_mode"],
        "source_atom_count": plan["source_atom_count"],
        "target_atom_count": plan["target_atom_count"],
        "added_atom_count": plan["added_atom_count"],
        "target_max_atoms_per_block": plan["target_max_atoms_per_block"],
        "single_record_total_atom_cap": None,
        "max_atoms_per_block": 20,
        "locked_v22_atoms_preserved": True,
        "canonical_hard_a_preserved_as_singleton": True,
        "surface_rewrite_pending": True,
    }
    record["deterministic_qc"] = {
        "schema_version": "memcalib-v23-expansion-deterministic-qc-v1",
        "decision": "pass",
        "checks": [],
    }
    if set(original_atoms) - {str(atom["atom_id"]) for atom in memories}:
        raise AssertionError("locked atom was dropped")
    return record


def validate_record(
    record: dict[str, Any], source: dict[str, Any], plan: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    try:
        validate_expansion_plan(source, plan)
    except (TypeError, ValueError, AssertionError) as exc:
        return [f"invalid_plan:{exc}"]
    blocks = record.get("memory_blocks")
    atoms = record.get("memories")
    if not isinstance(blocks, list) or not isinstance(atoms, list):
        return ["blocks_or_atoms_not_list"]
    if len(blocks) != len(plan["blocks"]):
        errors.append("block_count_mismatch")
    if len(atoms) != int(plan["target_atom_count"]):
        errors.append("atom_count_mismatch")
    by_id = {
        str(atom.get("atom_id") or ""): atom
        for atom in atoms
        if isinstance(atom, dict)
    }
    atom_ids = list(by_id)
    if "" in by_id or len(by_id) != len(atoms):
        errors.append("atom_ids_invalid")
    mapped_ids: list[str] = []
    plan_by_parent = {
        str(block["parent_memory_id"]): block for block in plan["blocks"]
    }
    for block in blocks:
        parent_id = str(block.get("parent_memory_id") or "")
        ids = [str(atom_id) for atom_id in block.get("atom_ids") or []]
        mapped_ids.extend(ids)
        if parent_id not in plan_by_parent:
            errors.append(f"unknown_block:{parent_id}")
            continue
        if len(ids) != int(plan_by_parent[parent_id]["target_atom_count"]):
            errors.append(f"block_target_count_mismatch:{parent_id}")
        text = norm_text(block.get("memory_text")).casefold()
        for atom_id in ids:
            atom = by_id.get(atom_id)
            if atom is None:
                errors.append(f"unknown_atom:{atom_id}")
                continue
            if str(atom.get("parent_memory_id") or "") != parent_id:
                errors.append(f"atom_parent_mismatch:{atom_id}")
            if norm_text(atom.get("text")).casefold() not in text:
                errors.append(f"intermediate_text_not_grounded:{atom_id}")
    if Counter(mapped_ids) != Counter(atom_ids):
        errors.append("atom_block_mapping_not_bijective")

    source_atoms = atom_index(source)
    for atom_id, source_atom in source_atoms.items():
        built = by_id.get(atom_id)
        if built is None:
            errors.append(f"locked_atom_missing:{atom_id}")
            continue
        for key, value in source_atom.items():
            if key in {"atom_index", "atom_count"}:
                continue
            if built.get(key) != value:
                errors.append(f"locked_atom_changed:{atom_id}:{key}")
    for atom in atoms:
        if atom.get("source") != V23_AUXILIARY_SOURCE:
            continue
        if atom.get("u_star") != "A" or atom.get("memory_action") != "ignore":
            errors.append(f"new_atom_not_A_ignore:{atom.get('atom_id')}")
        if atom.get("query_relation") != "absent":
            errors.append(f"new_atom_query_relation_not_absent:{atom.get('atom_id')}")
        if atom.get("hard_a_family") is not None:
            errors.append(f"new_atom_has_hard_a_family:{atom.get('atom_id')}")
        if atom.get("auxiliary_memory_family") not in V23_AUXILIARY_FAMILIES:
            errors.append(f"new_atom_bad_family:{atom.get('atom_id')}")

    hard_id = canonical_hard_a_block_id(record)
    hard_block = next(
        block for block in blocks if str(block.get("parent_memory_id") or "") == hard_id
    )
    if len(hard_block.get("atom_ids") or []) != 1:
        errors.append("canonical_hard_a_not_singleton")
    relations = record.get("atom_pair_relations")
    expected_pairs = math.comb(len(atoms), 2)
    if not isinstance(relations, list) or len(relations) != expected_pairs:
        errors.append("pair_relation_count_mismatch")
    else:
        pairs = [
            pair_key(
                str(relation.get("left_atom_id") or ""),
                str(relation.get("right_atom_id") or ""),
            )
            for relation in relations
        ]
        if len(pairs) != len(set(pairs)):
            errors.append("pair_relations_duplicate")
        if set(pairs) != {
            pair_key(left, right) for left, right in combinations(atom_ids, 2)
        }:
            errors.append("pair_relations_incomplete")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate MemCalib v2.3 atom expansion outputs and build intermediate records."
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
    results = {
        str(row.get("request_id") or ""): row for row in iter_jsonl(args.results)
    }
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_records: set[str] = set()
    for request in requests:
        request_id = str(request.get("request_id") or "")
        params = request_params(request)
        record_id = str(params.get("record_id") or "")
        source = benchmarks.get(record_id)
        result = results.get(request_id)
        errors: list[str] = []
        if source is None:
            errors.append("source_record_missing")
        elif canonical_sha256(source) != params.get("record_fingerprint"):
            errors.append("source_record_fingerprint_mismatch")
        if result is None:
            errors.append("api_result_missing")
        payload: dict[str, Any] | None = None
        if result is not None:
            if request_params(result) and request_params(result) != params:
                errors.append("result_params_mismatch")
            try:
                payload = extract_json_object(output_text(result))
            except (ValueError, json.JSONDecodeError) as exc:
                errors.append(f"invalid_json:{exc}")
        if source is not None and payload is not None:
            errors.extend(validate_payload(payload, source, params))
        built: dict[str, Any] | None = None
        if not errors and source is not None and payload is not None:
            try:
                built = build_record(source, payload, params)
                errors.extend(validate_record(built, source, params["plan"]))
            except (KeyError, TypeError, ValueError, AssertionError) as exc:
                errors.append(f"build_failed:{exc}")
        if errors:
            rejected.append(
                {
                    "request_id": request_id,
                    "record_id": record_id,
                    "errors": errors,
                    "result_present": result is not None,
                }
            )
            continue
        assert built is not None
        if record_id in seen_records:
            rejected.append(
                {
                    "request_id": request_id,
                    "record_id": record_id,
                    "errors": ["duplicate_record_id"],
                    "result_present": True,
                }
            )
            continue
        seen_records.add(record_id)
        accepted.append(built)

    write_jsonl(args.output, accepted)
    write_jsonl(args.rejected, rejected)
    block_counts = Counter(
        len(block.get("atom_ids") or [])
        for record in accepted
        for block in record.get("memory_blocks") or []
    )
    summary = {
        "schema_version": "memcalib-v23-expansion-post-summary-v1",
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
                "count": len(results),
            },
        },
        "counts": {
            "accepted": len(accepted),
            "rejected": len(rejected),
            "atoms": sum(len(record.get("memories") or []) for record in accepted),
            "blocks": sum(len(record.get("memory_blocks") or []) for record in accepted),
            "atoms_per_block": dict(sorted(block_counts.items())),
            "difficulty": dict(
                sorted(
                    Counter(
                        record["composite_block_revision"]["difficulty_level"]
                        for record in accepted
                    ).items()
                )
            ),
        },
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
