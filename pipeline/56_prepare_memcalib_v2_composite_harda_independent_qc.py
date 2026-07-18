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
REVISION_DIR = SCRIPT_DIR / "data" / "multidomain" / "full-v2" / "revision-composite-harda"
DEFAULT_INPUT = REVISION_DIR / "memcalib_v21_composite_harda_benchmark_15000.jsonl"
DEFAULT_OUTPUT = REVISION_DIR / "memcalib_v21_composite_harda_independent_qc_input_15000.jsonl"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")
DEFAULT_PROMPT = SCRIPT_DIR / "prompts" / "verify_memcalib_v2_composite_harda_revision_en.txt"
SCHEMA_VERSION = "memcalib-composite-harda-independent-qc-requests-v1"


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(SCRIPT_DIR.parent))
    except ValueError:
        return str(resolved)


def real_atom_ids(record: dict[str, Any]) -> list[str]:
    return [
        str(atom.get("atom_id") or "")
        for atom in record.get("memories") or []
        if isinstance(atom, dict) and atom.get("source") != "synthetic_hard_a"
    ]


def hard_a_family(record: dict[str, Any]) -> str:
    hard = [
        atom
        for atom in record.get("memories") or []
        if isinstance(atom, dict) and atom.get("source") == "synthetic_hard_a"
    ]
    if len(hard) != 1:
        raise ValueError(f"record {record.get('id')} must have exactly one synthetic Hard A atom")
    return str(hard[0].get("hard_a_family") or "")


def render_prompt(record: dict[str, Any], template: str) -> str:
    replacements = {
        "{record_id}": str(record.get("id") or ""),
        "{domain}": str(record.get("domain") or "health_seed"),
        "{hard_a_family}": hard_a_family(record),
        "{question}": str(record.get("question") or ""),
        "{source_answer}": str(record.get("source_answer") or ""),
        "{memory_blocks_json}": json.dumps(record.get("memory_blocks") or [], ensure_ascii=False, indent=2),
        "{memories_json}": json.dumps(record.get("memories") or [], ensure_ascii=False, indent=2),
        "{pair_relations_json}": json.dumps(record.get("atom_pair_relations") or [], ensure_ascii=False, indent=2),
    }
    content = template
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    return content


def build_request(record: dict[str, Any], template: str) -> dict[str, Any]:
    record_id = str(record.get("id") or "")
    atom_ids = real_atom_ids(record)
    if not record_id or len(atom_ids) < 2 or "" in atom_ids or len(atom_ids) != len(set(atom_ids)):
        raise ValueError(f"record {record_id!r} has invalid identity or real atoms")
    params = {
        "schema_version": SCHEMA_VERSION,
        "record_id": record_id,
        "record_fingerprint": canonical_sha256(record),
        "domain": str(record.get("domain") or "health_seed"),
        "hard_a_family": hard_a_family(record),
        "real_atom_ids": atom_ids,
    }
    return {
        "request_id": f"composite_harda_qc:{record_id}",
        "prompt": [{"role": "user", "content": render_prompt(record, template)}],
        "user_defined_params": params,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare independent QC requests for revised composite/Hard-A records.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--prompt-template", type=Path, default=DEFAULT_PROMPT)
    args = parser.parse_args()

    records = list(iter_jsonl(args.input))
    record_ids = [str(row.get("id") or "") for row in records]
    if "" in record_ids or len(record_ids) != len(set(record_ids)):
        raise ValueError("input record IDs must be non-empty and unique")
    template = args.prompt_template.read_text(encoding="utf-8")
    requests = [build_request(record, template) for record in records]
    write_jsonl(args.output, requests)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "input": {
            "path": portable_path(args.input),
            "sha256": file_sha256(args.input),
            "records": len(records),
        },
        "implementation": {
            "prepare": {"path": portable_path(Path(__file__)), "sha256": file_sha256(Path(__file__))},
            "prompt": {"path": portable_path(args.prompt_template), "sha256": file_sha256(args.prompt_template)},
        },
        "distribution": {
            "domain": dict(sorted(Counter(str(row.get("domain") or "health_seed") for row in records).items())),
            "hard_a_family": dict(sorted(Counter(hard_a_family(row) for row in records).items())),
        },
        "output": {
            "path": portable_path(args.output),
            "sha256": file_sha256(args.output),
            "requests": len(requests),
            "unique_request_ids": len({str(row["request_id"]) for row in requests}),
            "unique_record_fingerprints": len(
                {str(row["user_defined_params"]["record_fingerprint"]) for row in requests}
            ),
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
