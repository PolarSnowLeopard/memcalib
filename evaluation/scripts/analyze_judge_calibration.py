#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation.common import display_path, iter_jsonl, sha256_file, write_json
from evaluation.scripts.analyze_evaluation import compute_judge_agreement, compute_judge_output_quality


ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = ROOT / "evaluation" / "runs" / "memcalib-ordered-v2-500" / "calibration"
DEFAULT_PRIMARY = RUN_ROOT / "judgments" / "primary.valid.jsonl"
DEFAULT_SECONDARY = RUN_ROOT / "judgments" / "secondary.valid.jsonl"
DEFAULT_OUTPUT = (
    ROOT / "evaluation" / "releases" / "memcalib-ordered-v2-500" / "calibration-summary.json"
)
DEFAULT_REQUEST_MANIFEST = (
    ROOT / "evaluation" / "releases" / "memcalib-ordered-v2-500" / "calibration-request.manifest.json"
)


def ordered_protocol_summary(
    rows: list[dict[str, Any]], expected_protocol: str = "ordered-usage-v2"
) -> dict[str, Any]:
    atoms = [atom for row in rows for atom in row.get("atom_judgments") or []]
    scorable = [atom for atom in atoms if atom.get("scorable") is True]
    matrix = {gold: {predicted: 0 for predicted in ("A", "B", "C")} for gold in ("A", "B", "C")}
    complete = bool(atoms)
    for atom in atoms:
        if atom.get("scorable") is True and atom.get("predicted_usage_level") in ("A", "B", "C"):
            matrix[str(atom["u_star"])][str(atom["predicted_usage_level"])] += 1
        elif atom.get("scorable") is False and atom.get("predicted_usage_level") is None:
            continue
        else:
            complete = False
    return {
        "rows": len(rows),
        "protocol_rows": sum(row.get("judge_protocol") == expected_protocol for row in rows),
        "atoms": len(atoms),
        "scorable_atoms": len(scorable),
        "scorable_coverage": len(scorable) / len(atoms) if atoms else None,
        "full_confusion_available": complete,
        "gold_counts": dict(sorted(Counter(str(atom.get("u_star")) for atom in atoms).items())),
        "prediction_counts": dict(
            sorted(Counter(str(atom.get("predicted_usage_level")) for atom in scorable).items())
        ),
        "confusion_matrix": matrix if complete else None,
        "contradiction_rate": sum(bool(atom.get("contradiction")) for atom in scorable) / len(scorable)
        if scorable and expected_protocol == "ordered-usage-v2"
        else None,
        "explicit_contradiction_rate": sum(bool(atom.get("explicit_contradiction")) for atom in scorable)
        / len(scorable)
        if scorable and expected_protocol == "ordered-usage-v2.1"
        else None,
        "constraint_violation_rate": sum(bool(atom.get("constraint_violation")) for atom in scorable)
        / len(scorable)
        if scorable and expected_protocol == "ordered-usage-v2.1"
        else None,
    }


def summarize_calibration(
    primary: list[dict[str, Any]],
    secondary: list[dict[str, Any]],
    *,
    expected_answers: int,
    expected_protocol: str = "ordered-usage-v2",
    human_review: str = "pending",
) -> dict[str, Any]:
    primary_protocol = ordered_protocol_summary(primary, expected_protocol)
    secondary_protocol = ordered_protocol_summary(secondary, expected_protocol)
    agreement = compute_judge_agreement(primary, secondary)
    ordered = agreement.get("ordered_usage") or {}
    checks = {
        "primary_complete": len(primary) == expected_answers,
        "secondary_complete": len(secondary) == expected_answers,
        "primary_protocol_complete": primary_protocol["protocol_rows"] == expected_answers
        and primary_protocol["full_confusion_available"],
        "secondary_protocol_complete": secondary_protocol["protocol_rows"] == expected_answers
        and secondary_protocol["full_confusion_available"],
        "ordered_exact_at_least_0.80": (ordered.get("exact_agreement") or 0) >= 0.80,
        "linear_weighted_kappa_at_least_0.70": (ordered.get("linear_weighted_kappa") or 0) >= 0.70,
        "scorable_agreement_at_least_0.95": (agreement.get("scorable_exact_agreement") or 0) >= 0.95,
    }
    failed = [name for name, passed in checks.items() if not passed]
    agreement_slices = {}
    diagnostic_flags = []
    for field in ("model_key", "condition", "panel"):
        agreement_slices[field] = {}
        for value in sorted({str(row[field]) for row in primary}):
            primary_slice = [row for row in primary if str(row[field]) == value]
            answer_ids = {str(row["answer_request_id"]) for row in primary_slice}
            secondary_slice = [row for row in secondary if str(row["answer_request_id"]) in answer_ids]
            slice_agreement = compute_judge_agreement(primary_slice, secondary_slice)
            agreement_slices[field][value] = slice_agreement
            ordered_slice = slice_agreement.get("ordered_usage") or {}
            if ordered_slice.get("n", 0) >= 50 and (
                (ordered_slice.get("exact_agreement") or 0) < 0.80
                or (ordered_slice.get("linear_weighted_kappa") or 0) < 0.70
            ):
                diagnostic_flags.append(f"low_ordered_agreement:{field}:{value}")
    if failed:
        status = "automatic_checks_failed"
    elif diagnostic_flags:
        status = "automatic_checks_passed_with_flags"
    else:
        status = "automatic_checks_passed"
    return {
        "schema_version": "memcalib-ordered-judge-calibration-summary-v2",
        "judge_protocol": expected_protocol,
        "status": status,
        "expected_answers": expected_answers,
        "checks": checks,
        "failed_checks": failed,
        "diagnostic_flags": diagnostic_flags,
        "human_review": human_review,
        "primary_protocol": primary_protocol,
        "secondary_protocol": secondary_protocol,
        "agreement": agreement,
        "agreement_slices": agreement_slices,
        "output_quality": {
            "primary": compute_judge_output_quality(primary),
            "secondary": compute_judge_output_quality(secondary),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze ordered-usage-v2 Judge calibration results.")
    parser.add_argument("--primary", type=Path, default=DEFAULT_PRIMARY)
    parser.add_argument("--secondary", type=Path, default=DEFAULT_SECONDARY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--request-manifest", type=Path, default=DEFAULT_REQUEST_MANIFEST)
    parser.add_argument("--expected-answers", type=int, default=100)
    parser.add_argument("--protocol", default="ordered-usage-v2")
    parser.add_argument("--human-review-status", default="pending")
    parser.add_argument("--expert-anchor", type=Path)
    args = parser.parse_args()
    summary = summarize_calibration(
        list(iter_jsonl(args.primary)),
        list(iter_jsonl(args.secondary)),
        expected_answers=args.expected_answers,
        expected_protocol=args.protocol,
        human_review=args.human_review_status,
    )
    summary["inputs"] = {
        "request_manifest": {
            "path": display_path(args.request_manifest, ROOT),
            "sha256": sha256_file(args.request_manifest),
        },
        "primary_judgments": {
            "path": display_path(args.primary, ROOT),
            "sha256": sha256_file(args.primary),
        },
        "secondary_judgments": {
            "path": display_path(args.secondary, ROOT),
            "sha256": sha256_file(args.secondary),
        },
    }
    if args.expert_anchor:
        summary["inputs"]["expert_anchor"] = {
            "path": display_path(args.expert_anchor, ROOT),
            "sha256": sha256_file(args.expert_anchor),
        }
    run_root = args.primary.parent.parent
    resolution = {"api_validation": {}, "postprocess_initial": {}, "targeted_retries": {}}
    for key in ("primary", "secondary-deepseek", "secondary-kimi"):
        validation_path = run_root / "api" / f"{key}.validation.json"
        postprocess_path = run_root / "judgments" / f"{key}.summary.json"
        if validation_path.exists():
            resolution["api_validation"][key] = json.loads(validation_path.read_text(encoding="utf-8"))
        if postprocess_path.exists():
            resolution["postprocess_initial"][key] = json.loads(postprocess_path.read_text(encoding="utf-8"))
    for path in sorted((run_root / "judgments").glob("*.retry*.summary.json")):
        resolution["targeted_retries"][path.name] = json.loads(path.read_text(encoding="utf-8"))
    summary["resolution"] = resolution
    write_json(args.output, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    raise SystemExit(0 if summary["status"] != "automatic_checks_failed" else 1)


if __name__ == "__main__":
    main()
