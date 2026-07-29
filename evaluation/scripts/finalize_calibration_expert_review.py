#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from evaluation.common import iter_jsonl, sha256_file, write_json


ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "evaluation" / "archive" / "releases" / "memcalib-ordered-v2-500"
DEFAULT_RECORDS = RELEASE / "calibration-human-review-30.jsonl"
DEFAULT_ANNOTATIONS = RELEASE / "calibration-expert-review-30.json"
DEFAULT_BASE_HTML = RELEASE / "calibration-human-review-30.html"
DEFAULT_HIDDEN = ROOT / "evaluation" / "archive" / "releases" / "memcalib-v0.1-500" / "hidden-evaluation.jsonl"
DEFAULT_SUMMARY = RELEASE / "calibration-expert-review-30.summary.json"
DEFAULT_HTML = RELEASE / "calibration-expert-review-30.html"

LEVELS = {"A", "B", "C", "unscorable"}
CONTRADICTIONS = {"no", "explicit_fact", "constraint_violation", "both", "unclear"}
GOLD_QUALITY = {"valid", "revise", "invalid", "unclear"}
DECISIONS = {"accept", "revise", "reject", "unscorable"}


def judge_atom_map(judgment: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["atom_id"]): row for row in judgment.get("atom_judgments") or []}


def load_sources(path: Path) -> dict[str, str]:
    return {str(row["id"]): str(row["source_dataset"]) for row in iter_jsonl(path)}


def validate_annotations(
    records: list[dict[str, Any]], payload: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    annotations = payload.get("annotations")
    if not isinstance(annotations, dict):
        raise ValueError("annotations must be an object keyed by answer_request_id")

    records_by_id = {str(record["answer_request_id"]): record for record in records}
    if set(annotations) != set(records_by_id):
        missing = sorted(set(records_by_id) - set(annotations))
        extra = sorted(set(annotations) - set(records_by_id))
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
            raise ValueError(f"finding set must contain unique answer IDs: {name}")
        unknown = sorted(set(answer_ids) - set(records_by_id))
        if unknown:
            raise ValueError(f"unknown answer IDs in finding set {name}: {unknown}")
    return annotations


def matrix() -> dict[str, dict[str, int]]:
    return {row: {column: 0 for column in ("A", "B", "C")} for row in ("A", "B", "C")}


def sorted_nested(counters: dict[str, Counter[str]]) -> dict[str, dict[str, int]]:
    return {key: dict(sorted(value.items())) for key, value in sorted(counters.items())}


def summarize(
    records: list[dict[str, Any]],
    payload: dict[str, Any],
    annotations: dict[str, dict[str, Any]],
    sources: dict[str, str],
) -> dict[str, Any]:
    decisions: Counter[str] = Counter()
    issues: Counter[str] = Counter()
    usages: Counter[str] = Counter()
    contradictions: Counter[str] = Counter()
    qualities: Counter[str] = Counter()
    source_answers: Counter[str] = Counter()
    source_decisions: dict[str, Counter[str]] = defaultdict(Counter)
    source_qualities: dict[str, Counter[str]] = defaultdict(Counter)
    condition_decisions: dict[str, Counter[str]] = defaultdict(Counter)
    panel_decisions: dict[str, Counter[str]] = defaultdict(Counter)
    stratum_decisions: dict[str, Counter[str]] = defaultdict(Counter)
    gold_expert_all = matrix()
    gold_expert_valid = matrix()
    expert_primary = matrix()
    expert_secondary = matrix()
    judge_exact_all = Counter()
    judge_exact_valid_gold = Counter()
    scored_all = 0
    scored_valid_gold = 0

    for record in records:
        answer_id = str(record["answer_request_id"])
        sample_id = str(record["sample_id"])
        source = sources.get(sample_id, "unknown")
        annotation = annotations[answer_id]
        decision = str(annotation["decision"])
        decisions[decision] += 1
        issues[str(annotation.get("issue") or "none")] += 1
        source_answers[source] += 1
        source_decisions[source][decision] += 1
        condition_decisions[str(record["condition"])][decision] += 1
        panel_decisions[str(record["panel"])][decision] += 1
        stratum_decisions[str(record["review_stratum"])][decision] += 1
        primary = judge_atom_map(record["primary_judgment"])
        secondary = judge_atom_map(record["secondary_judgment"])

        for atom in record.get("atomic_memories") or []:
            atom_id = str(atom["atom_id"])
            atom_review = annotation["atoms"][atom_id]
            expert = str(atom_review["usage_level"])
            quality = str(atom_review["gold_quality"])
            gold = str(atom["u_star"])
            usages[expert] += 1
            contradictions[str(atom_review["contradiction"])] += 1
            qualities[quality] += 1
            source_qualities[source][quality] += 1
            if expert not in {"A", "B", "C"} or gold not in {"A", "B", "C"}:
                continue
            primary_level = str(primary[atom_id]["predicted_usage_level"])
            secondary_level = str(secondary[atom_id]["predicted_usage_level"])
            scored_all += 1
            judge_exact_all["primary"] += primary_level == expert
            judge_exact_all["secondary"] += secondary_level == expert
            gold_expert_all[gold][expert] += 1
            expert_primary[expert][primary_level] += 1
            expert_secondary[expert][secondary_level] += 1
            if quality == "valid":
                scored_valid_gold += 1
                judge_exact_valid_gold["primary"] += primary_level == expert
                judge_exact_valid_gold["secondary"] += secondary_level == expert
                gold_expert_valid[gold][expert] += 1

    def rate(counter: Counter[str], key: str, denominator: int) -> float:
        return round(counter[key] / denominator, 6) if denominator else 0.0

    return {
        "schema_version": "memcalib-calibration-expert-review-summary-v1",
        "reviewer_type": payload.get("reviewer_type"),
        "intended_use": payload.get("intended_use"),
        "records": len(records),
        "unique_samples": len({str(record["sample_id"]) for record in records}),
        "atoms": sum(len(record.get("atomic_memories") or []) for record in records),
        "decisions": dict(sorted(decisions.items())),
        "issues": dict(sorted(issues.items())),
        "usage_levels": dict(sorted(usages.items())),
        "contradictions": dict(sorted(contradictions.items())),
        "gold_quality": dict(sorted(qualities.items())),
        "source_answer_counts": dict(sorted(source_answers.items())),
        "source_decisions": sorted_nested(source_decisions),
        "source_gold_quality": sorted_nested(source_qualities),
        "condition_decisions": sorted_nested(condition_decisions),
        "panel_decisions": sorted_nested(panel_decisions),
        "review_stratum_decisions": sorted_nested(stratum_decisions),
        "judge_exact_agreement_with_expert": {
            "all_atoms": {
                "denominator": scored_all,
                "primary": rate(judge_exact_all, "primary", scored_all),
                "secondary": rate(judge_exact_all, "secondary", scored_all),
            },
            "valid_gold_atoms": {
                "denominator": scored_valid_gold,
                "primary": rate(judge_exact_valid_gold, "primary", scored_valid_gold),
                "secondary": rate(judge_exact_valid_gold, "secondary", scored_valid_gold),
            },
        },
        "confusion_matrices": {
            "gold_rows_expert_columns_all_atoms": gold_expert_all,
            "gold_rows_expert_columns_valid_gold_only": gold_expert_valid,
            "expert_rows_primary_columns": expert_primary,
            "expert_rows_secondary_columns": expert_secondary,
        },
        "finding_set_counts": {
            name: len(answer_ids) for name, answer_ids in sorted((payload.get("finding_sets") or {}).items())
        },
        "sampling_caveat": (
            "The 30-answer pack is stratified for calibration and disagreement diagnosis; "
            "its defect rates are not prevalence estimates for the 15,526-sample release."
        ),
    }


def render_reviewed_html(
    base_html: str, annotations: dict[str, dict[str, Any]], summary: dict[str, Any]
) -> str:
    html = base_html
    replacements = {
        "<title>MemCalib Judge 人工校准</title>": "<title>MemCalib 原两数据源专家预审结果</title>",
        "<h1>Judge 人工校准</h1>\n        <p>30 条回答，每个原子独立判断实际使用强度。英文原文是正式依据，中文译文仅辅助阅读。</p>": (
            "<h1>原两数据源专家预审结果</h1>\n"
            f"        <p>AI 辅助专家预审，不可替代论文人工标注。30 条中需修订 {summary['decisions'].get('revise', 0)} 条、"
            f"建议剔除 {summary['decisions'].get('reject', 0)} 条；161 个原子中 Gold 有效 "
            f"{summary['gold_quality'].get('valid', 0)} 个。英文原文是正式依据，中文译文仅辅助阅读。</p>"
        ),
        "const storageKey = 'memcalib-human-review-v2-bilingual';": (
            "const storageKey = 'memcalib-calibration-expert-review-v1';"
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
    parser = argparse.ArgumentParser(description="Validate and render the original-source 30-answer expert pre-audit.")
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--annotations", type=Path, default=DEFAULT_ANNOTATIONS)
    parser.add_argument("--base-html", type=Path, default=DEFAULT_BASE_HTML)
    parser.add_argument("--hidden", type=Path, default=DEFAULT_HIDDEN)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    args = parser.parse_args()

    records = list(iter_jsonl(args.records))
    payload = json.loads(args.annotations.read_text(encoding="utf-8"))
    annotations = validate_annotations(records, payload)
    summary = summarize(records, payload, annotations, load_sources(args.hidden))
    summary["inputs"] = {
        str(args.records.relative_to(ROOT)): {"sha256": sha256_file(args.records)},
        str(args.annotations.relative_to(ROOT)): {"sha256": sha256_file(args.annotations)},
        str(args.base_html.relative_to(ROOT)): {"sha256": sha256_file(args.base_html)},
        str(args.hidden.relative_to(ROOT)): {"sha256": sha256_file(args.hidden)},
    }
    args.html.write_text(
        render_reviewed_html(args.base_html.read_text(encoding="utf-8"), annotations, summary),
        encoding="utf-8",
    )
    summary["artifacts"] = {str(args.html.relative_to(ROOT)): {"sha256": sha256_file(args.html)}}
    write_json(args.summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
