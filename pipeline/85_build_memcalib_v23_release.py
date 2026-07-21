#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from memcalib_v23_common import (
    DIFFICULTY_LEVELS,
    V23_AUXILIARY_SOURCE,
    V23_DIR,
    atom_index,
    canonical_hard_a_block_id,
    file_sha256,
    norm_text,
    portable_path,
    scaled_level_quotas,
)
from utils import iter_jsonl, write_json, write_jsonl


DEFAULT_INPUT = V23_DIR / "memcalib_v23_independent_qc_15000.adjudicated.jsonl"
RELEASE_DIR = V23_DIR / "release"
DEFAULT_OUTPUT = RELEASE_DIR / "memcalib_v23_multidomain_benchmark_15000.jsonl"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")
DEFAULT_STATS = DEFAULT_OUTPUT.with_suffix(".statistics.json")
DEFAULT_REVIEW = RELEASE_DIR / "memcalib_v23_multidomain_benchmark_review.html"

LIST_MARKER_RE = re.compile(
    r"(?:^|\n)\s*(?:[-*\u2022]|\d{1,2}[.)])\s+|"
    r"(?:^|(?<=[.!?])\s+)\d{1,2}\.\s+(?=[A-Z])"
)
EXPECTED_DOMAINS = {
    "health_seed": 7500,
    "general": 3750,
    "coding": 3750,
}


def parse_domain_targets(values: list[str]) -> dict[str, int]:
    if not values:
        return dict(EXPECTED_DOMAINS)
    targets: dict[str, int] = {}
    for value in values:
        domain, separator, count_text = value.rpartition("=")
        if not separator or not domain or not count_text.isdigit():
            raise ValueError(f"invalid domain target {value!r}; expected DOMAIN=COUNT")
        count = int(count_text)
        if count <= 0 or domain in targets:
            raise ValueError(f"domain target must be unique and positive: {value!r}")
        targets[domain] = count
    return targets


def numeric_summary(values: list[int]) -> dict[str, float | int]:
    if not values:
        return {"min": 0, "median": 0, "mean": 0.0, "max": 0}
    return {
        "min": min(values),
        "median": statistics.median(values),
        "mean": sum(values) / len(values),
        "max": max(values),
    }


def validate_release(
    rows: list[dict[str, Any]], domain_targets: dict[str, int], allow_review: bool
) -> dict[str, Any]:
    violations: list[str] = []
    record_ids = [str(row.get("id") or "") for row in rows]
    source_ids = [str(row.get("source_id") or "") for row in rows]
    if "" in record_ids or len(record_ids) != len(set(record_ids)):
        violations.append("record_ids_not_unique")
    if "" in source_ids or len(source_ids) != len(set(source_ids)):
        violations.append("source_ids_not_unique")
    observed_domains = Counter(str(row.get("domain") or "") for row in rows)
    if dict(observed_domains) != domain_targets:
        violations.append(
            f"domain_targets_mismatch:{dict(observed_domains)}!={domain_targets}"
        )

    block_distribution: Counter[int] = Counter()
    atom_distribution: Counter[int] = Counter()
    difficulty: Counter[str] = Counter()
    difficulty_by_domain: dict[str, Counter[str]] = defaultdict(Counter)
    decisions: Counter[str] = Counter()
    total_atoms = 0
    total_blocks = 0
    mixed_label_blocks = 0
    for row in rows:
        record_id = str(row.get("id") or "")
        decision = str(row.get("v23_independent_qc", {}).get("decision") or "")
        decisions[decision] += 1
        if decision not in ({"strict_pass", "review"} if allow_review else {"strict_pass"}):
            violations.append(f"{record_id}:inadmissible_qc_decision:{decision}")
        level = str(
            row.get("composite_block_revision", {}).get("difficulty_level") or ""
        )
        if level not in DIFFICULTY_LEVELS:
            violations.append(f"{record_id}:bad_difficulty_level")
        difficulty[level] += 1
        difficulty_by_domain[str(row.get("domain") or "")][level] += 1
        blocks = row.get("memory_blocks")
        memories = row.get("memories")
        if not isinstance(blocks, list) or not isinstance(memories, list):
            violations.append(f"{record_id}:blocks_or_memories_not_list")
            continue
        if not 3 <= len(blocks) <= 20:
            violations.append(f"{record_id}:block_count_out_of_range")
        total_blocks += len(blocks)
        total_atoms += len(memories)
        block_distribution[len(blocks)] += 1
        atoms = atom_index(row)
        mapped: list[str] = []
        noncanonical_counts: list[int] = []
        hard_id = canonical_hard_a_block_id(row)
        for block in blocks:
            parent_id = str(block.get("parent_memory_id") or "")
            atom_ids = [str(atom_id) for atom_id in block.get("atom_ids") or []]
            mapped.extend(atom_ids)
            atom_count = len(atom_ids)
            atom_distribution[atom_count] += 1
            if not 1 <= atom_count <= 20:
                violations.append(f"{record_id}:{parent_id}:atom_count_out_of_range")
            if parent_id == hard_id:
                if atom_count != 1:
                    violations.append(f"{record_id}:canonical_hard_a_not_singleton")
            else:
                noncanonical_counts.append(atom_count)
            if atom_count >= 2:
                text = str(block.get("memory_text") or "")
                if "\n" in text or "\r" in text:
                    violations.append(f"{record_id}:{parent_id}:not_single_paragraph")
                if LIST_MARKER_RE.search(text):
                    violations.append(f"{record_id}:{parent_id}:visible_atom_markers")
                if block.get("surface_form") != "natural_paragraph":
                    violations.append(f"{record_id}:{parent_id}:surface_form_missing")
            labels = {str(atoms[atom_id].get("u_star") or "") for atom_id in atom_ids}
            if len(labels) > 1:
                mixed_label_blocks += 1
        if Counter(mapped) != Counter(atoms.keys()):
            violations.append(f"{record_id}:atom_block_mapping_not_bijective")
        if level == "level_1":
            if max(noncanonical_counts) > 4 or sum(
                value > 2 for value in noncanonical_counts
            ) > 1:
                violations.append(f"{record_id}:level_1_definition_failed")
        elif level == "level_2":
            if not 3 <= max(noncanonical_counts) <= 7:
                violations.append(f"{record_id}:level_2_definition_failed")
        elif level == "level_3":
            if not (
                max(noncanonical_counts) >= 8
                or sum(value >= 5 for value in noncanonical_counts) >= 2
            ):
                violations.append(f"{record_id}:level_3_definition_failed")
        for atom in memories:
            label = str(atom.get("u_star") or "")
            action = str(atom.get("memory_action") or "")
            if label == "A" and action != "ignore":
                violations.append(f"{record_id}:{atom.get('atom_id')}:A_not_ignore")
            if label in {"B", "C"} and action not in {"apply", "correct"}:
                violations.append(f"{record_id}:{atom.get('atom_id')}:BC_bad_action")
            if atom.get("source") == V23_AUXILIARY_SOURCE:
                if label != "A" or action != "ignore":
                    violations.append(
                        f"{record_id}:{atom.get('atom_id')}:v23_auxiliary_not_A_ignore"
                    )
                if atom.get("hard_a_family") is not None:
                    violations.append(
                        f"{record_id}:{atom.get('atom_id')}:v23_auxiliary_has_hard_a_family"
                    )

    for domain, count in domain_targets.items():
        expected = scaled_level_quotas(count)
        observed = {
            level: difficulty_by_domain[domain].get(level, 0)
            for level in DIFFICULTY_LEVELS
        }
        if observed != expected:
            violations.append(
                f"difficulty_quota_mismatch:{domain}:{observed}!={expected}"
            )
    return {
        "records": len(rows),
        "unique_record_ids": len(set(record_ids)),
        "unique_source_ids": len(set(source_ids)),
        "domain_targets_exact": dict(observed_domains) == domain_targets,
        "difficulty_targets_exact": not any(
            violation.startswith("difficulty_quota_mismatch")
            for violation in violations
        ),
        "block_count_range": [
            min(block_distribution) if block_distribution else 0,
            max(block_distribution) if block_distribution else 0,
        ],
        "atoms_per_block_range": [
            min(atom_distribution) if atom_distribution else 0,
            max(atom_distribution) if atom_distribution else 0,
        ],
        "visible_blocks": total_blocks,
        "memory_atoms": total_atoms,
        "mixed_label_blocks": mixed_label_blocks,
        "qc_decisions": dict(sorted(decisions.items())),
        "strict_only": set(decisions) == {"strict_pass"},
        "violations": violations,
    }


def build_statistics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    atoms = [atom for row in rows for atom in row.get("memories") or []]
    blocks = [block for row in rows for block in row.get("memory_blocks") or []]
    atoms_by_id = {
        str(row["id"]): atom_index(row)
        for row in rows
    }
    mixed = 0
    for row in rows:
        index = atoms_by_id[str(row["id"])]
        for block in row.get("memory_blocks") or []:
            labels = {index[str(atom_id)]["u_star"] for atom_id in block["atom_ids"]}
            if len(labels) > 1:
                mixed += 1
    return {
        "schema_version": "memcalib-v23-release-statistics-v1",
        "record_level": {
            "records": len(rows),
            "domain": dict(sorted(Counter(row["domain"] for row in rows).items())),
            "source_dataset": dict(
                sorted(Counter(row["source_dataset"] for row in rows).items())
            ),
            "difficulty": dict(
                sorted(
                    Counter(
                        row["composite_block_revision"]["difficulty_level"]
                        for row in rows
                    ).items()
                )
            ),
            "difficulty_by_domain": {
                domain: dict(
                    sorted(
                        Counter(
                            row["composite_block_revision"]["difficulty_level"]
                            for row in rows
                            if row["domain"] == domain
                        ).items()
                    )
                )
                for domain in sorted({row["domain"] for row in rows})
            },
            "blocks_per_record": numeric_summary(
                [len(row.get("memory_blocks") or []) for row in rows]
            ),
            "atoms_per_record": numeric_summary(
                [len(row.get("memories") or []) for row in rows]
            ),
        },
        "block_level": {
            "blocks": len(blocks),
            "atoms_per_block": dict(
                sorted(Counter(len(block.get("atom_ids") or []) for block in blocks).items())
            ),
            "multi_atom_blocks": sum(len(block.get("atom_ids") or []) >= 2 for block in blocks),
            "three_plus_atom_blocks": sum(len(block.get("atom_ids") or []) >= 3 for block in blocks),
            "mixed_label_blocks": mixed,
            "natural_paragraph_multi_atom_blocks": sum(
                len(block.get("atom_ids") or []) >= 2
                and block.get("surface_form") == "natural_paragraph"
                for block in blocks
            ),
        },
        "atom_level": {
            "atoms": len(atoms),
            "labels": dict(sorted(Counter(atom.get("u_star") for atom in atoms).items())),
            "label_action": dict(
                sorted(
                    Counter(
                        f"{atom.get('u_star')}:{atom.get('memory_action')}"
                        for atom in atoms
                    ).items()
                )
            ),
            "source": dict(sorted(Counter(atom.get("source") for atom in atoms).items())),
        },
    }


def stable_review_sample(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for domain in sorted({row["domain"] for row in rows}):
        for level in DIFFICULTY_LEVELS:
            candidates = sorted(
                (
                    row
                    for row in rows
                    if row["domain"] == domain
                    and row["composite_block_revision"]["difficulty_level"] == level
                ),
                key=lambda row: str(row["id"]),
            )
            selected.extend(candidates[:2])
    return selected


def write_review_html(path: Path, rows: list[dict[str, Any]]) -> None:
    cards: list[str] = []
    for row in stable_review_sample(rows):
        atoms = atom_index(row)
        block_html: list[str] = []
        for block in row.get("memory_blocks") or []:
            atom_rows = "".join(
                "<li><b>"
                + html.escape(str(atoms[str(atom_id)].get("u_star") or ""))
                + "</b> "
                + html.escape(str(atoms[str(atom_id)].get("text") or ""))
                + "</li>"
                for atom_id in block.get("atom_ids") or []
            )
            block_html.append(
                "<section><h3>"
                + html.escape(str(block.get("parent_memory_id") or ""))
                + f" <small>{len(block.get('atom_ids') or [])} atoms</small></h3>"
                + "<p>"
                + html.escape(str(block.get("memory_text") or ""))
                + "</p><details><summary>Hidden atoms</summary><ol>"
                + atom_rows
                + "</ol></details></section>"
            )
        cards.append(
            "<article><header><span>"
            + html.escape(str(row["domain"]))
            + " / "
            + html.escape(str(row["composite_block_revision"]["difficulty_level"]))
            + "</span><h2>"
            + html.escape(str(row["question"]))
            + "</h2><code>"
            + html.escape(str(row["id"]))
            + "</code></header>"
            + "".join(block_html)
            + "</article>"
        )
    document = """<!doctype html><html><head><meta charset='utf-8'><title>MemCalib v2.3 review</title>
<style>body{font-family:Inter,system-ui,sans-serif;margin:0;background:#f4f6f8;color:#17202a}main{max-width:1180px;margin:auto;padding:32px}article{background:white;border:1px solid #dce2e8;margin:0 0 28px;padding:24px;border-radius:8px}header span{font-weight:700;color:#176b5b}h2{font-size:20px}section{border-top:1px solid #e5e9ed;padding:14px 0}h3{font-size:15px}p{line-height:1.55}small,code{color:#68737d}li{margin:6px 0;line-height:1.45}</style></head><body><main><h1>MemCalib v2.3 stratified review</h1>""" + "".join(cards) + "</main></body></html>"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the validated MemCalib v2.3 multidomain release."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--statistics", type=Path, default=DEFAULT_STATS)
    parser.add_argument("--review-html", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--domain-target", action="append", default=[])
    parser.add_argument("--allow-review", action="store_true")
    args = parser.parse_args()

    rows = list(iter_jsonl(args.input))
    targets = parse_domain_targets(args.domain_target)
    validation = validate_release(rows, targets, args.allow_review)
    if validation["violations"]:
        preview = validation["violations"][:20]
        raise ValueError(
            f"release validation failed with {len(validation['violations'])} violations: {preview}"
        )
    write_jsonl(args.output, rows)
    statistics_payload = build_statistics(rows)
    write_json(args.statistics, statistics_payload)
    write_review_html(args.review_html, rows)
    manifest = {
        "schema_version": "memcalib-v23-multidomain-release-v1",
        "input": {
            "path": portable_path(args.input),
            "sha256": file_sha256(args.input),
            "records": len(rows),
        },
        "parameters": {
            "domain_targets": targets,
            "difficulty_weights": {"level_1": 0.25, "level_2": 0.50, "level_3": 0.25},
            "single_record_total_atom_cap": None,
            "max_atoms_per_block": 20,
            "allow_review": args.allow_review,
        },
        "validation": validation,
        "outputs": {
            "benchmark": {
                "path": portable_path(args.output),
                "sha256": file_sha256(args.output),
            },
            "statistics": {
                "path": portable_path(args.statistics),
                "sha256": file_sha256(args.statistics),
            },
            "review_html": {
                "path": portable_path(args.review_html),
                "sha256": file_sha256(args.review_html),
            },
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
