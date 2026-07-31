#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from memcalib_v23_common import canonical_sha256, file_sha256, norm_text, portable_path
from memcalib_v24_alignment import overlap, tokens
from memcalib_v24_coding_common import V23_RELEASE, V24_DIR
from utils import iter_jsonl, write_json, write_jsonl

from importlib import import_module


curation = import_module("121_build_memcalib_v241_curated_residual")

AUDIT_DIR = V24_DIR / "audit"
DEFAULT_INPUT = AUDIT_DIR / "memcalib_v241_curated_residual_554.jsonl"
DEFAULT_REPAIR = AUDIT_DIR / "memcalib_v241_curated_residual_consensus_554.repair.jsonl"
DEFAULT_BASELINE = V24_DIR / "memcalib_v24_coding_complete_3750.jsonl"
DEFAULT_QWEN_PREFIXES = (
    AUDIT_DIR / "memcalib_v241_curated_residual_qc_qwenmax_554",
    AUDIT_DIR / "memcalib_v241_curated_residual_qc_qwenmax_retry1_4",
)
DEFAULT_DEEPSEEK_PREFIXES = (
    AUDIT_DIR / "memcalib_v241_curated_residual_qc_deepseek_554",
    AUDIT_DIR / "memcalib_v241_curated_residual_qc_deepseek_retry1_7",
)
DEFAULT_OUTPUT = AUDIT_DIR / "memcalib_v241_curated_residual_adjudicated_80.jsonl"

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
META_TRANSITIONS = (
    "The memory-conditioned answer must also make the following user or project "
    "context explicit:",
    "The solution must preserve every explicit practical requirement in this "
    "original specification:",
)
IMPLEMENTATION_ADDITIONS = (
    "produce ",
    "complete ",
    "fill ",
    "finish ",
    "supply ",
    "generate ",
)


def partition_path(prefix: Path, partition: str) -> Path:
    return prefix.with_suffix(f".{partition}.jsonl")


def load_resolved_partitions(prefixes: tuple[Path, ...]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for prefix in prefixes:
        for partition in ("strict", "review", "reject", "invalid"):
            for row in iter_jsonl(partition_path(prefix, partition)):
                record_id = str(row.get("id") or row.get("record_id") or "")
                if not record_id:
                    raise ValueError(f"empty record ID under {prefix}")
                prior = rows.get(record_id)
                if prior is not None and prior["partition"] != "invalid":
                    raise ValueError(f"valid QC row was rerun unexpectedly: {record_id}")
                rows[record_id] = {"partition": partition, "row": row}
    return rows


def judge_output(entry: dict[str, Any] | None) -> dict[str, Any]:
    if not entry:
        return {}
    qc = entry["row"].get("v24_coding_independent_qc")
    if not isinstance(qc, dict):
        return {}
    output = qc.get("judge_output")
    return output if isinstance(output, dict) else {}


def collect_issues(
    record: dict[str, Any],
    qwen_entry: dict[str, Any] | None,
    deepseek_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    labels = {
        str(atom.get("atom_id") or ""): str(atom.get("u_star") or "")
        for atom in record.get("memories") or []
    }
    issues: dict[str, Any] = {
        "semantic_equivalence": False,
        "reference_completeness": False,
        "task_family_fidelity": False,
        "natural_language_only": False,
        "runtime_independence": False,
        "a_footprint_atom_ids": set(),
        "query_supplied_atom_ids": set(),
        "scored_label_issue_atom_ids": set(),
        "judge_partitions": {
            "qwen": qwen_entry["partition"] if qwen_entry else "missing",
            "deepseek": deepseek_entry["partition"] if deepseek_entry else "missing",
        },
    }
    for entry in (qwen_entry, deepseek_entry):
        output = judge_output(entry)
        for check in output.get("record_checks") or []:
            if not isinstance(check, dict) or check.get("verdict") == "pass":
                continue
            name = str(check.get("check") or "")
            if name in issues:
                issues[name] = True
        for check in output.get("atom_checks") or []:
            if not isinstance(check, dict):
                continue
            atom_id = str(check.get("atom_id") or "")
            if check.get("query_value_status") in {
                "partially_supplied",
                "fully_supplied",
            }:
                issues["query_supplied_atom_ids"].add(atom_id)
            atom_failed = any(
                check.get(key) == "fail"
                for key in (
                    "label_action_validity",
                    "answer_text_observability",
                    "rubric_objectivity",
                )
            )
            if not atom_failed:
                continue
            if labels.get(atom_id) == "A":
                issues["a_footprint_atom_ids"].add(atom_id)
            else:
                issues["scored_label_issue_atom_ids"].add(atom_id)
    return issues


def text_similarity(left: str, right: str) -> float:
    left_tokens = tokens(left)
    right_tokens = tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def choose_reference(
    *,
    current: str,
    baseline: str,
    source: str,
    semantic_equivalence_failed: bool,
) -> tuple[str, str]:
    candidates = {
        "current_curated": curation.strip_code_blocks(current),
        "v24_baseline": curation.strip_code_blocks(baseline),
        "original_reference_prose": curation.strip_code_blocks(source),
    }
    candidates = {
        name: text
        for name, text in candidates.items()
        if len(norm_text(text)) >= 80
    }
    if not candidates:
        raise ValueError("no usable reference candidate")
    if not semantic_equivalence_failed:
        return candidates.get("current_curated", next(iter(candidates.values()))), (
            "current_curated"
            if "current_curated" in candidates
            else next(iter(candidates))
        )
    best_name, best_text = max(
        candidates.items(),
        key=lambda item: (
            text_similarity(item[1], source),
            len(norm_text(item[1])),
            item[0] == "original_reference_prose",
        ),
    )
    return best_text, best_name


def normalized_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    seen: set[str] = set()
    for raw in SENTENCE_SPLIT_RE.split(text):
        value = curation.clean_inline_text(raw).strip()
        for transition in META_TRANSITIONS:
            value = value.replace(transition, "").strip()
        if not value:
            continue
        key = norm_text(value).casefold()
        if key in seen:
            continue
        seen.add(key)
        sentences.append(curation.ensure_sentence(value))
    return sentences


def remove_atom_footprint(
    sentences: list[str],
    atom: dict[str, Any],
) -> tuple[list[str], list[str]]:
    predicate = str(atom.get("atomic_predicate") or atom.get("text") or "")
    if not predicate:
        return sentences, []
    scored = [
        (index, overlap(sentence, predicate))
        for index, sentence in enumerate(sentences)
    ]
    removable = {
        index
        for index, score in scored
        if score >= 0.34
        or norm_text(predicate).casefold() in norm_text(sentences[index]).casefold()
    }
    if not removable and scored:
        best_index, best_score = max(scored, key=lambda item: item[1])
        if best_score >= 0.15:
            removable.add(best_index)
    removed = [sentences[index] for index in sorted(removable)]
    retained = [
        sentence for index, sentence in enumerate(sentences) if index not in removable
    ]
    return retained, removed


def infer_repaired_family(original_question: str) -> str:
    stripped = curation.clean_inline_text(original_question).casefold().lstrip()
    if stripped.startswith(IMPLEMENTATION_ADDITIONS):
        return "implementation_plan"
    return curation.infer_response_family(original_question)


def adjudicate_record(
    *,
    record: dict[str, Any],
    source: dict[str, Any],
    baseline: dict[str, Any],
    qwen_entry: dict[str, Any] | None,
    deepseek_entry: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    output = copy.deepcopy(record)
    issues = collect_issues(output, qwen_entry, deepseek_entry)
    reference, reference_channel = choose_reference(
        current=str(output.get("source_answer") or ""),
        baseline=str(baseline.get("source_answer") or ""),
        source=str(source.get("source_answer") or ""),
        semantic_equivalence_failed=issues["semantic_equivalence"],
    )
    sentences = normalized_sentences(reference)
    atoms = copy.deepcopy(output.get("memories") or [])
    by_id = {str(atom.get("atom_id") or ""): atom for atom in atoms}
    removed_a_sentences: dict[str, list[str]] = {}

    for atom_id in sorted(issues["a_footprint_atom_ids"]):
        atom = by_id.get(atom_id)
        if atom is None or atom.get("u_star") != "A":
            continue
        sentences, removed = remove_atom_footprint(sentences, atom)
        if removed:
            removed_a_sentences[atom_id] = removed

    demotions: list[dict[str, Any]] = []
    for atom_id in sorted(issues["query_supplied_atom_ids"]):
        atom = by_id.get(atom_id)
        if atom is None or atom.get("u_star") not in {"B", "C"}:
            continue
        demotions.append(
            {
                "atom_id": atom_id,
                "old_u_star": atom.get("u_star"),
                "new_u_star": "A",
                "old_memory_action": atom.get("memory_action"),
                "new_memory_action": "ignore",
                "reason": "Both scoring and the question already supply this value.",
            }
        )
        atom["u_star"] = "A"
        atom["memory_action"] = "ignore"
        atom.update(curation.query_supplied_a_supervision(atom))

    if not any(atom.get("u_star") in {"B", "C"} for atom in atoms):
        raise ValueError(f"adjudication removed every scored atom: {output.get('id')}")

    reference = " ".join(sentences)
    rebuilt: list[dict[str, Any]] = []
    for atom in atoms:
        updated, reference = curation.same_atom_supervision(atom, reference)
        rebuilt.append(updated)
    reference = " ".join(normalized_sentences(reference))
    if len(norm_text(reference)) < 80:
        raise ValueError(f"adjudicated reference too short: {output.get('id')}")

    family = infer_repaired_family(str(source.get("question") or ""))
    output["schema_version"] = "crk-2-canonical-memory-v2.4.1"
    output["question"] = curation.response_form_question(
        str(source.get("question") or ""), family
    )
    output["source_answer"] = reference
    output["memories"] = rebuilt
    output["memory_blocks"] = copy.deepcopy(source.get("memory_blocks") or [])
    output.pop("v24_coding_independent_qc", None)
    output.pop("v241_alignment_consensus", None)
    prior_revision = copy.deepcopy(
        output.get("coding_text_observability_revision") or {}
    )
    output["coding_text_observability_revision"] = {
        "schema_version": "memcalib-v241-curated-adjudication-v1",
        "task_family": family,
        "question_contract": "natural_language_only_no_code_blocks",
        "source_record_fingerprint": canonical_sha256(source),
        "input_record_fingerprint": canonical_sha256(record),
        "reference_channel": reference_channel,
        "a_footprints_removed": len(removed_a_sentences),
        "query_supplied_atoms_demoted_to_a": len(demotions),
        "same_atom_supervision_rebuilt": True,
        "prior_revision": prior_revision,
    }
    audit = {
        "schema_version": "memcalib-v241-curated-adjudication-audit-v1",
        "record_id": output.get("id"),
        "issues": {
            key: sorted(value) if isinstance(value, set) else value
            for key, value in issues.items()
        },
        "reference_channel": reference_channel,
        "removed_a_sentences": removed_a_sentences,
        "query_supplied_atom_demotions": demotions,
        "input_record_fingerprint": canonical_sha256(record),
        "output_record_fingerprint": canonical_sha256(output),
    }
    return output, audit


def rows_by_id(path: Path) -> dict[str, dict[str, Any]]:
    rows = list(iter_jsonl(path))
    ids = [str(row.get("id") or "") for row in rows]
    if "" in ids or len(ids) != len(set(ids)):
        raise ValueError(f"record IDs must be non-empty and unique: {path}")
    return dict(zip(ids, rows, strict=True))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Directly adjudicate the small residual from the curated MemCalib "
            "v2.4.1 coding repair."
        )
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--repair-selection", type=Path, default=DEFAULT_REPAIR)
    parser.add_argument("--source-benchmark", type=Path, default=V23_RELEASE)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    records = rows_by_id(args.input)
    repair_order = [
        str(row.get("record_id") or row.get("id") or "")
        for row in iter_jsonl(args.repair_selection)
    ]
    if "" in repair_order or len(repair_order) != len(set(repair_order)):
        raise ValueError("repair selection IDs must be non-empty and unique")
    repair_ids = set(repair_order)
    sources = {
        str(row.get("id") or ""): row
        for row in iter_jsonl(args.source_benchmark)
        if str(row.get("id") or "") in repair_ids
    }
    baseline = {
        record_id: row
        for record_id, row in rows_by_id(args.baseline).items()
        if record_id in repair_ids
    }
    if set(sources) != repair_ids or set(baseline) != repair_ids:
        raise ValueError("source or baseline does not cover the repair selection")
    qwen = load_resolved_partitions(DEFAULT_QWEN_PREFIXES)
    deepseek = load_resolved_partitions(DEFAULT_DEEPSEEK_PREFIXES)

    output: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for record_id in repair_order:
        repaired, audit = adjudicate_record(
            record=records[record_id],
            source=sources[record_id],
            baseline=baseline[record_id],
            qwen_entry=qwen.get(record_id),
            deepseek_entry=deepseek.get(record_id),
        )
        output.append(repaired)
        audits.append(audit)

    audit_path = args.audit_output or args.output.with_suffix(".audit.jsonl")
    manifest_path = args.manifest or args.output.with_suffix(".manifest.json")
    write_jsonl(args.output, output)
    write_jsonl(audit_path, audits)
    manifest = {
        "schema_version": "memcalib-v241-curated-adjudication-manifest-v1",
        "inputs": {
            key: {
                "path": portable_path(path),
                "sha256": file_sha256(path),
            }
            for key, path in {
                "input": args.input,
                "repair_selection": args.repair_selection,
                "source_benchmark": args.source_benchmark,
                "baseline": args.baseline,
            }.items()
        },
        "counts": {
            "records": len(output),
            "judge_pairs": dict(
                sorted(
                    Counter(
                        (
                            row["issues"]["judge_partitions"]["qwen"]
                            + "|"
                            + row["issues"]["judge_partitions"]["deepseek"]
                        )
                        for row in audits
                    ).items()
                )
            ),
            "reference_channels": dict(
                sorted(Counter(row["reference_channel"] for row in audits).items())
            ),
            "a_footprints_removed": sum(
                len(row["removed_a_sentences"]) for row in audits
            ),
            "query_supplied_atom_demotions": sum(
                len(row["query_supplied_atom_demotions"]) for row in audits
            ),
        },
        "outputs": {
            "records": {
                "path": portable_path(args.output),
                "sha256": file_sha256(args.output),
            },
            "audit": {
                "path": portable_path(audit_path),
                "sha256": file_sha256(audit_path),
            },
        },
    }
    write_json(manifest_path, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
