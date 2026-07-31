#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from memcalib_v23_common import canonical_sha256, file_sha256, portable_path
from memcalib_v24_coding_common import V24_DIR
from utils import iter_jsonl, write_json, write_jsonl


AUDIT_DIR = V24_DIR / "audit"
DEFAULT_REQUESTS = AUDIT_DIR / "memcalib_v241_semantic_qc_input_3750.jsonl"
DEFAULT_INVALID = AUDIT_DIR / "memcalib_v241_semantic_qc_qwen_3750.invalid.jsonl"
DEFAULT_OUTPUT = AUDIT_DIR / "memcalib_v241_semantic_qc_qwen_retry1_input.jsonl"

RETRY_SCHEMA = "memcalib-v241-semantic-qc-retry-requests-v1"


def request_params(row: dict[str, Any]) -> dict[str, Any]:
    return (
        row.get("user_defined_params")
        or row.get("passParams")
        or row.get("params")
        or {}
    )


def build_retry_request(
    original: dict[str, Any],
    invalid: dict[str, Any],
    retry_round: int,
) -> dict[str, Any]:
    retry = copy.deepcopy(original)
    params = copy.deepcopy(request_params(original))
    record_id = str(params.get("record_id") or invalid.get("record_id") or "")
    expected_ids = [str(value) for value in params.get("expected_atom_ids") or []]
    errors = [str(value) for value in invalid.get("errors") or []]
    if not record_id or not expected_ids or not errors:
        raise ValueError("retry request requires record ID, expected atom IDs, and errors")
    prompt = retry.get("prompt")
    if not isinstance(prompt, list) or len(prompt) != 1:
        raise ValueError("original QC request must contain exactly one message")
    content = prompt[0].get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("original QC request content is missing")
    retry_instruction = (
        "RETRY AFTER STRUCTURAL VALIDATION FAILURE.\n"
        f"The prior output errors were: {json.dumps(errors, ensure_ascii=False)}\n"
        "Return one complete JSON object with all required record checks in the "
        "specified order. The atom_checks array must contain exactly one concise "
        "entry for each of these atom IDs, in this exact order:\n"
        f"{json.dumps(expected_ids, ensure_ascii=False)}\n"
        "Each atom entry must be one object containing atom_id, "
        "label_action_validity, answer_text_observability, rubric_objectivity, "
        "query_value_status, and reason together. Do not split one atom into "
        "separate objects for separate checks. Do not omit, merge, rename, or "
        "duplicate an atom. Keep every reason under 30 words. Do not return "
        "Markdown or commentary outside the JSON object.\n\n"
    )
    retry["request_id"] = (
        f"v241_semantic_qc_retry{retry_round}:{record_id}"
    )
    retry["prompt"][0]["content"] = retry_instruction + content
    params["qc_retry"] = {
        "schema_version": RETRY_SCHEMA,
        "retry_round": retry_round,
        "prior_request_id": original.get("request_id"),
        "prior_errors": errors,
        "prior_errors_fingerprint": canonical_sha256(errors),
    }
    retry["user_defined_params"] = params
    retry.pop("passParams", None)
    retry.pop("params", None)
    return retry


def prepare_retries(
    requests: list[dict[str, Any]],
    invalid_rows: list[dict[str, Any]],
    retry_round: int,
) -> list[dict[str, Any]]:
    by_request_id = {
        str(row.get("request_id") or ""): row for row in requests
    }
    if "" in by_request_id or len(by_request_id) != len(requests):
        raise ValueError("original request IDs must be non-empty and unique")
    retries: list[dict[str, Any]] = []
    seen_record_ids: set[str] = set()
    for invalid in invalid_rows:
        prior_request_id = str(invalid.get("request_id") or "")
        original = by_request_id.get(prior_request_id)
        if original is None:
            raise ValueError(f"invalid row has no original request: {prior_request_id}")
        retry = build_retry_request(original, invalid, retry_round)
        record_id = str(request_params(retry).get("record_id") or "")
        if record_id in seen_record_ids:
            raise ValueError(f"duplicate invalid record ID: {record_id}")
        seen_record_ids.add(record_id)
        retries.append(retry)
    return retries


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare structural-only retries for v2.4.1 semantic QC."
    )
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--invalid", type=Path, default=DEFAULT_INVALID)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--retry-round", type=int, default=1)
    args = parser.parse_args()
    if args.retry_round < 1:
        raise ValueError("retry round must be positive")
    manifest_path = args.manifest or args.output.with_suffix(".manifest.json")
    requests = list(iter_jsonl(args.requests))
    invalid_rows = list(iter_jsonl(args.invalid))
    retries = prepare_retries(requests, invalid_rows, args.retry_round)
    write_jsonl(args.output, retries)
    manifest = {
        "schema_version": RETRY_SCHEMA,
        "inputs": {
            "requests": {
                "path": portable_path(args.requests),
                "sha256": file_sha256(args.requests),
                "count": len(requests),
            },
            "invalid": {
                "path": portable_path(args.invalid),
                "sha256": file_sha256(args.invalid),
                "count": len(invalid_rows),
            },
        },
        "retry_round": args.retry_round,
        "output": {
            "path": portable_path(args.output),
            "sha256": file_sha256(args.output),
            "requests": len(retries),
            "unique_request_ids": len(
                {str(row.get("request_id") or "") for row in retries}
            ),
        },
    }
    write_json(manifest_path, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
