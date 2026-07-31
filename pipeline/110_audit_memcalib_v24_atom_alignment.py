#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from memcalib_v23_common import file_sha256, portable_path
from memcalib_v24_alignment import analyze_atom_alignment
from memcalib_v24_coding_common import V24_DIR
from utils import iter_jsonl, write_json, write_jsonl


DEFAULT_INPUT = (
    V24_DIR / "release" / "memcalib_v24_multidomain_benchmark_15000.jsonl"
)
DEFAULT_PREFIX = V24_DIR / "audit" / "memcalib_v24_atom_alignment"

def expected_behavior(atom: dict[str, Any]) -> str:
    rubric = atom.get("usage_rubric")
    if not isinstance(rubric, dict):
        return ""
    return str(rubric.get("expected_answer_behavior") or "")


def audit_record(record: dict[str, Any]) -> dict[str, Any] | None:
    if record.get("domain") != "coding":
        return None
    applicable = [
        atom
        for atom in record.get("memories") or []
        if atom.get("u_star") in {"B", "C"}
    ]
    question = str(record.get("question") or "")
    findings: list[dict[str, Any]] = []
    for atom in applicable:
        atom_id = str(atom.get("atom_id") or "")
        expected = expected_behavior(atom)
        analysis = analyze_atom_alignment(atom, expected, applicable, question)
        reasons = analysis["reasons"]
        if not reasons:
            continue
        findings.append(
            {
                "atom_id": atom_id,
                "u_star": atom.get("u_star"),
                "memory_action": atom.get("memory_action"),
                "reasons": reasons,
                **{key: value for key, value in analysis.items() if key != "reasons"},
                "atom_text": atom.get("text"),
                "expected_answer_behavior": expected,
            }
        )
    if not findings:
        return None
    return {
        "schema_version": "memcalib-v24-atom-alignment-audit-v1",
        "record_id": record.get("id"),
        "domain": record.get("domain"),
        "source_dataset": record.get("source_dataset"),
        "question": question,
        "findings": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Flag deterministic atom/rubric and query-alignment risks."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--prefix", type=Path, default=DEFAULT_PREFIX)
    args = parser.parse_args()

    records = list(iter_jsonl(args.input))
    coding = [record for record in records if record.get("domain") == "coding"]
    flagged = [
        finding
        for record in coding
        if (finding := audit_record(record)) is not None
    ]
    reason_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    flagged_atom_count = 0
    for record in flagged:
        for finding in record["findings"]:
            flagged_atom_count += 1
            label_counts[str(finding["u_star"])] += 1
            reason_counts.update(finding["reasons"])

    output_path = args.prefix.with_suffix(".flagged.jsonl")
    summary_path = args.prefix.with_suffix(".summary.json")
    write_jsonl(output_path, flagged)
    summary = {
        "schema_version": "memcalib-v24-atom-alignment-audit-summary-v1",
        "scope": {
            "input": {
                "path": portable_path(args.input),
                "sha256": file_sha256(args.input),
                "records": len(records),
            },
            "coding_records": len(coding),
        },
        "results": {
            "flagged_records": len(flagged),
            "flagged_record_rate": len(flagged) / len(coding) if coding else 0.0,
            "flagged_atoms": flagged_atom_count,
            "reason_counts": dict(sorted(reason_counts.items())),
            "label_counts": dict(sorted(label_counts.items())),
        },
        "interpretation": {
            "status": "high_recall_candidate_screen_not_final_semantic_adjudication",
            "safe_claim": (
                "Flagged rows require semantic review. Unflagged rows are not "
                "automatically proven correct."
            ),
        },
        "outputs": {
            "flagged": {
                "path": portable_path(output_path),
                "sha256": file_sha256(output_path),
            }
        },
    }
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
