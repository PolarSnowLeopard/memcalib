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
REVISION_DIR = SCRIPT_DIR / "data" / "multidomain" / "full-v2" / "revision-composite-harda"
RELEASE_DIR = REVISION_DIR / "release"
DEFAULT_INPUT = REVISION_DIR / "memcalib_v21_composite_harda_independent_qc_15000.adjudicated.jsonl"
DEFAULT_OUTPUT = RELEASE_DIR / "memcalib_v21_multidomain_benchmark_15000.jsonl"
DEFAULT_MANIFEST = RELEASE_DIR / "memcalib_v21_multidomain_benchmark_15000.manifest.json"
DEFAULT_STATS = RELEASE_DIR / "memcalib_v21_multidomain_benchmark_15000.statistics.json"
DEFAULT_REVIEW = RELEASE_DIR / "memcalib_v21_multidomain_benchmark_review.html"
SCHEMA_VERSION = "memcalib-v21-multidomain-release-v1"
DOMAIN_TARGETS = {"health_seed": 7500, "general": 3750, "coding": 3750}
HARD_A_FAMILIES = {
    "factual_judgment_pollution",
    "scope_overreach",
    "current_evidence_conflict",
    "profile_style_near_neighbor",
    "untriggered_preference",
}
STACK_EXCHANGE_DATASET = "HuggingFaceH4/stack-exchange-preferences"
STACK_EXCHANGE_REQUIRED_FIELDS = (
    "question_author_name",
    "question_author_profile",
    "answer_author",
    "answer_author_profile",
    "question_url",
)
LABEL_ACTIONS = {
    "A": {"ignore"},
    "B": {"apply", "correct"},
    "C": {"apply", "correct"},
}


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(SCRIPT_DIR.parent))
    except ValueError:
        return str(resolved)


def hard_a_atom(record: dict[str, Any]) -> dict[str, Any] | None:
    atoms = [
        atom
        for atom in record.get("memories") or []
        if isinstance(atom, dict) and atom.get("source") == "synthetic_hard_a"
    ]
    return atoms[0] if len(atoms) == 1 else None


def validate_and_admit(
    rows: list[dict[str, Any]],
    *,
    allow_review: bool,
    expected_records: int = 15000,
    domain_targets: dict[str, int] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    targets = domain_targets or DOMAIN_TARGETS
    if any(count % len(HARD_A_FAMILIES) for count in targets.values()):
        raise ValueError("every domain target must be divisible by the number of Hard-A families")
    violations: list[str] = []
    ids: set[str] = set()
    source_ids: set[str] = set()
    domains: Counter[str] = Counter()
    families: Counter[str] = Counter()
    family_by_domain: dict[str, Counter[str]] = defaultdict(Counter)
    blocks_total = 0
    multi_blocks = 0
    stack_exchange_records = 0
    admitted: list[dict[str, Any]] = []

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

        decision = str((row.get("revision_independent_qc") or {}).get("computed_decision") or "")
        allowed = {"strict_pass", "review"} if allow_review else {"strict_pass"}
        if decision not in allowed:
            violations.append(f"{record_id}_forbidden_qc_decision_{decision}")
        if str((row.get("deterministic_qc") or {}).get("decision") or "") != "pass":
            violations.append(f"{record_id}_deterministic_not_pass")

        blocks = row.get("memory_blocks")
        memories = row.get("memories")
        if not isinstance(blocks, list) or len(blocks) != 2:
            violations.append(f"{record_id}_visible_block_count_not_two")
            blocks = []
        if not isinstance(memories, list) or len(memories) < 3:
            violations.append(f"{record_id}_memory_atom_count_too_low")
            memories = []
        blocks_total += len(blocks)
        multi_blocks += sum(len(block.get("atom_ids") or []) >= 2 for block in blocks)
        if blocks:
            if blocks[0].get("source") != "composite_grounded" or len(blocks[0].get("atom_ids") or []) < 2:
                violations.append(f"{record_id}_bad_composite_block")
            if blocks[1].get("source") != "synthetic_hard_a" or len(blocks[1].get("atom_ids") or []) != 1:
                violations.append(f"{record_id}_bad_hard_a_block")

        hard = hard_a_atom(row)
        if hard is None:
            violations.append(f"{record_id}_hard_a_atom_count_not_one")
        else:
            family = str(hard.get("hard_a_family") or "")
            if family not in HARD_A_FAMILIES:
                violations.append(f"{record_id}_bad_hard_a_family")
            families[family] += 1
            family_by_domain[domain][family] += 1
            if hard.get("u_star") != "A" or hard.get("memory_action") != "ignore":
                violations.append(f"{record_id}_bad_hard_a_label_action")
            if (hard.get("counterfactual_contract") or {}).get("observable_delta") != "none":
                violations.append(f"{record_id}_hard_a_observable_delta_not_none")

        for atom_index, atom in enumerate(memories):
            label = str(atom.get("u_star") or "")
            action = str(atom.get("memory_action") or "")
            if label not in LABEL_ACTIONS or action not in LABEL_ACTIONS.get(label, set()):
                violations.append(f"{record_id}_atom_{atom_index}_label_action_mismatch")

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
            "decision": "admitted_strict" if decision == "strict_pass" else "admitted_review",
            "record_fingerprint_before_admission": canonical_sha256(row),
        }
        admitted.append(released)

    if len(rows) != expected_records:
        violations.append(f"record_count_{len(rows)}_expected_{expected_records}")
    if dict(domains) != targets:
        violations.append(f"domain_distribution_{dict(sorted(domains.items()))}")
    per_family_total = sum(targets.values()) // len(HARD_A_FAMILIES)
    expected_families = {family: per_family_total for family in HARD_A_FAMILIES}
    if dict(families) != expected_families:
        violations.append(f"hard_a_family_distribution_{dict(sorted(families.items()))}")
    expected_by_domain = {
        domain: {family: count // len(HARD_A_FAMILIES) for family in HARD_A_FAMILIES}
        for domain, count in targets.items()
    }
    observed_by_domain = {
        domain: dict(counts) for domain, counts in family_by_domain.items()
    }
    if observed_by_domain != expected_by_domain:
        violations.append("hard_a_family_by_domain_not_exact")
    if blocks_total != expected_records * 2 or multi_blocks != expected_records:
        violations.append(f"multi_atom_block_counts_{multi_blocks}_of_{blocks_total}")
    if violations:
        raise ValueError(
            f"release validation failed with {len(violations)} violation(s): {', '.join(violations[:12])}"
        )
    validation = {
        "records": len(rows),
        "unique_record_ids": len(ids),
        "unique_source_ids": len(source_ids),
        "domain_targets_exact": True,
        "hard_a_families_exact_and_balanced": True,
        "two_visible_blocks_per_record": True,
        "multi_atom_visible_blocks": multi_blocks,
        "visible_blocks": blocks_total,
        "multi_atom_visible_block_share": multi_blocks / blocks_total,
        "records_with_multi_atom_visible_block": len(rows),
        "strict_only": not allow_review,
        "stack_exchange_records": stack_exchange_records,
        "stack_exchange_attribution_complete": stack_exchange_records,
        "violations": [],
    }
    return admitted, validation


def numeric_summary(values: list[int]) -> dict[str, float | int]:
    return {
        "min": min(values),
        "max": max(values),
        "mean": round(statistics.fmean(values), 4),
        "median": statistics.median(values),
    }


def build_statistics(rows: list[dict[str, Any]], validation: dict[str, Any]) -> dict[str, Any]:
    atoms = [atom for row in rows for atom in row.get("memories") or []]
    real_atoms = [atom for atom in atoms if atom.get("source") != "synthetic_hard_a"]
    hard_atoms = [atom for atom in atoms if atom.get("source") == "synthetic_hard_a"]
    by_domain_label: dict[str, Counter[str]] = defaultdict(Counter)
    by_domain_family: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        domain = str(row.get("domain") or "")
        by_domain_label[domain].update(str(atom.get("u_star") or "") for atom in row.get("memories") or [])
        hard = hard_a_atom(row)
        if hard:
            by_domain_family[domain][str(hard.get("hard_a_family") or "")] += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "validation": validation,
        "records": {
            "domain": dict(sorted(Counter(str(row.get("domain") or "") for row in rows).items())),
            "source_dataset": dict(
                sorted(Counter(str(row.get("source_dataset") or "") for row in rows).items())
            ),
            "source_topic": dict(
                sorted(Counter(str(row.get("source_topic") or "") for row in rows).items())
            ),
            "qc_decision": dict(
                sorted(
                    Counter(
                        str((row.get("revision_independent_qc") or {}).get("computed_decision") or "")
                        for row in rows
                    ).items()
                )
            ),
        },
        "structure": {
            "visible_blocks": sum(len(row.get("memory_blocks") or []) for row in rows),
            "multi_atom_visible_blocks": sum(
                len(block.get("atom_ids") or []) >= 2
                for row in rows
                for block in row.get("memory_blocks") or []
            ),
            "memory_atoms": len(atoms),
            "real_atoms": len(real_atoms),
            "synthetic_hard_a_atoms": len(hard_atoms),
            "atoms_per_record": numeric_summary([len(row.get("memories") or []) for row in rows]),
            "real_atoms_per_record": numeric_summary(
                [
                    sum(atom.get("source") != "synthetic_hard_a" for atom in row.get("memories") or [])
                    for row in rows
                ]
            ),
        },
        "memory": {
            "label": dict(sorted(Counter(str(atom.get("u_star") or "") for atom in atoms).items())),
            "label_action": dict(
                sorted(
                    Counter(
                        f"{atom.get('u_star', '')}:{atom.get('memory_action', '')}" for atom in atoms
                    ).items()
                )
            ),
            "memory_type": dict(
                sorted(Counter(str(atom.get("memory_type") or "") for atom in atoms).items())
            ),
            "hard_a_family": dict(
                sorted(Counter(str(atom.get("hard_a_family") or "") for atom in hard_atoms).items())
            ),
            "label_by_domain": {
                domain: dict(sorted(counts.items())) for domain, counts in sorted(by_domain_label.items())
            },
            "hard_a_family_by_domain": {
                domain: dict(sorted(counts.items())) for domain, counts in sorted(by_domain_family.items())
            },
        },
    }


def stable_review_sample(rows: list[dict[str, Any]], per_cell: int = 2) -> list[dict[str, Any]]:
    cells: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        hard = hard_a_atom(row)
        cells[(str(row.get("domain") or ""), str((hard or {}).get("hard_a_family") or ""))].append(row)
    selected = []
    for key, candidates in sorted(cells.items()):
        ordered = sorted(candidates, key=lambda row: hashlib.sha256(str(row.get("id")).encode()).hexdigest())
        selected.extend(ordered[:per_cell])
    return selected


def write_review_html(path: Path, rows: list[dict[str, Any]], statistics_data: dict[str, Any]) -> None:
    cards = []
    for row in stable_review_sample(rows):
        hard = hard_a_atom(row) or {}
        real = [atom for atom in row.get("memories") or [] if atom.get("source") != "synthetic_hard_a"]
        real_items = "".join(
            f"<li><span class='tag'>{html.escape(str(atom.get('u_star') or ''))}</span> "
            f"{html.escape(str(atom.get('text') or ''))}</li>"
            for atom in real
        )
        qc = row.get("revision_independent_qc") or {}
        cards.append(
            "<article>"
            f"<div class='meta'>{html.escape(str(row.get('domain')))} · "
            f"{html.escape(str(hard.get('hard_a_family')))} · {html.escape(str(row.get('id')))}</div>"
            f"<h2>{html.escape(str(row.get('question') or ''))}</h2>"
            f"<h3>Grounded composite atoms</h3><ol>{real_items}</ol>"
            f"<h3>Hard A</h3><p>{html.escape(str(hard.get('text') or ''))}</p>"
            f"<p><strong>Why ignored:</strong> {html.escape(str(hard.get('non_applicability_reason') or ''))}</p>"
            f"<p><strong>Independent QC:</strong> {html.escape(str(qc.get('computed_decision') or ''))}</p>"
            "</article>"
        )
    summary = html.escape(json.dumps(statistics_data["validation"], ensure_ascii=False, indent=2))
    content = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MemCalib v2.1 release review</title>
<style>
body{{margin:0;background:#f4f6f8;color:#17212b;font:15px/1.55 system-ui,sans-serif}}
header{{background:#17212b;color:#fff;padding:28px max(24px,calc((100vw - 1100px)/2))}}
main{{max-width:1100px;margin:auto;padding:24px}} article{{background:#fff;border:1px solid #d8dee5;border-radius:6px;padding:22px;margin:18px 0}}
h1{{margin:0 0 8px}} h2{{font-size:19px}} h3{{font-size:15px;margin-top:18px}} .meta{{color:#5d6a76;font-size:13px}}
.tag{{display:inline-block;min-width:22px;text-align:center;background:#e6edf3;border-radius:3px;font-weight:700}}
pre{{white-space:pre-wrap;background:#fff;border:1px solid #d8dee5;padding:16px}}
</style></head><body><header><h1>MemCalib v2.1 release review</h1>
<div>Stratified review sample: two records per domain × Hard-A family cell</div></header>
<main><h2>Release validation</h2><pre>{summary}</pre>{''.join(cards)}</main></body></html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and build the MemCalib v2.1 multidomain release.")
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
