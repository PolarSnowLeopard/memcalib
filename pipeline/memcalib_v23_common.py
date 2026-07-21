#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data" / "multidomain" / "full-v2"
V22_DIR = DATA_DIR / "revision-longtail-blocks"
V23_DIR = DATA_DIR / "revision-composite-blocks-v23"
V22_RELEASE = V22_DIR / "release" / "memcalib_v22_multidomain_benchmark_15000.jsonl"

DIFFICULTY_LEVELS = ("level_1", "level_2", "level_3")
DIFFICULTY_WEIGHTS = {
    "level_1": 0.25,
    "level_2": 0.50,
    "level_3": 0.25,
}
MAX_ATOMS_PER_BLOCK = 20
CANONICAL_HARD_A_SOURCE = "synthetic_hard_a"
V23_AUXILIARY_SOURCE = "synthetic_v23_auxiliary"
V23_AUXILIARY_FAMILIES = (
    "coherent_background_detail",
    "bounded_nearby_context",
    "same_episode_metadata",
    "non_decisive_prior_detail",
)
V23_AUXILIARY_ROLES = (
    "Add one independently scorable background fact from the same remembered episode.",
    "Add one bounded contextual detail that is coherent with the block but has no answer footprint.",
    "Add one distinct event, state, or preference detail without changing the current task's answer.",
    "Add one plausible same-user detail that a weak model might overuse but a correct model must ignore.",
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


def stable_key(seed: int, purpose: str, *parts: object) -> str:
    joined = ":".join(str(part) for part in parts)
    return hashlib.sha256(f"{seed}:{purpose}:{joined}".encode("utf-8")).hexdigest()


def norm_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def scaled_level_quotas(total: int) -> dict[str, int]:
    if total <= 0:
        raise ValueError("difficulty quota total must be positive")
    exact = {level: total * weight for level, weight in DIFFICULTY_WEIGHTS.items()}
    counts = {level: math.floor(value) for level, value in exact.items()}
    remaining = total - sum(counts.values())
    order = sorted(
        DIFFICULTY_LEVELS,
        key=lambda level: (
            -(exact[level] - counts[level]),
            DIFFICULTY_LEVELS.index(level),
        ),
    )
    for level in order[:remaining]:
        counts[level] += 1
    return counts


def atom_index(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    atoms = record.get("memories") or []
    if not isinstance(atoms, list):
        raise ValueError(f"record {record.get('id')} memories must be a list")
    output = {
        str(atom.get("atom_id") or ""): atom
        for atom in atoms
        if isinstance(atom, dict)
    }
    if "" in output or len(output) != len(atoms):
        raise ValueError(f"record {record.get('id')} has invalid atom IDs")
    return output


def canonical_hard_a_block_id(record: dict[str, Any]) -> str:
    atoms = atom_index(record)
    candidates = [
        str(block.get("parent_memory_id") or "")
        for block in record.get("memory_blocks") or []
        if isinstance(block, dict)
        and any(
            atoms.get(str(atom_id), {}).get("source") == CANONICAL_HARD_A_SOURCE
            for atom_id in block.get("atom_ids") or []
        )
    ]
    if len(candidates) != 1:
        raise ValueError(
            f"record {record.get('id')} must have exactly one canonical Hard A block"
        )
    block_id = candidates[0]
    block = next(
        block
        for block in record.get("memory_blocks") or []
        if str(block.get("parent_memory_id") or "") == block_id
    )
    if len(block.get("atom_ids") or []) != 1:
        raise ValueError(
            f"record {record.get('id')} canonical Hard A must remain a singleton"
        )
    return block_id


def level_one_eligible(record: dict[str, Any]) -> bool:
    hard_id = canonical_hard_a_block_id(record)
    noncanonical_counts = [
        len(block.get("atom_ids") or [])
        for block in record.get("memory_blocks") or []
        if str(block.get("parent_memory_id") or "") != hard_id
    ]
    return (
        bool(noncanonical_counts)
        and max(noncanonical_counts) <= 4
        and sum(count > 2 for count in noncanonical_counts) <= 1
    )


def assign_difficulty_levels(
    records: list[dict[str, Any]], seed: int
) -> tuple[dict[str, str], dict[str, dict[str, int]]]:
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        record_id = str(record.get("id") or "")
        if not record_id:
            raise ValueError("record IDs must be non-empty")
        by_domain[str(record.get("domain") or "health_seed")].append(record)

    assignments: dict[str, str] = {}
    quotas_by_domain: dict[str, dict[str, int]] = {}
    for domain, domain_records in sorted(by_domain.items()):
        quotas = scaled_level_quotas(len(domain_records))
        quotas_by_domain[domain] = quotas
        eligible = sorted(
            (record for record in domain_records if level_one_eligible(record)),
            key=lambda record: stable_key(
                seed, "difficulty:level_1", domain, record.get("id")
            ),
        )
        if len(eligible) < quotas["level_1"]:
            raise ValueError(
                f"domain {domain} has only {len(eligible)} Level 1 eligible records"
            )
        level_one_ids = {
            str(record["id"]) for record in eligible[: quotas["level_1"]]
        }
        remaining = sorted(
            (
                record
                for record in domain_records
                if str(record.get("id") or "") not in level_one_ids
            ),
            key=lambda record: stable_key(
                seed, "difficulty:remaining", domain, record.get("id")
            ),
        )
        level_three_ids = {
            str(record["id"]) for record in remaining[: quotas["level_3"]]
        }
        for record in domain_records:
            record_id = str(record["id"])
            if record_id in level_one_ids:
                assignments[record_id] = "level_1"
            elif record_id in level_three_ids:
                assignments[record_id] = "level_3"
            else:
                assignments[record_id] = "level_2"
        observed = {
            level: sum(
                assignments[str(record["id"])] == level for record in domain_records
            )
            for level in DIFFICULTY_LEVELS
        }
        if observed != quotas:
            raise AssertionError(f"difficulty assignment mismatch for {domain}")
    return assignments, quotas_by_domain


def stable_int(
    seed: int, purpose: str, lower: int, upper: int, *parts: object
) -> int:
    if lower > upper:
        raise ValueError("invalid stable integer range")
    value = int(stable_key(seed, purpose, *parts)[:16], 16)
    return lower + value % (upper - lower + 1)


def ordered_noncanonical_blocks(
    record: dict[str, Any], seed: int
) -> list[dict[str, Any]]:
    hard_id = canonical_hard_a_block_id(record)
    record_id = str(record.get("id") or "")
    blocks = [
        block
        for block in record.get("memory_blocks") or []
        if isinstance(block, dict)
        and str(block.get("parent_memory_id") or "") != hard_id
    ]
    if len(blocks) < 2:
        raise ValueError(f"record {record_id} needs at least two noncanonical blocks")
    atoms = atom_index(record)
    return sorted(
        blocks,
        key=lambda block: (
            -sum(
                atoms[str(atom_id)].get("u_star") in {"B", "C"}
                for atom_id in block.get("atom_ids") or []
            ),
            stable_key(
                seed,
                "focus-block",
                record_id,
                block.get("parent_memory_id"),
            ),
        ),
    )


def target_counts_for_level(
    record: dict[str, Any], level: str, seed: int
) -> tuple[dict[str, int], str]:
    if level not in DIFFICULTY_LEVELS:
        raise ValueError(f"unknown difficulty level {level!r}")
    record_id = str(record.get("id") or "")
    hard_id = canonical_hard_a_block_id(record)
    ordered = ordered_noncanonical_blocks(record, seed)
    current = {
        str(block.get("parent_memory_id") or ""): len(block.get("atom_ids") or [])
        for block in record.get("memory_blocks") or []
    }
    targets = {hard_id: 1}

    if level == "level_1":
        for block in ordered:
            parent_id = str(block["parent_memory_id"])
            targets[parent_id] = max(current[parent_id], 2)
        focus_id = str(ordered[0]["parent_memory_id"])
        targets[focus_id] = max(
            targets[focus_id],
            stable_int(seed, "level1-focus", 3, 4, record_id),
        )
        mode = "single_3_to_4_atom_focus"
    elif level == "level_2":
        for block in ordered:
            parent_id = str(block["parent_memory_id"])
            targets[parent_id] = max(current[parent_id], 3)
        focus_id = str(ordered[0]["parent_memory_id"])
        targets[focus_id] = max(
            targets[focus_id],
            stable_int(seed, "level2-focus", 5, 7, record_id),
        )
        mode = "single_5_to_7_atom_focus"
    else:
        for block in ordered:
            parent_id = str(block["parent_memory_id"])
            targets[parent_id] = max(current[parent_id], 3)
        selector = stable_int(seed, "level3-mode", 0, 9, record_id)
        if selector <= 3 or len(ordered) < 2:
            focus_id = str(ordered[0]["parent_memory_id"])
            targets[focus_id] = max(
                targets[focus_id],
                stable_int(seed, "level3-focus-8-12", 8, 12, record_id),
            )
            mode = "single_8_to_12_atom_focus"
        elif selector == 4:
            focus_id = str(ordered[0]["parent_memory_id"])
            targets[focus_id] = max(
                targets[focus_id],
                stable_int(seed, "level3-focus-13-20", 13, 20, record_id),
            )
            mode = "single_13_to_20_atom_focus"
        else:
            for ordinal, block in enumerate(ordered[:2], start=1):
                focus_id = str(block["parent_memory_id"])
                targets[focus_id] = max(
                    targets[focus_id],
                    stable_int(
                        seed,
                        f"level3-dual-focus-{ordinal}",
                        5,
                        7,
                        record_id,
                    ),
                )
            mode = "dual_5_to_7_atom_focus"

    if set(targets) != set(current):
        missing = sorted(set(current) - set(targets))
        raise AssertionError(f"target plan omitted blocks: {missing}")
    for parent_id, target in targets.items():
        if target < current[parent_id] or not 1 <= target <= MAX_ATOMS_PER_BLOCK:
            raise ValueError(
                f"record {record_id} block {parent_id} has invalid target {target}"
            )
    if targets[hard_id] != 1:
        raise AssertionError("canonical Hard A must stay singleton")
    return targets, mode


def build_expansion_plan(
    record: dict[str, Any], level: str, seed: int
) -> dict[str, Any]:
    record_id = str(record.get("id") or "")
    targets, mode = target_counts_for_level(record, level, seed)
    atoms = atom_index(record)
    blocks: list[dict[str, Any]] = []
    used_ids = set(atoms)
    for block_index, block in enumerate(record.get("memory_blocks") or [], start=1):
        parent_id = str(block.get("parent_memory_id") or "")
        current_ids = [str(atom_id) for atom_id in block.get("atom_ids") or []]
        target = targets[parent_id]
        added = target - len(current_ids)
        generated_specs: list[dict[str, Any]] = []
        for offset in range(1, added + 1):
            atom_id = f"v23_aux_b{block_index:02d}_a{offset:02d}"
            if atom_id in used_ids:
                raise ValueError(f"record {record_id} generated duplicate atom ID")
            used_ids.add(atom_id)
            family = V23_AUXILIARY_FAMILIES[
                stable_int(
                    seed,
                    "aux-family",
                    0,
                    len(V23_AUXILIARY_FAMILIES) - 1,
                    record_id,
                    parent_id,
                    offset,
                )
            ]
            role = V23_AUXILIARY_ROLES[
                stable_int(
                    seed,
                    "aux-role",
                    0,
                    len(V23_AUXILIARY_ROLES) - 1,
                    record_id,
                    parent_id,
                    offset,
                )
            ]
            generated_specs.append(
                {
                    "atom_id": atom_id,
                    "auxiliary_family": family,
                    "atom_role": role,
                }
            )
        blocks.append(
            {
                "parent_memory_id": parent_id,
                "current_atom_ids": current_ids,
                "current_atom_count": len(current_ids),
                "target_atom_count": target,
                "generated_atom_specs": generated_specs,
                "locked_atom_texts": [
                    {
                        "atom_id": atom_id,
                        "text": norm_text(atoms[atom_id].get("text")),
                    }
                    for atom_id in current_ids
                ],
            }
        )

    target_counts = [block["target_atom_count"] for block in blocks]
    noncanonical_counts = [
        block["target_atom_count"]
        for block in blocks
        if block["parent_memory_id"] != canonical_hard_a_block_id(record)
    ]
    plan = {
        "schema_version": "memcalib-v23-expansion-plan-v1",
        "difficulty_level": level,
        "difficulty_mode": mode,
        "canonical_hard_a_block_id": canonical_hard_a_block_id(record),
        "max_atoms_per_block": MAX_ATOMS_PER_BLOCK,
        "blocks": blocks,
        "source_atom_count": len(atoms),
        "target_atom_count": sum(target_counts),
        "added_atom_count": sum(target_counts) - len(atoms),
        "target_multi_atom_block_count": sum(value >= 2 for value in target_counts),
        "target_three_plus_block_count": sum(value >= 3 for value in target_counts),
        "target_max_atoms_per_block": max(target_counts),
        "difficulty_evidence": {
            "noncanonical_block_count": len(noncanonical_counts),
            "noncanonical_min_atoms": min(noncanonical_counts),
            "noncanonical_max_atoms": max(noncanonical_counts),
            "focus_mode": mode,
        },
    }
    validate_expansion_plan(record, plan)
    return plan


def validate_expansion_plan(record: dict[str, Any], plan: dict[str, Any]) -> None:
    record_id = str(record.get("id") or "")
    level = str(plan.get("difficulty_level") or "")
    if level not in DIFFICULTY_LEVELS:
        raise ValueError(f"record {record_id} has invalid difficulty level")
    blocks = plan.get("blocks")
    if not isinstance(blocks, list) or len(blocks) != len(record.get("memory_blocks") or []):
        raise ValueError(f"record {record_id} plan block coverage mismatch")
    source_ids = [
        str(block.get("parent_memory_id") or "")
        for block in record.get("memory_blocks") or []
    ]
    plan_ids = [str(block.get("parent_memory_id") or "") for block in blocks]
    if source_ids != plan_ids or len(plan_ids) != len(set(plan_ids)):
        raise ValueError(f"record {record_id} plan block order mismatch")
    hard_id = canonical_hard_a_block_id(record)
    targets = {
        str(block["parent_memory_id"]): int(block["target_atom_count"])
        for block in blocks
    }
    if targets.get(hard_id) != 1:
        raise ValueError(f"record {record_id} canonical Hard A is not singleton")
    if any(not 1 <= value <= MAX_ATOMS_PER_BLOCK for value in targets.values()):
        raise ValueError(f"record {record_id} target outside per-block range")
    noncanonical = [value for key, value in targets.items() if key != hard_id]
    if level == "level_1":
        if max(noncanonical) > 4 or sum(value > 2 for value in noncanonical) > 1:
            raise ValueError(f"record {record_id} violates Level 1 definition")
    elif level == "level_2":
        if not 3 <= max(noncanonical) <= 7:
            raise ValueError(f"record {record_id} violates Level 2 definition")
    else:
        complex_focus = max(noncanonical) >= 8 or sum(value >= 5 for value in noncanonical) >= 2
        if not complex_focus or max(noncanonical) > 20:
            raise ValueError(f"record {record_id} violates Level 3 definition")


def critical_tokens(text: str) -> set[str]:
    tokens = set(re.findall(r"\b\d+(?:[.,:/-]\d+)*\b", text))
    tokens.update(re.findall(r"\b[A-Z]{2,}[A-Z0-9_+.#/-]*\b", text))
    tokens.update(
        token
        for token in re.findall(r"\b[A-Za-z0-9_+.#/-]{2,}\b", text)
        if any(character.isdigit() for character in token)
        and any(not character.isdigit() for character in token)
    )
    tokens.update(re.findall(r"`([^`]+)`", text))
    return {
        norm_text(token).casefold()
        for token in tokens
        if norm_text(token)
    }
