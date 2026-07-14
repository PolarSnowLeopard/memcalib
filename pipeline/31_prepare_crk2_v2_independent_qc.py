#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from itertools import combinations
from pathlib import Path
from typing import Any

from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_100.jsonl"
DEFAULT_OUTPUT = SCRIPT_DIR / "data" / "crk2_v2_independent_qc_input_100.jsonl"
DEFAULT_MANIFEST = SCRIPT_DIR / "data" / "crk2_v2_independent_qc_input_100.manifest.json"
DEFAULT_PROMPT = SCRIPT_DIR / "prompts" / "verify_crk2_memory_benchmark_record_v2_en.txt"
POSTPROCESS_PATH = SCRIPT_DIR / "32_post_crk2_v2_independent_qc.py"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verifier_view(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": record.get("id"),
        "question": record.get("question"),
        "memory_blocks": record.get("memory_blocks"),
        "memories": record.get("memories"),
        "atom_pair_relations": record.get("atom_pair_relations"),
    }


def build_request(record: dict[str, Any], index: int, template: str) -> dict[str, Any]:
    view = verifier_view(record)
    atom_ids = sorted(str(memory.get("atom_id") or "") for memory in record.get("memories", []))
    expected_pairs = [list(pair) for pair in combinations(atom_ids, 2)]
    content = template.replace("{record_json}", json.dumps(view, ensure_ascii=False, indent=2))
    return {
        "request_id": f"crk2_v2_qc_{record.get('id')}",
        "prompt": [{"role": "user", "content": content}],
        "user_defined_params": {
            "qc_request_index": index,
            "record_id": record.get("id"),
            "record_fingerprint": canonical_sha256(view),
            "expected_atom_ids": atom_ids,
            "expected_pairs": expected_pairs,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare independent semantic QC requests for CRK-2 v2 records.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--prompt-template", type=Path, default=DEFAULT_PROMPT)
    args = parser.parse_args()

    records = list(iter_jsonl(args.input))
    template = args.prompt_template.read_text(encoding="utf-8")
    requests = [build_request(record, index, template) for index, record in enumerate(records, start=1)]
    write_jsonl(args.output, requests)
    manifest = {
        "schema_version": "crk2-independent-qc-requests-v2",
        "input": {"path": str(args.input), "sha256": file_sha256(args.input), "records": len(records)},
        "implementation": {
            "prepare": {"path": str(Path(__file__).resolve()), "sha256": file_sha256(Path(__file__).resolve())},
            "prompt": {"path": str(args.prompt_template), "sha256": file_sha256(args.prompt_template)},
            "postprocess": {"path": str(POSTPROCESS_PATH), "sha256": file_sha256(POSTPROCESS_PATH)},
        },
        "output": {"path": str(args.output), "sha256": file_sha256(args.output), "requests": len(requests)},
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
