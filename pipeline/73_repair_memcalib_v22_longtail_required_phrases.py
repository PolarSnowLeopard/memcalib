#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from utils import iter_jsonl, norm_text, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
V22_DIR = SCRIPT_DIR / "data" / "multidomain" / "full-v2" / "revision-longtail-blocks"
DEFAULT_REJECTED = (
    V22_DIR / "memcalib_v22_longtail_benchmark_semanticregex_15000.rejected.jsonl"
)
DEFAULT_OUTPUT = V22_DIR / "memcalib_v22_longtail_local_repair_result.jsonl"
DEFAULT_AUDIT = V22_DIR / "memcalib_v22_longtail_local_repair.audit.jsonl"
DEFAULT_MANIFEST = V22_DIR / "memcalib_v22_longtail_local_repair.manifest.json"
REPAIR_SCHEMA = "memcalib-v22-longtail-required-phrase-repair-v1"
ERROR_RE = re.compile(
    r"^synthetic_blocks\[(\d+)\]\.generated_atoms\[(\d+)\]"
    r"\.required_phrase_missing$"
)


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


def repaired_text(required_phrases: list[str]) -> str:
    if len(required_phrases) != 3 or any(not norm_text(value) for value in required_phrases):
        raise ValueError("expected exactly three non-empty required phrases")
    object_phrase, setting_phrase, time_phrase = map(norm_text, required_phrases)
    return (
        f"At the {setting_phrase} in {time_phrase}, the user attached a handwritten "
        f"inventory tag to the {object_phrase}."
    )


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


def repair_rejected_row(
    row: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    errors = row.get("errors")
    if not isinstance(errors, list) or not errors:
        raise ValueError("rejected row must contain at least one error")
    locations: list[tuple[int, int, str]] = []
    for raw_error in errors:
        error = str(raw_error)
        match = ERROR_RE.fullmatch(error)
        if not match:
            raise ValueError(f"unsupported local repair error: {error}")
        locations.append((int(match.group(1)), int(match.group(2)), error))

    request = row.get("request")
    payload = copy.deepcopy(row.get("parsed_payload"))
    result = row.get("result")
    if not isinstance(request, dict) or not isinstance(payload, dict) or not isinstance(result, dict):
        raise ValueError("rejected row is missing request, parsed_payload, or result")
    params = request.get("user_defined_params")
    plan = params.get("plan") if isinstance(params, dict) else None
    plan_blocks = plan.get("synthetic_blocks") if isinstance(plan, dict) else None
    payload_blocks = payload.get("synthetic_blocks")
    if not isinstance(plan_blocks, list) or not isinstance(payload_blocks, list):
        raise ValueError("request plan or parsed payload is missing synthetic blocks")
    if len(plan_blocks) != len(payload_blocks):
        raise ValueError("request plan and parsed payload block counts differ")

    audits: list[dict[str, Any]] = []
    seen_locations: set[tuple[int, int]] = set()
    for block_index, atom_index, error in locations:
        location = (block_index, atom_index)
        if location in seen_locations:
            raise ValueError(f"duplicate repair location: {location}")
        seen_locations.add(location)
        try:
            plan_block = plan_blocks[block_index]
            payload_block = payload_blocks[block_index]
            plan_atom = plan_block["generated_atom_specs"][atom_index]
            payload_atom = payload_block["generated_atoms"][atom_index]
        except (IndexError, KeyError, TypeError) as exc:
            raise ValueError(f"invalid repair location: {location}") from exc
        if plan_block.get("contains_canonical_hard_a"):
            raise ValueError("canonical Hard A blocks cannot be locally repaired")
        if plan_block.get("parent_memory_id") != payload_block.get("parent_memory_id"):
            raise ValueError("plan and payload parent_memory_id mismatch")
        atom_id = str(plan_atom.get("atom_id") or "")
        if not atom_id or atom_id != str(payload_atom.get("atom_id") or ""):
            raise ValueError("plan and payload atom_id mismatch")
        before = norm_text(str(payload_atom.get("text") or ""))
        after = repaired_text(list(plan_atom.get("required_phrases") or []))
        if before == after:
            raise ValueError("local repair did not change the atom text")
        payload_atom["text"] = after
        audits.append(
            {
                "schema_version": REPAIR_SCHEMA,
                "request_id": str(row.get("request_id") or ""),
                "record_id": str(row.get("record_id") or ""),
                "error": error,
                "block_index": block_index,
                "atom_index": atom_index,
                "parent_memory_id": str(plan_block.get("parent_memory_id") or ""),
                "atom_id": atom_id,
                "required_phrases": list(plan_atom.get("required_phrases") or []),
                "before_text": before,
                "after_text": after,
                "before_text_sha256": canonical_sha256(before),
                "after_text_sha256": canonical_sha256(after),
            }
        )
    return replace_response(result, payload), audits


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Deterministically repair only planned phrase omissions in rejected "
            "MemCalib v2.2 auxiliary atoms."
        )
    )
    parser.add_argument("--rejected", type=Path, default=DEFAULT_REJECTED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    rejected_rows = list(iter_jsonl(args.rejected))
    repaired_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    for row in rejected_rows:
        repaired, audits = repair_rejected_row(row)
        repaired_rows.append(repaired)
        audit_rows.extend(audits)
    request_ids = [str(row.get("request_id") or "") for row in repaired_rows]
    if "" in request_ids or len(request_ids) != len(set(request_ids)):
        raise ValueError("repaired result request IDs must be non-empty and unique")

    write_jsonl(args.output, repaired_rows)
    write_jsonl(args.audit, audit_rows)
    manifest = {
        "schema_version": REPAIR_SCHEMA,
        "input": {
            "path": portable_path(args.rejected),
            "sha256": file_sha256(args.rejected),
            "rejected_records": len(rejected_rows),
        },
        "counts": {
            "repaired_records": len(repaired_rows),
            "repaired_atoms": len(audit_rows),
            "unique_request_ids": len(set(request_ids)),
        },
        "outputs": {
            "results": {
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
