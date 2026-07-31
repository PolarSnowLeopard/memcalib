#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from memcalib_v23_common import file_sha256, portable_path
from memcalib_v24_coding_common import V24_DIR
from utils import iter_jsonl, write_json, write_jsonl


DEFAULT_INPUT = (
    V24_DIR
    / "v241"
    / "release"
    / "memcalib_v241_multidomain_benchmark_15000.jsonl"
)
DEFAULT_OUTPUT = (
    Path("docs")
    / "current"
    / "v2.4.1"
    / "review"
    / "memcalib-v241-manual-review-sample-30.jsonl"
)
SEED = 20260731
TARGETS = {
    "manual_finalization": 9,
    "alignment_reconciliation": 9,
    "coding_control": 6,
    "health_seed_control": 3,
    "general_control": 3,
}


def rank(record_id: str) -> str:
    return hashlib.sha256(f"{SEED}:{record_id}".encode()).hexdigest()


def channel(record: dict[str, Any]) -> str:
    remediation = record.get("v241_alignment_remediation")
    if isinstance(remediation, dict):
        return str(remediation.get("channel") or "unknown")
    return "unchanged_v24"


def stratum(record: dict[str, Any]) -> str:
    revision = record.get("coding_text_observability_revision")
    if (
        record.get("domain") == "coding"
        and isinstance(revision, dict)
        and revision.get("schema_version")
        == "memcalib-v241-manual-finalization-v1"
    ):
        return "manual_finalization"
    if (
        record.get("domain") == "coding"
        and isinstance(record.get("v241_alignment_reconciliation"), dict)
    ):
        return "alignment_reconciliation"
    if record.get("domain") == "coding":
        return "coding_control"
    if record.get("domain") == "health_seed":
        return "health_seed_control"
    if record.get("domain") == "general":
        return "general_control"
    raise ValueError(f"unknown domain: {record.get('domain')}")


def compact_atom(atom: dict[str, Any]) -> dict[str, Any]:
    contract = atom.get("counterfactual_contract")
    rubric = atom.get("usage_rubric")
    return {
        "atom_id": atom.get("atom_id"),
        "parent_memory_id": atom.get("parent_memory_id"),
        "text": atom.get("text"),
        "u_star": atom.get("u_star"),
        "memory_action": atom.get("memory_action"),
        "minimal_evidence": (
            contract.get("minimal_evidence") or []
            if isinstance(contract, dict)
            else []
        ),
        "expected_answer_behavior": (
            rubric.get("expected_answer_behavior")
            if isinstance(rubric, dict)
            else None
        ),
    }


def compact_record(record: dict[str, Any], review_stratum: str) -> dict[str, Any]:
    return {
        "id": record.get("id"),
        "domain": record.get("domain"),
        "review_stratum": review_stratum,
        "repair_channel": channel(record),
        "source_dataset": record.get("source_dataset"),
        "source_topic": record.get("source_topic"),
        "raw_query": record.get("raw_query"),
        "question": record.get("question"),
        "reference_answer": record.get("source_answer"),
        "memory_blocks": [
            {
                "parent_memory_id": block.get("parent_memory_id"),
                "memory_text": block.get("memory_text"),
                "atom_ids": block.get("atom_ids") or [],
            }
            for block in record.get("memory_blocks") or []
        ],
        "memories": [compact_atom(atom) for atom in record.get("memories") or []],
        "provenance": {
            "alignment_remediation": record.get("v241_alignment_remediation"),
            "alignment_reconciliation": record.get(
                "v241_alignment_reconciliation"
            ),
            "coding_revision": record.get("coding_text_observability_revision"),
        },
    }


def diverse_select(
    rows: list[dict[str, Any]],
    count: int,
) -> list[dict[str, Any]]:
    by_channel: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_channel[str(row["repair_channel"])].append(row)
    for values in by_channel.values():
        values.sort(key=lambda row: rank(str(row["id"])))
    selected: list[dict[str, Any]] = []
    for key in sorted(by_channel):
        if len(selected) == count:
            break
        selected.append(by_channel[key].pop(0))
    if len(selected) < count:
        remaining = sorted(
            (row for values in by_channel.values() for row in values),
            key=lambda row: rank(str(row["id"])),
        )
        selected.extend(remaining[: count - len(selected)])
    if len(selected) != count:
        raise ValueError(f"insufficient rows: requested={count}, got={len(selected)}")
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a deterministic, stratified v2.4.1 human-review sample."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    pools: dict[str, list[dict[str, Any]]] = defaultdict(list)
    input_count = 0
    for record in iter_jsonl(args.input):
        input_count += 1
        review_stratum = stratum(record)
        pools[review_stratum].append(compact_record(record, review_stratum))

    selected: list[dict[str, Any]] = []
    for review_stratum, target in TARGETS.items():
        pool = pools[review_stratum]
        if review_stratum == "manual_finalization":
            if len(pool) != target:
                raise ValueError(
                    f"manual finalization population changed: {len(pool)}"
                )
            chosen = sorted(pool, key=lambda row: rank(str(row["id"])))
        else:
            chosen = diverse_select(pool, target)
        selected.extend(chosen)
    selected.sort(
        key=lambda row: (
            list(TARGETS).index(str(row["review_stratum"])),
            rank(str(row["id"])),
        )
    )
    if len(selected) != sum(TARGETS.values()):
        raise ValueError("unexpected review sample size")
    write_jsonl(args.output, selected)
    manifest = args.manifest or args.output.with_suffix(".manifest.json")
    summary = {
        "schema_version": "memcalib-v241-manual-review-sample-v1",
        "input": {
            "path": portable_path(args.input),
            "sha256": file_sha256(args.input),
            "records": input_count,
        },
        "sampling": {
            "seed": SEED,
            "method": "deterministic_hash_with_repair_channel_diversity",
            "targets": TARGETS,
        },
        "output": {
            "path": portable_path(args.output),
            "sha256": file_sha256(args.output),
            "records": len(selected),
            "by_stratum": dict(
                sorted(Counter(row["review_stratum"] for row in selected).items())
            ),
            "by_domain": dict(
                sorted(Counter(row["domain"] for row in selected).items())
            ),
            "by_repair_channel": dict(
                sorted(Counter(row["repair_channel"] for row in selected).items())
            ),
        },
    }
    write_json(manifest, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
