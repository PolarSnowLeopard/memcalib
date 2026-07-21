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
DEFAULT_PATCHES = V23_DIR / "memcalib_v23_independent_qc_manual_completion_2.json"
DEFAULT_OUTPUT = V23_DIR / "memcalib_v23_independent_qc_final_result_15000.jsonl"
DEFAULT_AUDIT = V23_DIR / "memcalib_v23_independent_qc_manual_completion_2.audit.jsonl"
DEFAULT_MANIFEST = V23_DIR / "memcalib_v23_independent_qc_manual_completion_2.manifest.json"


def unique_index(rows: list[dict], source: str) -> dict[str, dict]:
    ids = [str(row.get("request_id") or "") for row in rows]
    if "" in ids or len(ids) != len(set(ids)):
        raise ValueError(f"{source} request IDs must be non-empty and unique")
    return dict(zip(ids, rows, strict=True))


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


def ordered(items: list[dict], key: str, expected: list[str]) -> list[dict]:
    index = {str(item.get(key) or ""): item for item in items}
    if set(index) != set(expected):
        raise ValueError(f"completed {key} coverage does not match expected IDs")
    return [index[item_id] for item_id in expected]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply explicit human completions for residual missing QC checks."
    )
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--patches", type=Path, default=DEFAULT_PATCHES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    requests = unique_index(list(iter_jsonl(args.requests)), "requests")
    result_rows = list(iter_jsonl(args.results))
    results = unique_index(result_rows, "results")
    patch_document = json.loads(args.patches.read_text(encoding="utf-8"))
    patches = patch_document.get("patches")
    if not isinstance(patches, list) or not patches:
        raise ValueError("patch document must contain a non-empty patches list")

    audits: list[dict[str, Any]] = []
    for patch in patches:
        request_id = str(patch.get("request_id") or "")
        request = requests.get(request_id)
        row = results.get(request_id)
        if request is None or row is None:
            raise ValueError(f"manual completion target missing: {request_id}")
        params = request.get("user_defined_params") or request.get("passParams") or {}
        qc = extract_json_object(str(row.get("response") or ""))
        before_sha256 = canonical_sha256(qc)

        added_checks = list(qc.get("added_atom_checks") or [])
        block_checks = list(qc.get("block_checks") or [])
        inserted_added = patch.get("added_atom_check")
        inserted_block = patch.get("block_check")
        if inserted_added is not None:
            atom_id = str(inserted_added.get("atom_id") or "")
            if atom_id in {str(item.get("atom_id") or "") for item in added_checks}:
                raise ValueError(f"added atom check already present: {request_id}/{atom_id}")
            added_checks.append(inserted_added)
        if inserted_block is not None:
            parent_id = str(inserted_block.get("parent_memory_id") or "")
            if parent_id in {
                str(item.get("parent_memory_id") or "") for item in block_checks
            }:
                raise ValueError(f"block check already present: {request_id}/{parent_id}")
            block_checks.append(inserted_block)

        qc["added_atom_checks"] = ordered(
            added_checks,
            "atom_id",
            [str(atom_id) for atom_id in params.get("added_atom_ids") or []],
        )
        qc["block_checks"] = ordered(
            block_checks,
            "parent_memory_id",
            [
                str(block.get("parent_memory_id") or "")
                for block in params.get("expected_blocks") or []
            ],
        )
        serialized = json.dumps(qc, ensure_ascii=False, separators=(",", ":"))
        updated = copy.deepcopy(row)
        set_response_text(updated, serialized)
        updated["manual_structural_completion"] = {
            "schema_version": "memcalib-v23-qc-manual-completion-v1",
            "reason": str(patch.get("reason") or ""),
            "before_sha256": before_sha256,
            "after_sha256": canonical_sha256(qc),
            "manual_adjudication": True,
        }
        results[request_id] = updated
        audits.append(
            {
                "request_id": request_id,
                "reason": str(patch.get("reason") or ""),
                "inserted_added_atom_id": (
                    inserted_added.get("atom_id") if inserted_added else None
                ),
                "inserted_parent_memory_id": (
                    inserted_block.get("parent_memory_id") if inserted_block else None
                ),
                "before_sha256": before_sha256,
                "after_sha256": canonical_sha256(qc),
                "manual_adjudication": True,
            }
        )

    output_rows = [results[str(row["request_id"])] for row in result_rows]
    write_jsonl(args.output, output_rows)
    write_jsonl(args.audit, audits)
    manifest = {
        "schema_version": "memcalib-v23-qc-manual-completion-manifest-v1",
        "policy": "explicit_human_completion_for_persistently_missing_checks",
        "inputs": {
            "requests": {"path": portable_path(args.requests), "sha256": file_sha256(args.requests)},
            "results": {"path": portable_path(args.results), "sha256": file_sha256(args.results)},
            "patches": {"path": portable_path(args.patches), "sha256": file_sha256(args.patches)},
        },
        "completion": {
            "patched_results": len(audits),
            "manual_adjudications": len(audits),
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
