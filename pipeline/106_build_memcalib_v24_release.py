#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from memcalib_v23_common import file_sha256, portable_path
from memcalib_v24_coding_common import (
    CODE_FENCE_RE,
    QUESTION_SUFFIXES,
    V23_RELEASE,
    V24_DIR,
    locked_supervision_fingerprint,
)
from utils import iter_jsonl, write_json, write_jsonl


DEFAULT_CODING = V24_DIR / "memcalib_v24_coding_complete_3750.jsonl"
RELEASE_DIR = V24_DIR / "release"
DEFAULT_OUTPUT = RELEASE_DIR / "memcalib_v24_multidomain_benchmark_15000.jsonl"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")
DEFAULT_STATS = DEFAULT_OUTPUT.with_suffix(".statistics.json")
DEFAULT_REVIEW = RELEASE_DIR / "memcalib_v24_multidomain_benchmark_review.html"
EXPECTED_DOMAINS = {
    "health_seed": 7500,
    "general": 3750,
    "coding": 3750,
}


def coding_admission_channel(row: dict[str, Any]) -> str | None:
    admission = row.get("v24_coding_admission")
    if not isinstance(admission, dict):
        return None
    channel = admission.get("channel")
    decision = admission.get("decision")
    if channel == "independent_qc_strict" and decision == "strict_pass":
        qc = row.get("v24_coding_independent_qc")
        if isinstance(qc, dict) and qc.get("decision") == "strict_pass":
            return channel
        return None
    if channel == "manual_adjudication" and decision == "manual_adjudicated_strict":
        adjudication = row.get("v24_manual_adjudication")
        if (
            isinstance(adjudication, dict)
            and adjudication.get("decision") == "manual_adjudicated_strict"
            and adjudication.get("labels_and_actions_changed") is False
            and adjudication.get("deterministic_validators_passed") is True
        ):
            return channel
    return None


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
    source_rows: list[dict[str, Any]],
    coding_rows: list[dict[str, Any]],
    release_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    violations: list[str] = []
    source_by_id = {str(row.get("id") or ""): row for row in source_rows}
    coding_by_id = {str(row.get("id") or ""): row for row in coding_rows}
    source_coding_ids = [
        str(row.get("id") or "")
        for row in source_rows
        if row.get("domain") == "coding"
    ]
    if len(coding_rows) != 3750 or set(coding_by_id) != set(source_coding_ids):
        violations.append("coding_coverage_not_exact")
    if len(coding_by_id) != len(coding_rows):
        violations.append("coding_ids_not_unique")

    release_ids = [str(row.get("id") or "") for row in release_rows]
    if len(release_rows) != 15000:
        violations.append("release_record_count_mismatch")
    if "" in release_ids or len(release_ids) != len(set(release_ids)):
        violations.append("release_ids_not_unique")
    if release_ids != [str(row.get("id") or "") for row in source_rows]:
        violations.append("source_order_or_coverage_changed")
    domains = Counter(str(row.get("domain") or "") for row in release_rows)
    if dict(domains) != EXPECTED_DOMAINS:
        violations.append(f"domain_distribution_mismatch:{dict(domains)}")

    for row in release_rows:
        record_id = str(row.get("id") or "")
        source = source_by_id[record_id]
        if row.get("domain") != "coding":
            comparable = copy.deepcopy(row)
            comparable["schema_version"] = source.get("schema_version")
            if comparable != source:
                violations.append(f"{record_id}:noncoding_content_changed")
            continue
        if coding_admission_channel(row) is None:
            violations.append(f"{record_id}:coding_not_admitted")
        revision = row.get("coding_text_observability_revision")
        if not isinstance(revision, dict):
            violations.append(f"{record_id}:coding_revision_missing")
            continue
        family = str(revision.get("task_family") or "")
        if family not in QUESTION_SUFFIXES:
            violations.append(f"{record_id}:bad_task_family")
        elif not str(row.get("question") or "").endswith(QUESTION_SUFFIXES[family]):
            violations.append(f"{record_id}:question_contract_missing")
        if CODE_FENCE_RE.search(str(row.get("question") or "")):
            violations.append(f"{record_id}:question_contains_code_fence")
        if CODE_FENCE_RE.search(str(row.get("source_answer") or "")):
            violations.append(f"{record_id}:reference_contains_code_fence")
        if row.get("memory_blocks") != source.get("memory_blocks"):
            violations.append(f"{record_id}:memory_blocks_changed")
        if locked_supervision_fingerprint(row) != locked_supervision_fingerprint(source):
            violations.append(f"{record_id}:locked_atom_supervision_changed")
    return {
        "records": len(release_rows),
        "unique_record_ids": len(set(release_ids)),
        "domain": dict(sorted(domains.items())),
        "coding_records": len(coding_rows),
        "coding_all_admitted": all(
            coding_admission_channel(row) is not None for row in coding_rows
        ),
        "violations": violations,
    }


def build_statistics(
    rows: list[dict[str, Any]], source_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    coding = [row for row in rows if row.get("domain") == "coding"]
    source_by_id = {str(row.get("id") or ""): row for row in source_rows}
    source_coding = [source_by_id[str(row["id"])] for row in coding]
    coding_atoms = [atom for row in coding for atom in row.get("memories") or []]
    return {
        "schema_version": "memcalib-v24-release-statistics-v1",
        "record_level": {
            "records": len(rows),
            "domain": dict(sorted(Counter(row.get("domain") for row in rows).items())),
            "source_dataset": dict(
                sorted(Counter(row.get("source_dataset") for row in rows).items())
            ),
        },
        "coding_revision": {
            "records": len(coding),
            "questions_changed_from_v23": sum(
                row.get("question") != source.get("question")
                for row, source in zip(coding, source_coding)
            ),
            "reference_answers_changed_from_v23": sum(
                row.get("source_answer") != source.get("source_answer")
                for row, source in zip(coding, source_coding)
            ),
            "question_contracts_present": sum(
                str(row.get("question") or "").endswith(
                    QUESTION_SUFFIXES[
                        row["coding_text_observability_revision"]["task_family"]
                    ]
                )
                for row in coding
            ),
            "task_family": dict(
                sorted(
                    Counter(
                        row["coding_text_observability_revision"]["task_family"]
                        for row in coding
                    ).items()
                )
            ),
            "questions_with_code_fences": sum(
                bool(CODE_FENCE_RE.search(str(row.get("question") or "")))
                for row in coding
            ),
            "reference_answers_with_code_fences": sum(
                bool(CODE_FENCE_RE.search(str(row.get("source_answer") or "")))
                for row in coding
            ),
            "v23_questions_with_code_fences": sum(
                bool(CODE_FENCE_RE.search(str(row.get("question") or "")))
                for row in source_coding
            ),
            "v23_reference_answers_with_code_fences": sum(
                bool(CODE_FENCE_RE.search(str(row.get("source_answer") or "")))
                for row in source_coding
            ),
            "atoms_per_record": numeric_summary(
                [len(row.get("memories") or []) for row in coding]
            ),
            "atom_labels": dict(
                sorted(Counter(atom.get("u_star") for atom in coding_atoms).items())
            ),
            "atom_actions": dict(
                sorted(
                    Counter(atom.get("memory_action") for atom in coding_atoms).items()
                )
            ),
            "admission_channel": dict(
                sorted(
                    Counter(
                        coding_admission_channel(row)
                        for row in coding
                    ).items()
                )
            ),
        },
    }


def stable_coding_review_sample(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    coding = [row for row in rows if row.get("domain") == "coding"]
    selected: list[dict[str, Any]] = []
    for family in sorted(QUESTION_SUFFIXES):
        candidates = [
            row
            for row in coding
            if row["coding_text_observability_revision"]["task_family"] == family
        ]
        candidates.sort(
            key=lambda row: hashlib.sha256(
                f"memcalib-v24-review:{row['id']}".encode("utf-8")
            ).hexdigest()
        )
        selected.extend(candidates[:10])
    return selected


def write_review_html(path: Path, rows: list[dict[str, Any]]) -> None:
    cards: list[str] = []
    for row in stable_coding_review_sample(rows):
        atoms = {
            str(atom.get("atom_id") or ""): atom
            for atom in row.get("memories") or []
        }
        block_html: list[str] = []
        for block in row.get("memory_blocks") or []:
            atom_rows = "".join(
                "<li><strong>"
                + html.escape(str(atoms[str(atom_id)].get("u_star") or ""))
                + "</strong> "
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
                + "</p><details><summary>Hidden atoms and labels</summary><ol>"
                + atom_rows
                + "</ol></details></section>"
            )
        cards.append(
            "<article><header><span>"
            + html.escape(
                str(row["coding_text_observability_revision"]["task_family"])
            )
            + " / "
            + html.escape(str(coding_admission_channel(row)))
            + "</span><h2>"
            + html.escape(str(row["question"]))
            + "</h2><code>"
            + html.escape(str(row["id"]))
            + "</code></header><h3>Hidden reference answer</h3><p>"
            + html.escape(str(row.get("source_answer") or ""))
            + "</p>"
            + "".join(block_html)
            + "</article>"
        )
    document = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>MemCalib v2.4 coding review</title><style>"
        "body{font-family:Inter,system-ui,sans-serif;margin:0;background:#f5f7f8;"
        "color:#17202a}main{max-width:1180px;margin:auto;padding:32px}"
        "article{background:white;border:1px solid #dce2e8;margin:0 0 28px;"
        "padding:24px;border-radius:8px}header span{font-weight:700;color:#146b5c}"
        "h2{font-size:20px;line-height:1.45}section{border-top:1px solid #e5e9ed;"
        "padding:14px 0}h3{font-size:15px}p{line-height:1.6;white-space:pre-wrap}"
        "small,code{color:#68737d}li{margin:6px 0;line-height:1.45}"
        "summary{cursor:pointer;font-weight:650}</style></head><body><main>"
        "<h1>MemCalib v2.4 coding text-observability review</h1>"
        "<p>Thirty deterministic examples: ten per coding task family. "
        "Questions and reference answers are natural-language-only; hidden atoms "
        "remain available for audit.</p>"
        + "".join(cards)
        + "</main></body></html>"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the full MemCalib v2.4 multidomain release."
    )
    parser.add_argument("--source", type=Path, default=V23_RELEASE)
    parser.add_argument("--coding", type=Path, default=DEFAULT_CODING)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--statistics", type=Path, default=DEFAULT_STATS)
    parser.add_argument("--review-html", type=Path, default=DEFAULT_REVIEW)
    args = parser.parse_args()

    source_rows = list(iter_jsonl(args.source))
    coding_rows = list(iter_jsonl(args.coding))
    coding_by_id = {str(row.get("id") or ""): row for row in coding_rows}
    release_rows: list[dict[str, Any]] = []
    for source in source_rows:
        record_id = str(source.get("id") or "")
        row = copy.deepcopy(coding_by_id.get(record_id, source))
        row["schema_version"] = "crk-2-canonical-memory-v2.4"
        release_rows.append(row)

    validation = validate_release(source_rows, coding_rows, release_rows)
    if validation["violations"]:
        raise ValueError(
            f"release validation failed with {len(validation['violations'])} "
            f"violations: {validation['violations'][:20]}"
        )
    write_jsonl(args.output, release_rows)
    statistics_payload = build_statistics(release_rows, source_rows)
    write_json(args.statistics, statistics_payload)
    write_review_html(args.review_html, release_rows)
    manifest = {
        "schema_version": "memcalib-v24-multidomain-release-v1",
        "inputs": {
            "v23_release": {
                "path": portable_path(args.source),
                "sha256": file_sha256(args.source),
                "records": len(source_rows),
            },
            "v24_coding_strict": {
                "path": portable_path(args.coding),
                "sha256": file_sha256(args.coding),
                "records": len(coding_rows),
            },
        },
        "scope": {
            "coding_records_revised": 3750,
            "noncoding_semantics_unchanged": True,
            "record_ids_and_order_preserved": True,
            "memory_atoms_blocks_labels_actions_preserved": True,
            "coding_questions_answers_contracts_rubrics_rebuilt": True,
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
