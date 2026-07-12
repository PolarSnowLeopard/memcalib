#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from evaluation.common import iter_jsonl, sha256_file, write_json, write_jsonl
from evaluation.scripts.build_human_review import (
    build_review_records,
    render_review_html,
    select_human_review_ids,
)
from evaluation.scripts.prepare_judge_requests import load_answers, select_stratified_answer_ids


ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = ROOT / "evaluation" / "runs" / "memcalib-ordered-v2-500" / "calibration"
RELEASE_ROOT = ROOT / "evaluation" / "releases" / "memcalib-ordered-v2-500"
DEFAULT_CONFIG = ROOT / "evaluation" / "configs" / "memcalib-ordered-v2-500.json"
DEFAULT_HIDDEN = ROOT / "evaluation" / "releases" / "memcalib-v0.1-500" / "hidden-evaluation.jsonl"
DEFAULT_ANSWERS = ROOT / "evaluation" / "runs" / "memcalib-v0.1-500" / "answers"
DEFAULT_PRIMARY = RUN_ROOT / "judgments" / "primary.valid.jsonl"
DEFAULT_SECONDARY = RUN_ROOT / "judgments" / "secondary.valid.jsonl"
DEFAULT_JSONL = RELEASE_ROOT / "calibration-human-review-30.jsonl"
DEFAULT_HTML = RELEASE_ROOT / "calibration-human-review-30.html"
DEFAULT_MANIFEST = RELEASE_ROOT / "calibration-human-review-30.manifest.json"


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
    args.html.parent.mkdir(parents=True, exist_ok=True)
    args.html.write_text(render_review_html(records), encoding="utf-8")
    manifest = {
        "schema_version": "memcalib-ordered-calibration-human-review-v1",
        "records": len(records),
        "strata": dict(sorted(Counter(row["review_stratum"] for row in records).items())),
        "models": dict(sorted(Counter(row["model_key"] for row in records).items())),
        "conditions": dict(sorted(Counter(row["condition"] for row in records).items())),
        "panels": dict(sorted(Counter(row["panel"] for row in records).items())),
        "artifacts": {
            args.jsonl.name: {"sha256": sha256_file(args.jsonl)},
            args.html.name: {"sha256": sha256_file(args.html)},
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
