#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from importlib import import_module
from pathlib import Path
from typing import Any

from memcalib_v23_common import canonical_sha256, file_sha256, portable_path
from memcalib_v24_coding_common import (
    V23_RELEASE,
    V24_DIR,
    locked_supervision_fingerprint,
)
from utils import iter_jsonl, write_json, write_jsonl


POST = import_module("103_post_memcalib_v24_coding_rewrite")

DEFAULT_STRICT_INPUTS = [
    V24_DIR / "memcalib_v24_coding_independent_qc_3750.strict.jsonl",
    V24_DIR / "memcalib_v24_coding_independent_qc_retry1_739.strict.jsonl",
    V24_DIR
    / "memcalib_v24_coding_independent_qc_retry1_salvaged_198.strict.jsonl",
    V24_DIR / "memcalib_v24_coding_independent_qc_retry2_429.strict.jsonl",
    V24_DIR / "memcalib_v24_coding_independent_qc_retry3_308.strict.jsonl",
    V24_DIR / "memcalib_v24_coding_independent_qc_retry4_184.strict.jsonl",
    V24_DIR / "memcalib_v24_coding_independent_qc_local_repair_163.strict.jsonl",
    V24_DIR / "memcalib_v24_coding_independent_qc_local_repair2_55.strict.jsonl",
    V24_DIR / "memcalib_v24_coding_independent_qc_local_repair3_43.strict.jsonl",
]
DEFAULT_MANUAL_INPUTS = [
    V24_DIR / "memcalib_v24_coding_manual_adjudication_15.jsonl",
]
DEFAULT_OUTPUT = V24_DIR / "memcalib_v24_coding_complete_3750.jsonl"
DEFAULT_AUDIT = DEFAULT_OUTPUT.with_suffix(".audit.jsonl")
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")


def validation_params(
    source: dict[str, Any], record: dict[str, Any]
) -> dict[str, Any]:
    revision = record.get("coding_text_observability_revision")
    if not isinstance(revision, dict):
        raise ValueError(f"{record.get('id')}: coding revision missing")
    return {
        "record_id": source["id"],
        "source_record_fingerprint": canonical_sha256(source),
        "locked_supervision_fingerprint": locked_supervision_fingerprint(source),
        "memory_blocks_fingerprint": canonical_sha256(
            source.get("memory_blocks") or []
        ),
        "task_family": revision.get("task_family"),
        "retry_round": revision.get("retry_round"),
        "retry_feedback_fingerprint": revision.get(
            "retry_feedback_fingerprint"
        ),
    }


def load_channel(
    paths: list[Path],
    *,
    channel: str,
    source_by_id: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], Counter[str]]:
    records: dict[str, dict[str, Any]] = {}
    audits: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for path in paths:
        rows = list(iter_jsonl(path))
        path_portable = portable_path(path)
        path_sha256 = file_sha256(path)
        path_ids = [str(row.get("id") or "") for row in rows]
        if "" in path_ids or len(path_ids) != len(set(path_ids)):
            raise ValueError(f"{path}: record IDs must be non-empty and unique")
        for input_record in rows:
            record_id = str(input_record.get("id") or "")
            if record_id in records:
                raise ValueError(f"{record_id}: duplicated across {channel} inputs")
            source = source_by_id.get(record_id)
            if source is None or source.get("domain") != "coding":
                raise ValueError(f"{record_id}: not a source coding record")

            if channel == "independent_qc_strict":
                qc = input_record.get("v24_coding_independent_qc")
                if not isinstance(qc, dict) or qc.get("decision") != "strict_pass":
                    raise ValueError(f"{record_id}: input is not independent-QC strict")
                admission_decision = "strict_pass"
            else:
                adjudication = input_record.get("v24_manual_adjudication")
                if (
                    not isinstance(adjudication, dict)
                    or adjudication.get("decision") != "manual_adjudicated_strict"
                    or adjudication.get("labels_and_actions_changed") is not False
                    or adjudication.get("deterministic_validators_passed") is not True
                ):
                    raise ValueError(
                        f"{record_id}: invalid manual-adjudication provenance"
                    )
                admission_decision = "manual_adjudicated_strict"

            record = copy.deepcopy(input_record)
            params = validation_params(source, record)
            errors = POST.validate_built_record(record, source, params)
            if errors:
                raise ValueError(f"{record_id}: deterministic validation failed: {errors}")
            revision = record["coding_text_observability_revision"]
            if revision.get("source_record_fingerprint") != canonical_sha256(source):
                raise ValueError(f"{record_id}: revision source fingerprint mismatch")

            record["v24_coding_admission"] = {
                "schema_version": "memcalib-v24-coding-admission-v1",
                "decision": admission_decision,
                "channel": channel,
                "source_path": path_portable,
                "source_file_sha256": path_sha256,
            }
            records[record_id] = record
            counts[path_portable] += 1
            audits.append(
                {
                    "schema_version": "memcalib-v24-coding-merge-audit-v1",
                    "record_id": record_id,
                    "channel": channel,
                    "decision": admission_decision,
                    "source_path": path_portable,
                    "source_file_sha256": path_sha256,
                    "source_record_fingerprint": canonical_sha256(source),
                    "input_record_fingerprint": canonical_sha256(input_record),
                    "output_record_fingerprint": canonical_sha256(record),
                }
            )
    return records, audits, counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge all accepted MemCalib v2.4 coding revision rounds."
    )
    parser.add_argument("--benchmark", type=Path, default=V23_RELEASE)
    parser.add_argument(
        "--strict-jsonl", type=Path, action="append", default=None
    )
    parser.add_argument(
        "--manual-jsonl", type=Path, action="append", default=None
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    strict_paths = args.strict_jsonl or DEFAULT_STRICT_INPUTS
    manual_paths = args.manual_jsonl or DEFAULT_MANUAL_INPUTS
    source_rows = list(iter_jsonl(args.benchmark))
    source_coding = [row for row in source_rows if row.get("domain") == "coding"]
    source_by_id = {str(row.get("id") or ""): row for row in source_coding}
    source_ids = [str(row.get("id") or "") for row in source_coding]
    if len(source_ids) != 3750 or len(source_ids) != len(set(source_ids)):
        raise ValueError("source benchmark must contain 3,750 unique coding records")

    strict, strict_audit, strict_counts = load_channel(
        strict_paths,
        channel="independent_qc_strict",
        source_by_id=source_by_id,
    )
    manual, manual_audit, manual_counts = load_channel(
        manual_paths,
        channel="manual_adjudication",
        source_by_id=source_by_id,
    )
    overlap = set(strict) & set(manual)
    if overlap:
        raise ValueError(f"strict/manual overlap: {sorted(overlap)[:20]}")
    merged_by_id = {**strict, **manual}
    missing = set(source_ids) - set(merged_by_id)
    extra = set(merged_by_id) - set(source_ids)
    if missing or extra or len(merged_by_id) != 3750:
        raise ValueError(
            "coding coverage mismatch: "
            f"merged={len(merged_by_id)}, missing={sorted(missing)[:20]}, "
            f"extra={sorted(extra)[:20]}"
        )

    output = [merged_by_id[record_id] for record_id in source_ids]
    audits_by_id = {
        str(row["record_id"]): row for row in strict_audit + manual_audit
    }
    audits = [audits_by_id[record_id] for record_id in source_ids]
    write_jsonl(args.output, output)
    write_jsonl(args.audit, audits)
    manifest = {
        "schema_version": "memcalib-v24-coding-merge-manifest-v1",
        "inputs": {
            "benchmark": {
                "path": portable_path(args.benchmark),
                "sha256": file_sha256(args.benchmark),
            },
            "independent_qc_strict": [
                {
                    "path": portable_path(path),
                    "sha256": file_sha256(path),
                    "records": strict_counts[portable_path(path)],
                }
                for path in strict_paths
            ],
            "manual_adjudication": [
                {
                    "path": portable_path(path),
                    "sha256": file_sha256(path),
                    "records": manual_counts[portable_path(path)],
                }
                for path in manual_paths
            ],
        },
        "counts": {
            "source_coding": len(source_coding),
            "independent_qc_strict": len(strict),
            "manual_adjudicated_strict": len(manual),
            "merged": len(output),
            "unique_record_ids": len(merged_by_id),
            "task_family": dict(
                sorted(
                    Counter(
                        row["coding_text_observability_revision"]["task_family"]
                        for row in output
                    ).items()
                )
            ),
        },
        "invariants": {
            "source_order_preserved": True,
            "exact_source_coding_coverage": True,
            "labels_actions_memory_atoms_and_blocks_locked": True,
            "all_records_pass_deterministic_text_observability_validators": True,
        },
        "outputs": {
            "records": {
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
