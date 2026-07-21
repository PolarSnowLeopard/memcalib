#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from memcalib_v23_common import (
    V23_AUXILIARY_SOURCE,
    V23_DIR,
    atom_index,
    canonical_sha256,
    file_sha256,
    portable_path,
)
from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = V23_DIR / "memcalib_v23_rewritten_benchmark_15000.jsonl"
DEFAULT_OUTPUT = V23_DIR / "memcalib_v23_independent_qc_input_15000.jsonl"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")
DEFAULT_PROMPT = SCRIPT_DIR / "prompts" / "verify_memcalib_v23_composite_blocks_en.txt"
REQUEST_SCHEMA = "memcalib-v23-composite-independent-qc-requests-v1"


def compact_blocks(record: dict[str, Any]) -> list[dict[str, Any]]:
    atoms = atom_index(record)
    return [
        {
            "parent_memory_id": block.get("parent_memory_id"),
            "memory_text": block.get("memory_text"),
            "atoms": [
                {
                    "atom_id": str(atom_id),
                    "text": atoms[str(atom_id)].get("text"),
                    "audit_role": (
                        "added_auxiliary_A"
                        if atoms[str(atom_id)].get("source") == V23_AUXILIARY_SOURCE
                        else "locked_previously_audited"
                    ),
                }
                for atom_id in block.get("atom_ids") or []
            ],
        }
        for block in record.get("memory_blocks") or []
    ]


def render_prompt(record: dict[str, Any], template: str) -> str:
    replacements = {
        "{record_id}": str(record.get("id") or ""),
        "{domain}": str(record.get("domain") or "health_seed"),
        "{question}": str(record.get("question") or ""),
        "{blocks_json}": json.dumps(
            compact_blocks(record), ensure_ascii=False, indent=2
        ),
    }
    content = template
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    return content


def build_request(record: dict[str, Any], template: str) -> dict[str, Any]:
    atoms = atom_index(record)
    added_ids = [
        str(atom["atom_id"])
        for atom in record.get("memories") or []
        if atom.get("source") == V23_AUXILIARY_SOURCE
    ]
    expected_blocks = [
        {
            "parent_memory_id": str(block.get("parent_memory_id") or ""),
            "atom_ids": [str(atom_id) for atom_id in block.get("atom_ids") or []],
            "surface_fingerprint": canonical_sha256(block.get("memory_text")),
        }
        for block in record.get("memory_blocks") or []
    ]
    params = {
        "schema_version": REQUEST_SCHEMA,
        "record_id": str(record.get("id") or ""),
        "record_fingerprint": canonical_sha256(record),
        "difficulty_level": record.get("composite_block_revision", {}).get(
            "difficulty_level"
        ),
        "added_atom_ids": added_ids,
        "expected_blocks": expected_blocks,
        "all_atom_fingerprint": canonical_sha256(
            {atom_id: atoms[atom_id].get("text") for atom_id in sorted(atoms)}
        ),
    }
    return {
        "request_id": f"v23_independent_qc:{record['id']}",
        "prompt": [{"role": "user", "content": render_prompt(record, template)}],
        "user_defined_params": params,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare independent semantic QC for MemCalib v2.3 expansion and surface rewrites."
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
    template = args.prompt_template.read_text(encoding="utf-8")
    requests = [build_request(record, template) for record in records]
    write_jsonl(args.output, requests)
    manifest = {
        "schema_version": REQUEST_SCHEMA,
        "inputs": {
            "rewritten_benchmark": {
                "path": portable_path(args.input),
                "sha256": file_sha256(args.input),
                "records": len(records),
            }
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
            "difficulty": dict(
                sorted(
                    Counter(
                        request["user_defined_params"]["difficulty_level"]
                        for request in requests
                    ).items()
                )
            ),
            "added_atoms": sum(
                len(request["user_defined_params"]["added_atom_ids"])
                for request in requests
            ),
            "records_without_added_atoms": sum(
                not request["user_defined_params"]["added_atom_ids"]
                for request in requests
            ),
            "blocks": sum(
                len(request["user_defined_params"]["expected_blocks"])
                for request in requests
            ),
        },
        "output": {
            "path": portable_path(args.output),
            "sha256": file_sha256(args.output),
            "requests": len(requests),
            "unique_request_ids": len({request["request_id"] for request in requests}),
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
