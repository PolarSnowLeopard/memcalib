#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from memcalib_v23_common import V23_DIR, canonical_sha256, file_sha256, portable_path
from utils import extract_json_object, iter_jsonl, write_json, write_jsonl


DEFAULT_RESULTS = V23_DIR / "memcalib_v23_surface_rewrite_resolved_result_15000.jsonl"
DEFAULT_PATCHES = V23_DIR / "memcalib_v23_surface_rewrite_residual_patch_4.json"
DEFAULT_OUTPUT = V23_DIR / "memcalib_v23_surface_rewrite_patched_result_15000.jsonl"
DEFAULT_AUDIT = V23_DIR / "memcalib_v23_surface_rewrite_residual_patch_4.audit.jsonl"
DEFAULT_MANIFEST = V23_DIR / "memcalib_v23_surface_rewrite_residual_patch_4.manifest.json"


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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply explicit, audited residual surface-rewrite patches."
    )
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--patches", type=Path, default=DEFAULT_PATCHES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    rows = list(iter_jsonl(args.results))
    result_ids = [str(row.get("request_id") or "") for row in rows]
    if "" in result_ids or len(result_ids) != len(set(result_ids)):
        raise ValueError("result request IDs must be non-empty and unique")
    results = dict(zip(result_ids, rows, strict=True))
    patch_document = json.loads(args.patches.read_text(encoding="utf-8"))
    patches = patch_document.get("patches")
    if not isinstance(patches, list) or not patches:
        raise ValueError("patch document must contain a non-empty patches list")

    audits: list[dict[str, Any]] = []
    patched_ids: set[str] = set()
    for patch in patches:
        record_id = str(patch.get("record_id") or "")
        parent_id = str(patch.get("parent_memory_id") or "")
        request_id = f"v23_surface_rewrite:{record_id}"
        if request_id in patched_ids:
            raise ValueError(f"duplicate patch for {request_id}")
        row = results.get(request_id)
        if row is None:
            raise ValueError(f"patch target missing: {request_id}")
        payload = extract_json_object(response_text(row))
        blocks = payload.get("blocks")
        if not isinstance(blocks, list):
            raise ValueError(f"patch target {request_id} has no blocks list")
        matching = [
            block
            for block in blocks
            if isinstance(block, dict)
            and str(block.get("parent_memory_id") or "") == parent_id
        ]
        if len(matching) != 1:
            raise ValueError(
                f"patch target {request_id}/{parent_id} matched {len(matching)} blocks"
            )
        block = matching[0]
        before = str(block.get("memory_text") or "")
        expected = str(patch.get("expected_text") or "")
        after = str(patch.get("replacement_text") or "")
        if before != expected:
            raise ValueError(f"patch precondition failed for {request_id}/{parent_id}")
        if not after.strip() or "\n" in after or "\r" in after:
            raise ValueError(f"replacement must be one non-empty paragraph: {request_id}")
        block["memory_text"] = after
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        updated = copy.deepcopy(row)
        set_response_text(updated, serialized)
        updated["local_deterministic_repair"] = {
            "schema_version": "memcalib-v23-surface-rewrite-local-patch-v1",
            "parent_memory_id": parent_id,
            "before_sha256": canonical_sha256(before),
            "after_sha256": canonical_sha256(after),
            "reason": str(patch.get("reason") or ""),
            "atom_content_changed": False,
        }
        results[request_id] = updated
        patched_ids.add(request_id)
        audits.append(
            {
                "request_id": request_id,
                "record_id": record_id,
                "parent_memory_id": parent_id,
                "reason": str(patch.get("reason") or ""),
                "before_sha256": canonical_sha256(before),
                "after_sha256": canonical_sha256(after),
                "before_text": before,
                "after_text": after,
                "atom_content_changed": False,
            }
        )

    output_rows = [results[request_id] for request_id in result_ids]
    write_jsonl(args.output, output_rows)
    write_jsonl(args.audit, audits)
    manifest = {
        "schema_version": "memcalib-v23-surface-rewrite-local-patch-manifest-v1",
        "policy": "explicit_text_patch_with_exact_precondition",
        "inputs": {
            "results": {
                "path": portable_path(args.results),
                "sha256": file_sha256(args.results),
                "count": len(rows),
            },
            "patches": {
                "path": portable_path(args.patches),
                "sha256": file_sha256(args.patches),
                "count": len(patches),
            },
        },
        "repair": {
            "patched_results": len(patched_ids),
            "atom_content_changes": 0,
            "audit_rows": len(audits),
        },
        "outputs": {
            "results": {
                "path": portable_path(args.output),
                "sha256": file_sha256(args.output),
                "count": len(output_rows),
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
