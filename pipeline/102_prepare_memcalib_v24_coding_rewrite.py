#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from memcalib_v23_common import canonical_sha256, file_sha256, portable_path
from memcalib_v24_coding_common import (
    TASK_FAMILIES,
    V23_RELEASE,
    V24_DIR,
    applicable_atoms,
    locked_supervision_fingerprint,
    stable_task_family,
)
from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = V24_DIR / "memcalib_v24_coding_rewrite_input_3750.jsonl"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")
DEFAULT_PROMPT = (
    SCRIPT_DIR / "prompts" / "rewrite_memcalib_v24_coding_as_text_reasoning_en.txt"
)
REQUEST_SCHEMA = "memcalib-v24-coding-text-rewrite-requests-v1"


def compact_blocks(record: dict[str, Any]) -> list[dict[str, Any]]:
    atoms = {
        str(atom.get("atom_id") or ""): atom for atom in record.get("memories") or []
    }
    return [
        {
            "parent_memory_id": block.get("parent_memory_id"),
            "memory_text": block.get("memory_text"),
            "atoms": [
                {
                    "atom_id": atom_id,
                    "text": atoms[atom_id].get("text"),
                    "u_star": atoms[atom_id].get("u_star"),
                    "memory_action": atoms[atom_id].get("memory_action"),
                }
                for raw_atom_id in block.get("atom_ids") or []
                if (atom_id := str(raw_atom_id)) in atoms
            ],
        }
        for block in record.get("memory_blocks") or []
    ]


def render_prompt(
    record: dict[str, Any],
    task_family: str,
    template: str,
    retry_feedback: list[str] | None = None,
) -> str:
    replacements = {
        "{record_id}": str(record.get("id") or ""),
        "{task_family}": task_family,
        "{original_question}": str(record.get("question") or ""),
        "{original_reference_answer}": str(record.get("source_answer") or ""),
        "{blocks_json}": json.dumps(
            compact_blocks(record), ensure_ascii=False, indent=2
        ),
        "{retry_feedback}": json.dumps(
            retry_feedback or ["None. This is the first attempt."],
            ensure_ascii=False,
            indent=2,
        ),
    }
    content = template
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    return content


def build_request(
    record: dict[str, Any],
    template: str,
    task_family: str | None = None,
    retry_feedback: list[str] | None = None,
    retry_round: int = 0,
) -> dict[str, Any]:
    record_id = str(record.get("id") or "")
    family = task_family or stable_task_family(record_id)
    if family not in TASK_FAMILIES:
        raise ValueError(f"unsupported task family: {family}")
    applicable = applicable_atoms(record)
    params = {
        "schema_version": REQUEST_SCHEMA,
        "record_id": record_id,
        "source_record_fingerprint": canonical_sha256(record),
        "locked_supervision_fingerprint": locked_supervision_fingerprint(record),
        "memory_blocks_fingerprint": canonical_sha256(record.get("memory_blocks") or []),
        "task_family": family,
        "retry_round": retry_round,
        "retry_feedback_fingerprint": canonical_sha256(retry_feedback or []),
        "expected_applicable_atoms": [
            {
                "atom_id": str(atom.get("atom_id") or ""),
                "u_star": atom.get("u_star"),
                "memory_action": atom.get("memory_action"),
            }
            for atom in applicable
        ],
    }
    request_prefix = (
        "v24_coding_rewrite"
        if retry_round == 0
        else f"v24_coding_rewrite_retry{retry_round}"
    )
    return {
        "request_id": f"{request_prefix}:{record_id}",
        "prompt": [
            {
                "role": "user",
                "content": render_prompt(
                    record,
                    family,
                    template,
                    retry_feedback=retry_feedback,
                ),
            }
        ],
        "user_defined_params": params,
    }


def selection_data(
    paths: list[Path],
) -> tuple[set[str] | None, dict[str, list[str]]]:
    if not paths:
        return None, {}
    ids: set[str] = set()
    feedback: dict[str, list[str]] = {}
    for path in paths:
        for row in iter_jsonl(path):
            if row.get("domain") not in {None, "coding"}:
                continue
            record_id = str(row.get("id") or row.get("record_id") or "")
            ids.add(record_id)
            details: list[str] = []
            if isinstance(row.get("errors"), list):
                details.extend(f"Structural error: {error}" for error in row["errors"])
            qc = row.get("v24_coding_independent_qc")
            if isinstance(qc, dict):
                details.extend(
                    f"Independent QC: {reason}"
                    for reason in qc.get("decision_reasons") or []
                )
                judge = qc.get("judge_output")
                if isinstance(judge, dict):
                    for check in judge.get("record_checks") or []:
                        if (
                            isinstance(check, dict)
                            and check.get("verdict") != "pass"
                        ):
                            details.append(
                                "Record check "
                                f"{check.get('check')}={check.get('verdict')}: "
                                f"{check.get('reason')}"
                            )
                    for check in judge.get("atom_checks") or []:
                        if not isinstance(check, dict):
                            continue
                        nonpass = [
                            f"{key}={check.get(key)}"
                            for key in (
                                "label_action_validity",
                                "answer_text_observability",
                                "rubric_objectivity",
                                "query_value_status",
                            )
                            if check.get(key)
                            not in {"pass", "not_supplied", None}
                        ]
                        if nonpass:
                            details.append(
                                f"Atom {check.get('atom_id')} "
                                + ", ".join(nonpass)
                                + f": {check.get('reason')}"
                            )
            if details:
                feedback.setdefault(record_id, []).extend(details)
    if "" in ids:
        raise ValueError("selection contains an empty coding record ID")
    feedback = {
        record_id: list(dict.fromkeys(items))
        for record_id, items in feedback.items()
    }
    return ids, feedback


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare full MemCalib v2.4 coding rewrites as answer-text-observable "
            "reasoning tasks."
        )
    )
    parser.add_argument("--input", type=Path, default=V23_RELEASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--prompt-template", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument(
        "--selection-jsonl",
        type=Path,
        action="append",
        default=[],
        help="Optional JSONL whose coding IDs define a pilot subset.",
    )
    parser.add_argument(
        "--feedback-jsonl",
        type=Path,
        action="append",
        default=[],
        help=(
            "Optional QC JSONL used only to enrich retry feedback. Unlike "
            "--selection-jsonl, these files do not add record IDs to the target set."
        ),
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--retry-round", type=int, default=0)
    args = parser.parse_args()

    if args.retry_round < 0:
        raise ValueError("--retry-round must be non-negative")
    selected_ids, feedback_by_id = selection_data(args.selection_jsonl)
    _, extra_feedback_by_id = selection_data(args.feedback_jsonl)
    for record_id, items in extra_feedback_by_id.items():
        if selected_ids is not None and record_id not in selected_ids:
            continue
        feedback_by_id.setdefault(record_id, []).extend(items)
    feedback_by_id = {
        record_id: list(dict.fromkeys(items))
        for record_id, items in feedback_by_id.items()
    }
    all_records = list(iter_jsonl(args.input))
    source_ids = [str(record.get("id") or "") for record in all_records]
    if "" in source_ids or len(source_ids) != len(set(source_ids)):
        raise ValueError("input record IDs must be non-empty and unique")
    records = [
        record
        for record in all_records
        if record.get("domain") == "coding"
        and (selected_ids is None or str(record.get("id") or "") in selected_ids)
    ]
    if selected_ids is not None:
        observed = {str(record.get("id") or "") for record in records}
        missing = selected_ids - observed
        if missing:
            raise ValueError(f"selection IDs missing from input: {sorted(missing)[:20]}")
    if args.limit is not None:
        if args.limit <= 0:
            raise ValueError("--limit must be positive")
        records = records[: args.limit]
    if not records:
        raise ValueError("no coding records selected")

    template = args.prompt_template.read_text(encoding="utf-8")
    requests = [
        build_request(
            record,
            template,
            retry_feedback=feedback_by_id.get(str(record.get("id") or "")),
            retry_round=args.retry_round,
        )
        for record in records
    ]
    request_ids = [request["request_id"] for request in requests]
    if len(request_ids) != len(set(request_ids)):
        raise ValueError("request IDs are not unique")
    write_jsonl(args.output, requests)

    family_counts = Counter(
        request["user_defined_params"]["task_family"] for request in requests
    )
    applicable_counts = Counter(
        len(request["user_defined_params"]["expected_applicable_atoms"])
        for request in requests
    )
    manifest = {
        "schema_version": REQUEST_SCHEMA,
        "inputs": {
            "benchmark": {
                "path": portable_path(args.input),
                "sha256": file_sha256(args.input),
                "records": len(all_records),
                "coding_records": sum(
                    record.get("domain") == "coding" for record in all_records
                ),
            },
            "selection": (
                {
                    "sources": [
                        {
                            "path": portable_path(path),
                            "sha256": file_sha256(path),
                        }
                        for path in args.selection_jsonl
                    ],
                    "coding_ids": len(selected_ids or ()),
                }
                if args.selection_jsonl
                else None
            ),
            "feedback": (
                {
                    "sources": [
                        {
                            "path": portable_path(path),
                            "sha256": file_sha256(path),
                        }
                        for path in args.feedback_jsonl
                    ],
                    "records_with_feedback": len(feedback_by_id),
                }
                if args.feedback_jsonl
                else None
            ),
        },
        "implementation": {
            "prepare": {
                "path": portable_path(Path(__file__)),
                "sha256": file_sha256(Path(__file__).resolve()),
            },
            "prompt": {
                "path": portable_path(args.prompt_template),
                "sha256": file_sha256(args.prompt_template),
            },
        },
        "parameters": {
            "task_family_policy": {
                "implementation_plan": "stable hash buckets 0-4",
                "behavior_prediction": "stable hash buckets 5-7",
                "debugging_diagnosis": "stable hash buckets 8-9",
            },
            "labels_and_actions_locked": True,
            "memory_atoms_and_blocks_locked": True,
            "question_and_rubrics_rebuilt": True,
            "retry_round": args.retry_round,
            "records_with_retry_feedback": sum(
                bool(feedback_by_id.get(str(record.get("id") or "")))
                for record in records
            ),
        },
        "distribution": {
            "records": len(records),
            "task_family": dict(sorted(family_counts.items())),
            "applicable_atoms": sum(
                len(request["user_defined_params"]["expected_applicable_atoms"])
                for request in requests
            ),
            "applicable_atoms_per_record": dict(sorted(applicable_counts.items())),
        },
        "output": {
            "path": portable_path(args.output),
            "sha256": file_sha256(args.output),
            "requests": len(requests),
            "unique_request_ids": len(set(request_ids)),
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
