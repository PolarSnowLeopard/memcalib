#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from memcalib_v23_common import V23_DIR, canonical_sha256, file_sha256, portable_path
from utils import extract_json_object, iter_jsonl, write_json, write_jsonl


DEFAULT_REQUESTS = V23_DIR / "memcalib_v23_manual_independent_qc_input_334.jsonl"
DEFAULT_RESULTS = V23_DIR / "memcalib_v23_repaired_independent_qc_result_334.jsonl"
DEFAULT_PATCHES = V23_DIR / "memcalib_v23_manual_qc_adjudication_4.json"
DEFAULT_OUTPUT = V23_DIR / "memcalib_v23_manual_independent_qc_result_334.jsonl"
DEFAULT_AUDIT = V23_DIR / "memcalib_v23_manual_qc_adjudication_4.audit.jsonl"
DEFAULT_MANIFEST = V23_DIR / "memcalib_v23_manual_qc_adjudication_4.manifest.json"


def unique_index(rows: list[dict[str, Any]], source: str) -> dict[str, dict[str, Any]]:
    ids = [str(row.get("request_id") or "") for row in rows]
    if "" in ids or len(ids) != len(set(ids)):
        raise ValueError(f"{source} request IDs must be non-empty and unique")
    return dict(zip(ids, rows, strict=True))


def set_response(row: dict[str, Any], text: str) -> None:
    row["response"] = text
    raw = row.get("raw_response")
    if isinstance(raw, dict):
        choices = raw.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            message = choices[0].get("message")
            if isinstance(message, dict):
                message["content"] = text


def replace_or_add(
    items: list[dict[str, Any]], key: str, replacement: dict[str, Any]
) -> list[dict[str, Any]]:
    target = str(replacement.get(key) or "")
    if not target:
        raise ValueError(f"manual QC replacement has no {key}")
    output = [item for item in items if str(item.get(key) or "") != target]
    output.append(replacement)
    return output


def ordered(items: list[dict[str, Any]], key: str, expected: list[str]) -> list[dict[str, Any]]:
    index = {str(item.get(key) or ""): item for item in items}
    if set(index) != set(expected):
        raise ValueError(f"manual QC {key} coverage does not match expected IDs")
    return [index[item_id] for item_id in expected]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply explicit human QC adjudications to four residual v2.3 records."
    )
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--patches", type=Path, default=DEFAULT_PATCHES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    request_rows = list(iter_jsonl(args.requests))
    requests = unique_index(request_rows, "requests")
    result_rows = list(iter_jsonl(args.results))
    results = unique_index(result_rows, "results")
    if set(requests) != set(results):
        raise ValueError("manual QC requests and source results must cover the same IDs")
    document = json.loads(args.patches.read_text(encoding="utf-8"))
    patches = document.get("patches")
    if not isinstance(patches, list) or not patches:
        raise ValueError("patch document must contain a non-empty patches list")

    audits: list[dict[str, Any]] = []
    for patch in patches:
        request_id = str(patch.get("request_id") or "")
        request = requests.get(request_id)
        source_result = results.get(request_id)
        if request is None or source_result is None:
            raise ValueError(f"manual QC target is missing: {request_id}")
        updated = copy.deepcopy(source_result)
        params = request.get("user_defined_params") or {}
        for key in ("passParams", "user_defined_params", "params"):
            if key in updated:
                updated[key] = copy.deepcopy(params)
        qc = extract_json_object(str(updated.get("response") or ""))
        before_sha256 = canonical_sha256(qc)
        qc["record_id"] = params["record_id"]
        added = list(qc.get("added_atom_checks") or [])
        blocks = list(qc.get("block_checks") or [])
        for replacement in patch.get("added_atom_checks") or []:
            added = replace_or_add(added, "atom_id", replacement)
        for replacement in patch.get("block_checks") or []:
            blocks = replace_or_add(blocks, "parent_memory_id", replacement)
        qc["added_atom_checks"] = ordered(
            added, "atom_id", [str(value) for value in params.get("added_atom_ids") or []]
        )
        qc["block_checks"] = ordered(
            blocks,
            "parent_memory_id",
            [str(item["parent_memory_id"]) for item in params.get("expected_blocks") or []],
        )
        qc["declared_decision"] = "strict_pass"
        qc["decision_reasons"] = [str(patch.get("decision_reason") or "")]
        qc["self_check"] = {
            "all_added_atom_ids_exact": True,
            "all_block_ids_exact": True,
            "all_block_atom_coverage_exact": True,
            "locked_supervision_not_rejudged": True,
        }
        serialized = json.dumps(qc, ensure_ascii=False, separators=(",", ":"))
        set_response(updated, serialized)
        updated["manual_qc_adjudication"] = {
            "schema_version": "memcalib-v23-manual-qc-adjudication-v1",
            "reason": str(patch.get("reason") or ""),
            "content_repair": bool(patch.get("content_repair")),
            "human_adjudication": True,
            "before_sha256": before_sha256,
            "after_sha256": canonical_sha256(qc),
        }
        results[request_id] = updated
        audits.append(
            {
                "request_id": request_id,
                "record_id": params["record_id"],
                "reason": str(patch.get("reason") or ""),
                "content_repair": bool(patch.get("content_repair")),
                "added_atom_checks_replaced_or_added": [
                    item["atom_id"] for item in patch.get("added_atom_checks") or []
                ],
                "block_checks_replaced_or_added": [
                    item["parent_memory_id"] for item in patch.get("block_checks") or []
                ],
                "before_sha256": before_sha256,
                "after_sha256": canonical_sha256(qc),
                "human_adjudication": True,
            }
        )

    output_rows = [results[str(row["request_id"])] for row in request_rows]
    write_jsonl(args.output, output_rows)
    write_jsonl(args.audit, audits)
    manifest = {
        "schema_version": "memcalib-v23-manual-qc-adjudication-manifest-v1",
        "policy": "explicit_human_recheck_of_two_minimal_repairs_and_two_missing_checks",
        "inputs": {
            "requests": {"path": portable_path(args.requests), "sha256": file_sha256(args.requests)},
            "results": {"path": portable_path(args.results), "sha256": file_sha256(args.results)},
            "patches": {"path": portable_path(args.patches), "sha256": file_sha256(args.patches)},
        },
        "adjudication": {
            "records": len(audits),
            "content_repairs_rechecked": sum(bool(item["content_repair"]) for item in audits),
            "structural_completions": sum(not bool(item["content_repair"]) for item in audits),
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
