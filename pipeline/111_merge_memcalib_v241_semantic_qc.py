#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any

from memcalib_v23_common import file_sha256, portable_path
from memcalib_v24_coding_common import V24_DIR
from utils import iter_jsonl, write_json, write_jsonl


AUDIT_DIR = V24_DIR / "audit"
DEFAULT_BENCHMARK = V24_DIR / "memcalib_v24_coding_complete_3750.jsonl"
DEFAULT_QWEN_PREFIX = AUDIT_DIR / "memcalib_v241_semantic_qc_qwen_3750"
DEFAULT_DEEPSEEK_PREFIX = AUDIT_DIR / "memcalib_v241_semantic_qc_deepseek_3750"
DEFAULT_DETERMINISTIC = (
    AUDIT_DIR / "memcalib_v24_atom_alignment.flagged.jsonl"
)
DEFAULT_PREFIX = AUDIT_DIR / "memcalib_v241_semantic_qc_consensus_3750"

SCHEMA_VERSION = "memcalib-v241-semantic-qc-consensus-v1"
HARD_DETERMINISTIC_REASONS = {
    "probable_cross_atom_rubric_swap",
    "probable_query_atom_value_leakage",
    "probable_query_rubric_value_leakage",
}


def partition_path(prefix: Path, decision: str) -> Path:
    return prefix.with_suffix(f".{decision}.jsonl")


def load_judge_partitions(prefix: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for decision in ("strict", "review", "reject", "invalid"):
        path = partition_path(prefix, decision)
        for row in iter_jsonl(path):
            record_id = str(row.get("id") or row.get("record_id") or "")
            if not record_id:
                raise ValueError(f"empty record ID in {path}")
            if record_id in rows:
                raise ValueError(
                    f"record {record_id} appears in multiple partitions for {prefix}"
                )
            normalized = "strict_pass" if decision == "strict" else decision
            qc = row.get("v24_coding_independent_qc")
            rows[record_id] = {
                "decision": normalized,
                "decision_reasons": (
                    list(qc.get("decision_reasons") or [])
                    if isinstance(qc, dict)
                    else []
                ),
                "judge_output": (
                    qc.get("judge_output") if isinstance(qc, dict) else None
                ),
                "structural_errors": list(row.get("errors") or []),
                "partition_path": portable_path(path),
            }
    return rows


def load_resolved_judge_partitions(
    prefixes: list[Path],
) -> dict[str, dict[str, Any]]:
    resolved: dict[str, dict[str, Any]] = {}
    for prefix in prefixes:
        current = load_judge_partitions(prefix)
        for record_id, row in current.items():
            prior = resolved.get(record_id)
            if prior is not None and prior["decision"] != "invalid":
                raise ValueError(
                    f"valid judge record was rerun unexpectedly: {record_id}"
                )
            resolved[record_id] = row
    return resolved


def load_deterministic_findings(
    path: Path,
) -> dict[str, list[dict[str, Any]]]:
    findings: dict[str, list[dict[str, Any]]] = {}
    for row in iter_jsonl(path):
        record_id = str(row.get("record_id") or "")
        if not record_id:
            raise ValueError(f"empty deterministic audit record ID in {path}")
        if record_id in findings:
            raise ValueError(f"duplicate deterministic audit record ID: {record_id}")
        findings[record_id] = list(row.get("findings") or [])
    return findings


def compact_finding(finding: dict[str, Any]) -> dict[str, Any]:
    return {
        "atom_id": finding.get("atom_id"),
        "u_star": finding.get("u_star"),
        "reasons": list(finding.get("reasons") or []),
        "atom_text": finding.get("atom_text"),
        "expected_answer_behavior": finding.get("expected_answer_behavior"),
        "best_other_atom_id": finding.get("best_other_atom_id"),
    }


def judge_feedback(name: str, judge: dict[str, Any]) -> list[str]:
    feedback = [
        f"{name} decision: {judge['decision']}",
        *[
            f"{name} decision reason: {reason}"
            for reason in judge.get("decision_reasons") or []
        ],
        *[
            f"{name} structural error: {error}"
            for error in judge.get("structural_errors") or []
        ],
    ]
    output = judge.get("judge_output")
    if isinstance(output, dict):
        for check in output.get("record_checks") or []:
            if isinstance(check, dict) and check.get("verdict") != "pass":
                feedback.append(
                    f"{name} record check {check.get('check')}="
                    f"{check.get('verdict')}: {check.get('reason')}"
                )
        for check in output.get("atom_checks") or []:
            if not isinstance(check, dict):
                continue
            verdicts = [
                f"{key}={check.get(key)}"
                for key in (
                    "label_action_validity",
                    "answer_text_observability",
                    "rubric_objectivity",
                    "query_value_status",
                )
                if check.get(key) not in {"pass", "not_supplied", None}
            ]
            if verdicts:
                feedback.append(
                    f"{name} atom {check.get('atom_id')} "
                    + ", ".join(verdicts)
                    + f": {check.get('reason')}"
                )
    return feedback


def build_consensus(
    benchmark: list[dict[str, Any]],
    qwen: dict[str, dict[str, Any]],
    deepseek: dict[str, dict[str, Any]],
    deterministic: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    strict: list[dict[str, Any]] = []
    repair: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    record_ids = [str(record.get("id") or "") for record in benchmark]
    if "" in record_ids or len(record_ids) != len(set(record_ids)):
        raise ValueError("benchmark record IDs must be non-empty and unique")
    for record in benchmark:
        record_id = str(record["id"])
        qwen_row = qwen.get(
            record_id,
            {
                "decision": "invalid",
                "decision_reasons": [],
                "structural_errors": ["judge_partition_missing"],
            },
        )
        deepseek_row = deepseek.get(
            record_id,
            {
                "decision": "invalid",
                "decision_reasons": [],
                "structural_errors": ["judge_partition_missing"],
            },
        )
        deterministic_findings = [
            compact_finding(finding)
            for finding in deterministic.get(record_id, [])
        ]
        hard_reasons = sorted(
            {
                reason
                for finding in deterministic_findings
                for reason in finding["reasons"]
                if reason in HARD_DETERMINISTIC_REASONS
            }
        )
        accepted = (
            qwen_row["decision"] == "strict_pass"
            and deepseek_row["decision"] == "strict_pass"
            and not hard_reasons
        )
        feedback = [
            *judge_feedback("qwen", qwen_row),
            *judge_feedback("deepseek", deepseek_row),
            *[
                "Deterministic audit "
                f"atom {finding.get('atom_id')}: {', '.join(finding['reasons'])}; "
                f"atom='{finding.get('atom_text')}'; "
                f"rubric='{finding.get('expected_answer_behavior')}'"
                for finding in deterministic_findings
            ],
        ]
        consensus = {
            "schema_version": SCHEMA_VERSION,
            "record_id": record_id,
            "decision": "strict_pass" if accepted else "repair",
            "qwen_decision": qwen_row["decision"],
            "deepseek_decision": deepseek_row["decision"],
            "hard_deterministic_reasons": hard_reasons,
            "deterministic_findings": deterministic_findings,
        }
        audit.append({**consensus, "feedback": feedback})
        if accepted:
            retained = copy.deepcopy(record)
            retained["v241_alignment_consensus"] = consensus
            strict.append(retained)
        else:
            repair.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "id": record_id,
                    "record_id": record_id,
                    "domain": "coding",
                    "errors": feedback,
                    "v241_alignment_consensus": consensus,
                }
            )
    extra_qwen = set(qwen) - set(record_ids)
    extra_deepseek = set(deepseek) - set(record_ids)
    if extra_qwen or extra_deepseek:
        raise ValueError(
            "judge partitions contain IDs outside benchmark: "
            f"qwen={sorted(extra_qwen)[:10]}, "
            f"deepseek={sorted(extra_deepseek)[:10]}"
        )
    return strict, repair, audit


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Merge two independent semantic QC passes with deterministic hard "
            "alignment blockers for MemCalib v2.4.1 coding repair selection."
        )
    )
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--qwen-prefix", type=Path, action="append")
    parser.add_argument(
        "--deepseek-prefix", type=Path, action="append"
    )
    parser.add_argument(
        "--deterministic-findings",
        type=Path,
        default=DEFAULT_DETERMINISTIC,
    )
    parser.add_argument("--prefix", type=Path, default=DEFAULT_PREFIX)
    args = parser.parse_args()

    benchmark = list(iter_jsonl(args.benchmark))
    qwen_prefixes = args.qwen_prefix or [DEFAULT_QWEN_PREFIX]
    deepseek_prefixes = args.deepseek_prefix or [DEFAULT_DEEPSEEK_PREFIX]
    qwen = load_resolved_judge_partitions(qwen_prefixes)
    deepseek = load_resolved_judge_partitions(deepseek_prefixes)
    deterministic = load_deterministic_findings(args.deterministic_findings)
    strict, repair, audit = build_consensus(
        benchmark,
        qwen,
        deepseek,
        deterministic,
    )
    paths = {
        "strict": args.prefix.with_suffix(".strict.jsonl"),
        "repair": args.prefix.with_suffix(".repair.jsonl"),
        "audit": args.prefix.with_suffix(".audit.jsonl"),
    }
    write_jsonl(paths["strict"], strict)
    write_jsonl(paths["repair"], repair)
    write_jsonl(paths["audit"], audit)
    pair_counts = Counter(
        (row["qwen_decision"], row["deepseek_decision"]) for row in audit
    )
    hard_reason_counts = Counter(
        reason
        for row in audit
        for reason in row["hard_deterministic_reasons"]
    )
    summary = {
        "schema_version": f"{SCHEMA_VERSION}-summary",
        "policy": {
            "retain_unchanged": (
                "qwen strict_pass AND deepseek strict_pass AND no deterministic "
                "hard blocker"
            ),
            "all_other_records": "targeted_rewrite",
            "hard_deterministic_reasons": sorted(HARD_DETERMINISTIC_REASONS),
        },
        "inputs": {
            "benchmark": {
                "path": portable_path(args.benchmark),
                "sha256": file_sha256(args.benchmark),
                "records": len(benchmark),
            },
            "qwen_prefixes": [portable_path(path) for path in qwen_prefixes],
            "deepseek_prefixes": [
                portable_path(path) for path in deepseek_prefixes
            ],
            "deterministic_findings": {
                "path": portable_path(args.deterministic_findings),
                "sha256": file_sha256(args.deterministic_findings),
            },
        },
        "counts": {
            "strict": len(strict),
            "repair": len(repair),
            "audit": len(audit),
            "judge_decision_pairs": {
                f"{left}|{right}": count
                for (left, right), count in sorted(pair_counts.items())
            },
            "hard_deterministic_reasons": dict(sorted(hard_reason_counts.items())),
        },
        "outputs": {
            key: {
                "path": portable_path(path),
                "sha256": file_sha256(path),
            }
            for key, path in paths.items()
        },
    }
    summary_path = args.prefix.with_suffix(".summary.json")
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
