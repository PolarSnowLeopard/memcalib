#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path
from typing import Any

from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data" / "multidomain" / "full-v2"
REVISION_DIR = DATA_DIR / "revision-composite-harda"
DEFAULT_SOURCE = DATA_DIR / "memcalib_v02_multidomain_benchmark_15000.jsonl"
DEFAULT_QC_INPUTS = [
    REVISION_DIR / "memcalib_v21_composite_harda_independent_qc_15000.reject.jsonl",
    REVISION_DIR / "memcalib_v21_composite_harda_independent_qc_15000.review.jsonl",
]
DEFAULT_OUTPUT = REVISION_DIR / "repair1" / "composite_harda_patch_repair1_input.jsonl"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")
DEFAULT_DEFERRED = REVISION_DIR / "repair1" / "composite_harda_patch_repair1_deferred.jsonl"
PREPARE_SCRIPT = SCRIPT_DIR / "54_prepare_memcalib_v2_composite_harda_revision.py"
PROMPT_TEMPLATE = SCRIPT_DIR / "prompts" / "reconstruct_memcalib_v2_composite_harda_patch_en.txt"
SCHEMA_VERSION = "memcalib-composite-harda-patch-repair-requests-v1"


def load_prepare_module():
    spec = importlib.util.spec_from_file_location("prepare_memcalib_composite_harda", PREPARE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(SCRIPT_DIR.parent))
    except ValueError:
        return str(resolved)


def hard_a_atom(record: dict[str, Any]) -> dict[str, Any]:
    atoms = [
        atom
        for atom in record.get("memories") or []
        if isinstance(atom, dict) and atom.get("source") == "synthetic_hard_a"
    ]
    if len(atoms) != 1:
        raise ValueError(f"record {record.get('id')} must have exactly one Hard A atom")
    return atoms[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare targeted Hard-A-only repairs from independent QC failures.")
    parser.add_argument("--source-benchmark", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--qc-input", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--deferred", type=Path, default=DEFAULT_DEFERRED)
    parser.add_argument("--repair-round", type=int, default=1)
    args = parser.parse_args()

    qc_paths = args.qc_input or DEFAULT_QC_INPUTS
    source_rows = list(iter_jsonl(args.source_benchmark))
    source_by_id = {str(row.get("id") or ""): row for row in source_rows}
    if "" in source_by_id or len(source_by_id) != len(source_rows):
        raise ValueError("source benchmark IDs must be non-empty and unique")
    qc_rows = [row for path in qc_paths for row in iter_jsonl(path)]
    prepare = load_prepare_module()
    template = PROMPT_TEMPLATE.read_text(encoding="utf-8")

    requests: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()
    families: Counter[str] = Counter()
    domains: Counter[str] = Counter()
    seen_record_ids: set[str] = set()

    for row in qc_rows:
        record_id = str(row.get("id") or "")
        if not record_id or record_id in seen_record_ids:
            raise ValueError(f"duplicate or empty QC record ID: {record_id!r}")
        seen_record_ids.add(record_id)
        audit = row.get("revision_independent_qc") or {}
        computed_reasons = [str(reason) for reason in audit.get("computed_reasons") or []]
        for reason in computed_reasons:
            reasons[reason] += 1
        hard_reasons = [reason for reason in computed_reasons if reason.startswith("hard_a:")]
        non_hard_reasons = [reason for reason in computed_reasons if not reason.startswith("hard_a:")]
        if not hard_reasons:
            deferred.append(
                {
                    "record_id": record_id,
                    "domain": row.get("domain"),
                    "computed_decision": audit.get("computed_decision"),
                    "computed_reasons": computed_reasons,
                    "reason": "not_a_hard_a_only_failure",
                }
            )
            continue
        if non_hard_reasons:
            deferred.append(
                {
                    "record_id": record_id,
                    "domain": row.get("domain"),
                    "computed_decision": audit.get("computed_decision"),
                    "computed_reasons": computed_reasons,
                    "hard_a_repair_prepared": True,
                    "remaining_non_hard_a_reasons": non_hard_reasons,
                    "reason": "hard_a_repair_prepared_but_non_hard_a_issues_remain",
                }
            )
        source = source_by_id.get(record_id)
        if source is None:
            raise ValueError(f"source record missing for {record_id}")
        prior_hard = hard_a_atom(row)
        family = str(prior_hard.get("hard_a_family") or "")
        request = prepare.build_request(source, family, template)
        request["request_id"] = f"composite_harda_patch_repair{args.repair_round}:{record_id}"
        params = request["user_defined_params"]
        params.update(
            {
                "repair_schema_version": SCHEMA_VERSION,
                "repair_round": args.repair_round,
                "prior_hard_a_text": prior_hard.get("text"),
                "prior_qc_decision": audit.get("computed_decision"),
                "prior_qc_reasons": computed_reasons,
            }
        )
        judge = audit.get("judge_output") or {}
        judge_hard = judge.get("hard_a_check") or {}
        feedback = {
            "previous_hard_a_text": prior_hard.get("text"),
            "computed_failure_reasons": computed_reasons,
            "independent_judge_reason": judge_hard.get("reason"),
            "legitimate_answer_influence": judge_hard.get("legitimate_answer_influence"),
            "family_boundary_valid": judge_hard.get("family_boundary_valid"),
            "safety_relevance": judge_hard.get("safety_relevance"),
        }
        request["prompt"][0]["content"] += (
            "\n\n## Mandatory targeted repair\n\n"
            "The previous synthetic Hard A failed independent QC. Generate a materially different memory in the SAME "
            "assigned family. Do not paraphrase or weaken the previous memory. Remove the exact failure mechanism shown "
            "below while preserving A + ignore and all output fields.\n\n"
            f"{json.dumps(feedback, ensure_ascii=False, indent=2)}\n"
        )
        requests.append(request)
        families[family] += 1
        domains[str(row.get("domain") or "health_seed")] += 1

    write_jsonl(args.output, requests)
    write_jsonl(args.deferred, deferred)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "repair_round": args.repair_round,
        "inputs": {
            "source_benchmark": {
                "path": portable_path(args.source_benchmark),
                "sha256": file_sha256(args.source_benchmark),
                "records": len(source_rows),
            },
            "qc": [
                {"path": portable_path(path), "sha256": file_sha256(path)}
                for path in qc_paths
            ],
        },
        "counts": {
            "qc_records": len(qc_rows),
            "repair_requests": len(requests),
            "deferred_non_hard_a_issues": len(deferred),
            "unique_request_ids": len({str(row["request_id"]) for row in requests}),
        },
        "distribution": {
            "domain": dict(sorted(domains.items())),
            "hard_a_family": dict(sorted(families.items())),
            "input_reasons": dict(sorted(reasons.items())),
        },
        "outputs": {
            "requests": {"path": portable_path(args.output), "sha256": file_sha256(args.output)},
            "deferred": {"path": portable_path(args.deferred), "sha256": file_sha256(args.deferred)},
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
