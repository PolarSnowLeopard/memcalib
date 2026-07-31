#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from memcalib_v23_common import canonical_sha256, file_sha256, portable_path
from memcalib_v24_coding_common import (
    V23_RELEASE,
    applicable_atoms,
    locked_supervision_fingerprint,
    stable_task_family,
)
from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PROMPT = (
    SCRIPT_DIR / "prompts" / "rewrite_memcalib_v241_locked_surface_en.txt"
)
REQUEST_SCHEMA = "memcalib-v241-locked-surface-requests-v1"


def correction_evidence(atom: dict[str, Any]) -> list[str]:
    contract = atom.get("counterfactual_contract")
    if isinstance(contract, dict):
        evidence = contract.get("minimal_evidence")
        if isinstance(evidence, list):
            output = [
                str(item).strip()
                for item in evidence
                if isinstance(item, str) and item.strip()
            ][:3]
            if output:
                return output
        behavior = contract.get("with_memory_behavior")
        if isinstance(behavior, str) and behavior.strip():
            return [behavior.strip()]
    return [str(atom.get("text") or "").strip()]


def locked_requirements(record: dict[str, Any]) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    for atom in applicable_atoms(record):
        action = str(atom.get("memory_action") or "")
        evidence = (
            correction_evidence(atom)
            if action == "correct"
            else [str(atom.get("text") or "").strip()]
        )
        requirements.append(
            {
                "atom_id": str(atom.get("atom_id") or ""),
                "role": "primary" if atom.get("u_star") == "C" else "supporting",
                "action": action,
                "required_evidence": evidence,
            }
        )
    return requirements


def render_prompt(
    record: dict[str, Any],
    template: str,
    requirements: list[dict[str, Any]],
) -> str:
    values = {
        "{record_id}": str(record.get("id") or ""),
        "{task_family}": stable_task_family(str(record.get("id") or "")),
        "{source_topic}": str(record.get("source_topic") or "coding_other"),
        "{original_question}": str(record.get("question") or ""),
        "{requirements_json}": json.dumps(
            requirements, ensure_ascii=False, indent=2
        ),
    }
    output = template
    for placeholder, value in values.items():
        output = output.replace(placeholder, value)
    return output


def build_request(
    record: dict[str, Any],
    template: str,
    retry_round: int,
) -> dict[str, Any]:
    record_id = str(record.get("id") or "")
    requirements = locked_requirements(record)
    family = stable_task_family(record_id)
    return {
        "request_id": f"v241_locked_surface_r{retry_round}:{record_id}",
        "prompt": [
            {
                "role": "user",
                "content": render_prompt(record, template, requirements),
            }
        ],
        "user_defined_params": {
            "schema_version": REQUEST_SCHEMA,
            "record_id": record_id,
            "task_family": family,
            "source_record_fingerprint": canonical_sha256(record),
            "locked_supervision_fingerprint": locked_supervision_fingerprint(record),
            "memory_blocks_fingerprint": canonical_sha256(
                record.get("memory_blocks") or []
            ),
            "locked_requirements": requirements,
            "retry_round": retry_round,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare attribution-locked v2.4.1 coding surface rewrites."
    )
    parser.add_argument("--benchmark", type=Path, default=V23_RELEASE)
    parser.add_argument("--selection-jsonl", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--prompt-template", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--retry-round", type=int, default=1)
    args = parser.parse_args()

    selected_ids: set[str] = set()
    selection_inputs: list[dict[str, Any]] = []
    for path in args.selection_jsonl:
        rows = list(iter_jsonl(path))
        ids = {
            str(row.get("record_id") or row.get("id") or "")
            for row in rows
            if str(row.get("record_id") or row.get("id") or "")
        }
        selected_ids.update(ids)
        selection_inputs.append(
            {
                "path": portable_path(path),
                "sha256": file_sha256(path),
                "records": len(rows),
                "unique_ids": len(ids),
            }
        )

    template = args.prompt_template.read_text(encoding="utf-8")
    records = [
        record
        for record in iter_jsonl(args.benchmark)
        if record.get("domain") == "coding"
        and str(record.get("id") or "") in selected_ids
    ]
    found_ids = {str(record.get("id") or "") for record in records}
    missing = selected_ids - found_ids
    if missing:
        raise ValueError(f"selection IDs missing from benchmark: {sorted(missing)[:10]}")
    requests = [
        build_request(record, template, args.retry_round) for record in records
    ]
    request_ids = [str(row["request_id"]) for row in requests]
    if len(request_ids) != len(set(request_ids)):
        raise ValueError("request IDs must be unique")
    write_jsonl(args.output, requests)

    role_counts = Counter(
        requirement["role"]
        for request in requests
        for requirement in request["user_defined_params"]["locked_requirements"]
    )
    action_counts = Counter(
        requirement["action"]
        for request in requests
        for requirement in request["user_defined_params"]["locked_requirements"]
    )
    manifest = {
        "schema_version": REQUEST_SCHEMA,
        "inputs": {
            "benchmark": {
                "path": portable_path(args.benchmark),
                "sha256": file_sha256(args.benchmark),
            },
            "selection": selection_inputs,
        },
        "implementation": {
            "prepare": {
                "path": portable_path(Path(__file__)),
                "sha256": file_sha256(Path(__file__)),
            },
            "prompt": {
                "path": portable_path(args.prompt_template),
                "sha256": file_sha256(args.prompt_template),
            },
        },
        "parameters": {"retry_round": args.retry_round},
        "distribution": {
            "records": len(records),
            "roles": dict(role_counts),
            "actions": dict(action_counts),
        },
        "output": {
            "path": portable_path(args.output),
            "sha256": file_sha256(args.output),
            "requests": len(requests),
            "unique_request_ids": len(set(request_ids)),
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
