#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from evaluation.common import iter_jsonl, sha256_file, write_json, write_jsonl
from evaluation.scripts.build_human_review import (
    build_review_records,
    select_human_review_ids,
)
from evaluation.scripts.prepare_judge_requests import load_answers, select_stratified_answer_ids


ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = ROOT / "evaluation" / "runs" / "memcalib-ordered-v2-500" / "calibration"
RELEASE_ROOT = ROOT / "evaluation" / "archive" / "releases" / "memcalib-ordered-v2-500"
DEFAULT_CONFIG = ROOT / "evaluation" / "archive" / "configs" / "memcalib-ordered-v2-500.json"
DEFAULT_HIDDEN = ROOT / "evaluation" / "archive" / "releases" / "memcalib-v0.1-500" / "hidden-evaluation.jsonl"
DEFAULT_ANSWERS = ROOT / "evaluation" / "runs" / "memcalib-v0.1-500" / "answers"
DEFAULT_PRIMARY = RUN_ROOT / "judgments" / "primary.valid.jsonl"
DEFAULT_SECONDARY = RUN_ROOT / "judgments" / "secondary.valid.jsonl"
DEFAULT_JSONL = RELEASE_ROOT / "calibration-human-review-30.jsonl"
DEFAULT_HTML = RELEASE_ROOT / "calibration-human-review-30.html"
DEFAULT_MANIFEST = RELEASE_ROOT / "calibration-human-review-30.manifest.json"
DEFAULT_TRANSLATIONS = RELEASE_ROOT / "calibration-human-review-30.translations-zh.jsonl"
DEFAULT_TRANSLATION_SUMMARY = RELEASE_ROOT / "calibration-human-review-30.translations-zh.summary.json"
DEFAULT_TEMPLATE = ROOT / "evaluation" / "templates" / "calibration-review-bilingual.html"


def attach_translations(records: list[dict], path: Path) -> int:
    if not path.exists():
        return 0
    by_id = {str(row["answer_request_id"]): row.get("translations_zh") or {} for row in iter_jsonl(path)}
    localized = 0
    for record in records:
        translations = by_id.get(str(record["answer_request_id"]))
        if translations:
            record["translations_zh"] = translations
            localized += 1
    return localized


def render_calibration_review_html(records: list[dict], template_path: Path) -> str:
    payload = json.dumps(records, ensure_ascii=False).replace("</", "<\\/")
    template = template_path.read_text(encoding="utf-8")
    placeholder = "__MEMCALIB_RECORDS_JSON__"
    if template.count(placeholder) != 1:
        raise ValueError(f"template must contain exactly one {placeholder} placeholder")
    return template.replace(placeholder, payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a 30-answer ordered-usage-v2 calibration review pack.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--hidden", type=Path, default=DEFAULT_HIDDEN)
    parser.add_argument("--answers", type=Path, default=DEFAULT_ANSWERS)
    parser.add_argument("--primary", type=Path, default=DEFAULT_PRIMARY)
    parser.add_argument("--secondary", type=Path, default=DEFAULT_SECONDARY)
    parser.add_argument("--jsonl", type=Path, default=DEFAULT_JSONL)
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--translations", type=Path, default=DEFAULT_TRANSLATIONS)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    samples = list(iter_jsonl(args.hidden))
    all_answers = load_answers(args.answers, config)
    primary = list(iter_jsonl(args.primary))
    secondary = list(iter_jsonl(args.secondary))
    calibration_ids = {str(row["answer_request_id"]) for row in primary}
    answers = [row for row in all_answers if str(row["request_id"]) in calibration_ids]
    random_ids = select_stratified_answer_ids(
        answers,
        seed=int(config["seed"]) + 3,
        representative_per_cell=1,
        diagnostic_per_cell=1,
    )
    selected = select_human_review_ids(
        answers,
        primary,
        secondary,
        random_ids=random_ids,
        diagnostic_count=10,
        seed=int(config["seed"]) + 4,
    )
    records = build_review_records(selected, samples, answers, primary, secondary)
    write_jsonl(args.jsonl, records)
    localized_records = attach_translations(records, args.translations)
    args.html.parent.mkdir(parents=True, exist_ok=True)
    args.html.write_text(render_calibration_review_html(records, args.template), encoding="utf-8")
    artifacts = {
        args.jsonl.name: {"sha256": sha256_file(args.jsonl)},
        args.html.name: {"sha256": sha256_file(args.html)},
    }
    if args.translations.exists():
        artifacts[args.translations.name] = {"sha256": sha256_file(args.translations)}
    if DEFAULT_TRANSLATION_SUMMARY.exists():
        artifacts[DEFAULT_TRANSLATION_SUMMARY.name] = {"sha256": sha256_file(DEFAULT_TRANSLATION_SUMMARY)}
    manifest = {
        "schema_version": "memcalib-ordered-calibration-human-review-v2",
        "records": len(records),
        "localized_records": localized_records,
        "display_languages": ["en", "zh-CN"] if localized_records else ["en"],
        "authoritative_language": "en",
        "strata": dict(sorted(Counter(row["review_stratum"] for row in records).items())),
        "models": dict(sorted(Counter(row["model_key"] for row in records).items())),
        "conditions": dict(sorted(Counter(row["condition"] for row in records).items())),
        "panels": dict(sorted(Counter(row["panel"] for row in records).items())),
        "artifacts": artifacts,
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
