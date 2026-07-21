#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from memcalib_v23_common import (
    V23_DIR,
    atom_index,
    canonical_sha256,
    critical_tokens,
    file_sha256,
    portable_path,
)
from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = V23_DIR / "memcalib_v23_expanded_benchmark_15000.jsonl"
DEFAULT_OUTPUT = V23_DIR / "memcalib_v23_surface_rewrite_input_15000.jsonl"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")
DEFAULT_PROMPT = SCRIPT_DIR / "prompts" / "rewrite_memcalib_v23_memory_blocks_en.txt"
REQUEST_SCHEMA = "memcalib-v23-surface-rewrite-requests-v1"


def rewrite_blocks(record: dict[str, Any]) -> list[dict[str, Any]]:
    atoms = atom_index(record)
    return [
        {
            "parent_memory_id": block.get("parent_memory_id"),
            "atoms": [
                {
                    "atom_id": str(atom_id),
                    "text": atoms[str(atom_id)].get("text"),
                }
                for atom_id in block.get("atom_ids") or []
            ],
        }
        for block in record.get("memory_blocks") or []
        if len(block.get("atom_ids") or []) >= 2
    ]


def render_prompt(record: dict[str, Any], template: str) -> str:
    replacements = {
        "{record_id}": str(record.get("id") or ""),
        "{blocks_json}": json.dumps(
            rewrite_blocks(record), ensure_ascii=False, indent=2
        ),
    }
    content = template
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    return content


def build_request(record: dict[str, Any], template: str) -> dict[str, Any]:
    record_id = str(record.get("id") or "")
    blocks = rewrite_blocks(record)
    if not blocks:
        raise ValueError(f"record {record_id} has no multi-atom blocks to rewrite")
    params = {
        "schema_version": REQUEST_SCHEMA,
        "record_id": record_id,
        "record_fingerprint": canonical_sha256(record),
        "expected_blocks": [
            {
                "parent_memory_id": block["parent_memory_id"],
                "atom_ids": [atom["atom_id"] for atom in block["atoms"]],
                "atom_text_fingerprint": canonical_sha256(
                    [atom["text"] for atom in block["atoms"]]
                ),
                "critical_tokens": sorted(
                    {
                        token
                        for atom in block["atoms"]
                        for token in critical_tokens(str(atom["text"]))
                    }
                ),
            }
            for block in blocks
        ],
    }
    return {
        "request_id": f"v23_surface_rewrite:{record_id}",
        "prompt": [{"role": "user", "content": render_prompt(record, template)}],
        "user_defined_params": params,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare label-blind natural-paragraph rewrites for MemCalib v2.3 blocks."
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
    block_counts = Counter(
        len(request["user_defined_params"]["expected_blocks"])
        for request in requests
    )
    manifest = {
        "schema_version": REQUEST_SCHEMA,
        "inputs": {
            "expanded_benchmark": {
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
        "privacy_and_blinding": {
            "question_supplied": False,
            "labels_supplied": False,
            "actions_supplied": False,
            "rubrics_supplied": False,
            "atom_texts_supplied": True,
        },
        "distribution": {
            "records": len(requests),
            "multi_atom_blocks": sum(
                rewritten_count * record_count
                for rewritten_count, record_count in block_counts.items()
            ),
            "multi_atom_blocks_per_record": dict(sorted(block_counts.items())),
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
