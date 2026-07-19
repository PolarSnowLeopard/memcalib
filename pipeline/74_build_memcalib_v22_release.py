#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
V22_DIR = SCRIPT_DIR / "data" / "multidomain" / "full-v2" / "revision-longtail-blocks"
RELEASE_DIR = V22_DIR / "release"
DEFAULT_INPUT = V22_DIR / "memcalib_v22_longtail_independent_qc_15000.adjudicated.jsonl"
DEFAULT_OUTPUT = RELEASE_DIR / "memcalib_v22_multidomain_benchmark_15000.jsonl"
DEFAULT_MANIFEST = RELEASE_DIR / "memcalib_v22_multidomain_benchmark_15000.manifest.json"
DEFAULT_STATS = RELEASE_DIR / "memcalib_v22_multidomain_benchmark_15000.statistics.json"
DEFAULT_REVIEW = RELEASE_DIR / "memcalib_v22_multidomain_benchmark_review.html"
SCHEMA_VERSION = "memcalib-v22-multidomain-release-v1"
DOMAIN_TARGETS = {"health_seed": 7500, "general": 3750, "coding": 3750}
BLOCK_DISTRIBUTION = {
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
LABEL_ACTIONS = {
    "A": {"ignore"},
    "B": {"apply", "correct"},
    "C": {"apply", "correct"},
}
STACK_EXCHANGE_DATASET = "HuggingFaceH4/stack-exchange-preferences"
STACK_EXCHANGE_REQUIRED_FIELDS = (
    "question_author_name",
    "question_author_profile",
    "answer_author",
    "answer_author_profile",
    "question_url",
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


def numeric_summary(values: list[int]) -> dict[str, float | int]:
    return {
        "min": min(values),
        "max": max(values),
        "mean": round(statistics.fmean(values), 4),
        "median": statistics.median(values),
    }


def hard_a_atom(record: dict[str, Any]) -> dict[str, Any] | None:
    atoms = [
        atom
        for atom in record.get("memories") or []
        if isinstance(atom, dict) and atom.get("source") == "synthetic_hard_a"
    ]
    return atoms[0] if len(atoms) == 1 else None


def validate_and_admit(
    rows: list[dict[str, Any]], *, allow_review: bool
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    violations: list[str] = []
    ids: set[str] = set()
    source_ids: set[str] = set()
    domains: Counter[str] = Counter()
    block_distribution: Counter[int] = Counter()
    hard_a_families: Counter[str] = Counter()
    hard_a_by_domain: dict[str, Counter[str]] = defaultdict(Counter)
    labels: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    visible_blocks = 0
    multi_atom_blocks = 0
    stack_exchange_records = 0
    admitted: list[dict[str, Any]] = []
    allowed_decisions = {"strict_pass", "review"} if allow_review else {"strict_pass"}

    for index, row in enumerate(rows):
        record_id = str(row.get("id") or "")
        source_id = str(row.get("source_id") or "")
        domain = str(row.get("domain") or "")
        if not record_id or record_id in ids:
            violations.append(f"row_{index}_bad_or_duplicate_id")
        if not source_id or source_id in source_ids:
            violations.append(f"row_{index}_bad_or_duplicate_source_id")
        ids.add(record_id)
        source_ids.add(source_id)
        domains[domain] += 1
        if row.get("schema_version") != "crk-2-canonical-memory-v2.2":
            violations.append(f"{record_id}_bad_record_schema")

        qc = row.get("longtail_independent_qc") or {}
        decision = str(qc.get("computed_decision") or "")
        if decision not in allowed_decisions:
            violations.append(f"{record_id}_forbidden_qc_decision_{decision}")

        blocks = row.get("memory_blocks")
        memories = row.get("memories")
        if not isinstance(blocks, list) or not 3 <= len(blocks) <= 20:
            violations.append(f"{record_id}_visible_block_count_out_of_range")
            blocks = []
        if not isinstance(memories, list) or not memories:
            violations.append(f"{record_id}_memories_missing")
            memories = []
        block_distribution[len(blocks)] += 1
        visible_blocks += len(blocks)
        record_multi_blocks = sum(
            len(block.get("atom_ids") or []) >= 2 for block in blocks
        )
        multi_atom_blocks += record_multi_blocks
        if blocks and record_multi_blocks != (len(blocks) + 1) // 2:
            violations.append(f"{record_id}_multi_atom_block_target_not_exact")

        mapped_atom_ids = [
            str(atom_id)
            for block in blocks
            for atom_id in block.get("atom_ids") or []
        ]
        memory_atom_ids = [str(atom.get("atom_id") or "") for atom in memories]
        if (
            "" in memory_atom_ids
            or len(memory_atom_ids) != len(set(memory_atom_ids))
            or len(mapped_atom_ids) != len(set(mapped_atom_ids))
            or Counter(mapped_atom_ids) != Counter(memory_atom_ids)
        ):
            violations.append(f"{record_id}_atom_block_mapping_not_bijective")

        hard = hard_a_atom(row)
        if hard is None:
            violations.append(f"{record_id}_hard_a_atom_count_not_one")
        else:
            family = str(hard.get("hard_a_family") or "")
            if family not in HARD_A_FAMILIES:
                violations.append(f"{record_id}_bad_hard_a_family")
            hard_a_families[family] += 1
            hard_a_by_domain[domain][family] += 1
            if hard.get("u_star") != "A" or hard.get("memory_action") != "ignore":
                violations.append(f"{record_id}_bad_hard_a_label_action")
            hard_blocks = [
                block
                for block in blocks
                if block.get("source") == "synthetic_hard_a"
            ]
            if (
                len(hard_blocks) != 1
                or hard_blocks[0].get("atom_ids") != [hard.get("atom_id")]
            ):
                violations.append(f"{record_id}_hard_a_block_not_singleton")

        for atom_index, atom in enumerate(memories):
            label = str(atom.get("u_star") or "")
            action = str(atom.get("memory_action") or "")
            source = str(atom.get("source") or "")
            labels[label] += 1
            sources[source] += 1
            if label not in LABEL_ACTIONS or action not in LABEL_ACTIONS[label]:
                violations.append(f"{record_id}_atom_{atom_index}_label_action_mismatch")
            if source == "synthetic_retrieval_noise":
                if label != "A" or action != "ignore":
                    violations.append(f"{record_id}_atom_{atom_index}_bad_noise_label_action")
                if str(atom.get("retrieval_noise_family") or "") not in AUXILIARY_NOISE_FAMILIES:
                    violations.append(f"{record_id}_atom_{atom_index}_bad_noise_family")

        if str(row.get("source_dataset") or "") == STACK_EXCHANGE_DATASET:
            stack_exchange_records += 1
            metadata = row.get("source_metadata")
            if not isinstance(metadata, dict):
                violations.append(f"{record_id}_missing_stack_exchange_metadata")
            else:
                for field in STACK_EXCHANGE_REQUIRED_FIELDS:
                    if not str(metadata.get(field) or "").strip():
                        violations.append(f"{record_id}_missing_{field}")
                if metadata.get("attribution_complete") is not True:
                    violations.append(f"{record_id}_attribution_not_complete")

        released = copy.deepcopy(row)
        released["revision_release_admission"] = {
            "schema_version": SCHEMA_VERSION,
            "decision": (
                "admitted_strict" if decision == "strict_pass" else "admitted_review"
            ),
            "record_fingerprint_before_admission": canonical_sha256(row),
        }
        admitted.append(released)

    if len(rows) != 15000:
        violations.append(f"record_count_{len(rows)}_expected_15000")
    if dict(domains) != DOMAIN_TARGETS:
        violations.append(f"domain_distribution_{dict(sorted(domains.items()))}")
    if dict(block_distribution) != BLOCK_DISTRIBUTION:
        violations.append(
            f"block_distribution_{dict(sorted(block_distribution.items()))}"
        )
    expected_family_counts = {family: 3000 for family in HARD_A_FAMILIES}
    if dict(hard_a_families) != expected_family_counts:
        violations.append("hard_a_family_distribution_not_exact")
    expected_by_domain = {
        domain: {family: count // 5 for family in HARD_A_FAMILIES}
        for domain, count in DOMAIN_TARGETS.items()
    }
    if {domain: dict(counts) for domain, counts in hard_a_by_domain.items()} != expected_by_domain:
        violations.append("hard_a_family_by_domain_not_exact")
    if visible_blocks != 74800 or multi_atom_blocks != 41700:
        violations.append(
            f"block_totals_{visible_blocks}_multi_{multi_atom_blocks}"
        )
    if sum(labels.values()) != 118819:
        violations.append(f"memory_atom_total_{sum(labels.values())}_expected_118819")
    if violations:
        raise ValueError(
            f"release validation failed with {len(violations)} violation(s): "
            + ", ".join(violations[:15])
        )

    validation = {
        "records": len(rows),
        "unique_record_ids": len(ids),
        "unique_source_ids": len(source_ids),
        "domain_targets_exact": True,
        "block_count_range": [3, 20],
        "block_distribution_exact": True,
        "visible_blocks": visible_blocks,
        "multi_atom_visible_blocks": multi_atom_blocks,
        "multi_atom_visible_block_share": multi_atom_blocks / visible_blocks,
        "records_with_multi_atom_visible_block": len(rows),
        "memory_atoms": sum(labels.values()),
        "hard_a_families_exact_and_balanced": True,
        "atom_block_mapping_bijective": True,
        "label_action_combinations_valid": True,
        "strict_only": not allow_review,
        "stack_exchange_records": stack_exchange_records,
        "stack_exchange_attribution_complete": stack_exchange_records,
        "violations": [],
    }
    return admitted, validation


def build_statistics(
    rows: list[dict[str, Any]], validation: dict[str, Any]
) -> dict[str, Any]:
    atoms = [atom for row in rows for atom in row.get("memories") or []]
    blocks = [block for row in rows for block in row.get("memory_blocks") or []]
    labels_by_domain: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        labels_by_domain[str(row.get("domain") or "")].update(
            str(atom.get("u_star") or "") for atom in row.get("memories") or []
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "validation": validation,
        "records": {
            "domain": dict(
                sorted(Counter(str(row.get("domain") or "") for row in rows).items())
            ),
            "source_dataset": dict(
                sorted(
                    Counter(str(row.get("source_dataset") or "") for row in rows).items()
                )
            ),
            "source_topic": dict(
                sorted(
                    Counter(str(row.get("source_topic") or "") for row in rows).items()
                )
            ),
            "qc_decision": dict(
                sorted(
                    Counter(
                        str(
                            (row.get("longtail_independent_qc") or {}).get(
                                "computed_decision"
                            )
                            or ""
                        )
                        for row in rows
                    ).items()
                )
            ),
        },
        "block_level": {
            "visible_blocks": len(blocks),
            "blocks_per_record": {
                str(key): value for key, value in sorted(BLOCK_DISTRIBUTION.items())
            },
            "atoms_per_visible_block": dict(
                sorted(Counter(len(block.get("atom_ids") or []) for block in blocks).items())
            ),
            "multi_atom_visible_blocks": validation["multi_atom_visible_blocks"],
            "multi_atom_visible_block_share": validation[
                "multi_atom_visible_block_share"
            ],
        },
        "atom_level": {
            "memory_atoms": len(atoms),
            "atoms_per_record": numeric_summary(
                [len(row.get("memories") or []) for row in rows]
            ),
            "label": dict(
                sorted(Counter(str(atom.get("u_star") or "") for atom in atoms).items())
            ),
            "label_action": dict(
                sorted(
                    Counter(
                        f"{atom.get('u_star', '')}:{atom.get('memory_action', '')}"
                        for atom in atoms
                    ).items()
                )
            ),
            "source": dict(
                sorted(Counter(str(atom.get("source") or "") for atom in atoms).items())
            ),
            "label_by_domain": {
                domain: dict(sorted(counts.items()))
                for domain, counts in sorted(labels_by_domain.items())
            },
            "hard_a_family": dict(
                sorted(
                    Counter(
                        str(atom.get("hard_a_family") or "")
                        for atom in atoms
                        if atom.get("source") == "synthetic_hard_a"
                    ).items()
                )
            ),
            "auxiliary_retrieval_noise_family": dict(
                sorted(
                    Counter(
                        str(atom.get("retrieval_noise_family") or "")
                        for atom in atoms
                        if atom.get("source") == "synthetic_retrieval_noise"
                    ).items()
                )
            ),
        },
    }


def stable_review_sample(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bands = ((3, 4), (5, 6), (7, 10), (11, 20))
    selected: list[dict[str, Any]] = []
    for domain in DOMAIN_TARGETS:
        for lower, upper in bands:
            candidates = [
                row
                for row in rows
                if row.get("domain") == domain
                and lower <= len(row.get("memory_blocks") or []) <= upper
            ]
            ordered = sorted(
                candidates,
                key=lambda row: hashlib.sha256(str(row.get("id")).encode()).hexdigest(),
            )
            selected.extend(ordered[:2])
    return selected


def write_review_html(
    path: Path, rows: list[dict[str, Any]], statistics_data: dict[str, Any]
) -> None:
    cards: list[str] = []
    for row in stable_review_sample(rows):
        atom_by_id = {
            str(atom.get("atom_id") or ""): atom for atom in row.get("memories") or []
        }
        block_items: list[str] = []
        for block in row.get("memory_blocks") or []:
            atoms = [atom_by_id.get(str(atom_id)) or {} for atom_id in block.get("atom_ids") or []]
            atom_items = "".join(
                "<li>"
                f"<span class='label'>{html.escape(str(atom.get('u_star') or ''))}</span>"
                f"{html.escape(str(atom.get('text') or ''))}"
                "</li>"
                for atom in atoms
            )
            block_items.append(
                "<section class='block'>"
                f"<h3>{html.escape(str(block.get('parent_memory_id') or 'memory block'))}"
                f" <small>{len(atoms)} atom(s)</small></h3><ol>{atom_items}</ol></section>"
            )
        cards.append(
            "<article>"
            f"<div class='meta'>{html.escape(str(row.get('domain')))} · "
            f"{len(row.get('memory_blocks') or [])} blocks · "
            f"{len(row.get('memories') or [])} atoms · {html.escape(str(row.get('id')))}</div>"
            f"<h2>{html.escape(str(row.get('question') or ''))}</h2>"
            + "".join(block_items)
            + "</article>"
        )
    validation = html.escape(
        json.dumps(statistics_data["validation"], ensure_ascii=False, indent=2)
    )
    content = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MemCalib v2.2 release review</title>
<style>
body{{margin:0;background:#f3f5f7;color:#17212b;font:15px/1.55 system-ui,sans-serif}}
header{{background:#17212b;color:#fff;padding:30px max(24px,calc((100vw - 1180px)/2))}}
main{{max-width:1180px;margin:auto;padding:24px}} article{{background:#fff;border:1px solid #d8dee5;border-radius:6px;padding:22px;margin:18px 0}}
h1{{margin:0 0 8px}} h2{{font-size:19px}} h3{{font-size:15px;margin:0 0 8px}} small{{color:#66727d;font-weight:400}}
.meta{{color:#5d6a76;font-size:13px}} .block{{border-top:1px solid #e4e8ec;padding-top:14px;margin-top:14px}}
.label{{display:inline-block;min-width:22px;text-align:center;background:#e6edf3;border-radius:3px;font-weight:700;margin-right:8px}}
pre{{white-space:pre-wrap;background:#fff;border:1px solid #d8dee5;padding:16px}} li{{margin:6px 0}}
</style></head><body><header><h1>MemCalib v2.2 release review</h1>
<div>Long-tail 3–20 block interface · stratified by domain and block-count band</div></header>
<main><h2>Release validation</h2><pre>{validation}</pre>{''.join(cards)}</main></body></html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate and build the MemCalib v2.2 long-tail release."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--statistics", type=Path, default=DEFAULT_STATS)
    parser.add_argument("--review-html", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--allow-review", action="store_true")
    args = parser.parse_args()

    rows = list(iter_jsonl(args.input))
    admitted, validation = validate_and_admit(rows, allow_review=args.allow_review)
    write_jsonl(args.output, admitted)
    statistics_data = build_statistics(admitted, validation)
    write_json(args.statistics, statistics_data)
    write_review_html(args.review_html, admitted, statistics_data)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "input": {
            "path": portable_path(args.input),
            "sha256": file_sha256(args.input),
            "records": len(rows),
        },
        "validation": validation,
        "outputs": {
            "benchmark": {
                "path": portable_path(args.output),
                "sha256": file_sha256(args.output),
                "records": len(admitted),
            },
            "statistics": {
                "path": portable_path(args.statistics),
                "sha256": file_sha256(args.statistics),
            },
            "review_html": {
                "path": portable_path(args.review_html),
                "sha256": file_sha256(args.review_html),
                "sample_records": len(stable_review_sample(admitted)),
            },
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
