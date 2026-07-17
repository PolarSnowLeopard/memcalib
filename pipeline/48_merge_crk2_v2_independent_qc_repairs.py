#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from utils import iter_jsonl, write_json, write_jsonl


DECISIONS = ("strict_pass", "review", "reject", "invalid")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def row_id(row: dict[str, Any]) -> str:
    return str(row.get("id") or row.get("record_id") or "")


def index_bucket(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        record_id = row_id(row)
        if not record_id or record_id in indexed:
            raise ValueError(f"{label} has invalid or duplicate record id: {record_id}")
        indexed[record_id] = row
    return indexed


def merge_qc_buckets(
    prior: dict[str, list[dict[str, Any]]], retry: dict[str, list[dict[str, Any]]]
) -> dict[str, list[dict[str, Any]]]:
    prior_index = {decision: index_bucket(prior[decision], f"prior {decision}") for decision in DECISIONS}
    retry_index = {decision: index_bucket(retry[decision], f"retry {decision}") for decision in DECISIONS}

    prior_owner: dict[str, str] = {}
    retry_owner: dict[str, str] = {}
    for decision in DECISIONS:
        for record_id in prior_index[decision]:
            if record_id in prior_owner:
                raise ValueError(f"record appears in multiple prior buckets: {record_id}")
            prior_owner[record_id] = decision
        for record_id in retry_index[decision]:
            if record_id in retry_owner:
                raise ValueError(f"record appears in multiple retry buckets: {record_id}")
            retry_owner[record_id] = decision
    merged = {decision: [] for decision in DECISIONS}
    for decision in DECISIONS:
        for row in prior[decision]:
            if row_id(row) not in retry_owner:
                merged[decision].append(row)
        merged[decision].extend(retry[decision])

    merged_ids = [row_id(row) for decision in DECISIONS for row in merged[decision]]
    if len(merged_ids) != len(set(merged_ids)) or set(merged_ids) != set(prior_owner) | set(retry_owner):
        raise ValueError("merged QC coverage is not unique and complete")
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge targeted independent-QC results into prior QC buckets.")
    for decision in DECISIONS:
        parser.add_argument(f"--prior-{decision.replace('_', '-')}", type=Path, required=True)
        parser.add_argument(f"--retry-{decision.replace('_', '-')}", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    benchmark = list(iter_jsonl(args.benchmark))
    benchmark_by_id = index_bucket(benchmark, "benchmark")
    prior_paths = {decision: getattr(args, f"prior_{decision}") for decision in DECISIONS}
    retry_paths = {decision: getattr(args, f"retry_{decision}") for decision in DECISIONS}
    prior = {decision: list(iter_jsonl(prior_paths[decision])) for decision in DECISIONS}
    retry = {decision: list(iter_jsonl(retry_paths[decision])) for decision in DECISIONS}
    merged = merge_qc_buckets(prior, retry)

    outputs = {}
    for decision in DECISIONS:
        path = Path(f"{args.output_prefix}.{decision}.jsonl")
        write_jsonl(path, merged[decision])
        outputs[decision] = {"path": str(path), "sha256": file_sha256(path), "records": len(merged[decision])}

    domain_counts: dict[str, dict[str, int]] = {}
    for decision in DECISIONS:
        counts = Counter()
        for row in merged[decision]:
            record = benchmark_by_id.get(row_id(row), {})
            counts[str(record.get("domain") or "unknown")] += 1
        domain_counts[decision] = dict(sorted(counts.items()))
    summary = {
        "schema_version": "crk2-v2-independent-qc-repair-merge-v1",
        "benchmark": {"path": str(args.benchmark), "sha256": file_sha256(args.benchmark), "records": len(benchmark)},
        "prior_inputs": {
            decision: {"path": str(path), "sha256": file_sha256(path), "records": len(prior[decision])}
            for decision, path in prior_paths.items()
        },
        "retry_inputs": {
            decision: {"path": str(path), "sha256": file_sha256(path), "records": len(retry[decision])}
            for decision, path in retry_paths.items()
        },
        "counts": {decision: len(merged[decision]) for decision in DECISIONS},
        "domain_counts": domain_counts,
        "outputs": outputs,
    }
    write_json(args.summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
