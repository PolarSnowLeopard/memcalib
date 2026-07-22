#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation.common import iter_jsonl, write_json, write_jsonl
from evaluation.scripts.prepare_answer_requests import build_answer_messages


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN = ROOT / "sft/runs/memcalib-v23-sft-pilot-500"
DEFAULT_SYSTEM = ROOT / "evaluation/prompts/answer-system.txt"


def index_unique(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    result = {str(row[key]): row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"duplicate {key} values")
    return result


def inspect_judgment(
    row: dict[str, Any], expected_actions: dict[str, str] | None = None
) -> dict[str, Any]:
    expected_actions = expected_actions or {}
    atom_errors = []
    auxiliary_errors = []
    over_budget = 0
    under_budget = 0
    rank = {"A": 0, "B": 1, "C": 2}
    for atom in row.get("atom_judgments") or []:
        gold = str(atom.get("u_star") or "")
        predicted = atom.get("predicted_usage_level")
        atom_id = str(atom.get("atom_id") or "")
        if atom.get("scorable") is not True or predicted not in rank or gold not in rank:
            atom_errors.append(f"unscorable:{atom_id}")
            continue
        delta = rank[str(predicted)] - rank[gold]
        over_budget += max(delta, 0)
        under_budget += max(-delta, 0)
        if delta:
            atom_errors.append(f"usage_mismatch:{atom_id}:{gold}->{predicted}")
        if atom.get("explicit_contradiction") is True and expected_actions.get(atom_id) != "correct":
            auxiliary_errors.append(f"explicit_contradiction:{atom_id}")
        if atom.get("constraint_violation") is True:
            auxiliary_errors.append(f"constraint_violation:{atom_id}")
    if row.get("safety_failure") is True:
        auxiliary_errors.append("safety_failure")
    if int(row.get("task_quality") or 0) < 3:
        auxiliary_errors.append(f"task_quality_below_3:{row.get('task_quality')}")
    return {
        "strict": not atom_errors and not auxiliary_errors,
        "over_budget": over_budget,
        "under_budget": under_budget,
        "task_quality": row.get("task_quality"),
        "atom_errors": atom_errors,
        "auxiliary_errors": auxiliary_errors,
    }


def swift_record(sample: dict[str, Any], response: str, system_prompt: str) -> dict[str, Any]:
    messages = build_answer_messages(sample, "full_memory", system_prompt)
    converted = [
        {"role": message["role"], "content": message["content"], "loss": False}
        for message in messages
    ]
    converted.append({"role": "assistant", "content": response.strip(), "loss": True})
    return {"messages": converted}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hidden", type=Path, default=DEFAULT_RUN / "pilot.hidden.jsonl")
    parser.add_argument(
        "--answers", type=Path, default=DEFAULT_RUN / "answers/qwen37max-teacher/full_memory.jsonl"
    )
    parser.add_argument("--primary", type=Path, default=DEFAULT_RUN / "judgments/primary.valid.jsonl")
    parser.add_argument(
        "--secondary", type=Path, default=DEFAULT_RUN / "judgments/secondary-deepseek.valid.jsonl"
    )
    parser.add_argument("--system-prompt", type=Path, default=DEFAULT_SYSTEM)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RUN / "sft")
    args = parser.parse_args()

    samples = index_unique(list(iter_jsonl(args.hidden)), "id")
    answers = index_unique(list(iter_jsonl(args.answers)), "request_id")
    primary = index_unique(list(iter_jsonl(args.primary)), "answer_request_id")
    secondary = index_unique(list(iter_jsonl(args.secondary)), "answer_request_id")
    system_prompt = args.system_prompt.read_text(encoding="utf-8")

    primary_rows = []
    dual_rows = []
    audit_rows = []
    rejected_rows = []
    status_counts: Counter[str] = Counter()
    total_by_domain: Counter[str] = Counter()
    dual_by_domain: Counter[str] = Counter()
    total_by_difficulty: Counter[str] = Counter()
    dual_by_difficulty: Counter[str] = Counter()
    reason_types: Counter[str] = Counter()
    correction_counts: Counter[str] = Counter()
    for answer_id, answer in answers.items():
        params = answer.get("user_defined_params") or {}
        sample_id = str(params.get("sample_id") or "")
        sample = samples.get(sample_id)
        p_row = primary.get(answer_id)
        s_row = secondary.get(answer_id)
        if sample is None or p_row is None or s_row is None:
            missing = [
                name
                for name, value in (("sample", sample), ("primary", p_row), ("secondary", s_row))
                if value is None
            ]
            status = "incomplete"
            p_check = None
            s_check = None
            reasons = ["missing:" + ",".join(missing)]
        else:
            expected_actions = {
                str(memory["atom_id"]): str(memory["memory_action"])
                for memory in sample.get("memories") or []
            }
            p_check = inspect_judgment(p_row, expected_actions)
            s_check = inspect_judgment(s_row, expected_actions)
            if p_check["strict"] and s_check["strict"]:
                status = "dual_strict"
                reasons = []
            elif p_check["strict"]:
                status = "primary_strict_secondary_review"
                reasons = s_check["atom_errors"] + s_check["auxiliary_errors"]
            else:
                status = "rejected"
                reasons = p_check["atom_errors"] + p_check["auxiliary_errors"]

        response = str(answer.get("response") or "").strip()
        response_sha = hashlib.sha256(response.encode("utf-8")).hexdigest()
        audit = {
            "answer_request_id": answer_id,
            "sample_id": sample_id,
            "status": status,
            "response_sha256": response_sha,
            "primary": p_check,
            "secondary": s_check,
            "reasons": reasons,
        }
        audit_rows.append(audit)
        status_counts[status] += 1
        if sample is not None:
            domain = str(sample.get("domain") or "unknown")
            level = str(
                (sample.get("composite_block_revision") or {}).get("difficulty_level") or "unassigned"
            )
            has_correction = any(
                str(memory.get("memory_action") or "") == "correct"
                for memory in sample.get("memories") or []
            )
            total_by_domain[domain] += 1
            total_by_difficulty[level] += 1
            correction_counts["total_correct" if has_correction else "total_noncorrect"] += 1
            if status == "dual_strict":
                dual_by_domain[domain] += 1
                dual_by_difficulty[level] += 1
                correction_counts["dual_correct" if has_correction else "dual_noncorrect"] += 1
        for reason in reasons:
            reason_types[str(reason).split(":", 1)[0]] += 1
        if sample is not None and p_check is not None and p_check["strict"]:
            primary_rows.append(swift_record(sample, response, system_prompt))
        if sample is not None and status == "dual_strict":
            dual_rows.append(swift_record(sample, response, system_prompt))
        if status != "dual_strict":
            rejected_rows.append({**audit, "response": response})

    write_jsonl(args.output_dir / "swift-sft.primary-strict.jsonl", primary_rows)
    write_jsonl(args.output_dir / "swift-sft.dual-strict.jsonl", dual_rows)
    write_jsonl(args.output_dir / "target-admission.audit.jsonl", audit_rows)
    write_jsonl(args.output_dir / "target-admission.non-dual-strict.jsonl", rejected_rows)
    summary = {
        "schema_version": "memcalib-v23-sft-target-admission-v1",
        "answers": len(answers),
        "primary_judgments": len(primary),
        "secondary_judgments": len(secondary),
        "status": dict(sorted(status_counts.items())),
        "primary_strict_sft": len(primary_rows),
        "dual_strict_sft": len(dual_rows),
        "policy": {
            "all_atoms_scorable": True,
            "predicted_usage_equals_gold": True,
            "max_over_budget": 0,
            "max_under_budget": 0,
            "explicit_contradiction": "allowed_only_for_memory_action_correct",
            "constraint_violation": False,
            "safety_failure": False,
            "minimum_task_quality": 3,
        },
        "diagnostics": {
            "dual_strict_by_domain": {
                key: {
                    "passed": dual_by_domain[key],
                    "total": total_by_domain[key],
                    "rate": dual_by_domain[key] / total_by_domain[key],
                }
                for key in sorted(total_by_domain)
            },
            "dual_strict_by_difficulty": {
                key: {
                    "passed": dual_by_difficulty[key],
                    "total": total_by_difficulty[key],
                    "rate": dual_by_difficulty[key] / total_by_difficulty[key],
                }
                for key in sorted(total_by_difficulty)
            },
            "correction_records": {
                "passed": correction_counts["dual_correct"],
                "total": correction_counts["total_correct"],
                "rate": correction_counts["dual_correct"] / correction_counts["total_correct"]
                if correction_counts["total_correct"]
                else None,
            },
            "noncorrection_records": {
                "passed": correction_counts["dual_noncorrect"],
                "total": correction_counts["total_noncorrect"],
                "rate": correction_counts["dual_noncorrect"] / correction_counts["total_noncorrect"]
                if correction_counts["total_noncorrect"]
                else None,
            },
            "non_dual_strict_reason_types": dict(sorted(reason_types.items())),
        },
    }
    write_json(args.output_dir / "target-admission.summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
