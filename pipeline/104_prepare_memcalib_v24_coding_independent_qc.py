#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from memcalib_v23_common import canonical_sha256, file_sha256, portable_path
from memcalib_v24_coding_common import V24_DIR, locked_supervision_fingerprint
from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = V24_DIR / "memcalib_v24_coding_rewrite_3750.valid.jsonl"
DEFAULT_OUTPUT = V24_DIR / "memcalib_v24_coding_independent_qc_input_3750.jsonl"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")
DEFAULT_PROMPT = (
    SCRIPT_DIR
    / "prompts"
    / "verify_memcalib_v24_coding_text_observability_en.txt"
)
REQUEST_SCHEMA = "memcalib-v24-coding-text-independent-qc-requests-v1"


def compact_record(record: dict[str, Any]) -> dict[str, Any]:
    atoms = {
        str(atom.get("atom_id") or ""): atom for atom in record.get("memories") or []
    }
    return {
        "record_id": record.get("id"),
        "task_family": record.get("coding_text_observability_revision", {}).get(
            "task_family"
        ),
        "question": record.get("question"),
        "reference_answer": record.get("source_answer"),
        "memory_blocks": [
            {
                "parent_memory_id": block.get("parent_memory_id"),
                "memory_text": block.get("memory_text"),
                "atoms": [
                    {
                        "atom_id": atom_id,
                        "text": atoms[atom_id].get("text"),
                        "u_star": atoms[atom_id].get("u_star"),
                        "memory_action": atoms[atom_id].get("memory_action"),
                        "counterfactual_contract": atoms[atom_id].get(
                            "counterfactual_contract"
                        ),
                        "usage_rubric": atoms[atom_id].get("usage_rubric"),
                    }
                    for raw_atom_id in block.get("atom_ids") or []
                    if (atom_id := str(raw_atom_id)) in atoms
                ],
            }
            for block in record.get("memory_blocks") or []
        ],
    }


def render_prompt(record: dict[str, Any], template: str) -> str:
    return template.replace(
        "{record_json}",
        json.dumps(compact_record(record), ensure_ascii=False, indent=2),
    )


def build_request(record: dict[str, Any], template: str) -> dict[str, Any]:
    record_id = str(record.get("id") or "")
    params = {
        "schema_version": REQUEST_SCHEMA,
        "record_id": record_id,
        "record_fingerprint": canonical_sha256(record),
        "locked_supervision_fingerprint": locked_supervision_fingerprint(record),
        "task_family": record.get("coding_text_observability_revision", {}).get(
            "task_family"
        ),
        "expected_atom_ids": [
            str(atom.get("atom_id") or "") for atom in record.get("memories") or []
        ],
    }
    return {
        "request_id": f"v24_coding_independent_qc:{record_id}",
        "prompt": [{"role": "user", "content": render_prompt(record, template)}],
        "user_defined_params": params,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare independent QC for MemCalib v2.4 coding answer-text "
            "observability revisions."
        )
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--prompt-template", type=Path, default=DEFAULT_PROMPT)
    args = parser.parse_args()

    records = list(iter_jsonl(args.input))
    record_ids = [str(record.get("id") or "") for record in records]
    if "" in record_ids or len(record_ids) != len(set(record_ids)):
        raise ValueError("input record IDs must be non-empty and unique")
    if any(record.get("domain") != "coding" for record in records):
        raise ValueError("independent coding QC input contains a non-coding record")
    template = args.prompt_template.read_text(encoding="utf-8")
    requests = [build_request(record, template) for record in records]
    write_jsonl(args.output, requests)
    manifest = {
        "schema_version": REQUEST_SCHEMA,
        "input": {
            "path": portable_path(args.input),
            "sha256": file_sha256(args.input),
            "records": len(records),
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
        "distribution": {
            "task_family": dict(
                sorted(
                    Counter(
                        request["user_defined_params"]["task_family"]
                        for request in requests
                    ).items()
                )
            ),
            "atoms": sum(
                len(request["user_defined_params"]["expected_atom_ids"])
                for request in requests
            ),
        },
        "output": {
            "path": portable_path(args.output),
            "sha256": file_sha256(args.output),
            "requests": len(requests),
            "unique_request_ids": len(
                {request["request_id"] for request in requests}
            ),
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
