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


DEFAULT_ORDER = V24_DIR / "memcalib_v24_coding_complete_3750.jsonl"
DEFAULT_BASE_RELEASE = (
    V24_DIR / "release" / "memcalib_v24_multidomain_benchmark_15000.jsonl"
)
DEFAULT_ACCEPTED_INPUTS = (
    (
        "retained_dual_strict",
        V24_DIR
        / "audit"
        / "memcalib_v241_semantic_qc_consensus_3750.strict.jsonl",
    ),
    (
        "locked_surface_dual_strict",
        V24_DIR
        / "audit"
        / "memcalib_v241_locked_surface_consensus_1586.strict.jsonl",
    ),
    (
        "practical_solution_r4_dual_strict",
        V24_DIR
        / "audit"
        / "memcalib_v241_practical_solution_r4_consensus_v2_1116.strict.jsonl",
    ),
    (
        "practical_solution_r5_dual_strict",
        V24_DIR
        / "audit"
        / "memcalib_v241_practical_solution_r5_consensus_v2_233.strict.jsonl",
    ),
    (
        "freeform_rewrite1_dual_strict",
        V24_DIR / "audit" / "memcalib_v241_rewrite1_consensus_1807.strict.jsonl",
    ),
    (
        "freeform_rewrite2_dual_strict",
        V24_DIR / "audit" / "memcalib_v241_rewrite2_consensus_229.strict.jsonl",
    ),
    (
        "freeform_rewrite3_dual_strict",
        V24_DIR / "audit" / "memcalib_v241_rewrite3_consensus_61.strict.jsonl",
    ),
    (
        "relabel_aware_candidate_dual_strict",
        V24_DIR
        / "audit"
        / "memcalib_v241_repaired_candidates_consensus_687.strict.jsonl",
    ),
    (
        "direct_question_repair_dual_strict",
        V24_DIR
        / "audit"
        / "memcalib_v241_direct_question_repair_consensus_511.strict.jsonl",
    ),
    (
        "curated_residual_final",
        V24_DIR / "audit" / "memcalib_v241_curated_residual_final_554.jsonl",
    ),
)
DEFAULT_CODING_OUTPUT = (
    V24_DIR
    / "v241"
    / "intermediate"
    / "memcalib_v241_coding_candidate_3750.jsonl"
)
DEFAULT_RELEASE_OUTPUT = (
    V24_DIR
    / "v241"
    / "intermediate"
    / "memcalib_v241_multidomain_candidate_15000.jsonl"
)

SCHEMA_VERSION = "memcalib-v241-alignment-remediation-v1"


def rows_by_id(
    rows: list[dict[str, Any]],
    name: str,
) -> dict[str, dict[str, Any]]:
    ids = [str(row.get("id") or "") for row in rows]
    if "" in ids or len(ids) != len(set(ids)):
        raise ValueError(f"{name} record IDs must be non-empty and unique")
    return dict(zip(ids, rows, strict=True))


def merge_coding_records(
    baseline: list[dict[str, Any]],
    retained: list[dict[str, Any]],
    repaired: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return merge_coding_record_groups(
        baseline,
        (
            ("retained_dual_strict", retained),
            ("targeted_rewrite_dual_strict", repaired),
        ),
    )


def atom_content_fingerprint(record: dict[str, Any]) -> str:
    return canonical_sha256(
        [
            {
                key: atom.get(key)
                for key in (
                    "memory_id",
                    "parent_memory_id",
                    "atom_id",
                    "atom_index",
                    "atom_count",
                    "text",
                    "evidence",
                    "atomic_predicate",
                    "derivation",
                    "source",
                    "memory_type",
                )
            }
            for atom in record.get("memories") or []
        ]
    )


def label_action_changes(
    baseline: dict[str, Any],
    selected: dict[str, Any],
) -> list[dict[str, Any]]:
    old = {
        str(atom.get("atom_id") or ""): atom
        for atom in baseline.get("memories") or []
    }
    changes: list[dict[str, Any]] = []
    for atom in selected.get("memories") or []:
        atom_id = str(atom.get("atom_id") or "")
        prior = old.get(atom_id, {})
        before = (prior.get("u_star"), prior.get("memory_action"))
        after = (atom.get("u_star"), atom.get("memory_action"))
        if before == after:
            continue
        changes.append(
            {
                "atom_id": atom_id,
                "old_u_star": before[0],
                "new_u_star": after[0],
                "old_memory_action": before[1],
                "new_memory_action": after[1],
            }
        )
    return changes


def merge_coding_record_groups(
    baseline: list[dict[str, Any]],
    groups: tuple[tuple[str, list[dict[str, Any]]], ...],
) -> list[dict[str, Any]]:
    baseline_by_id = rows_by_id(baseline, "baseline coding")
    merged_by_id: dict[str, dict[str, Any]] = {}
    channels: dict[str, str] = {}
    for channel, rows in groups:
        group = rows_by_id(rows, channel)
        overlap = set(merged_by_id) & set(group)
        if overlap:
            raise ValueError(
                f"accepted coding groups overlap: {sorted(overlap)[:20]}"
            )
        merged_by_id.update(group)
        channels.update({record_id: channel for record_id in group})
    missing = set(baseline_by_id) - set(merged_by_id)
    extra = set(merged_by_id) - set(baseline_by_id)
    if missing or extra:
        raise ValueError(
            "v2.4.1 coding coverage mismatch: "
            f"missing={sorted(missing)[:20]}, extra={sorted(extra)[:20]}"
        )
    merged: list[dict[str, Any]] = []
    for baseline_row in baseline:
        record_id = str(baseline_row["id"])
        selected = copy.deepcopy(merged_by_id[record_id])
        if selected.get("domain") != "coding":
            raise ValueError(f"v2.4.1 replacement is not coding: {record_id}")
        if atom_content_fingerprint(selected) != atom_content_fingerprint(baseline_row):
            raise ValueError(f"memory atom identity or text changed: {record_id}")
        if canonical_sha256(selected.get("memory_blocks") or []) != canonical_sha256(
            baseline_row.get("memory_blocks") or []
        ):
            raise ValueError(f"memory blocks changed: {record_id}")
        changes = label_action_changes(baseline_row, selected)
        selected["schema_version"] = "crk-2-canonical-memory-v2.4.1"
        selected["v241_alignment_remediation"] = {
            "schema_version": SCHEMA_VERSION,
            "channel": channels[record_id],
            "baseline_record_fingerprint": canonical_sha256(baseline_row),
            "output_record_fingerprint_before_annotation": canonical_sha256(selected),
            "atom_identity_and_text_preserved": True,
            "memory_blocks_preserved": True,
            "label_action_changes": changes,
        }
        merged.append(selected)
    return merged


def replace_coding_release(
    base_release: list[dict[str, Any]],
    coding: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    release_by_id = rows_by_id(base_release, "base release")
    coding_by_id = rows_by_id(coding, "v2.4.1 coding")
    base_coding_ids = {
        record_id
        for record_id, row in release_by_id.items()
        if row.get("domain") == "coding"
    }
    if set(coding_by_id) != base_coding_ids:
        raise ValueError("v2.4.1 coding IDs do not match base release coding IDs")
    return [
        copy.deepcopy(coding_by_id.get(str(row["id"]), row))
        for row in base_release
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build immutable MemCalib v2.4.1 coding and full releases."
    )
    parser.add_argument("--baseline-coding", type=Path, default=DEFAULT_ORDER)
    parser.add_argument("--base-release", type=Path, default=DEFAULT_BASE_RELEASE)
    parser.add_argument(
        "--accepted",
        action="append",
        default=[],
        metavar="CHANNEL=PATH",
        help="Accepted coding partition; repeat for every mutually exclusive channel.",
    )
    parser.add_argument("--coding-output", type=Path, default=DEFAULT_CODING_OUTPUT)
    parser.add_argument("--release-output", type=Path, default=DEFAULT_RELEASE_OUTPUT)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    manifest_path = args.manifest or args.release_output.with_suffix(".manifest.json")

    baseline = list(iter_jsonl(args.baseline_coding))
    base_release = list(iter_jsonl(args.base_release))
    accepted_specs: list[tuple[str, Path]] = []
    if args.accepted:
        for value in args.accepted:
            channel, separator, raw_path = str(value).partition("=")
            if not separator or not channel or not raw_path:
                raise ValueError("--accepted must use CHANNEL=PATH")
            accepted_specs.append((channel, Path(raw_path)))
    else:
        accepted_specs = list(DEFAULT_ACCEPTED_INPUTS)
    accepted_groups = tuple(
        (channel, list(iter_jsonl(path))) for channel, path in accepted_specs
    )
    coding = merge_coding_record_groups(baseline, accepted_groups)
    release = replace_coding_release(base_release, coding)
    if len(coding) != 3750 or len(release) != 15000:
        raise ValueError(
            f"unexpected release size: coding={len(coding)}, release={len(release)}"
        )
    write_jsonl(args.coding_output, coding)
    write_jsonl(args.release_output, release)
    manifest = {
        "schema_version": f"{SCHEMA_VERSION}-manifest",
        "inputs": {
            key: {
                "path": portable_path(path),
                "sha256": file_sha256(path),
            }
            for key, path in {
                "baseline_coding": args.baseline_coding,
                "base_release": args.base_release,
            }.items()
        }
        | {
            "accepted": [
                {
                    "channel": channel,
                    "path": portable_path(path),
                    "sha256": file_sha256(path),
                    "records": len(rows),
                }
                for (channel, path), (_, rows) in zip(
                    accepted_specs, accepted_groups, strict=True
                )
            ]
        },
        "counts": {
            "coding": len(coding),
            "accepted_by_channel": {
                channel: len(rows) for channel, rows in accepted_groups
            },
            "release": len(release),
        },
        "outputs": {
            "coding": {
                "path": portable_path(args.coding_output),
                "sha256": file_sha256(args.coding_output),
            },
            "release": {
                "path": portable_path(args.release_output),
                "sha256": file_sha256(args.release_output),
            },
        },
    }
    write_json(manifest_path, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
