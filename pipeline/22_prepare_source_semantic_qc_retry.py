#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from utils import iter_jsonl, write_json, write_jsonl


SCHEMA_VERSION = "crk2-source-semantic-qc-retry-v1"
RETRY_INSTRUCTION = """

RETRY CORRECTION
The previous judgment failed evidence grounding only. Keep the same schema and evaluate the source again. Every evidence value must be one contiguous exact substring copied character-for-character from an allowed displayed field. For memory_extractability, use SOURCE CONTEXT or CURRENT QUESTION. For answer relevance, answer substantiveness, and safety/plausibility, use REFERENCE ANSWER. For question completeness, use CURRENT QUESTION. For text integrity, use SOURCE CONTEXT, CURRENT QUESTION, or REFERENCE ANSWER. Do not paraphrase, summarize, normalize spelling, omit list markers, or join non-contiguous spans with ellipses.
""".rstrip()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def invalid_request_ids(invalid_rows: list[dict[str, Any]]) -> set[str]:
    ids = {
        str((row.get("source") or {}).get("request_id") or "")
        for row in invalid_rows
    }
    ids.discard("")
    if len(ids) != len(invalid_rows):
        raise ValueError("invalid rows must contain one unique source.request_id each")
    return ids


def build_retry_requests(
    requests: list[dict[str, Any]],
    invalid_rows: list[dict[str, Any]],
    retry_round: int,
) -> list[dict[str, Any]]:
    if retry_round <= 0:
        raise ValueError("retry_round must be positive")
    target_ids = invalid_request_ids(invalid_rows)
    retries: list[dict[str, Any]] = []
    for request in requests:
        request_id = str(request.get("request_id") or "")
        if request_id not in target_ids:
            continue
        retry = copy.deepcopy(request)
        prompt = retry.get("prompt")
        if not isinstance(prompt, list) or not prompt:
            raise ValueError(f"request {request_id} has no message prompt")
        user_messages = [message for message in prompt if isinstance(message, dict) and message.get("role") == "user"]
        if not user_messages:
            raise ValueError(f"request {request_id} has no user message")
        user_messages[-1]["content"] = str(user_messages[-1].get("content") or "") + RETRY_INSTRUCTION
        params = dict(retry.get("user_defined_params") or {})
        params["semantic_qc_retry_round"] = retry_round
        params["semantic_qc_retry_reason"] = "evidence_grounding"
        retry["user_defined_params"] = params
        retries.append(retry)

    found_ids = {str(request.get("request_id") or "") for request in retries}
    missing = sorted(target_ids - found_ids)
    if missing:
        raise ValueError(f"invalid request IDs missing from original input: {missing[:5]}")
    return retries


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare retry requests for invalid source semantic-QC outputs.")
    parser.add_argument("--input", type=Path, required=True, help="Original semantic-QC request JSONL.")
    parser.add_argument("--invalid", type=Path, required=True, help="Invalid rows emitted by the semantic-QC postprocessor.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--retry-round", type=int, default=1)
    args = parser.parse_args()

    requests = list(iter_jsonl(args.input))
    invalid_rows = list(iter_jsonl(args.invalid))
    retries = build_retry_requests(requests, invalid_rows, args.retry_round)
    write_jsonl(args.output, retries)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "retry_round": args.retry_round,
        "reason": "evidence_grounding",
        "input": {"path": str(args.input), "sha256": file_sha256(args.input), "records": len(requests)},
        "invalid": {"path": str(args.invalid), "sha256": file_sha256(args.invalid), "records": len(invalid_rows)},
        "output": {"path": str(args.output), "sha256": file_sha256(args.output), "records": len(retries)},
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
