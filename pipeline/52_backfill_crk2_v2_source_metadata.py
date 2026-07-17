#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from utils import iter_jsonl, write_json, write_jsonl


SCHEMA_VERSION = "memcalib-source-metadata-backfill-v1"
STACK_EXCHANGE_DATASET = "HuggingFaceH4/stack-exchange-preferences"
STACK_EXCHANGE_REQUIRED_FIELDS = (
    "question_author_name",
    "question_author_profile",
    "answer_author",
    "answer_author_profile",
    "question_url",
)
BUCKET_SUFFIXES = {
    "strict_pass": "strict_pass.jsonl",
    "review": "review.jsonl",
    "reject": "reject.jsonl",
    "invalid": "invalid.jsonl",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_id(row: dict[str, Any]) -> str:
    return str(row.get("source_id") or row.get("id") or row.get("source_raw_id") or "")


def load_generation_metadata(path: Path) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in iter_jsonl(path):
        params = row.get("user_defined_params") or row.get("passParams") or row.get("params") or {}
        row_source_id = source_id(params)
        if not row_source_id or row_source_id in indexed:
            raise ValueError(f"generation lineage has missing or duplicate source ID: {row_source_id!r}")
        metadata = params.get("source_metadata")
        indexed[row_source_id] = dict(metadata) if isinstance(metadata, dict) else {}
    return indexed


def stack_exchange_attribution_errors(metadata: dict[str, Any]) -> list[str]:
    errors = [
        f"missing_{field}"
        for field in STACK_EXCHANGE_REQUIRED_FIELDS
        if not str(metadata.get(field) or "").strip()
    ]
    if metadata.get("attribution_complete") is not True:
        errors.append("attribution_not_complete")
    return errors


def backfill_rows(
    rows: list[dict[str, Any]],
    metadata_by_source_id: dict[str, dict[str, Any]],
    *,
    benchmark_by_id: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    output: list[dict[str, Any]] = []
    ids: set[str] = set()
    source_ids: set[str] = set()
    stack_exchange_records = 0
    metadata_attached = 0
    for row in rows:
        record_id = str(row.get("id") or row.get("record_id") or "")
        benchmark_row = benchmark_by_id.get(record_id) if benchmark_by_id is not None else None
        row_source_id = str(
            row.get("source_id")
            or (benchmark_row or {}).get("source_id")
            or ""
        )
        if not record_id or record_id in ids:
            raise ValueError(f"rows have missing or duplicate record ID: {record_id!r}")
        if not row_source_id or row_source_id in source_ids:
            raise ValueError(f"rows have missing or duplicate source ID: {row_source_id!r}")
        if benchmark_by_id is not None and benchmark_row is None:
            raise ValueError(f"QC bucket contains record absent from benchmark: {record_id}")
        if benchmark_row is not None and row.get("source_id") not in (None, "", benchmark_row.get("source_id")):
            raise ValueError(f"QC/benchmark source ID mismatch for {record_id}")
        if row_source_id not in metadata_by_source_id:
            raise ValueError(f"no generation lineage for source ID: {row_source_id}")

        repaired = dict(row)
        repaired.setdefault("source_id", row_source_id)
        if benchmark_row is not None:
            repaired.setdefault("source_dataset", benchmark_row.get("source_dataset"))
        metadata = metadata_by_source_id[row_source_id]
        if metadata:
            repaired["source_metadata"] = metadata
            metadata_attached += 1
        if str(repaired.get("source_dataset") or "") == STACK_EXCHANGE_DATASET:
            stack_exchange_records += 1
            errors = stack_exchange_attribution_errors(metadata)
            if errors:
                raise ValueError(
                    f"incomplete Stack Exchange attribution for {record_id}: {','.join(errors)}"
                )
        output.append(repaired)
        ids.add(record_id)
        source_ids.add(row_source_id)
    return output, {
        "records": len(output),
        "unique_record_ids": len(ids),
        "unique_source_ids": len(source_ids),
        "metadata_attached": metadata_attached,
        "stack_exchange_records": stack_exchange_records,
        "stack_exchange_attribution_complete": stack_exchange_records,
    }


def path_audit(path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"path": str(path), "sha256": file_sha256(path), "records": len(rows)}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill construction source metadata from immutable generation lineage."
    )
    parser.add_argument("--generation-input", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--strict", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--reject", type=Path, required=True)
    parser.add_argument("--invalid", type=Path, required=True)
    parser.add_argument("--benchmark-output", type=Path, required=True)
    parser.add_argument("--qc-output-prefix", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    metadata_by_source_id = load_generation_metadata(args.generation_input)
    benchmark_input = list(iter_jsonl(args.benchmark))
    benchmark, benchmark_audit = backfill_rows(benchmark_input, metadata_by_source_id)
    write_jsonl(args.benchmark_output, benchmark)
    benchmark_by_id = {str(row["id"]): row for row in benchmark}
    benchmark_ids = set(benchmark_by_id)

    bucket_inputs = {
        "strict_pass": args.strict,
        "review": args.review,
        "reject": args.reject,
        "invalid": args.invalid,
    }
    bucket_outputs: dict[str, dict[str, Any]] = {}
    covered_ids: set[str] = set()
    decision_counts: Counter[str] = Counter()
    for decision, input_path in bucket_inputs.items():
        rows = list(iter_jsonl(input_path))
        repaired, audit = backfill_rows(rows, metadata_by_source_id, benchmark_by_id=benchmark_by_id)
        repaired_ids = {str(row.get("id") or row.get("record_id") or "") for row in repaired}
        duplicate_ids = covered_ids & repaired_ids
        if duplicate_ids:
            raise ValueError(f"QC buckets overlap on {len(duplicate_ids)} record IDs")
        covered_ids.update(repaired_ids)
        decision_counts[decision] = len(repaired)
        output_path = Path(f"{args.qc_output_prefix}.{BUCKET_SUFFIXES[decision]}")
        write_jsonl(output_path, repaired)
        bucket_outputs[decision] = {
            "input": path_audit(input_path, rows),
            "output": path_audit(output_path, repaired),
            **audit,
        }
    if covered_ids != benchmark_ids:
        raise ValueError(
            f"QC coverage mismatch: missing={len(benchmark_ids - covered_ids)}, "
            f"extra={len(covered_ids - benchmark_ids)}"
        )

    summary = {
        "schema_version": SCHEMA_VERSION,
        "total": len(benchmark),
        "decision_counts": dict(sorted(decision_counts.items())),
        "benchmark": benchmark_audit,
        "qc_coverage": {
            "records": len(covered_ids),
            "unique_record_ids": len(covered_ids),
            "complete": covered_ids == benchmark_ids,
        },
    }
    summary_path = Path(f"{args.qc_output_prefix}.summary.json")
    write_json(summary_path, summary)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generation_input": {
            "path": str(args.generation_input),
            "sha256": file_sha256(args.generation_input),
            "records": len(metadata_by_source_id),
        },
        "benchmark": {
            "input": path_audit(args.benchmark, benchmark_input),
            "output": path_audit(args.benchmark_output, benchmark),
            **benchmark_audit,
        },
        "qc_buckets": bucket_outputs,
        "summary": {
            "path": str(summary_path),
            "sha256": file_sha256(summary_path),
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
