#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import importlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from memcalib_v23_common import canonical_sha256, file_sha256, norm_text, portable_path
from memcalib_v24_coding_common import V24_DIR
from utils import iter_jsonl, write_json, write_jsonl


release_builder = importlib.import_module("113_build_memcalib_v241_release")
alignment = importlib.import_module("110_audit_memcalib_v24_atom_alignment")
finalizer = importlib.import_module("123_finalize_memcalib_v241_curated_residual")

DEFAULT_CANDIDATE = (
    V24_DIR
    / "v241"
    / "intermediate"
    / "memcalib_v241_coding_candidate_3750.jsonl"
)
DEFAULT_BASE_RELEASE = (
    V24_DIR / "release" / "memcalib_v24_multidomain_benchmark_15000.jsonl"
)
DEFAULT_CODING_OUTPUT = (
    V24_DIR / "v241" / "memcalib_v241_coding_complete_3750.jsonl"
)
DEFAULT_RELEASE_OUTPUT = (
    V24_DIR
    / "v241"
    / "release"
    / "memcalib_v241_multidomain_benchmark_15000.jsonl"
)


def ensure_sentence(text: str) -> str:
    value = " ".join(str(text).split()).strip()
    if not value:
        return ""
    return value if value.endswith((".", "!", "?")) else value + "."


def reconcile_record(
    record: dict[str, Any],
    finding: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    output = copy.deepcopy(record)
    flagged_ids = {
        str(item.get("atom_id") or "") for item in finding.get("findings") or []
    }
    by_id = {
        str(atom.get("atom_id") or ""): atom
        for atom in output.get("memories") or []
    }
    missing_ids = flagged_ids - set(by_id)
    if missing_ids:
        raise ValueError(f"missing flagged atoms: {sorted(missing_ids)}")
    reference = str(output.get("source_answer") or "").strip()
    appended: list[str] = []
    rebuilt: list[dict[str, Any]] = []
    for atom in output.get("memories") or []:
        atom_id = str(atom.get("atom_id") or "")
        if atom_id not in flagged_ids:
            rebuilt.append(copy.deepcopy(atom))
            continue
        if atom.get("u_star") not in {"B", "C"}:
            raise ValueError(f"flagged atom is not scored: {output['id']}:{atom_id}")
        if atom.get("memory_action") != "apply":
            raise ValueError(
                f"non-apply atom requires semantic adjudication: {output['id']}:{atom_id}"
            )
        evidence = ensure_sentence(
            str(atom.get("atomic_predicate") or atom.get("text") or "")
        )
        if not evidence:
            raise ValueError(f"empty atom evidence: {output['id']}:{atom_id}")
        if norm_text(evidence).casefold() not in norm_text(reference).casefold():
            appended.append(evidence)
        rebuilt.append(finalizer.scored_supervision(atom, evidence))
    if appended:
        reference = (
            reference.rstrip()
            + "\n\nRelevant project context: "
            + " ".join(appended)
        )
    prior = copy.deepcopy(output.get("v241_alignment_remediation") or {})
    output["source_answer"] = reference
    output["memories"] = rebuilt
    output["v241_alignment_reconciliation"] = {
        "schema_version": "memcalib-v241-alignment-reconciliation-v1",
        "input_record_fingerprint": canonical_sha256(record),
        "flagged_atom_ids": sorted(flagged_ids),
        "reference_evidence_appended": appended,
        "repair_rule": "same_atom_apply_evidence_only",
        "labels_actions_atoms_and_blocks_preserved": True,
        "prior_alignment_remediation": prior,
    }
    residual = alignment.audit_record(output)
    if residual is not None:
        raise ValueError(
            f"deterministic alignment remains after reconciliation: {output['id']}"
        )
    audit = {
        "schema_version": "memcalib-v241-alignment-reconciliation-audit-v1",
        "record_id": output.get("id"),
        "flagged_atom_ids": sorted(flagged_ids),
        "input_findings": copy.deepcopy(finding.get("findings") or []),
        "reference_evidence_appended": appended,
        "input_record_fingerprint": canonical_sha256(record),
        "output_record_fingerprint": canonical_sha256(output),
    }
    return output, audit


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deterministically reconcile residual v2.4.1 atom/rubric risks."
    )
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--base-release", type=Path, default=DEFAULT_BASE_RELEASE)
    parser.add_argument("--coding-output", type=Path, default=DEFAULT_CODING_OUTPUT)
    parser.add_argument("--release-output", type=Path, default=DEFAULT_RELEASE_OUTPUT)
    parser.add_argument("--audit-output", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    candidate = list(iter_jsonl(args.candidate))
    base_release = list(iter_jsonl(args.base_release))
    findings: dict[str, dict[str, Any]] = {}
    for record in candidate:
        finding = alignment.audit_record(record)
        if finding is not None:
            findings[str(finding.get("record_id") or "")] = finding
    reconciled: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for record in candidate:
        record_id = str(record.get("id") or "")
        finding = findings.get(record_id)
        if finding is None:
            reconciled.append(copy.deepcopy(record))
            continue
        output, audit = reconcile_record(record, finding)
        reconciled.append(output)
        audits.append(audit)
    residual = [
        finding
        for record in reconciled
        if (finding := alignment.audit_record(record)) is not None
    ]
    if residual:
        raise ValueError(f"alignment reconciliation left {len(residual)} records")
    release = release_builder.replace_coding_release(base_release, reconciled)
    if len(reconciled) != 3750 or len(release) != 15000:
        raise ValueError(
            f"unexpected output size: coding={len(reconciled)}, release={len(release)}"
        )

    audit_output = args.audit_output or args.coding_output.with_suffix(".audit.jsonl")
    manifest = args.manifest or args.release_output.with_suffix(".manifest.json")
    write_jsonl(args.coding_output, reconciled)
    write_jsonl(args.release_output, release)
    write_jsonl(audit_output, audits)
    reason_counts: Counter[str] = Counter()
    flagged_atoms = 0
    for audit in audits:
        for item in audit["input_findings"]:
            flagged_atoms += 1
            reason_counts.update(item.get("reasons") or [])
    summary = {
        "schema_version": "memcalib-v241-alignment-reconciliation-summary-v1",
        "inputs": {
            "candidate": {
                "path": portable_path(args.candidate),
                "sha256": file_sha256(args.candidate),
                "records": len(candidate),
            },
            "base_release": {
                "path": portable_path(args.base_release),
                "sha256": file_sha256(args.base_release),
                "records": len(base_release),
            },
        },
        "counts": {
            "coding": len(reconciled),
            "release": len(release),
            "reconciled_records": len(audits),
            "reconciled_atoms": flagged_atoms,
            "original_reason_counts": dict(sorted(reason_counts.items())),
            "residual_alignment_findings": 0,
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
            "audit": {
                "path": portable_path(audit_output),
                "sha256": file_sha256(audit_output),
            },
        },
    }
    write_json(manifest, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
