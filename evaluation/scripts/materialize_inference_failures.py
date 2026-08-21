#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evaluation.common import iter_jsonl, request_fingerprint, write_json, write_jsonl


FAILURE_RESPONSE = "[Inference failed: no model response was produced.]"


def materialize_failures(
    requests: list[dict[str, Any]],
    results: list[dict[str, Any]],
    failed_rows: list[dict[str, Any]],
    *,
    served_model: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    request_by_id = {str(row["request_id"]): row for row in requests}
    if len(request_by_id) != len(requests):
        raise ValueError("request IDs are not unique")
    result_by_id = {str(row["request_id"]): row for row in results}
    if len(result_by_id) != len(results):
        raise ValueError("result IDs are not unique")
    failed_by_id = {str(row.get("request_id") or ""): row for row in failed_rows}
    missing_ids = [request_id for request_id in request_by_id if request_id not in result_by_id]
    unaudited = [request_id for request_id in missing_ids if request_id not in failed_by_id]
    if unaudited:
        raise ValueError(f"missing results lack failed-request audit: {unaudited}")

    failures = []
    for request_id, result in result_by_id.items():
        if not result.get("inference_failure"):
            continue
        request = request_by_id.get(request_id)
        if request is None:
            raise ValueError(f"synthetic failure has unknown request ID: {request_id}")
        failures.append(
            {
                "request_id": request_id,
                "sample_id": str((request.get("user_defined_params") or {}).get("sample_id") or ""),
                "model_key": str((request.get("user_defined_params") or {}).get("model_key") or ""),
                "condition": str((request.get("user_defined_params") or {}).get("condition") or ""),
                "score_policy": "observable_memory_footprint_A_and_task_quality_0",
            }
        )
    for request_id in missing_ids:
        request = request_by_id[request_id]
        synthetic = {
            "request_id": request_id,
            "input_fingerprint": request_fingerprint(request),
            "response": FAILURE_RESPONSE,
            "raw_response": {
                "id": f"inference-failure:{request_id}",
                "object": "chat.completion",
                "created": 0,
                "model": served_model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": FAILURE_RESPONSE,
                            "reasoning_content": None,
                        },
                        "finish_reason": "inference_failure",
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            },
            "user_defined_params": request.get("user_defined_params") or {},
            "inference_failure": {
                "counted_in_official_denominator": True,
                "score_policy": "observable_memory_footprint_A_and_task_quality_0",
                "failed_audit_present": True,
            },
        }
        result_by_id[request_id] = synthetic
        failures.append(
            {
                "request_id": request_id,
                "sample_id": str((request.get("user_defined_params") or {}).get("sample_id") or ""),
                "model_key": str((request.get("user_defined_params") or {}).get("model_key") or ""),
                "condition": str((request.get("user_defined_params") or {}).get("condition") or ""),
                "score_policy": "observable_memory_footprint_A_and_task_quality_0",
            }
        )

    ordered = [result_by_id[str(request["request_id"])] for request in requests]
    audit = {
        "schema_version": "memcalib-inference-failure-policy-v1",
        "expected_requests": len(requests),
        "real_model_responses": len(requests) - len(failures),
        "inference_failures": len(failures),
        "failure_response": FAILURE_RESPONSE,
        "policy": {
            "keep_in_official_denominator": True,
            "observable_memory_footprint": "A for every atom",
            "task_quality": 0,
            "rerun_model": False,
        },
        "failures": sorted(failures, key=lambda row: str(row["request_id"])),
    }
    return ordered, audit


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Materialize audited inference failures without rerunning the answer model."
    )
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--failed", type=Path, required=True)
    parser.add_argument("--served-model", required=True)
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()

    requests = list(iter_jsonl(args.requests))
    results = list(iter_jsonl(args.results)) if args.results.exists() else []
    failed_rows = list(iter_jsonl(args.failed)) if args.failed.exists() else []
    materialized, audit = materialize_failures(
        requests, results, failed_rows, served_model=args.served_model
    )
    write_jsonl(args.results, materialized)
    write_json(args.audit, audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
