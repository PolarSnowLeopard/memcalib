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
DEFAULT_REJECTED = SCRIPT_DIR / "data" / "crk2_v2_independent_qc.reject.jsonl"
DEFAULT_REQUESTS = SCRIPT_DIR / "data" / "crk2_v2_generation_input_18000.jsonl"
DEFAULT_PROMPT = SCRIPT_DIR / "prompts" / "repair_crk2_memory_benchmark_record_v2_semantic_en.txt"
DEFAULT_OUTPUT = SCRIPT_DIR / "data" / "crk2_v2_semantic_repair1_input.jsonl"
DEFAULT_MANIFEST = SCRIPT_DIR / "data" / "crk2_v2_semantic_repair1_input.manifest.json"
SCHEMA_VERSION = "crk2-v2-semantic-repair-requests-v1"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def source_id_from_params(params: dict[str, Any]) -> str:
    return str(params.get("id") or params.get("source_raw_id") or "")


def index_generation_requests(path: Path) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for request in iter_jsonl(path):
        params = request.get("user_defined_params") or {}
        source_id = source_id_from_params(params)
        if not source_id or source_id in indexed:
            raise ValueError(f"invalid or duplicate generation source_id: {source_id}")
        indexed[source_id] = request
    return indexed


def repair_view(record: dict[str, Any]) -> dict[str, Any]:
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


def render_prompt(record: dict[str, Any], params: dict[str, Any], template: str) -> str:
    qc = record.get("independent_qc") or {}
    replacements = {
        "{domain}": str(record.get("domain") or params.get("domain") or "health_seed"),
        "{source_dataset}": str(record.get("source_dataset") or params.get("source_dataset") or ""),
        "{source_id}": str(record.get("source_id") or source_id_from_params(params)),
        "{topic}": str(record.get("source_topic") or params.get("topic") or ""),
        "{source_context}": str(params.get("dialogue_context") or params.get("source_context") or ""),
        "{raw_question}": str(params.get("raw_question") or ""),
        "{source_answer}": str(params.get("doctor_answer") or params.get("source_answer") or ""),
        "{original_record_json}": json.dumps(repair_view(record), ensure_ascii=False, separators=(",", ":")),
        "{independent_qc_json}": json.dumps(qc, ensure_ascii=False, separators=(",", ":")),
    }
    content = template
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    return content


def build_semantic_repair_request(
    record: dict[str, Any], generation_request: dict[str, Any], retry_round: int, template: str
) -> dict[str, Any]:
    record_id = str(record.get("id") or "")
    source_id = str(record.get("source_id") or "")
    params = dict(generation_request.get("user_defined_params") or {})
    if not record_id or not source_id or source_id_from_params(params) != source_id:
        raise ValueError(f"record/generation lineage mismatch: record_id={record_id}, source_id={source_id}")
    qc = record.get("independent_qc")
    if not isinstance(qc, dict) or qc.get("decision") != "reject":
        raise ValueError(f"semantic repair input must be an independent-QC reject: {record_id}")
    params["crk2_v2_semantic_repair"] = {
        "schema_version": SCHEMA_VERSION,
        "retry_round": retry_round,
        "original_record_id": record_id,
        "original_record_fingerprint": canonical_sha256(record),
        "independent_qc_decision": qc.get("decision"),
        "independent_qc_declared_decision": qc.get("declared_decision"),
        "independent_qc_decision_reasons": qc.get("decision_reasons") or [],
        "independent_qc_issues": qc.get("issues") or [],
    }
    return {
        "request_id": record_id,
        "prompt": [{"role": "user", "content": render_prompt(record, params, template)}],
        "user_defined_params": params,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare targeted semantic repairs for independent-QC rejects.")
    parser.add_argument("--rejected", type=Path, default=DEFAULT_REJECTED)
    parser.add_argument("--generation-requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--prompt-template", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--retry-round", type=int, default=1)
    parser.add_argument(
        "--target-ids-from",
        type=Path,
        help="Optional JSONL whose id/request_id/record_id values restrict which rejected records are repaired.",
    )
    args = parser.parse_args()
    if args.retry_round < 1:
        raise ValueError("retry-round must be positive")

    generation = index_generation_requests(args.generation_requests)
    template = args.prompt_template.read_text(encoding="utf-8")
    rejected = list(iter_jsonl(args.rejected))
    target_ids: set[str] | None = None
    if args.target_ids_from:
        target_ids = set()
        for row in iter_jsonl(args.target_ids_from):
            record_id = str(row.get("id") or row.get("request_id") or row.get("record_id") or "")
            if not record_id or record_id in target_ids:
                raise ValueError(f"target ID input has an invalid or duplicate record id: {record_id}")
            target_ids.add(record_id)
        available_ids = {str(row.get("id") or "") for row in rejected}
        missing_targets = sorted(target_ids - available_ids)
        if missing_targets:
            raise ValueError(f"target IDs absent from rejected input: {missing_targets}")
        rejected = [row for row in rejected if str(row.get("id") or "") in target_ids]
    requests = []
    for record in rejected:
        source_id = str(record.get("source_id") or "")
        source_request = generation.get(source_id)
        if source_request is None:
            raise ValueError(f"no generation request for rejected source_id: {source_id}")
        requests.append(build_semantic_repair_request(record, source_request, args.retry_round, template))
    request_ids = [str(row.get("request_id") or "") for row in requests]
    if "" in request_ids or len(request_ids) != len(set(request_ids)):
        raise ValueError("semantic repair request IDs must be non-empty and unique")
    write_jsonl(args.output, requests)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "retry_round": args.retry_round,
        "inputs": {
            "rejected": {"path": str(args.rejected), "sha256": file_sha256(args.rejected), "records": len(rejected)},
            "generation_requests": {
                "path": str(args.generation_requests),
                "sha256": file_sha256(args.generation_requests),
                "records": len(generation),
            },
            "target_ids": (
                {
                    "path": str(args.target_ids_from),
                    "sha256": file_sha256(args.target_ids_from),
                    "records": len(target_ids or ()),
                }
                if args.target_ids_from
                else None
            ),
        },
        "implementation": {
            "prepare": {"path": str(Path(__file__).resolve()), "sha256": file_sha256(Path(__file__).resolve())},
            "prompt": {"path": str(args.prompt_template), "sha256": file_sha256(args.prompt_template)},
        },
        "distribution": {
            "domain": dict(sorted(Counter(str(row.get("domain") or "health_seed") for row in rejected).items())),
            "source_dataset": dict(
                sorted(Counter(str(row.get("source_dataset") or "unknown") for row in rejected).items())
            ),
        },
        "output": {"path": str(args.output), "sha256": file_sha256(args.output), "requests": len(requests)},
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
