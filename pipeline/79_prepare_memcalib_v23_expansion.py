#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from memcalib_v23_common import (
    DIFFICULTY_LEVELS,
    V22_RELEASE,
    V23_DIR,
    assign_difficulty_levels,
    atom_index,
    build_expansion_plan,
    canonical_sha256,
    file_sha256,
    portable_path,
    stable_key,
)
from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = V22_RELEASE
DEFAULT_OUTPUT = V23_DIR / "memcalib_v23_expansion_input_15000.jsonl"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")
DEFAULT_PROMPT = SCRIPT_DIR / "prompts" / "expand_memcalib_v23_composite_atoms_en.txt"
REQUEST_SCHEMA = "memcalib-v23-expansion-requests-v1"


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
            key=lambda row: stable_key(seed, "pilot-record", row.get("id")),
        )
        if len(candidates) < quota:
            raise ValueError(f"domain {domain} has {len(candidates)} records; requested {quota}")
        selected.extend(candidates[:quota])
    return selected


def compact_locked_blocks(record: dict[str, Any]) -> list[dict[str, Any]]:
    atoms = atom_index(record)
    return [
        {
            "parent_memory_id": block.get("parent_memory_id"),
            "memory_text": block.get("memory_text"),
            "atoms": [
                {
                    "atom_id": atom_id,
                    "text": atoms[str(atom_id)].get("text"),
                }
                for atom_id in block.get("atom_ids") or []
            ],
        }
        for block in record.get("memory_blocks") or []
    ]


def prompt_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "difficulty_level": plan["difficulty_level"],
        "difficulty_mode": plan["difficulty_mode"],
        "blocks": [
            {
                "parent_memory_id": block["parent_memory_id"],
                "current_atom_count": block["current_atom_count"],
                "target_atom_count": block["target_atom_count"],
                "generated_atom_specs": block["generated_atom_specs"],
            }
            for block in plan["blocks"]
            if block["generated_atom_specs"]
        ],
    }


def render_prompt(
    record: dict[str, Any], plan: dict[str, Any], template: str
) -> str:
    replacements = {
        "{record_id}": str(record.get("id") or ""),
        "{domain}": str(record.get("domain") or "health_seed"),
        "{question}": str(record.get("question") or ""),
        "{locked_blocks_json}": json.dumps(
            compact_locked_blocks(record), ensure_ascii=False, indent=2
        ),
        "{expansion_plan_json}": json.dumps(
            prompt_plan(plan), ensure_ascii=False, indent=2
        ),
    }
    content = template
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    return content


def build_request(
    record: dict[str, Any], plan: dict[str, Any], template: str
) -> dict[str, Any]:
    record_id = str(record.get("id") or "")
    params = {
        "schema_version": REQUEST_SCHEMA,
        "record_id": record_id,
        "record_fingerprint": canonical_sha256(record),
        "domain": str(record.get("domain") or "health_seed"),
        "source_dataset": str(record.get("source_dataset") or ""),
        "plan": plan,
    }
    return {
        "request_id": f"v23_expansion:{record_id}",
        "prompt": [{"role": "user", "content": render_prompt(record, plan, template)}],
        "user_defined_params": params,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare three-level MemCalib v2.3 composite-atom expansion requests."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--prompt-template", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--domain-quota", action="append", default=[])
    parser.add_argument("--seed", type=int, default=20260721)
    args = parser.parse_args()

    rows = list(iter_jsonl(args.input))
    record_ids = [str(row.get("id") or "") for row in rows]
    if "" in record_ids or len(record_ids) != len(set(record_ids)):
        raise ValueError("input record IDs must be non-empty and unique")
    quotas = parse_domain_quotas(args.domain_quota)
    selected = select_records(rows, quotas, args.seed)
    assignments, level_quotas = assign_difficulty_levels(selected, args.seed)
    plans = {
        str(record["id"]): build_expansion_plan(
            record, assignments[str(record["id"])], args.seed
        )
        for record in selected
    }
    template = args.prompt_template.read_text(encoding="utf-8")
    requests = [
        build_request(record, plans[str(record["id"])], template)
        for record in sorted(
            selected,
            key=lambda row: stable_key(args.seed, "request-order", row.get("id")),
        )
    ]
    write_jsonl(args.output, requests)

    plan_rows = [request["user_defined_params"]["plan"] for request in requests]
    block_targets = Counter(
        int(block["target_atom_count"])
        for plan in plan_rows
        for block in plan["blocks"]
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
            "domain_quotas": quotas,
            "difficulty_levels": list(DIFFICULTY_LEVELS),
            "difficulty_weights": {"level_1": 0.25, "level_2": 0.50, "level_3": 0.25},
            "single_record_total_atom_cap": None,
            "max_atoms_per_block": 20,
        },
        "distribution": {
            "domain": dict(
                sorted(
                    Counter(
                        str(record.get("domain") or "health_seed")
                        for record in selected
                    ).items()
                )
            ),
            "difficulty": dict(
                sorted(Counter(assignments.values()).items())
            ),
            "difficulty_by_domain": level_quotas,
            "target_atoms_per_block": dict(sorted(block_targets.items())),
            "difficulty_modes": dict(
                sorted(Counter(plan["difficulty_mode"] for plan in plan_rows).items())
            ),
        },
        "planned_totals": {
            "records": len(plan_rows),
            "visible_blocks": sum(len(plan["blocks"]) for plan in plan_rows),
            "source_atoms": sum(plan["source_atom_count"] for plan in plan_rows),
            "target_atoms": sum(plan["target_atom_count"] for plan in plan_rows),
            "added_atoms": sum(plan["added_atom_count"] for plan in plan_rows),
            "multi_atom_blocks": sum(
                plan["target_multi_atom_block_count"] for plan in plan_rows
            ),
            "three_plus_atom_blocks": sum(
                plan["target_three_plus_block_count"] for plan in plan_rows
            ),
        },
        "output": {
            "path": portable_path(args.output),
            "sha256": file_sha256(args.output),
            "requests": len(requests),
            "unique_request_ids": len({request["request_id"] for request in requests}),
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
