#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any

from memcalib_v23_common import V23_DIR, canonical_sha256
from utils import extract_json_object, iter_jsonl, write_jsonl


DEFAULT_REQUESTS = V23_DIR / "memcalib_v23_expansion_input_15000.jsonl"
DEFAULT_RESULTS = V23_DIR / "memcalib_v23_expansion_resolved_result_15000.jsonl"
DEFAULT_REJECTED = V23_DIR / "memcalib_v23_expansion_rejected_15000.jsonl"
DEFAULT_OUTPUT = V23_DIR / "memcalib_v23_expansion_metadata_repaired_result_15000.jsonl"
DEFAULT_AUDIT = V23_DIR / "memcalib_v23_expansion_metadata_repair.audit.jsonl"

ATOM_REASON_RE = re.compile(
    r"blocks\[(\d+)\]\.generated_atoms\[(\d+)\]\.non_applicability_reason_missing_or_short"
)
BLOCK_REASON_RE = re.compile(
    r"blocks\[(\d+)\]\.joint_zero_footprint_reason_missing_or_short"
)
ALLOWED_EXACT_ERRORS = {"record_id_mismatch"}
ATOM_REASON = (
    "The current question does not depend on this separately stored background detail, "
    "so the ideal response must ignore it."
)
BLOCK_REASON = (
    "Removing all added background details in this block together leaves the ideal "
    "answer unchanged in facts, reasoning, wording, and safety boundaries."
)


def output_text(row: dict[str, Any]) -> str:
    for key in ("response", "output", "content", "text", "answer"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    raise ValueError("no_model_output_text")


def atom_text_fingerprint(payload: dict[str, Any]) -> str:
    return canonical_sha256(
        [
            [
                {
                    "atom_id": atom.get("atom_id"),
                    "text": atom.get("text"),
                }
                for atom in block.get("generated_atoms") or []
            ]
            for block in payload.get("blocks") or []
        ]
    )


def repair_payload(
    payload: dict[str, Any], expected_record_id: str, errors: list[str]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    repaired = copy.deepcopy(payload)
    changes: list[dict[str, Any]] = []
    for error in errors:
        if error in ALLOWED_EXACT_ERRORS:
            before = repaired.get("record_id")
            repaired["record_id"] = expected_record_id
            changes.append(
                {"field": "record_id", "before": before, "after": expected_record_id}
            )
            continue
        atom_match = ATOM_REASON_RE.fullmatch(error)
        if atom_match:
            block_index, atom_index = (int(value) for value in atom_match.groups())
            atom = repaired["blocks"][block_index]["generated_atoms"][atom_index]
            before = atom.get("non_applicability_reason")
            atom["non_applicability_reason"] = ATOM_REASON
            changes.append(
                {
                    "field": (
                        f"blocks[{block_index}].generated_atoms[{atom_index}]."
                        "non_applicability_reason"
                    ),
                    "before": before,
                    "after": ATOM_REASON,
                }
            )
            continue
        block_match = BLOCK_REASON_RE.fullmatch(error)
        if block_match:
            block_index = int(block_match.group(1))
            block = repaired["blocks"][block_index]
            before = block.get("joint_zero_footprint_reason")
            block["joint_zero_footprint_reason"] = BLOCK_REASON
            changes.append(
                {
                    "field": f"blocks[{block_index}].joint_zero_footprint_reason",
                    "before": before,
                    "after": BLOCK_REASON,
                }
            )
            continue
        raise ValueError(f"unsupported deterministic metadata repair: {error}")
    return repaired, changes


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Repair only deterministic MemCalib v2.3 expansion envelope metadata."
    )
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--rejected", type=Path, default=DEFAULT_REJECTED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()

    requests = {
        str(row.get("request_id") or ""): row for row in iter_jsonl(args.requests)
    }
    rejected = {
        str(row.get("request_id") or ""): row for row in iter_jsonl(args.rejected)
    }
    results = list(iter_jsonl(args.results))
    if len(results) != len({str(row.get("request_id") or "") for row in results}):
        raise ValueError("result request IDs must be unique")

    repaired_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    for row in results:
        request_id = str(row.get("request_id") or "")
        rejection = rejected.get(request_id)
        if rejection is None:
            repaired_rows.append(row)
            continue
        request = requests.get(request_id)
        if request is None:
            raise ValueError(f"request missing for rejected row {request_id}")
        params = request.get("user_defined_params") or {}
        expected_record_id = str(params.get("record_id") or "")
        errors = [str(error) for error in rejection.get("errors") or []]
        payload = extract_json_object(output_text(row))
        before_atom_texts = atom_text_fingerprint(payload)
        repaired_payload, changes = repair_payload(payload, expected_record_id, errors)
        after_atom_texts = atom_text_fingerprint(repaired_payload)
        if before_atom_texts != after_atom_texts:
            raise AssertionError(f"atom text changed during metadata repair: {request_id}")
        repaired_row = copy.deepcopy(row)
        repaired_row["response"] = json.dumps(repaired_payload, ensure_ascii=False)
        repaired_rows.append(repaired_row)
        audit_rows.append(
            {
                "request_id": request_id,
                "record_id": expected_record_id,
                "source_errors": errors,
                "changes": changes,
                "payload_before_sha256": canonical_sha256(payload),
                "payload_after_sha256": canonical_sha256(repaired_payload),
                "atom_text_fingerprint_before": before_atom_texts,
                "atom_text_fingerprint_after": after_atom_texts,
                "atom_text_changed": False,
            }
        )

    if set(rejected) != {row["request_id"] for row in audit_rows}:
        raise AssertionError("not every rejected row received an audited repair")
    write_jsonl(args.output, repaired_rows)
    write_jsonl(args.audit, audit_rows)
    print(
        json.dumps(
            {
                "results": len(repaired_rows),
                "repaired": len(audit_rows),
                "atom_text_changes": 0,
                "output": str(args.output),
                "audit": str(args.audit),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
