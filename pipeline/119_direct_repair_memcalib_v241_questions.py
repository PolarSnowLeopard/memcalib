#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from memcalib_v23_common import canonical_sha256, file_sha256, norm_text, portable_path
from memcalib_v24_coding_common import (
    BENCHMARK_META_RE,
    CODE_FENCE_RE,
    V23_RELEASE,
    V24_DIR,
    materialize_question,
)
from utils import iter_jsonl, write_json, write_jsonl


AUDIT_DIR = V24_DIR / "audit"
DEFAULT_INPUT = AUDIT_DIR / "memcalib_v241_repaired_candidates_687.jsonl"
DEFAULT_SELECTION = (
    AUDIT_DIR / "memcalib_v241_repaired_candidates_consensus_687.repair.jsonl"
)
DEFAULT_OUTPUT = AUDIT_DIR / "memcalib_v241_direct_question_repair_511.jsonl"

IMPLEMENTATION_PREFIXES = (
    "write ",
    "create ",
    "implement ",
    "build ",
    "develop ",
    "design ",
    "define ",
    "add ",
    "modify ",
    "convert ",
)
DEBUG_MARKERS = (
    " why ",
    " error",
    " fail",
    " bug",
    " incorrect",
    " wrong",
    " fix ",
    " debug",
    " troubleshoot",
    " exception",
    " crash",
    " not work",
    " doesn't work",
    " does not work",
)


def clean_original_question(value: str) -> str:
    cleaned = CODE_FENCE_RE.sub("", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        raise ValueError("original question is empty")
    return cleaned


def infer_task_family(question: str) -> str:
    lowered = f" {question.casefold()} "
    stripped = question.lstrip().casefold()
    if stripped.startswith(IMPLEMENTATION_PREFIXES):
        return "implementation_plan"
    if any(marker in lowered for marker in DEBUG_MARKERS):
        return "debugging_diagnosis"
    return "behavior_prediction"


def direct_task_stem(original_question: str, family: str) -> str:
    original = clean_original_question(original_question)
    if family == "implementation_plan":
        return (
            "Describe a step-by-step implementation plan in natural language for "
            "accomplishing this original software-engineering request, while "
            f"preserving all of its functional requirements: {original}"
        )
    if family == "debugging_diagnosis":
        return (
            "Diagnose the software-engineering issue in this original request and "
            "describe the corrected behavior in natural language while preserving "
            f"its practical scope: {original}"
        )
    return (
        "Answer this original software-engineering question by explaining the "
        "expected behavior, decisions, outputs, and relevant failure paths in "
        f"natural language: {original}"
    )


def repair_record(
    candidate: dict[str, Any],
    source: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    record = copy.deepcopy(candidate)
    old_question = str(record.get("question") or "")
    old_revision = record.get("coding_text_observability_revision")
    old_family = (
        str(old_revision.get("task_family") or "")
        if isinstance(old_revision, dict)
        else ""
    )
    family = infer_task_family(str(source.get("question") or ""))
    stem = direct_task_stem(str(source.get("question") or ""), family)
    if BENCHMARK_META_RE.search(stem):
        raise ValueError(f"direct task stem leaks benchmark metadata: {record['id']}")
    new_question = materialize_question(stem, family)
    if CODE_FENCE_RE.search(new_question):
        raise ValueError(f"direct task question contains code fence: {record['id']}")
    record["question"] = new_question
    revision = copy.deepcopy(old_revision) if isinstance(old_revision, dict) else {}
    revision["task_family"] = family
    revision["direct_question_repair"] = {
        "schema_version": "memcalib-v241-direct-question-repair-v1",
        "source_question_fingerprint": canonical_sha256(
            str(source.get("question") or "")
        ),
        "prior_question_fingerprint": canonical_sha256(old_question),
        "prior_task_family": old_family,
        "new_task_family": family,
        "repair_policy": "restore_original_practical_scope_change_response_form_only",
    }
    record["coding_text_observability_revision"] = revision
    audit = {
        "schema_version": "memcalib-v241-direct-question-repair-audit-v1",
        "record_id": record["id"],
        "source_question": source.get("question"),
        "prior_question": old_question,
        "repaired_question": new_question,
        "prior_task_family": old_family,
        "new_task_family": family,
        "source_record_fingerprint": canonical_sha256(source),
        "candidate_record_fingerprint": canonical_sha256(candidate),
        "output_record_fingerprint": canonical_sha256(record),
    }
    return record, audit


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Directly restore original practical scope for residual v2.4.1 coding "
            "questions without regenerating reference answers."
        )
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--source-benchmark", type=Path, default=V23_RELEASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    candidates = {
        str(row.get("id") or ""): row for row in iter_jsonl(args.input)
    }
    selected_ids = [
        str(row.get("id") or row.get("record_id") or "")
        for row in iter_jsonl(args.selection)
    ]
    if "" in selected_ids or len(selected_ids) != len(set(selected_ids)):
        raise ValueError("selection record IDs must be non-empty and unique")
    sources = {
        str(row.get("id") or ""): row
        for row in iter_jsonl(args.source_benchmark)
        if str(row.get("id") or "") in set(selected_ids)
    }
    missing = set(selected_ids) - set(candidates)
    missing_sources = set(selected_ids) - set(sources)
    if missing or missing_sources:
        raise ValueError(
            f"missing candidates={sorted(missing)[:10]}, "
            f"missing sources={sorted(missing_sources)[:10]}"
        )

    output: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    family_changes: Counter[str] = Counter()
    for record_id in selected_ids:
        repaired, audit = repair_record(candidates[record_id], sources[record_id])
        output.append(repaired)
        audits.append(audit)
        family_changes[
            f"{audit['prior_task_family']}->{audit['new_task_family']}"
        ] += 1
    audit_path = args.audit_output or args.output.with_suffix(".audit.jsonl")
    manifest_path = args.manifest or args.output.with_suffix(".manifest.json")
    write_jsonl(args.output, output)
    write_jsonl(audit_path, audits)
    manifest = {
        "schema_version": "memcalib-v241-direct-question-repair-manifest-v1",
        "inputs": {
            key: {"path": portable_path(path), "sha256": file_sha256(path)}
            for key, path in {
                "candidate": args.input,
                "selection": args.selection,
                "source_benchmark": args.source_benchmark,
            }.items()
        },
        "counts": {
            "selected": len(selected_ids),
            "output": len(output),
            "audit": len(audits),
        },
        "task_family_changes": dict(sorted(family_changes.items())),
        "outputs": {
            "records": {
                "path": portable_path(args.output),
                "sha256": file_sha256(args.output),
            },
            "audit": {
                "path": portable_path(audit_path),
                "sha256": file_sha256(audit_path),
            },
        },
    }
    write_json(manifest_path, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
