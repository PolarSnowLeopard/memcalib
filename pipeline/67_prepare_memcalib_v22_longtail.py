#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data" / "multidomain" / "full-v2"
V21_DIR = DATA_DIR / "revision-composite-harda"
V22_DIR = DATA_DIR / "revision-longtail-blocks"
DEFAULT_INPUT = V21_DIR / "release" / "memcalib_v21_multidomain_benchmark_15000.jsonl"
DEFAULT_OUTPUT = V22_DIR / "memcalib_v22_longtail_augmentation_input_15000.jsonl"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")
DEFAULT_PROMPT = SCRIPT_DIR / "prompts" / "expand_memcalib_v22_longtail_blocks_en.txt"

REQUEST_SCHEMA = "memcalib-v22-longtail-augmentation-requests-v1"
TARGET_DISTRIBUTION = {
    3: 4200,
    4: 3600,
    5: 2700,
    6: 1800,
    7: 1052,
    8: 600,
    9: 376,
    10: 224,
    11: 148,
    12: 104,
    13: 76,
    14: 44,
    15: 32,
    16: 20,
    17: 12,
    18: 4,
    19: 4,
    20: 4,
}
TARGET_TOTAL = sum(TARGET_DISTRIBUTION.values())
HARD_A_FAMILIES = (
    "factual_judgment_pollution",
    "scope_overreach",
    "current_evidence_conflict",
    "profile_style_near_neighbor",
    "untriggered_preference",
)
AUXILIARY_NOISE_FAMILIES = (
    "cross_domain_episode",
    "non_task_profile_detail",
    "unrelated_physical_artifact_preference",
)
AUXILIARY_NOISE_DEFINITIONS = {
    "cross_domain_episode": (
        "A remembered episode belongs to a clearly different life or project domain. It may be retrieved through "
        "recency or user-identity metadata, but supplies no evidence, method, constraint, or example for the question."
    ),
    "non_task_profile_detail": (
        "A stable profile detail concerns a clearly different offline activity or household context. It cannot alter "
        "the answer's content, presentation, implementation, safety advice, or structure."
    ),
    "unrelated_physical_artifact_preference": (
        "A genuine preference governs a tangible physical object in an unrelated private activity. It is not a "
        "communication, information, recommendation, software, health, or workflow preference."
    ),
}
DOMAIN_ALLOWED_NOISE_POOLS = {
    "health_seed": (
        "Choose only clearly non-health offline topics such as postage-stamp storage, museum ticket keepsakes, "
        "garden furniture placement, wall-art frames, travel postcards, or non-food craft supplies. Do not mention "
        "health, medicine, fitness, diet, bodies, care, appointments, insurance, pharmacies, or clinical administration."
    ),
    "general": (
        "Choose a clearly different offline topic after reading the question, such as postage-stamp storage, wall-art "
        "frames, garden furniture placement, analog photo albums, or non-food craft supplies. If the question touches "
        "one of those topics, choose another. Do not reuse its people, places, products, methods, records, or entities."
    ),
    "coding": (
        "Choose only clearly nontechnical offline topics such as postage-stamp storage, museum ticket keepsakes, "
        "garden furniture placement, wall-art frames, analog photo albums, travel postcards, or non-food craft "
        "supplies. Do not mention software, computers, data, code, documentation, projects, testing, or digital workflows."
    ),
}
SCENE_OBJECTS = (
    "postage stamp album",
    "museum ticket folder",
    "travel postcard box",
    "botanical print frame",
    "ceramic mosaic tray",
    "garden bench slat",
    "analog photo album",
    "fountain pen case",
    "embroidery thread card",
    "fabric swatch binder",
    "model railway scenery piece",
    "coin display tray",
    "pressed flower folio",
    "wooden puzzle box",
    "seashell collection drawer",
    "watercolor brush roll",
)
SCENE_MODIFIERS = (
    "cobalt blue",
    "forest green",
    "burnished copper",
    "matte charcoal",
    "pale lilac",
    "mustard yellow",
    "deep burgundy",
    "weathered teak",
    "cream linen",
    "smoky gray",
    "terracotta",
    "indigo",
    "sage green",
    "walnut stained",
    "ivory",
    "rust red",
)
SCENE_SETTINGS = (
    "west-facing sunroom cabinet",
    "north hallway shelf",
    "cedar chest in the guest room",
    "lower drawer of the entryway console",
    "glass-fronted living-room cupboard",
    "top shelf of the garden shed",
    "oak cabinet beside the staircase",
    "linen closet storage basket",
    "workbench drawer in the garage",
    "bookcase in the reading room",
    "covered patio storage bench",
    "attic keepsake trunk",
    "spare-room display shelf",
    "foyer sideboard drawer",
    "under-stair storage cabinet",
    "studio supply cupboard",
)
SCENE_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
ATOM_ROLES = (
    "state one acquisition, organization, or use event involving the assigned physical object",
    "state one distinct placement, maintenance, or selection fact from the same scene",
)
DOMAIN_GUARDRAILS = {
    "health_seed": (
        "All added memories must be non-clinical. Never add medications, treatments, diagnoses, symptoms, allergies, "
        "contraindications, prognosis, urgency, risk tolerance, care preferences, or facts that a safe answer should "
        "acknowledge. Also forbid language, jargon, reading-level, tone, detail, format, and communication preferences."
    ),
    "general": (
        "Do not add recommendation criteria, accessibility needs, audience constraints, safety preferences, or format "
        "preferences that the current task could legitimately honor. Do not add methods, records, sources, examples, "
        "or named entities that could help answer the current question."
    ),
    "coding": (
        "Do not add library, syntax, dependency, performance, naming, formatting, comment, or implementation preferences "
        "that could produce another valid solution to the current task. Do not add architecture, modularity, tooling, "
        "deployment, testing, compatibility, accessibility, or workflow preferences. To keep deterministic leakage "
        "checks unambiguous, the generated memory text must not contain any of these literal words even in an offline "
        "sense: software, computer, digital, data, code, coding, program, script, API, library, framework, database, "
        "server, client, web, Python, JavaScript, Java, PHP, shell, deployment, testing, version, repository, algorithm, "
        "developer, or technical."
    ),
}


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


def parse_domain_quotas(values: list[str]) -> dict[str, int]:
    quotas: dict[str, int] = {}
    for value in values:
        domain, separator, count_text = value.rpartition("=")
        if not separator or not domain or not count_text.isdigit():
            raise ValueError(f"invalid domain quota {value!r}; expected DOMAIN=COUNT")
        count = int(count_text)
        if count <= 0 or domain in quotas:
            raise ValueError(f"domain quota must be unique and positive: {value!r}")
        quotas[domain] = count
    return quotas


def select_records(
    rows: list[dict[str, Any]], quotas: dict[str, int], seed: int
) -> list[dict[str, Any]]:
    if not quotas:
        return list(rows)
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_domain[str(row.get("domain") or "health_seed")].append(row)
    selected: list[dict[str, Any]] = []
    for domain, quota in sorted(quotas.items()):
        candidates = sorted(
            by_domain.get(domain, []),
            key=lambda row: stable_key(seed, "pilot", row.get("id")),
        )
        if len(candidates) < quota:
            raise ValueError(f"domain {domain!r} has {len(candidates)} records; requested {quota}")
        selected.extend(candidates[:quota])
    return selected


def scaled_distribution(total: int) -> dict[int, int]:
    if total <= 0:
        raise ValueError("distribution total must be positive")
    exact = {
        block_count: total * quota / TARGET_TOTAL
        for block_count, quota in TARGET_DISTRIBUTION.items()
    }
    counts = {block_count: math.floor(value) for block_count, value in exact.items()}
    remaining = total - sum(counts.values())
    order = sorted(
        TARGET_DISTRIBUTION,
        key=lambda block_count: (
            -(exact[block_count] - counts[block_count]),
            stable_key(20260719, "distribution-tie", block_count),
        ),
    )
    for block_count in order[:remaining]:
        counts[block_count] += 1
    return {key: value for key, value in sorted(counts.items()) if value}


def assign_block_counts(
    rows: list[dict[str, Any]], seed: int
) -> tuple[dict[str, int], dict[str, dict[int, int]]]:
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        record_id = str(row.get("id") or "")
        if not record_id:
            raise ValueError("all records must have non-empty IDs")
        by_domain[str(row.get("domain") or "health_seed")].append(row)

    assignments: dict[str, int] = {}
    quotas_by_domain: dict[str, dict[int, int]] = {}
    for domain, domain_rows in sorted(by_domain.items()):
        quotas = scaled_distribution(len(domain_rows))
        quotas_by_domain[domain] = quotas
        target_counts = [
            block_count
            for block_count, quota in sorted(quotas.items())
            for _ in range(quota)
        ]
        ordered = sorted(
            domain_rows,
            key=lambda row: stable_key(seed, f"block-count:{domain}", row.get("id")),
        )
        if len(target_counts) != len(ordered):
            raise AssertionError("scaled distribution did not cover the domain")
        for row, block_count in zip(ordered, target_counts, strict=True):
            assignments[str(row["id"])] = block_count
    return assignments, quotas_by_domain


def real_atoms(record: dict[str, Any]) -> list[dict[str, Any]]:
    atoms = [
        atom
        for atom in record.get("memories") or []
        if isinstance(atom, dict) and atom.get("source") != "synthetic_hard_a"
    ]
    if len(atoms) < 2:
        raise ValueError(f"record {record.get('id')} has fewer than two grounded atoms")
    return atoms


def canonical_hard_a(record: dict[str, Any]) -> dict[str, Any]:
    atoms = [
        atom
        for atom in record.get("memories") or []
        if isinstance(atom, dict) and atom.get("source") == "synthetic_hard_a"
    ]
    if len(atoms) != 1:
        raise ValueError(f"record {record.get('id')} must have exactly one canonical Hard A")
    family = str(atoms[0].get("hard_a_family") or "")
    if family not in HARD_A_FAMILIES:
        raise ValueError(f"record {record.get('id')} has invalid canonical Hard A family")
    return atoms[0]


def contiguous_partitions(items: list[str], groups: int) -> list[list[str]]:
    if groups < 1 or groups > len(items):
        raise ValueError("invalid contiguous partition count")
    base, remainder = divmod(len(items), groups)
    output: list[list[str]] = []
    offset = 0
    for index in range(groups):
        size = base + (1 if index < remainder else 0)
        output.append(items[offset : offset + size])
        offset += size
    return output


def auxiliary_family_cycle(record_id: str, seed: int) -> list[str]:
    return sorted(
        AUXILIARY_NOISE_FAMILIES,
        key=lambda family: stable_key(seed, "aux-family", record_id, family),
    )


def build_plan(record: dict[str, Any], target_blocks: int, seed: int) -> dict[str, Any]:
    if target_blocks < 3 or target_blocks > 20:
        raise ValueError("target block count must be in [3, 20]")
    record_id = str(record.get("id") or "")
    grounded_atoms = real_atoms(record)
    grounded_ids = [str(atom.get("atom_id") or "") for atom in grounded_atoms]
    if "" in grounded_ids or len(grounded_ids) != len(set(grounded_ids)):
        raise ValueError(f"record {record_id} has invalid grounded atom IDs")

    grounded_count = min(len(grounded_ids) - 1, max(1, target_blocks // 2))
    grounded_partitions = contiguous_partitions(grounded_ids, grounded_count)
    grounded_blocks = [
        {
            "parent_memory_id": f"v22_grounded_{index:02d}",
            "atom_ids": atom_ids,
            "atom_count": len(atom_ids),
        }
        for index, atom_ids in enumerate(grounded_partitions, start=1)
    ]
    grounded_multi = sum(len(atom_ids) >= 2 for atom_ids in grounded_partitions)

    target_multi = math.ceil(target_blocks / 2)
    synthetic_count = target_blocks - grounded_count
    noise_block_count = synthetic_count - 1
    noise_multi = target_multi - grounded_multi
    if not 0 <= noise_multi <= noise_block_count:
        raise AssertionError("cannot satisfy target multi-atom count")

    canonical = canonical_hard_a(record)
    canonical_family = str(canonical["hard_a_family"])
    cycle = auxiliary_family_cycle(record_id, seed)
    synthetic_blocks: list[dict[str, Any]] = [
        {
            "parent_memory_id": "v22_harda_01",
            "canonical_hard_a_family": canonical_family,
            "retrieval_noise_family": None,
            "atom_count": 1,
            "contains_canonical_hard_a": True,
            "generated_atom_ids": [],
        }
    ]
    for noise_index in range(1, noise_block_count + 1):
        block_index = noise_index + 1
        atom_count = 2 if noise_index <= noise_multi else 1
        generated_atom_ids = [
            f"v22_noise_{block_index:02d}_a{atom_index}"
            for atom_index in range(1, atom_count + 1)
        ]
        synthetic_blocks.append(
            {
                "parent_memory_id": f"v22_noise_{block_index:02d}",
                "canonical_hard_a_family": None,
                "retrieval_noise_family": cycle[
                    (noise_index - 1) % len(cycle)
                ],
                "atom_count": atom_count,
                "contains_canonical_hard_a": False,
                "generated_atom_ids": generated_atom_ids,
            }
        )

    all_parent_ids = [
        block["parent_memory_id"] for block in grounded_blocks + synthetic_blocks
    ]
    block_order = sorted(
        all_parent_ids,
        key=lambda parent_id: stable_key(seed, "block-order", record_id, parent_id),
    )
    synthetic_atom_count = sum(block["atom_count"] for block in synthetic_blocks)
    plan = {
        "target_block_count": target_blocks,
        "target_multi_atom_block_count": target_multi,
        "grounded_blocks": grounded_blocks,
        "synthetic_blocks": synthetic_blocks,
        "block_order": block_order,
        "locked_real_atom_count": len(grounded_atoms),
        "synthetic_atom_count": synthetic_atom_count,
        "new_synthetic_atom_count": synthetic_atom_count - 1,
        "target_atom_count": len(grounded_atoms) + synthetic_atom_count,
    }
    if len(block_order) != target_blocks:
        raise AssertionError("block plan size mismatch")
    if sum(block["atom_count"] >= 2 for block in grounded_blocks + synthetic_blocks) != target_multi:
        raise AssertionError("multi-atom block plan mismatch")
    return plan


def scene_spec(index: int) -> dict[str, Any]:
    if index < 0:
        raise ValueError("scene index must be non-negative")
    value = index
    object_index = value % len(SCENE_OBJECTS)
    value //= len(SCENE_OBJECTS)
    modifier_index = value % len(SCENE_MODIFIERS)
    value //= len(SCENE_MODIFIERS)
    setting_index = value % len(SCENE_SETTINGS)
    value //= len(SCENE_SETTINGS)
    month_index = value % len(SCENE_MONTHS)
    value //= len(SCENE_MONTHS)
    year = 2008 + value
    return {
        "scene_index": index,
        "object_phrase": f"{SCENE_MODIFIERS[modifier_index]} {SCENE_OBJECTS[object_index]}",
        "setting_phrase": SCENE_SETTINGS[setting_index],
        "time_phrase": f"{SCENE_MONTHS[month_index]} {year}",
    }


def scene_conflicts_with_question(spec: dict[str, Any], question: str) -> bool:
    question_tokens = set(re.findall(r"[a-z]{4,}", question.casefold()))
    object_tokens = set(re.findall(r"[a-z]{4,}", str(spec["object_phrase"]).casefold()))
    return bool(question_tokens & object_tokens)


def assign_scene_specs(
    records_by_id: dict[str, dict[str, Any]],
    plans_by_id: dict[str, dict[str, Any]],
    seed: int,
) -> None:
    blocks = [
        (record_id, block)
        for record_id, plan in plans_by_id.items()
        for block in plan["synthetic_blocks"]
        if block["generated_atom_ids"]
    ]
    blocks.sort(
        key=lambda item: stable_key(
            seed, "scene-order", item[0], item[1]["parent_memory_id"]
        )
    )
    cursor = 0
    used: set[tuple[str, str, str]] = set()
    for record_id, block in blocks:
        question = str(records_by_id[record_id].get("question") or "")
        while True:
            spec = scene_spec(cursor)
            cursor += 1
            key = (
                str(spec["object_phrase"]),
                str(spec["setting_phrase"]),
                str(spec["time_phrase"]),
            )
            if key in used or scene_conflicts_with_question(spec, question):
                continue
            used.add(key)
            break
        block["scene_spec"] = spec
        block["generated_atom_specs"] = [
            {
                "atom_id": atom_id,
                "atom_role": ATOM_ROLES[index % len(ATOM_ROLES)],
                "required_phrases": [
                    spec["object_phrase"],
                    spec["setting_phrase"],
                    spec["time_phrase"],
                ],
            }
            for index, atom_id in enumerate(block["generated_atom_ids"])
        ]


def compact_atom(atom: dict[str, Any]) -> dict[str, Any]:
    return {
        "atom_id": atom.get("atom_id"),
        "text": atom.get("text"),
        "memory_type": atom.get("memory_type"),
        "u_star": atom.get("u_star"),
        "memory_action": atom.get("memory_action"),
        "usage_rubric": atom.get("usage_rubric"),
    }


def render_prompt(
    record: dict[str, Any], plan: dict[str, Any], template: str
) -> str:
    assigned_families = sorted(
        {
            str(block["retrieval_noise_family"])
            for block in plan["synthetic_blocks"]
            if block["generated_atom_ids"]
        }
    )
    replacements = {
        "{record_id}": str(record.get("id") or ""),
        "{domain}": str(record.get("domain") or "health_seed"),
        "{source_topic}": str(record.get("source_topic") or ""),
        "{question}": str(record.get("question") or ""),
        "{locked_real_atoms_json}": json.dumps(
            [compact_atom(atom) for atom in real_atoms(record)],
            ensure_ascii=False,
            indent=2,
        ),
        "{canonical_hard_a_json}": json.dumps(
            compact_atom(canonical_hard_a(record))
            | {
                "hard_a_family": canonical_hard_a(record).get("hard_a_family"),
                "surface_relevance": canonical_hard_a(record).get("surface_relevance"),
                "non_applicability_reason": canonical_hard_a(record).get(
                    "non_applicability_reason"
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        "{synthetic_block_plan_json}": json.dumps(
            plan["synthetic_blocks"], ensure_ascii=False, indent=2
        ),
        "{noise_family_definitions_json}": json.dumps(
            {
                family: AUXILIARY_NOISE_DEFINITIONS[family]
                for family in assigned_families
            },
            ensure_ascii=False,
            indent=2,
        ),
        "{domain_guardrail}": DOMAIN_GUARDRAILS[
            str(record.get("domain") or "health_seed")
        ],
        "{allowed_noise_pool}": DOMAIN_ALLOWED_NOISE_POOLS[
            str(record.get("domain") or "health_seed")
        ],
    }
    content = template
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    return content


def build_request(
    record: dict[str, Any], plan: dict[str, Any], template: str
) -> dict[str, Any]:
    record_id = str(record.get("id") or "")
    generated_ids = [
        atom_id
        for block in plan["synthetic_blocks"]
        for atom_id in block["generated_atom_ids"]
    ]
    specified_ids = [
        spec["atom_id"]
        for block in plan["synthetic_blocks"]
        for spec in block.get("generated_atom_specs") or []
    ]
    if generated_ids != specified_ids:
        raise ValueError(f"record {record_id} does not have complete scene specs")
    params = {
        "schema_version": REQUEST_SCHEMA,
        "record_id": record_id,
        "record_fingerprint": canonical_sha256(record),
        "domain": str(record.get("domain") or "health_seed"),
        "source_dataset": str(record.get("source_dataset") or ""),
        "source_topic": str(record.get("source_topic") or ""),
        "plan": plan,
    }
    return {
        "request_id": f"v22_longtail_augmentation:{record_id}",
        "prompt": [{"role": "user", "content": render_prompt(record, plan, template)}],
        "user_defined_params": params,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare MemCalib v2.2 3-20 block long-tail augmentation requests."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--prompt-template", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--domain-quota", action="append", default=[])
    parser.add_argument("--seed", type=int, default=20260719)
    args = parser.parse_args()

    rows = list(iter_jsonl(args.input))
    record_ids = [str(row.get("id") or "") for row in rows]
    if "" in record_ids or len(record_ids) != len(set(record_ids)):
        raise ValueError("input record IDs must be non-empty and unique")
    selected = select_records(rows, parse_domain_quotas(args.domain_quota), args.seed)
    assignments, quotas_by_domain = assign_block_counts(selected, args.seed)
    template = args.prompt_template.read_text(encoding="utf-8")
    selected_by_id = {str(row["id"]): row for row in selected}
    plans_by_id = {
        record_id: build_plan(record, assignments[record_id], args.seed)
        for record_id, record in selected_by_id.items()
    }
    assign_scene_specs(selected_by_id, plans_by_id, args.seed)
    requests = [
        build_request(row, plans_by_id[str(row["id"])], template)
        for row in sorted(
            selected,
            key=lambda row: stable_key(args.seed, "request-order", row.get("id")),
        )
    ]
    write_jsonl(args.output, requests)

    plans = [row["user_defined_params"]["plan"] for row in requests]
    block_distribution = Counter(plan["target_block_count"] for plan in plans)
    multi_distribution = Counter(
        plan["target_multi_atom_block_count"] for plan in plans
    )
    manifest = {
        "schema_version": REQUEST_SCHEMA,
        "inputs": {
            "benchmark": {
                "path": portable_path(args.input),
                "sha256": file_sha256(args.input),
                "records": len(rows),
            }
        },
        "implementation": {
            "prepare": {
                "path": portable_path(Path(__file__)),
                "sha256": file_sha256(Path(__file__).resolve()),
            },
            "prompt": {
                "path": portable_path(args.prompt_template),
                "sha256": file_sha256(args.prompt_template),
            },
        },
        "parameters": {
            "seed": args.seed,
            "domain_quotas": parse_domain_quotas(args.domain_quota),
            "target_distribution_full": TARGET_DISTRIBUTION,
            "canonical_hard_a_families": list(HARD_A_FAMILIES),
            "auxiliary_retrieval_noise_families": list(
                AUXILIARY_NOISE_FAMILIES
            ),
        },
        "distribution": {
            "domain": dict(
                sorted(
                    Counter(
                        str(row.get("domain") or "health_seed") for row in selected
                    ).items()
                )
            ),
            "target_blocks": dict(sorted(block_distribution.items())),
            "target_multi_atom_blocks": dict(sorted(multi_distribution.items())),
            "target_blocks_by_domain": {
                domain: dict(sorted(quotas.items()))
                for domain, quotas in sorted(quotas_by_domain.items())
            },
        },
        "planned_totals": {
            "records": len(plans),
            "visible_blocks": sum(plan["target_block_count"] for plan in plans),
            "multi_atom_visible_blocks": sum(
                plan["target_multi_atom_block_count"] for plan in plans
            ),
            "multi_atom_visible_block_share": (
                sum(plan["target_multi_atom_block_count"] for plan in plans)
                / sum(plan["target_block_count"] for plan in plans)
            ),
            "memory_atoms": sum(plan["target_atom_count"] for plan in plans),
            "new_synthetic_atoms": sum(
                plan["new_synthetic_atom_count"] for plan in plans
            ),
            "unique_auxiliary_scenes": len(
                {
                    (
                        block["scene_spec"]["object_phrase"],
                        block["scene_spec"]["setting_phrase"],
                        block["scene_spec"]["time_phrase"],
                    )
                    for plan in plans
                    for block in plan["synthetic_blocks"]
                    if block["generated_atom_ids"]
                }
            ),
        },
        "output": {
            "path": portable_path(args.output),
            "sha256": file_sha256(args.output),
            "requests": len(requests),
            "unique_request_ids": len(
                {str(request["request_id"]) for request in requests}
            ),
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
