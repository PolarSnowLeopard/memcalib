#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from memcalib_v23_common import V23_DIR, canonical_sha256, file_sha256, portable_path
from utils import extract_json_object, iter_jsonl, write_json, write_jsonl


DEFAULT_REQUESTS = V23_DIR / "memcalib_v23_independent_qc_input_15000.jsonl"
DEFAULT_RESULTS = V23_DIR / "memcalib_v23_independent_qc_resolved_result_15000.jsonl"
DEFAULT_INVALID = V23_DIR / "memcalib_v23_independent_qc_15000.invalid.jsonl"
DEFAULT_OUTPUT = V23_DIR / "memcalib_v23_independent_qc_metadata_repaired_result_15000.jsonl"
DEFAULT_AUDIT = V23_DIR / "memcalib_v23_independent_qc_metadata_repair.audit.jsonl"
DEFAULT_MANIFEST = V23_DIR / "memcalib_v23_independent_qc_metadata_repair.manifest.json"


def response_text(row: dict[str, Any]) -> str:
    value = row.get("response")
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"result {row.get('request_id')} has no response text")
    return value


def set_response_text(row: dict[str, Any], text: str) -> None:
    row["response"] = text
    raw = row.get("raw_response")
    if not isinstance(raw, dict):
        return
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return
    message = choices[0].get("message")
    if isinstance(message, dict):
        message["content"] = text


def unique_index(rows: list[dict], source: str) -> dict[str, dict]:
    ids = [str(row.get("request_id") or "") for row in rows]
    if "" in ids or len(ids) != len(set(ids)):
        raise ValueError(f"{source} request IDs must be non-empty and unique")
    return dict(zip(ids, rows, strict=True))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Repair QC response record IDs when that is the only structural error."
    )
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--invalid", type=Path, default=DEFAULT_INVALID)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    requests = unique_index(list(iter_jsonl(args.requests)), "requests")
    result_rows = list(iter_jsonl(args.results))
    results = unique_index(result_rows, "results")
    invalid_rows = list(iter_jsonl(args.invalid))
    repair_ids = {
        str(row.get("request_id") or "")
        for row in invalid_rows
        if row.get("errors") == ["record_id_mismatch"]
    }
    audits: list[dict[str, Any]] = []
    for request_id in sorted(repair_ids):
        request = requests.get(request_id)
        row = results.get(request_id)
        if request is None or row is None:
            raise ValueError(f"repair target missing request or result: {request_id}")
        params = request.get("user_defined_params") or request.get("passParams") or {}
        expected_id = str(params.get("record_id") or "")
        qc = extract_json_object(response_text(row))
        before_id = str(qc.get("record_id") or "")
        qc["record_id"] = expected_id
        serialized = json.dumps(qc, ensure_ascii=False, separators=(",", ":"))
        updated = copy.deepcopy(row)
        set_response_text(updated, serialized)
        updated["local_deterministic_repair"] = {
            "schema_version": "memcalib-v23-qc-metadata-repair-v1",
            "field": "record_id",
            "before_sha256": canonical_sha256(before_id),
            "after_sha256": canonical_sha256(expected_id),
            "semantic_judgment_changed": False,
        }
        results[request_id] = updated
        audits.append(
            {
                "request_id": request_id,
                "field": "record_id",
                "before_sha256": canonical_sha256(before_id),
                "after_sha256": canonical_sha256(expected_id),
                "semantic_judgment_changed": False,
            }
        )

    output_rows = [results[str(row["request_id"])] for row in result_rows]
    write_jsonl(args.output, output_rows)
    write_jsonl(args.audit, audits)
    manifest = {
        "schema_version": "memcalib-v23-qc-metadata-repair-manifest-v1",
        "policy": "record_id_only_when_sole_structural_error",
        "inputs": {
            "requests": {"path": portable_path(args.requests), "sha256": file_sha256(args.requests)},
            "results": {"path": portable_path(args.results), "sha256": file_sha256(args.results)},
            "invalid": {"path": portable_path(args.invalid), "sha256": file_sha256(args.invalid)},
        },
        "repair": {
            "repaired_results": len(audits),
            "semantic_judgment_changes": 0,
        },
        "outputs": {
            "results": {"path": portable_path(args.output), "sha256": file_sha256(args.output)},
            "audit": {"path": portable_path(args.audit), "sha256": file_sha256(args.audit)},
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
