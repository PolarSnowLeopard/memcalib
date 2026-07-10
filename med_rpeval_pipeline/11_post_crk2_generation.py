#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from utils import extract_json_object, norm_text, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = SCRIPT_DIR / "data" / "crk2_memory_benchmark_100.jsonl"
DEFAULT_SUMMARY = SCRIPT_DIR / "data" / "crk2_memory_benchmark_100.summary.json"
DEFAULT_HTML = SCRIPT_DIR / "data" / "crk2_memory_benchmark_100.html"

COMMON_RUBRIC_KEYS = {
    "expected_answer_behavior",
    "memory_usage_weight",
    "validity_scope",
    "correct_use",
    "under_use",
    "over_use",
    "forbidden_memory_role",
    "failure_direction",
    "observable_checks",
}
LABEL_SPECIFIC_RUBRIC_KEYS = {
    "A": {"contamination_signals"},
    "B": {"allowed_memory_use", "maximum_footprint"},
    "C": {"controlling_factor", "missing_memory_failure"},
}
MEMORY_REQUIRED_KEYS = {
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
    "u_star",
    "subtype",
    "hard_a_family",
    "label_reason",
    "construction_target",
    "usage_rubric",
}
BLOCK_REQUIRED_KEYS = {"parent_memory_id", "raw_evidence", "memory_text", "source", "u_star", "atom_ids"}
TARGET_REQUIRED_KEYS = {"task_goal", "memory_role", "usage_boundary", "failure_direction"}
FIRST_PERSON_EN = re.compile(r"^\s*(?:i|i'm|i’ve|i've|i am|my|me|mine|we|we're|we are|our)\b", re.IGNORECASE)
FIRST_PERSON_CN_PREFIXES = ("我", "我的", "本人", "我们", "咱们")
LABEL_ORDER = ("A", "B", "C")


def effective_usage_rubric(memory: dict[str, Any]) -> dict[str, Any]:
    """Return judge rubric after normalizing common model field-placement drift."""
    rubric = memory.get("usage_rubric") if isinstance(memory.get("usage_rubric"), dict) else {}
    merged = dict(rubric)
    label = str(memory.get("u_star", "")).strip().upper()
    for key in LABEL_SPECIFIC_RUBRIC_KEYS.get(label, set()):
        if key not in merged and key in memory:
            merged[key] = memory[key]
    return merged


def is_first_person_stored_memory(text: Any) -> bool:
    normalized = norm_text(str(text or ""))
    if not normalized:
        return False
    return normalized.startswith(FIRST_PERSON_CN_PREFIXES) or bool(FIRST_PERSON_EN.match(normalized))


def ordered_label_set(labels: list[str]) -> list[str]:
    present = set(labels)
    return [label for label in LABEL_ORDER if label in present]


def add_parent_label_metadata(blocks: list[dict[str, Any]], memories: list[dict[str, Any]]) -> dict[str, Any]:
    labels_by_parent: dict[str, list[str]] = {}
    for memory in memories:
        labels_by_parent.setdefault(str(memory.get("parent_memory_id", "")), []).append(str(memory.get("u_star", "")))

    label_set_counts: Counter = Counter()
    mode_counts: Counter = Counter()
    for block in blocks:
        labels = ordered_label_set(labels_by_parent.get(str(block.get("parent_memory_id", "")), []))
        mode = "mixed" if len(labels) > 1 else "homogeneous"
        label_set_key = "+".join(labels) if labels else "none"
        block["parent_label_set"] = labels
        block["parent_label_mode"] = mode
        label_set_counts[label_set_key] += 1
        mode_counts[mode] += 1

    return {
        "mixed_parent_count": mode_counts["mixed"],
        "homogeneous_parent_count": mode_counts["homogeneous"],
        "parent_label_set_counts": dict(label_set_counts),
        "parent_label_mode_counts": dict(mode_counts),
    }


def load_rubric_builder():
    path = SCRIPT_DIR / "09_build_memory_abc_rubric_dataset.py"
    spec = importlib.util.spec_from_file_location("memory_abc_rubric_dataset", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def get_params(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("passParams") or row.get("user_defined_params") or row.get("params") or {}


def get_text(row: dict[str, Any]) -> str:
    for key in ("response", "output", "content", "text", "answer"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    raw = row.get("raw_response")
    if isinstance(raw, dict):
        choices = raw.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
    raise ValueError("No model output text found")


def normalize_bool(value: Any) -> bool:
    return value is True or str(value).strip().lower() == "true"


def normalize_block(block: dict[str, Any], index: int) -> dict[str, Any]:
    parent_id = norm_text(str(block.get("parent_memory_id") or f"p{index}"))
    atom_ids = block.get("atom_ids") if isinstance(block.get("atom_ids"), list) else []
    memory_text = norm_text(str(block.get("memory_text") or block.get("text", "")))
    raw_evidence = norm_text(str(block.get("raw_evidence") or block.get("evidence") or block.get("text", "")))
    return {
        "parent_memory_id": parent_id,
        "raw_evidence": raw_evidence,
        "memory_text": memory_text,
        "text": memory_text,
        "source": norm_text(str(block.get("source", ""))),
        "u_star": str(block.get("u_star", "")).strip().upper(),
        "label_reason": norm_text(str(block.get("label_reason", ""))),
        "atom_count": int(block.get("atom_count") or len(atom_ids) or 0),
        "atom_ids": [str(atom_id) for atom_id in atom_ids],
        "atomization_notes": norm_text(str(block.get("atomization_notes", ""))),
        "hard_a_family": block.get("hard_a_family"),
    }


def normalize_memory(memory: dict[str, Any], index: int) -> dict[str, Any]:
    label = str(memory.get("u_star", "")).strip().upper()
    target = memory.get("construction_target") if isinstance(memory.get("construction_target"), dict) else {}
    rubric = effective_usage_rubric(memory)
    normalized = {
        "memory_id": norm_text(str(memory.get("memory_id") or f"m{index}")),
        "parent_memory_id": norm_text(str(memory.get("parent_memory_id", ""))),
        "atom_id": norm_text(str(memory.get("atom_id", ""))),
        "atom_index": int(memory.get("atom_index") or index),
        "atom_count": int(memory.get("atom_count") or 1),
        "text": norm_text(str(memory.get("text") or memory.get("atomic_predicate") or "")),
        "evidence": norm_text(str(memory.get("evidence", ""))),
        "atomic_predicate": norm_text(str(memory.get("atomic_predicate") or memory.get("text") or "")),
        "derivation": norm_text(str(memory.get("derivation", ""))),
        "source": norm_text(str(memory.get("source", ""))),
        "memory_type": norm_text(str(memory.get("memory_type", ""))),
        "u_star": label,
        "subtype": norm_text(str(memory.get("subtype", ""))),
        "hard_a_family": memory.get("hard_a_family"),
        "label_reason": norm_text(str(memory.get("label_reason", ""))),
        "verifier_reason": norm_text(str(memory.get("verifier_reason", ""))),
        "overlap_group": memory.get("overlap_group"),
        "overlap_note": norm_text(str(memory.get("overlap_note", ""))),
        "construction_target": {
            "task_goal": norm_text(str(target.get("task_goal", ""))),
            "memory_role": norm_text(str(target.get("memory_role", ""))),
            "usage_boundary": norm_text(str(target.get("usage_boundary", ""))),
            "failure_direction": norm_text(str(target.get("failure_direction", ""))),
        },
        "usage_rubric": dict(rubric),
        "judge_trace": memory.get("judge_trace", {}),
    }
    return normalized


def validate_model_record(rec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if rec.get("accepted") is False:
        errors.append("model_rejected_record")
    if len(norm_text(str(rec.get("question", "")))) < 10:
        errors.append("question_too_short")

    blocks = rec.get("memory_blocks")
    memories = rec.get("memories")
    if not isinstance(blocks, list) or not blocks:
        errors.append("missing_required_memory_blocks")
        blocks = []
    if not isinstance(memories, list) or not memories:
        errors.append("missing_required_memories")
        memories = []

    for block_index, block in enumerate(blocks):
        if not isinstance(block, dict):
            errors.append(f"bad_block_{block_index}")
            continue
        missing = BLOCK_REQUIRED_KEYS - set(block)
        if missing:
            errors.append(f"block_{block_index}_missing_{','.join(sorted(missing))}")
        if is_first_person_stored_memory(block.get("memory_text")):
            errors.append(f"block_{block_index}_first_person_memory_text")

    block_atom_ids = {
        str(atom_id)
        for block in blocks
        if isinstance(block, dict) and isinstance(block.get("atom_ids"), list)
        for atom_id in block.get("atom_ids", [])
    }
    memory_atom_ids = set()
    labels = []
    for memory_index, memory in enumerate(memories):
        if not isinstance(memory, dict):
            errors.append(f"bad_memory_{memory_index}")
            continue
        missing = MEMORY_REQUIRED_KEYS - set(memory)
        if missing:
            errors.append(f"memory_{memory_index}_missing_{','.join(sorted(missing))}")
        label = str(memory.get("u_star", "")).strip().upper()
        labels.append(label)
        atom_id = str(memory.get("atom_id", ""))
        if atom_id:
            memory_atom_ids.add(atom_id)
        if label not in {"A", "B", "C"}:
            errors.append(f"memory_{memory_index}_bad_label")
        if is_first_person_stored_memory(memory.get("text")):
            errors.append(f"memory_{memory_index}_first_person_text")
        target = memory.get("construction_target") if isinstance(memory.get("construction_target"), dict) else {}
        if not TARGET_REQUIRED_KEYS.issubset(target):
            errors.append(f"memory_{memory_index}_bad_construction_target")
        rubric = effective_usage_rubric(memory)
        if not COMMON_RUBRIC_KEYS.issubset(rubric):
            errors.append(f"memory_{memory_index}_bad_common_rubric")
        specific = LABEL_SPECIFIC_RUBRIC_KEYS.get(label, set())
        if not specific.issubset(rubric):
            errors.append(f"memory_{memory_index}_bad_label_specific_rubric")
        expected_weight = {"A": "none", "B": "supporting", "C": "controlling"}.get(label)
        if expected_weight and rubric.get("memory_usage_weight") != expected_weight:
            errors.append(f"memory_{memory_index}_bad_usage_weight")

    if block_atom_ids and memory_atom_ids and block_atom_ids != memory_atom_ids:
        errors.append("block_memory_atom_id_mismatch")
    if not any(label in {"B", "C"} for label in labels):
        errors.append("missing_applied_label")
    if not any(
        str(memory.get("u_star", "")).strip().upper() == "A" and memory.get("source") == "synthetic_hard_a"
        for memory in memories
        if isinstance(memory, dict)
    ):
        errors.append("missing_synthetic_hard_a")
    return errors


def normalize_model_record(raw: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    source_id = str(params.get("id") or params.get("source_raw_id") or "")
    blocks = [normalize_block(block, index + 1) for index, block in enumerate(raw.get("memory_blocks", []))]
    memories = [normalize_memory(memory, index + 1) for index, memory in enumerate(raw.get("memories", []))]
    parent_label_metadata = add_parent_label_metadata(blocks, memories)
    qc = raw.get("qc") if isinstance(raw.get("qc"), dict) else {}
    audit = raw.get("construction_audit") if isinstance(raw.get("construction_audit"), dict) else {}
    split = str(audit.get("quality_subset") or "clean")
    return {
        "id": f"crk2_{source_id}",
        "domain": "health_seed",
        "source_dataset": params.get("source_dataset", ""),
        "source_id": source_id,
        "source_record_id": source_id,
        "source_split": params.get("source_split", ""),
        "source_index": params.get("source_index", ""),
        "source_topic": params.get("topic", ""),
        "raw_query": params.get("raw_question", ""),
        "doctor_answer": params.get("doctor_answer", ""),
        "question": norm_text(str(raw.get("question", ""))),
        "memory_blocks": blocks,
        "memories": memories,
        "composition": {
            "memory_count": len(memories),
            "parent_memory_count": len(blocks),
            "label_counts": {
                label: sum(1 for memory in memories if memory.get("u_star") == label)
                for label in ("A", "B", "C")
            },
            "has_synthetic_hard_a": any(memory.get("source") == "synthetic_hard_a" for memory in memories),
            "hard_a_families": sorted({memory.get("hard_a_family") for memory in memories if memory.get("hard_a_family")}),
            **parent_label_metadata,
        },
        "qc": {
            "atomicity_pass": normalize_bool(qc.get("atomicity_pass")),
            "duplicate_pass": normalize_bool(qc.get("duplicate_pass")),
            "question_memory_leakage_pass": normalize_bool(qc.get("question_memory_leakage_pass")),
            "hard_a_target_consistency_pass": normalize_bool(qc.get("hard_a_target_consistency_pass")),
            "rubric_objectivity_pass": normalize_bool(qc.get("rubric_objectivity_pass")),
            "counterfactual_pass": qc.get("counterfactual_pass", "pending_model_test"),
            "manual_audit": qc.get("manual_audit", "not_sampled"),
            "overlap_groups": qc.get("overlap_groups", []),
            "question_memory_leakage_issues": qc.get("question_memory_leakage_issues", []),
        },
        "construction_audit": audit or {"schema_version": "crk-2-canonical-memory-v1", "quality_subset": split, "pipeline_steps": []},
        "split": split,
        "prototype_notes": norm_text(str(raw.get("notes", ""))),
    }


def summarize_and_render(samples: list[dict[str, Any]], summary_path: Path, html_path: Path) -> dict[str, Any]:
    builder = load_rubric_builder()
    summary = builder.summarize(samples)
    summary["pipeline"] = "crk2_llm_generation"
    parent_modes = Counter()
    parent_label_sets = Counter()
    for sample in samples:
        for block in sample.get("memory_blocks", []):
            mode = block.get("parent_label_mode", "unknown")
            label_set = "+".join(block.get("parent_label_set", [])) if isinstance(block.get("parent_label_set"), list) else str(block.get("parent_label_set", "unknown"))
            parent_modes[mode] += 1
            parent_label_sets[label_set or "none"] += 1
    summary["parent_label_mode_counts"] = dict(parent_modes)
    summary["parent_label_set_counts"] = dict(parent_label_sets)
    total_parent = sum(parent_modes.values())
    summary["mixed_parent_count"] = parent_modes.get("mixed", 0)
    summary["mixed_parent_rate"] = parent_modes.get("mixed", 0) / total_parent if total_parent else 0
    summary["prototype_limitations"] = [
        "This preview is generated by the CRK-2 canonical-memory prompt from normalized public QA seed records.",
        "Raw evidence is retained for audit, while stored memories are third-person canonical summaries used for A/B/C labeling and judge rubrics.",
        "Current seed source is still medical-heavy; later benchmark iterations should add broader general-dialogue sources.",
        "Counterfactual answer tests, cross-model judge calibration, and manual audit sampling are not run yet.",
    ]
    write_json(summary_path, summary)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html = "\n".join(line.rstrip() for line in builder.build_html(samples, summary).splitlines()) + "\n"
    html_path.write_text(html, encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse CRK-2 full LLM construction results into benchmark JSONL and HTML.")
    parser.add_argument("--input", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--rejected", type=Path)
    parser.add_argument("--target", type=int, default=100)
    args = parser.parse_args()

    rejected_path = args.rejected or args.output.with_name(args.output.stem + ".rejected.jsonl")
    kept = []
    rejected = []
    for input_path in args.input:
        for row_index, line in enumerate(input_path.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            row = json.loads(line)
            params = get_params(row)
            try:
                raw = extract_json_object(get_text(row))
                errors = validate_model_record(raw)
                if errors:
                    rejected.append(
                        {"input": str(input_path), "row_index": row_index, "errors": errors, "params": params, "raw": raw}
                    )
                    continue
                kept.append(normalize_model_record(raw, params))
                if args.target and len(kept) >= args.target:
                    break
            except Exception as exc:  # noqa: BLE001
                rejected.append({"input": str(input_path), "row_index": row_index, "errors": [type(exc).__name__, str(exc)], "params": params})
        if args.target and len(kept) >= args.target:
            break

    write_jsonl(args.output, kept)
    write_jsonl(rejected_path, rejected)
    summary = summarize_and_render(kept, args.summary, args.html) if kept else {"total_samples": 0}
    print(
        json.dumps(
            {
                "output": str(args.output),
                "input": [str(path) for path in args.input],
                "summary": str(args.summary),
                "html": str(args.html),
                "rejected": str(rejected_path),
                "kept": len(kept),
                "rejected_count": len(rejected),
                **summary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
