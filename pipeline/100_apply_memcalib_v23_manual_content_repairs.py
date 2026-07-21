#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any

from memcalib_v23_common import V23_DIR, atom_index, canonical_sha256, file_sha256, portable_path
from utils import iter_jsonl, write_json, write_jsonl


DEFAULT_INPUT = V23_DIR / "memcalib_v23_repaired_records_334.jsonl"
DEFAULT_PATCHES = V23_DIR / "memcalib_v23_manual_content_repair_2.json"
DEFAULT_OUTPUT = V23_DIR / "memcalib_v23_repaired_records_manual_334.jsonl"
DEFAULT_AUDIT = V23_DIR / "memcalib_v23_manual_content_repair_2.audit.jsonl"
DEFAULT_MANIFEST = V23_DIR / "memcalib_v23_manual_content_repair_2.manifest.json"
LIST_MARKER_RE = re.compile(r"(?:^|\s)(?:\d{1,2}[.)]|[-*•])\s+")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply explicit minimal content repairs to residual v2.3 QC rejects."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--patches", type=Path, default=DEFAULT_PATCHES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    rows = list(iter_jsonl(args.input))
    ids = [str(row.get("id") or "") for row in rows]
    if "" in ids or len(ids) != len(set(ids)):
        raise ValueError("input record IDs must be non-empty and unique")
    records = dict(zip(ids, rows, strict=True))
    document = json.loads(args.patches.read_text(encoding="utf-8"))
    patches = document.get("patches")
    if not isinstance(patches, list) or not patches:
        raise ValueError("patch document must contain a non-empty patches list")

    audits: list[dict[str, Any]] = []
    for patch in patches:
        record_id = str(patch.get("record_id") or "")
        atom_id = str(patch.get("atom_id") or "")
        record = records.get(record_id)
        if record is None:
            raise ValueError(f"manual repair target is missing: {record_id}")
        original = copy.deepcopy(record)
        atoms = atom_index(record)
        atom = atoms.get(atom_id)
        if atom is None or atom.get("source") != "synthetic_v23_auxiliary":
            raise ValueError(f"manual repair atom is not a v2.3 auxiliary: {record_id}/{atom_id}")
        parent_id = str(atom.get("parent_memory_id") or "")
        if parent_id != str(patch.get("parent_memory_id") or ""):
            raise ValueError(f"manual repair parent mismatch: {record_id}/{atom_id}")
        block = next(
            (
                item
                for item in record.get("memory_blocks") or []
                if str(item.get("parent_memory_id") or "") == parent_id
            ),
            None,
        )
        if block is None or atom_id not in [str(value) for value in block.get("atom_ids") or []]:
            raise ValueError(f"manual repair block mapping is invalid: {record_id}/{atom_id}")

        before_atom = copy.deepcopy(atom)
        before_block_text = str(block.get("memory_text") or "")
        atom_patch = patch.get("atom") or {}
        for field in (
            "text",
            "memory_type",
            "subtype",
            "label_reason",
            "coherence_reason",
            "non_applicability_reason",
            "independence_reason",
        ):
            value = atom_patch.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"manual repair field is missing: {record_id}/{atom_id}/{field}")
            atom[field] = value.strip()
        atom["atomic_predicate"] = atom["text"]
        atom["construction_target"]["usage_boundary"] = atom["non_applicability_reason"]
        atom["counterfactual_contract"]["with_memory_behavior"] = (
            "Give the same answer without mentioning or using this atom."
        )
        atom["usage_rubric"]["validity_scope"] = atom["non_applicability_reason"]
        atom["usage_rubric"]["failure_direction"] = atom["label_reason"]

        memory_text = str(patch.get("memory_text") or "").strip()
        if not memory_text or "\n" in memory_text or LIST_MARKER_RE.search(memory_text):
            raise ValueError(f"manual repair memory_text is not one natural paragraph: {record_id}")
        block["memory_text"] = memory_text
        block["surface_form"] = "natural_paragraph"
        surface = copy.deepcopy(block.get("surface_rewrite") or {})
        surface["after_sha256"] = canonical_sha256(memory_text)
        surface["atom_text_fingerprint"] = canonical_sha256(
            [atoms[str(value)].get("text") for value in block.get("atom_ids") or []]
        )
        surface["local_manual_repair"] = True
        block["surface_rewrite"] = surface

        revision = copy.deepcopy(record.get("composite_block_revision") or {})
        revision["surface_rewrite_fingerprint"] = canonical_sha256(
            {
                str(item.get("parent_memory_id") or ""): canonical_sha256(
                    str(item.get("memory_text") or "")
                )
                for item in record.get("memory_blocks") or []
                if len(item.get("atom_ids") or []) >= 2
            }
        )
        record["composite_block_revision"] = revision
        record["manual_content_repair"] = {
            "schema_version": "memcalib-v23-manual-content-repair-v1",
            "atom_id": atom_id,
            "parent_memory_id": parent_id,
            "reason": str(patch.get("reason") or ""),
            "supervision_changed": False,
            "atom_count_changed": False,
            "block_count_changed": False,
        }

        if atom.get("u_star") != "A" or atom.get("memory_action") != "ignore":
            raise AssertionError(f"manual repair changed supervision: {record_id}/{atom_id}")
        if [item.get("atom_id") for item in record.get("memories") or []] != [
            item.get("atom_id") for item in original.get("memories") or []
        ]:
            raise AssertionError(f"manual repair changed atom IDs or order: {record_id}")
        if [item.get("parent_memory_id") for item in record.get("memory_blocks") or []] != [
            item.get("parent_memory_id") for item in original.get("memory_blocks") or []
        ]:
            raise AssertionError(f"manual repair changed block IDs or order: {record_id}")
        audits.append(
            {
                "record_id": record_id,
                "atom_id": atom_id,
                "parent_memory_id": parent_id,
                "reason": str(patch.get("reason") or ""),
                "record_before_sha256": canonical_sha256(original),
                "record_after_sha256": canonical_sha256(record),
                "atom_before_sha256": canonical_sha256(before_atom),
                "atom_after_sha256": canonical_sha256(atom),
                "block_text_before_sha256": canonical_sha256(before_block_text),
                "block_text_after_sha256": canonical_sha256(memory_text),
                "supervision_changed": False,
                "atom_count_changed": False,
                "block_count_changed": False,
            }
        )

    output_rows = [records[record_id] for record_id in ids]
    write_jsonl(args.output, output_rows)
    write_jsonl(args.audit, audits)
    manifest = {
        "schema_version": "memcalib-v23-manual-content-repair-manifest-v1",
        "policy": "minimal_single_atom_and_parent_paragraph_repair_for_residual_rejects",
        "inputs": {
            "records": {"path": portable_path(args.input), "sha256": file_sha256(args.input)},
            "patches": {"path": portable_path(args.patches), "sha256": file_sha256(args.patches)},
        },
        "repairs": {
            "records": len(audits),
            "atoms": len(audits),
            "supervision_changes": 0,
            "atom_count_changes": 0,
            "block_count_changes": 0,
        },
        "outputs": {
            "records": {"path": portable_path(args.output), "sha256": file_sha256(args.output)},
            "audit": {"path": portable_path(args.audit), "sha256": file_sha256(args.audit)},
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
