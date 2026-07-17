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
DEFAULT_PROMPT = SCRIPT_DIR / "prompts" / "reconstruct_crk2_memory_benchmark_record_v2_en.txt"
SCHEMA_VERSION = "crk2-v2-reserve-reconstruction-requests-v1"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def source_id(params: dict[str, Any]) -> str:
    return str(params.get("id") or params.get("source_raw_id") or "")


def reconstruction_view(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: record.get(key)
        for key in (
            "schema_version",
            "accepted",
            "question",
            "memory_blocks",
            "memories",
            "atom_pair_relations",
            "qc",
            "notes",
        )
    }


def render_prompt(row: dict[str, Any], params: dict[str, Any], template: str) -> str:
    record = row.get("parsed_record") if isinstance(row.get("parsed_record"), dict) else {}
    replacements = {
        "{failed_errors_json}": json.dumps(row.get("errors") or [], ensure_ascii=False, separators=(",", ":")),
        "{domain}": str(params.get("domain") or "health_seed"),
        "{source_dataset}": str(params.get("source_dataset") or ""),
        "{source_id}": source_id(params),
        "{topic}": str(params.get("topic") or ""),
        "{source_context}": str(params.get("dialogue_context") or params.get("source_context") or ""),
        "{raw_question}": str(params.get("raw_question") or ""),
        "{source_answer}": str(params.get("doctor_answer") or params.get("source_answer") or ""),
        "{original_record_json}": json.dumps(
            reconstruction_view(record), ensure_ascii=False, separators=(",", ":")
        ),
    }
    content = template
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    return content


def build_reconstruction_request(row: dict[str, Any], retry_round: int, template: str) -> dict[str, Any]:
    params = dict(row.get("user_defined_params") or row.get("params") or {})
    record_id = str(row.get("request_id") or "")
    source = source_id(params)
    if not record_id or not source:
        raise ValueError("reserve reconstruction row has no request/source id")
    params["crk2_v2_reserve_reconstruction"] = {
        "schema_version": SCHEMA_VERSION,
        "retry_round": retry_round,
        "prior_request_id": record_id,
        "prior_reject_fingerprint": canonical_sha256(row),
        "prior_errors": row.get("errors") or [],
    }
    return {
        "request_id": record_id,
        "prompt": [{"role": "user", "content": render_prompt(row, params, template)}],
        "user_defined_params": params,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare reserve reconstruction requests from deterministic rejects.")
    parser.add_argument("--rejected", type=Path, required=True)
    parser.add_argument("--prompt-template", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--retry-round", type=int, default=1)
    args = parser.parse_args()
    if args.retry_round < 1:
        raise ValueError("retry-round must be positive")

    rejected = list(iter_jsonl(args.rejected))
    template = args.prompt_template.read_text(encoding="utf-8")
    requests = [build_reconstruction_request(row, args.retry_round, template) for row in rejected]
    request_ids = [str(row.get("request_id") or "") for row in requests]
    if "" in request_ids or len(request_ids) != len(set(request_ids)):
        raise ValueError("reserve reconstruction request IDs must be non-empty and unique")
    write_jsonl(args.output, requests)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "retry_round": args.retry_round,
        "inputs": {
            "rejected": {"path": str(args.rejected), "sha256": file_sha256(args.rejected), "records": len(rejected)},
        },
        "implementation": {
            "prepare": {"path": str(Path(__file__).resolve()), "sha256": file_sha256(Path(__file__).resolve())},
            "prompt": {"path": str(args.prompt_template), "sha256": file_sha256(args.prompt_template)},
        },
        "distribution": {
            "domain": dict(
                sorted(
                    Counter(
                        str((row.get("user_defined_params") or {}).get("domain") or "health_seed")
                        for row in rejected
                    ).items()
                )
            )
        },
        "output": {"path": str(args.output), "sha256": file_sha256(args.output), "requests": len(requests)},
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
