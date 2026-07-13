#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from utils import iter_jsonl, write_json


SCRIPT_DIR = Path(__file__).resolve().parent
POSTPROCESS_PATH = SCRIPT_DIR / "11_post_crk2_generation.py"
SCHEMA_VERSION = "memcalib-multidomain-pilot-validation-v1"


def load_postprocessor():
    spec = importlib.util.spec_from_file_location("multidomain_benchmark_postprocessor", POSTPROCESS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


POST = load_postprocessor()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tokens(text: Any) -> list[str]:
    return re.findall(r"[a-zA-Z0-9_]+", str(text or "").casefold())


def shingles(text: Any, width: int = 6) -> set[str]:
    values = tokens(text)
    return {" ".join(values[index : index + width]) for index in range(max(0, len(values) - width + 1))}


def validate_file(path: Path, expected_rows: int, expected_domain: str | None) -> dict[str, Any]:
    rows = list(iter_jsonl(path))
    errors: list[str] = []
    ids = [str(row.get("id") or "") for row in rows]
    if len(rows) != expected_rows:
        errors.append(f"row_count:{len(rows)}!={expected_rows}")
    if "" in ids or len(set(ids)) != len(ids):
        errors.append("sample_ids_not_unique_nonempty")
    domains = Counter(str(row.get("domain") or "") for row in rows)
    if expected_domain and domains != Counter({expected_domain: expected_rows}):
        errors.append(f"domain_distribution:{dict(domains)}")

    validation_error_counts: Counter[str] = Counter()
    answer_overlap_records: set[str] = set()
    answer_overlap_atoms = 0
    source_licenses: Counter[str] = Counter()
    repair_rounds: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    total_parent_blocks = 0
    non_atomic_parent_blocks = 0
    samples_with_non_atomic = 0
    for row in rows:
        params = {
            "domain": row.get("domain"),
            "raw_question": row.get("raw_query"),
            "source_context": row.get("source_context"),
            "source_answer": row.get("source_answer"),
        }
        validation_error_counts.update(POST.validate_model_record(row, params))
        source_licenses[str(row.get("source_license") or "missing")] += 1
        repair_rounds[str((row.get("lineage") or {}).get("generation_repair_round", 0))] += 1
        blocks = list(row.get("memory_blocks") or [])
        total_parent_blocks += len(blocks)
        block_atom_counts = [int(block.get("atom_count") or len(block.get("atom_ids") or [])) for block in blocks]
        non_atomic_parent_blocks += sum(count > 1 for count in block_atom_counts)
        samples_with_non_atomic += int(any(count > 1 for count in block_atom_counts))
        visible_shingles = shingles(row.get("raw_query")) | shingles(row.get("source_context"))
        answer_only = shingles(row.get("source_answer")) - visible_shingles
        for memory in row.get("memories", []):
            label_counts[str(memory.get("u_star") or "unknown")] += 1
            if memory.get("source") == "synthetic_hard_a":
                continue
            overlap = answer_only & (shingles(memory.get("text")) | shingles(memory.get("atomic_predicate")))
            if overlap:
                answer_overlap_records.add(str(row.get("id") or ""))
                answer_overlap_atoms += 1
    if validation_error_counts:
        errors.append("record_validation_failed")
    if "missing" in source_licenses:
        errors.append("source_license_missing")

    return {
        "path": str(path),
        "sha256": file_sha256(path),
        "rows": len(rows),
        "unique_ids": len(set(ids)),
        "domains": dict(sorted(domains.items())),
        "source_licenses": dict(sorted(source_licenses.items())),
        "generation_repair_rounds": dict(sorted(repair_rounds.items())),
        "label_counts": dict(sorted(label_counts.items())),
        "parent_memory_structure": {
            "parent_blocks": total_parent_blocks,
            "non_atomic_parent_blocks": non_atomic_parent_blocks,
            "non_atomic_parent_rate": round(non_atomic_parent_blocks / total_parent_blocks, 6)
            if total_parent_blocks
            else 0.0,
            "samples_with_non_atomic_parent": samples_with_non_atomic,
        },
        "validation_error_counts": dict(sorted(validation_error_counts.items())),
        "reference_answer_overlap_audit": {
            "method": "six-token answer-only shingle overlap; audit signal, not an automatic rejection",
            "records_flagged": len(answer_overlap_records),
            "atoms_flagged": answer_overlap_atoms,
        },
        "status": "pass" if not errors else "fail",
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate grounded multi-domain MemCalib pilot benchmark files.")
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--domain", action="append", default=[])
    parser.add_argument("--expected-rows", type=int, default=100)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.domain and len(args.domain) != len(args.input):
        raise ValueError("provide one --domain per --input, or omit all domains")
    domains = args.domain or [None] * len(args.input)
    files = [validate_file(path, args.expected_rows, domain) for path, domain in zip(args.input, domains)]
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if all(item["status"] == "pass" for item in files) else "fail",
        "expected_rows_per_file": args.expected_rows,
        "files": files,
    }
    write_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
