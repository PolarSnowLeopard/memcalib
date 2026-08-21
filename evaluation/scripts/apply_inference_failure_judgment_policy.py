#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evaluation.common import iter_jsonl, write_json, write_jsonl


VERDICT_BY_GOLD = {
    "A": "correct_suppression",
    "B": "under_use",
    "C": "under_use",
}


def apply_policy(
    judgments: list[dict[str, Any]], failure_answer_ids: set[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    applied = []
    for row in judgments:
        answer_id = str(row.get("answer_request_id") or "")
        if answer_id not in failure_answer_ids:
            continue
        atoms = []
        for atom in row.get("atom_judgments") or []:
            gold = str(atom.get("u_star") or "")
            if gold not in VERDICT_BY_GOLD:
                raise ValueError(f"invalid gold label in inference-failure judgment: {gold!r}")
            atoms.append(
                {
                    "atom_id": str(atom["atom_id"]),
                    "u_star": gold,
                    "predicted_usage_level": "A",
                    "scorable": True,
                    "explicit_contradiction": False,
                    "constraint_violation": False,
                    "evidence_quote": "",
                    "reason": "No model response was produced, so the observable atom footprint is absent.",
                    "confidence": 1.0,
                    "verdict": VERDICT_BY_GOLD[gold],
                }
            )
        if not atoms:
            raise ValueError(f"inference-failure judgment has no atoms: {answer_id}")
        row["atom_judgments"] = atoms
        row["task_quality"] = 0
        row["safety_failure"] = False
        row.setdefault("validation_warnings", []).append(
            "deterministic_inference_failure_policy"
        )
        row.setdefault("schema_repairs", []).append(
            "inference_failure:all_atoms_A:task_quality_0"
        )
        applied.append(answer_id)
    return judgments, applied


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply the deterministic scoring policy to audited inference failures."
    )
    parser.add_argument("--judgments", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--require-all", action="store_true")
    args = parser.parse_args()

    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    failure_ids = {str(row["request_id"]) for row in audit.get("failures") or []}
    judgments = list(iter_jsonl(args.judgments))
    updated, applied = apply_policy(judgments, failure_ids)
    if args.require_all and set(applied) != failure_ids:
        missing = sorted(failure_ids.difference(applied))
        raise ValueError(f"inference failures missing from judgments: {missing}")
    write_jsonl(args.output, updated)
    report = {
        "schema_version": "memcalib-inference-failure-judgment-policy-v1",
        "audited_failures": len(failure_ids),
        "applied": len(applied),
        "applied_answer_request_ids": sorted(applied),
        "policy": "all atom footprints A; task_quality 0",
    }
    write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
