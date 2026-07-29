#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation.common import display_path, iter_jsonl, sha256_file, write_json, write_jsonl


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "pipeline" / "data" / "crk2_canonical_memory_benchmark_en_15528.jsonl"
DEFAULT_OUTPUT = ROOT / "evaluation" / "archive" / "releases" / "memcalib-v0.1-full-15526"
LABELS = {"A", "B", "C"}
QC_KEYS = (
    "atomicity_pass",
    "duplicate_pass",
    "question_memory_leakage_pass",
    "hard_a_target_consistency_pass",
    "rubric_objectivity_pass",
)
MODEL_FACING_KEYS = {
    "id",
    "panel",
    "source_dataset",
    "source_topic",
    "question",
    "memory_blocks",
}


def write_deterministic_gzip(source: Path, output: Path) -> None:
    with source.open("rb") as source_handle, output.open("wb") as raw_output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_output, mtime=0) as compressed:
            shutil.copyfileobj(source_handle, compressed, length=1024 * 1024)


def contains_cjk(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff]", value))


def canonicalize_parent_blocks(row: dict[str, Any]) -> tuple[dict[str, Any], int]:
    value = dict(row)
    atoms = {str(atom["atom_id"]): atom for atom in row.get("memories") or []}
    merged: list[dict[str, Any]] = []
    positions: dict[str, int] = {}
    repairs = 0
    for raw_block in row.get("memory_blocks") or []:
        block = dict(raw_block)
        parent_id = str(block.get("parent_memory_id") or "")
        if parent_id not in positions:
            positions[parent_id] = len(merged)
            merged.append(block)
            continue
        repairs += 1
        target = merged[positions[parent_id]]
        target["memory_text"] = " ".join(
            part.strip() for part in (str(target.get("memory_text") or ""), str(block.get("memory_text") or "")) if part.strip()
        )
        target["text"] = target["memory_text"]
        target["raw_evidence"] = " ".join(
            part.strip() for part in (str(target.get("raw_evidence") or ""), str(block.get("raw_evidence") or "")) if part.strip()
        )
        target["atom_ids"] = list(target.get("atom_ids") or []) + list(block.get("atom_ids") or [])
        target["atom_count"] = len(target["atom_ids"])
        reasons = [str(target.get("label_reason") or "").strip(), str(block.get("label_reason") or "").strip()]
        target["label_reason"] = " ".join(reason for reason in reasons if reason)
        notes = [str(target.get("atomization_notes") or "").strip(), str(block.get("atomization_notes") or "").strip()]
        target["atomization_notes"] = " ".join(note for note in notes if note)

    for block in merged:
        labels = sorted(
            {str(atoms[str(atom_id)]["u_star"]) for atom_id in block.get("atom_ids") or []},
            key=("A", "B", "C").index,
        )
        block["parent_label_set"] = labels
        block["parent_label_mode"] = "mixed" if len(labels) > 1 else "homogeneous"
        if labels:
            block["u_star"] = labels[0] if len(labels) == 1 else max(labels, key=("A", "B", "C").index)
    value["memory_blocks"] = merged
    audit = dict(value.get("construction_audit") or {})
    if repairs:
        audit["release_parent_block_merges"] = repairs
    value["construction_audit"] = audit
    return value, repairs


def normalized_question(row: dict[str, Any]) -> str:
    return re.sub(r"\s+", " ", str(row.get("question") or "").casefold()).strip()


def deduplicate_questions(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(normalized_question(row), []).append(row)
    keep_ids: set[str] = set()
    exclusions: list[dict[str, Any]] = []
    for question_key, group in groups.items():
        kept = max(
            group,
            key=lambda row: (
                len(row.get("memories") or []),
                sum(bool(atom.get("hard_a_family")) for atom in row.get("memories") or []),
                len(row.get("memory_blocks") or []),
                str(row.get("id") or ""),
            ),
        )
        kept_id = str(kept["id"])
        keep_ids.add(kept_id)
        for row in group:
            if str(row["id"]) != kept_id:
                exclusions.append(
                    {
                        "excluded_id": str(row["id"]),
                        "kept_id": kept_id,
                        "normalized_question": question_key,
                        "reason": "exact_normalized_question_duplicate",
                    }
                )
    return [row for row in rows if str(row["id"]) in keep_ids], sorted(exclusions, key=lambda row: row["excluded_id"])


def validate_record(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    sample_id = str(row.get("id") or "")
    question = row.get("question")
    blocks = row.get("memory_blocks")
    atoms = row.get("memories")
    if not sample_id:
        errors.append("missing_id")
    if not isinstance(question, str) or not question.strip():
        errors.append("missing_question")
    elif contains_cjk(question):
        errors.append("question_contains_cjk")
    if not isinstance(blocks, list) or not blocks:
        errors.append("missing_memory_blocks")
        blocks = []
    if not isinstance(atoms, list) or not atoms:
        errors.append("missing_atomic_memories")
        atoms = []

    atom_ids = [str(atom.get("atom_id") or "") for atom in atoms if isinstance(atom, dict)]
    if not all(atom_ids) or len(atom_ids) != len(set(atom_ids)):
        errors.append("invalid_or_duplicate_atom_ids")
    atom_by_id = {
        str(atom["atom_id"]): atom
        for atom in atoms
        if isinstance(atom, dict) and atom.get("atom_id")
    }
    block_ids = [str(block.get("parent_memory_id") or "") for block in blocks if isinstance(block, dict)]
    if not all(block_ids) or len(block_ids) != len(set(block_ids)):
        errors.append("invalid_or_duplicate_parent_ids")
    referenced_atoms: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            errors.append("memory_block_not_object")
            continue
        memory_text = block.get("memory_text")
        if not isinstance(memory_text, str) or not memory_text.strip():
            errors.append("missing_memory_text")
        elif contains_cjk(memory_text):
            errors.append("memory_text_contains_cjk")
        block_atom_ids = block.get("atom_ids")
        if not isinstance(block_atom_ids, list) or not block_atom_ids:
            errors.append("missing_block_atom_ids")
            continue
        referenced_atoms.extend(str(value) for value in block_atom_ids)
        parent_id = str(block.get("parent_memory_id") or "")
        if any(str(atom_by_id.get(str(atom_id), {}).get("parent_memory_id") or "") != parent_id for atom_id in block_atom_ids):
            errors.append("parent_atom_link_mismatch")
    if set(referenced_atoms) != set(atom_ids) or len(referenced_atoms) != len(atom_ids):
        errors.append("block_atom_coverage_mismatch")

    for atom in atoms:
        if not isinstance(atom, dict):
            errors.append("atomic_memory_not_object")
            continue
        if atom.get("u_star") not in LABELS:
            errors.append("invalid_u_star")
        text = atom.get("text")
        if not isinstance(text, str) or not text.strip():
            errors.append("missing_atom_text")
        elif contains_cjk(text):
            errors.append("atom_text_contains_cjk")
        rubric = atom.get("usage_rubric")
        if not isinstance(rubric, dict) or not rubric:
            errors.append("missing_usage_rubric")
    qc = row.get("qc") or {}
    for key in QC_KEYS:
        if qc.get(key) is not True:
            errors.append(f"qc_failed:{key}")
    return sorted(set(errors))


def model_facing_record(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "panel": "formal",
        "source_dataset": str(row["source_dataset"]),
        "source_topic": str(row["source_topic"]),
        "question": str(row["question"]),
        "memory_blocks": [
            {
                "parent_memory_id": str(block["parent_memory_id"]),
                "memory_text": str(block["memory_text"]),
            }
            for block in row["memory_blocks"]
        ],
    }


def release_full_benchmark(input_path: Path, output_dir: Path, expected_samples: int) -> dict[str, Any]:
    source_rows = list(iter_jsonl(input_path))
    canonicalized = [canonicalize_parent_blocks(row) for row in source_rows]
    canonical_rows = [row for row, _ in canonicalized]
    rows, duplicate_exclusions = deduplicate_questions(canonical_rows)
    parent_block_merges = sum(repairs for _, repairs in canonicalized)
    repaired_samples = sum(repairs > 0 for _, repairs in canonicalized)
    ids = [str(row.get("id") or "") for row in rows]
    errors: Counter[str] = Counter()
    for row in rows:
        errors.update(validate_record(row))
    if len(source_rows) != expected_samples:
        errors["sample_count_mismatch"] += 1
    if len(ids) != len(set(ids)):
        errors["duplicate_sample_ids"] += len(ids) - len(set(ids))
    if errors:
        raise ValueError(f"full benchmark release validation failed: {dict(sorted(errors.items()))}")

    hidden_rows = []
    model_rows = []
    for row in rows:
        hidden = dict(row)
        hidden["panel"] = "formal"
        hidden["evaluation"] = {"panel": "formal", "protocol_scope": "full_memory_primary"}
        hidden_rows.append(hidden)
        model_rows.append(model_facing_record(row))
    if any(set(row) != MODEL_FACING_KEYS for row in model_rows):
        raise ValueError("model-facing schema contains unexpected hidden fields")

    output_dir.mkdir(parents=True, exist_ok=True)
    hidden_path = output_dir / "hidden-evaluation.jsonl"
    model_path = output_dir / "model-facing.jsonl"
    ids_path = output_dir / "sample-ids.txt"
    exclusions_path = output_dir / "excluded-exact-question-duplicates.jsonl"
    write_jsonl(hidden_path, hidden_rows)
    write_jsonl(model_path, model_rows)
    hidden_gzip_path = hidden_path.with_suffix(hidden_path.suffix + ".gz")
    model_gzip_path = model_path.with_suffix(model_path.suffix + ".gz")
    write_deterministic_gzip(hidden_path, hidden_gzip_path)
    write_deterministic_gzip(model_path, model_gzip_path)
    ids_path.write_text("".join(f"{sample_id}\n" for sample_id in ids), encoding="utf-8")
    write_jsonl(exclusions_path, duplicate_exclusions)

    atoms = [atom for row in rows for atom in row["memories"]]
    parent_memories = sum(len(row["memory_blocks"]) for row in rows)
    normalized_questions = Counter(normalized_question(row) for row in rows)
    duplicate_question_groups = sum(count > 1 for count in normalized_questions.values())
    duplicate_question_rows = sum(count for count in normalized_questions.values() if count > 1)
    manifest = {
        "schema_version": "memcalib-full-release-v1",
        "status": "locked",
        "scope": "full_memory_primary",
        "counts": {
            "samples": len(rows),
            "source_samples": len(source_rows),
            "unique_sample_ids": len(set(ids)),
            "parent_memories": parent_memories,
            "atomic_memories": len(atoms),
            "avg_atoms_per_sample": len(atoms) / len(rows),
            "duplicate_question_groups": duplicate_question_groups,
            "duplicate_question_rows": duplicate_question_rows,
            "excluded_exact_question_duplicates": len(duplicate_exclusions),
            "release_repaired_samples": repaired_samples,
            "release_parent_block_merges": parent_block_merges,
        },
        "distributions": {
            "source_dataset": dict(sorted(Counter(str(row["source_dataset"]) for row in rows).items())),
            "source_topic": dict(sorted(Counter(str(row["source_topic"]) for row in rows).items())),
            "u_star": dict(sorted(Counter(str(atom["u_star"]) for atom in atoms).items())),
            "memory_type": dict(sorted(Counter(str(atom["memory_type"]) for atom in atoms).items())),
            "atom_count_per_sample": dict(sorted(Counter(len(row["memories"]) for row in rows).items())),
        },
        "quality_checks": {
            "required_fields": "passed",
            "sample_id_uniqueness": "passed",
            "parent_atom_integrity": "passed",
            "abc_enum_validity": "passed",
            "construction_qc": {key: len(rows) for key in QC_KEYS},
            "english_model_facing_text": "passed",
            "hidden_field_exclusion": "passed",
            "duplicate_parent_block_repair": {
                "status": "passed",
                "repaired_samples": repaired_samples,
                "merged_duplicate_blocks": parent_block_merges,
            },
            "exact_question_deduplication": {
                "status": "passed",
                "excluded_rows": len(duplicate_exclusions),
                "remaining_duplicate_groups": duplicate_question_groups,
            },
        },
        "artifacts": {
            "source": {
                "path": display_path(input_path, ROOT),
                "rows": len(source_rows),
                "sha256": sha256_file(input_path),
            },
            "hidden-evaluation.jsonl": {"rows": len(rows), "sha256": sha256_file(hidden_path)},
            "hidden-evaluation.jsonl.gz": {"rows": len(rows), "sha256": sha256_file(hidden_gzip_path)},
            "model-facing.jsonl": {"rows": len(rows), "sha256": sha256_file(model_path)},
            "model-facing.jsonl.gz": {"rows": len(rows), "sha256": sha256_file(model_gzip_path)},
            "sample-ids.txt": {"rows": len(rows), "sha256": sha256_file(ids_path)},
            "excluded-exact-question-duplicates.jsonl": {
                "rows": len(duplicate_exclusions),
                "sha256": sha256_file(exclusions_path),
            },
        },
    }
    write_json(output_dir / "release-manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and lock the full MemCalib benchmark release.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--expected-samples", type=int, default=15528)
    args = parser.parse_args()
    manifest = release_full_benchmark(args.input, args.output_dir, args.expected_samples)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
