#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
V22_DIR = SCRIPT_DIR / "data" / "multidomain" / "full-v2" / "revision-longtail-blocks"
DEFAULT_INPUT = V22_DIR / "memcalib_v22_longtail_benchmark_15000.jsonl"
DEFAULT_OUTPUT = V22_DIR / "memcalib_v22_longtail_independent_qc_input_15000.jsonl"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")
DEFAULT_PROMPT = SCRIPT_DIR / "prompts" / "verify_memcalib_v22_longtail_noise_en.txt"
REQUEST_SCHEMA = "memcalib-v22-longtail-independent-qc-requests-v1"


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(SCRIPT_DIR.parent))
    except ValueError:
        return str(resolved)


def auxiliary_atoms(record: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        atom
        for atom in record.get("memories") or []
        if isinstance(atom, dict) and atom.get("source") == "synthetic_retrieval_noise"
    ]


def locked_atoms(record: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        atom
        for atom in record.get("memories") or []
        if isinstance(atom, dict)
        and atom.get("source") not in {"synthetic_hard_a", "synthetic_retrieval_noise"}
    ]


def canonical_hard_a(record: dict[str, Any]) -> dict[str, Any]:
    atoms = [
        atom
        for atom in record.get("memories") or []
        if isinstance(atom, dict)
        and atom.get("source") == "synthetic_hard_a"
        and atom.get("canonical_hard_a") is True
    ]
    if len(atoms) != 1:
        raise ValueError(f"record {record.get('id')} must have one canonical Hard A")
    return atoms[0]


def auxiliary_blocks(record: dict[str, Any], atom_ids: set[str]) -> list[dict[str, Any]]:
    return [
        block
        for block in record.get("memory_blocks") or []
        if isinstance(block, dict)
        and any(str(atom_id) in atom_ids for atom_id in block.get("atom_ids") or [])
    ]


def compact_atom(atom: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "atom_id",
        "text",
        "memory_type",
        "u_star",
        "memory_action",
        "hard_a_family",
        "retrieval_noise_family",
        "label_reason",
        "surface_relevance",
        "non_applicability_reason",
    )
    return {key: atom.get(key) for key in keys}


def compact_block(block: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "parent_memory_id",
        "memory_text",
        "atom_ids",
        "canonical_hard_a_family",
        "retrieval_noise_family",
        "joint_no_footprint_reason",
    )
    return {key: block.get(key) for key in keys}


def render_prompt(record: dict[str, Any], template: str) -> str:
    auxiliaries = auxiliary_atoms(record)
    auxiliary_ids = {str(atom["atom_id"]) for atom in auxiliaries}
    replacements = {
        "{record_id}": str(record.get("id") or ""),
        "{domain}": str(record.get("domain") or "health_seed"),
        "{question}": str(record.get("question") or ""),
        "{source_answer}": str(record.get("source_answer") or ""),
        "{locked_atoms_json}": json.dumps(
            [compact_atom(atom) for atom in locked_atoms(record)],
            ensure_ascii=False,
            indent=2,
        ),
        "{canonical_hard_a_json}": json.dumps(
            compact_atom(canonical_hard_a(record)), ensure_ascii=False, indent=2
        ),
        "{auxiliary_blocks_json}": json.dumps(
            [compact_block(block) for block in auxiliary_blocks(record, auxiliary_ids)],
            ensure_ascii=False,
            indent=2,
        ),
        "{auxiliary_atoms_json}": json.dumps(
            [compact_atom(atom) for atom in auxiliaries], ensure_ascii=False, indent=2
        ),
    }
    content = template
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    return content


def build_request(record: dict[str, Any], template: str) -> dict[str, Any]:
    record_id = str(record.get("id") or "")
    auxiliaries = auxiliary_atoms(record)
    atom_ids = [str(atom.get("atom_id") or "") for atom in auxiliaries]
    if not record_id or not atom_ids or "" in atom_ids or len(atom_ids) != len(set(atom_ids)):
        raise ValueError(f"record {record_id!r} has invalid auxiliary atoms")
    blocks = auxiliary_blocks(record, set(atom_ids))
    block_map = {
        str(block.get("parent_memory_id") or ""): [
            str(atom_id)
            for atom_id in block.get("atom_ids") or []
            if str(atom_id) in set(atom_ids)
        ]
        for block in blocks
    }
    if "" in block_map or not block_map or any(not ids for ids in block_map.values()):
        raise ValueError(f"record {record_id!r} has invalid auxiliary blocks")
    params = {
        "schema_version": REQUEST_SCHEMA,
        "record_id": record_id,
        "record_fingerprint": canonical_sha256(record),
        "domain": str(record.get("domain") or "health_seed"),
        "auxiliary_atom_ids": atom_ids,
        "auxiliary_block_atom_ids": block_map,
    }
    return {
        "request_id": f"v22_longtail_qc:{record_id}",
        "prompt": [{"role": "user", "content": render_prompt(record, template)}],
        "user_defined_params": params,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare independent semantic QC for MemCalib v2.2 auxiliary retrieval noise."
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
        "input": {
            "path": portable_path(args.input),
            "sha256": file_sha256(args.input),
            "records": len(records),
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
        "distribution": {
            "domain": dict(
                sorted(
                    Counter(
                        str(record.get("domain") or "health_seed")
                        for record in records
                    ).items()
                )
            ),
            "auxiliary_atoms_per_record": dict(
                sorted(Counter(len(auxiliary_atoms(record)) for record in records).items())
            ),
        },
        "output": {
            "path": portable_path(args.output),
            "sha256": file_sha256(args.output),
            "requests": len(requests),
            "unique_request_ids": len({request["request_id"] for request in requests}),
            "unique_record_fingerprints": len(
                {
                    request["user_defined_params"]["record_fingerprint"]
                    for request in requests
                }
            ),
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
