#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
V22_DIR = SCRIPT_DIR / "data" / "multidomain" / "full-v2" / "revision-longtail-blocks"
DEFAULT_INVALID = (
    V22_DIR / "memcalib_v22_longtail_independent_qc_resolved1_15000.invalid.jsonl"
)
DEFAULT_OUTPUT = V22_DIR / "memcalib_v22_longtail_qc_record_id_repair_result.jsonl"
DEFAULT_AUDIT = V22_DIR / "memcalib_v22_longtail_qc_record_id_repair.audit.jsonl"
DEFAULT_MANIFEST = V22_DIR / "memcalib_v22_longtail_qc_record_id_repair.manifest.json"
REPAIR_SCHEMA = "memcalib-v22-longtail-qc-record-id-repair-v1"


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


def replace_response(result: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    repaired = copy.deepcopy(result)
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    repaired["response"] = encoded
    raw = repaired.get("raw_response")
    if isinstance(raw, dict):
        choices = raw.get("choices")
        if (
            isinstance(choices, list)
            and choices
            and isinstance(choices[0], dict)
            and isinstance(choices[0].get("message"), dict)
        ):
            choices[0]["message"]["content"] = encoded
    return repaired


def repair_invalid_row(
    row: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    errors = row.get("validation_errors")
    if errors != ["record_id_mismatch"]:
        raise ValueError(f"unsupported QC repair errors: {errors}")
    request_id = str(row.get("request_id") or "")
    expected_record_id = str(row.get("record_id") or "")
    judge = row.get("judge_output")
    raw_result = row.get("raw_result")
    if not request_id or not expected_record_id:
        raise ValueError("invalid audit is missing request_id or record_id")
    if not isinstance(judge, dict) or not isinstance(raw_result, dict):
        raise ValueError("invalid audit is missing judge_output or raw_result")
    before_record_id = str(judge.get("record_id") or "")
    if not before_record_id or before_record_id == expected_record_id:
        raise ValueError("record ID repair would be empty or a no-op")
    repaired_judge = copy.deepcopy(judge)
    repaired_judge["record_id"] = expected_record_id
    repaired_result = replace_response(raw_result, repaired_judge)
    audit = {
        "schema_version": REPAIR_SCHEMA,
        "request_id": request_id,
        "record_id": expected_record_id,
        "validation_errors": list(errors),
        "before_record_id": before_record_id,
        "after_record_id": expected_record_id,
        "judge_output_before_sha256": canonical_sha256(judge),
        "judge_output_after_sha256": canonical_sha256(repaired_judge),
        "changed_fields": ["record_id"],
    }
    return repaired_result, audit


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Repair only an otherwise-valid MemCalib v2.2 QC record ID typo."
    )
    parser.add_argument("--invalid", type=Path, default=DEFAULT_INVALID)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    invalid_rows = list(iter_jsonl(args.invalid))
    repaired_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    for row in invalid_rows:
        repaired, audit = repair_invalid_row(row)
        repaired_rows.append(repaired)
        audit_rows.append(audit)
    request_ids = [str(row.get("request_id") or "") for row in repaired_rows]
    if "" in request_ids or len(request_ids) != len(set(request_ids)):
        raise ValueError("repaired request IDs must be non-empty and unique")

    write_jsonl(args.output, repaired_rows)
    write_jsonl(args.audit, audit_rows)
    manifest = {
        "schema_version": REPAIR_SCHEMA,
        "input": {
            "path": portable_path(args.invalid),
            "sha256": file_sha256(args.invalid),
            "invalid_records": len(invalid_rows),
        },
        "counts": {
            "repaired_records": len(repaired_rows),
            "changed_fields": len(audit_rows),
            "unique_request_ids": len(set(request_ids)),
        },
        "outputs": {
            "result": {
                "path": portable_path(args.output),
                "sha256": file_sha256(args.output),
            },
            "audit": {
                "path": portable_path(args.audit),
                "sha256": file_sha256(args.audit),
            },
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
