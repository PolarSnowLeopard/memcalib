#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from evaluation.common import iter_jsonl, sha256_file, write_json


ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "evaluation" / "archive" / "releases" / "memcalib-ordered-v2.1-multidomain-pilot-200"
DEFAULT_RECORDS = RELEASE / "multidomain-human-review-30.jsonl"
DEFAULT_ANNOTATIONS = RELEASE / "multidomain-expert-review-30.json"
DEFAULT_BASE_HTML = RELEASE / "multidomain-human-review-30.html"
DEFAULT_SUMMARY = RELEASE / "multidomain-expert-review-30.summary.json"
DEFAULT_HTML = RELEASE / "multidomain-expert-review-30.html"

LEVELS = {"A", "B", "C", "unscorable"}
CONTRADICTIONS = {"no", "explicit_fact", "constraint_violation", "both", "unclear"}
GOLD_QUALITY = {"valid", "revise", "invalid", "unclear"}
DECISIONS = {"accept", "revise", "reject", "unscorable"}


def judge_atom_map(judgment: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["atom_id"]): row for row in judgment.get("atom_judgments") or []}


def validate_annotations(
    records: list[dict[str, Any]], payload: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    annotations = payload.get("annotations")
    if not isinstance(annotations, dict):
        raise ValueError("annotations must be an object keyed by answer_request_id")

    records_by_id = {str(record["answer_request_id"]): record for record in records}
    expected_ids = set(records_by_id)
    actual_ids = set(annotations)
    if expected_ids != actual_ids:
        missing = sorted(expected_ids - actual_ids)
        extra = sorted(actual_ids - expected_ids)
        raise ValueError(f"annotation answer IDs mismatch; missing={missing}, extra={extra}")

    for answer_id, record in records_by_id.items():
        annotation = annotations[answer_id]
        if annotation.get("decision") not in DECISIONS:
            raise ValueError(f"invalid decision for {answer_id}: {annotation.get('decision')}")
        if not isinstance(annotation.get("note"), str):
            raise ValueError(f"note must be a string for {answer_id}")
        atom_annotations = annotation.get("atoms")
        if not isinstance(atom_annotations, dict):
            raise ValueError(f"atoms must be an object for {answer_id}")
        expected_atoms = {str(atom["atom_id"]) for atom in record.get("atomic_memories") or []}
        if set(atom_annotations) != expected_atoms:
            raise ValueError(f"atom IDs mismatch for {answer_id}")
        for atom_id, atom_annotation in atom_annotations.items():
            if atom_annotation.get("usage_level") not in LEVELS:
                raise ValueError(f"invalid usage level for {answer_id}/{atom_id}")
            if atom_annotation.get("contradiction") not in CONTRADICTIONS:
                raise ValueError(f"invalid contradiction for {answer_id}/{atom_id}")
            if atom_annotation.get("gold_quality") not in GOLD_QUALITY:
                raise ValueError(f"invalid Gold quality for {answer_id}/{atom_id}")

    finding_sets = payload.get("finding_sets") or {}
    if not isinstance(finding_sets, dict):
        raise ValueError("finding_sets must be an object")
    for name, answer_ids in finding_sets.items():
        if not isinstance(answer_ids, list) or len(answer_ids) != len(set(answer_ids)):
            raise ValueError(f"finding set must be a unique list: {name}")
        unknown = sorted(set(answer_ids) - expected_ids)
        if unknown:
            raise ValueError(f"unknown answer IDs in finding set {name}: {unknown}")
    return annotations


def matrix() -> dict[str, dict[str, int]]:
    return {gold: {predicted: 0 for predicted in ("A", "B", "C")} for gold in ("A", "B", "C")}


def summarize(
    records: list[dict[str, Any]], payload: dict[str, Any], annotations: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    decision_counts: Counter[str] = Counter()
    issue_counts: Counter[str] = Counter()
    usage_counts: Counter[str] = Counter()
    contradiction_counts: Counter[str] = Counter()
    gold_quality_counts: Counter[str] = Counter()
    domain_decisions: dict[str, Counter[str]] = defaultdict(Counter)
    domain_gold_quality: dict[str, Counter[str]] = defaultdict(Counter)
    condition_decisions: dict[str, Counter[str]] = defaultdict(Counter)
    category_decisions: dict[str, Counter[str]] = defaultdict(Counter)
    category_gold_quality: dict[str, Counter[str]] = defaultdict(Counter)
    primary_exact = 0
    secondary_exact = 0
    scored_atoms = 0
    gold_expert = matrix()
    expert_primary = matrix()
    expert_secondary = matrix()

    for record in records:
        answer_id = str(record["answer_request_id"])
        annotation = annotations[answer_id]
        decision = str(annotation["decision"])
        issue = str(annotation.get("issue") or "none")
        domain = str(record["domain"])
        condition = str(record["condition"])
        category = str(record["selection_category"])
        decision_counts[decision] += 1
        issue_counts[issue] += 1
        domain_decisions[domain][decision] += 1
        condition_decisions[condition][decision] += 1
        category_decisions[category][decision] += 1
        primary = judge_atom_map(record["primary_judgment"])
        secondary = judge_atom_map(record["secondary_judgment"])

        for atom in record.get("atomic_memories") or []:
            atom_id = str(atom["atom_id"])
            expert = str(annotation["atoms"][atom_id]["usage_level"])
            contradiction = str(annotation["atoms"][atom_id]["contradiction"])
            quality = str(annotation["atoms"][atom_id]["gold_quality"])
            gold = str(atom["u_star"])
            usage_counts[expert] += 1
            contradiction_counts[contradiction] += 1
            gold_quality_counts[quality] += 1
            domain_gold_quality[domain][quality] += 1
            category_gold_quality[category][quality] += 1
            if expert not in {"A", "B", "C"} or gold not in {"A", "B", "C"}:
                continue
            primary_level = str(primary[atom_id]["predicted_usage_level"])
            secondary_level = str(secondary[atom_id]["predicted_usage_level"])
            scored_atoms += 1
            primary_exact += primary_level == expert
            secondary_exact += secondary_level == expert
            gold_expert[gold][expert] += 1
            expert_primary[expert][primary_level] += 1
            expert_secondary[expert][secondary_level] += 1

    finding_sets = payload.get("finding_sets") or {}
    return {
        "schema_version": "memcalib-multidomain-expert-review-summary-v1",
        "reviewer_type": payload.get("reviewer_type"),
        "intended_use": payload.get("intended_use"),
        "records": len(records),
        "atoms": sum(len(record.get("atomic_memories") or []) for record in records),
        "decisions": dict(sorted(decision_counts.items())),
        "issues": dict(sorted(issue_counts.items())),
        "usage_levels": dict(sorted(usage_counts.items())),
        "contradictions": dict(sorted(contradiction_counts.items())),
        "gold_quality": dict(sorted(gold_quality_counts.items())),
        "domain_decisions": {
            domain: dict(sorted(counts.items())) for domain, counts in sorted(domain_decisions.items())
        },
        "domain_gold_quality": {
            domain: dict(sorted(counts.items())) for domain, counts in sorted(domain_gold_quality.items())
        },
        "condition_decisions": {
            condition: dict(sorted(counts.items()))
            for condition, counts in sorted(condition_decisions.items())
        },
        "category_decisions": {
            category: dict(sorted(counts.items()))
            for category, counts in sorted(category_decisions.items())
        },
        "category_gold_quality": {
            category: dict(sorted(counts.items()))
            for category, counts in sorted(category_gold_quality.items())
        },
        "judge_exact_agreement_with_expert": {
            "denominator_atoms": scored_atoms,
            "primary": round(primary_exact / scored_atoms, 6),
            "secondary": round(secondary_exact / scored_atoms, 6),
        },
        "confusion_matrices": {
            "gold_rows_expert_columns": gold_expert,
            "expert_rows_primary_columns": expert_primary,
            "expert_rows_secondary_columns": expert_secondary,
        },
        "finding_set_counts": {
            name: len(answer_ids) for name, answer_ids in sorted(finding_sets.items())
        },
    }


def render_reviewed_html(
    base_html: str, annotations: dict[str, dict[str, Any]], summary: dict[str, Any]
) -> str:
    html = base_html
    replacements = {
        "<title>MemCalib 多领域有效性审查</title>": "<title>MemCalib 多领域专家预审结果</title>",
        "<h1>多领域有效性审查</h1>\n        <p>30 条分层回答，核验多领域 Gold、rubric 与双 Judge。英文原文是正式依据，中文译文仅辅助阅读。</p>": (
            "<h1>多领域专家预审结果</h1>\n"
            f"        <p>AI 辅助专家预审，不可替代论文人工标注。30 条中接受 {summary['decisions'].get('accept', 0)} 条、"
            f"需修订 {summary['decisions'].get('revise', 0)} 条、剔除 {summary['decisions'].get('reject', 0)} 条；"
            f"Gold 有效 {summary['gold_quality'].get('valid', 0)} / {summary['atoms']} 个原子。</p>"
        ),
        "const storageKey = 'memcalib-multidomain-human-review-v1';": (
            "const storageKey = 'memcalib-multidomain-expert-review-v1';"
        ),
    }
    for old, new in replacements.items():
        if html.count(old) != 1:
            raise ValueError(f"reviewed HTML customization anchor must occur exactly once: {old}")
        html = html.replace(old, new)

    saved_anchor = "const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');"
    if html.count(saved_anchor) != 1:
        raise ValueError("saved-state anchor must occur exactly once")
    preload = json.dumps(annotations, ensure_ascii=False).replace("</", "<\\/")
    html = html.replace(
        saved_anchor,
        f"const preloadedSaved = {preload};\n    "
        "const saved = {...preloadedSaved, ...JSON.parse(localStorage.getItem(storageKey) || '{}')};",
    )
    return html


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and render the 30-answer expert pre-audit.")
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--annotations", type=Path, default=DEFAULT_ANNOTATIONS)
    parser.add_argument("--base-html", type=Path, default=DEFAULT_BASE_HTML)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    args = parser.parse_args()

    records = list(iter_jsonl(args.records))
    payload = json.loads(args.annotations.read_text(encoding="utf-8"))
    annotations = validate_annotations(records, payload)
    summary = summarize(records, payload, annotations)
    summary["inputs"] = {
        str(args.records.relative_to(ROOT)): {"sha256": sha256_file(args.records)},
        str(args.annotations.relative_to(ROOT)): {"sha256": sha256_file(args.annotations)},
        str(args.base_html.relative_to(ROOT)): {"sha256": sha256_file(args.base_html)},
    }
    args.html.write_text(
        render_reviewed_html(args.base_html.read_text(encoding="utf-8"), annotations, summary),
        encoding="utf-8",
    )
    summary["artifacts"] = {
        str(args.html.relative_to(ROOT)): {"sha256": sha256_file(args.html)}
    }
    write_json(args.summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
