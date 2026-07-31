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
from memcalib_v24_coding_common import (
    BENCHMARK_META_RE,
    CODE_FENCE_RE,
    V23_RELEASE,
    V24_DIR,
    materialize_question,
)
from utils import iter_jsonl, write_json, write_jsonl


AUDIT_DIR = V24_DIR / "audit"
DEFAULT_CANDIDATES = AUDIT_DIR / "memcalib_v241_direct_question_repair_511.jsonl"
DEFAULT_REPAIR_SELECTION = (
    AUDIT_DIR / "memcalib_v241_direct_question_repair_consensus_511.repair.jsonl"
)
DEFAULT_UNRESOLVED = (
    AUDIT_DIR / "memcalib_v241_repaired_candidates_unresolved_98.jsonl"
)
DEFAULT_OUTPUT = AUDIT_DIR / "memcalib_v241_direct_supervision_repair_554.jsonl"

FENCED_BLOCK_RE = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)
INLINE_TICK_RE = re.compile(r"`([^`\n]+)`")
IMPLEMENTATION_PREFIXES = (
    "write ",
    "create ",
    "implement ",
    "build ",
    "develop ",
    "design ",
    "define ",
    "add ",
    "modify ",
    "convert ",
)
DEBUG_MARKERS = (
    " why ",
    " error",
    " fail",
    " bug",
    " incorrect",
    " wrong",
    " fix ",
    " debug",
    " troubleshoot",
    " exception",
    " crash",
    " not work",
    " doesn't work",
    " does not work",
)
BEHAVIOR_MARKERS = (
    " what happens ",
    " what will happen ",
    " expected behavior",
    " expected output",
    " what output",
    " what result",
    " return value",
    " evaluate to",
    " how does ",
    " how is ",
)


def clean_text(value: str) -> str:
    cleaned = CODE_FENCE_RE.sub("", value)
    cleaned = INLINE_TICK_RE.sub(r"\1", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def prose_outside_fences(value: str) -> str:
    return clean_text(FENCED_BLOCK_RE.sub(" ", value))


def infer_task_family(question: str) -> str:
    lowered = f" {question.casefold()} "
    stripped = question.lstrip().casefold()
    if any(marker in lowered for marker in DEBUG_MARKERS):
        return "debugging_diagnosis"
    if any(marker in lowered for marker in BEHAVIOR_MARKERS):
        return "behavior_prediction"
    if stripped.startswith(IMPLEMENTATION_PREFIXES):
        return "implementation_plan"
    return "implementation_plan"


def direct_task_stem(original_question: str, family: str) -> str:
    original = clean_text(original_question)
    if family == "implementation_plan":
        return (
            "Describe a step-by-step implementation plan in natural language for "
            "accomplishing this original software-engineering request while "
            f"preserving every functional requirement: {original}"
        )
    if family == "debugging_diagnosis":
        return (
            "Diagnose this original software-engineering issue and describe the "
            "corrected behavior in natural language while preserving its practical "
            f"scope: {original}"
        )
    return (
        "Explain the expected behavior and decisions for this original "
        "software-engineering question in natural language: "
        f"{original}"
    )


def atom_required_fragments(atom: dict[str, Any]) -> list[str]:
    rubric = atom.get("usage_rubric")
    contract = atom.get("counterfactual_contract")
    fragments: list[str] = []
    if isinstance(rubric, dict):
        expected = clean_text(str(rubric.get("expected_answer_behavior") or ""))
        if expected:
            fragments.append(expected)
    if isinstance(contract, dict):
        for value in contract.get("minimal_evidence") or []:
            fragment = clean_text(str(value))
            if fragment:
                fragments.append(fragment)
    if not fragments:
        fragments.append(clean_text(str(atom.get("text") or "")))
    output: list[str] = []
    seen: set[str] = set()
    for fragment in fragments:
        key = norm_text(fragment).casefold()
        if key and key not in seen:
            output.append(fragment.rstrip("."))
            seen.add(key)
    return output


def operationalize_atom_text(value: str) -> str:
    text = clean_text(value).rstrip(".")
    patterns = (
        (
            re.compile(r"^The user requires\s+(.+)$", re.IGNORECASE),
            "The solution must satisfy this user requirement: {body}.",
        ),
        (
            re.compile(r"^The user prefers\s+(.+)$", re.IGNORECASE),
            "The solution should honor this user preference: {body}.",
        ),
        (
            re.compile(r"^The project uses\s+(.+)$", re.IGNORECASE),
            "The solution should use the project's stated context: {body}.",
        ),
        (
            re.compile(r"^The project targets\s+(.+)$", re.IGNORECASE),
            "The solution must target {body}.",
        ),
        (
            re.compile(r"^The development environment is\s+(.+)$", re.IGNORECASE),
            "Use {body} as the development environment.",
        ),
        (
            re.compile(r"^The current system uses\s+(.+)$", re.IGNORECASE),
            "The solution should account for the current system using {body}.",
        ),
    )
    for pattern, template in patterns:
        match = pattern.fullmatch(text)
        if match:
            return template.format(body=match.group(1).rstrip("."))
    return "The solution should account for this stated constraint: " + text + "."


def rebuild_atom_supervision(atom: dict[str, Any]) -> dict[str, Any]:
    restored = copy.deepcopy(atom)
    label = str(restored.get("u_star") or "")
    action = str(restored.get("memory_action") or "")
    if label not in {"B", "C"} or action == "correct":
        rubric = restored.get("usage_rubric")
        if isinstance(rubric, dict):
            rubric["validity_scope"] = (
                "The complete natural-language answer to the original practical "
                "software-engineering request."
            )
        return restored

    atom_text = clean_text(
        str(restored.get("atomic_predicate") or restored.get("text") or "")
    )
    if not atom_text:
        raise ValueError(f"applicable atom text is empty: {restored.get('atom_id')}")
    role = "supporting" if label == "B" else "controlling"
    expected = operationalize_atom_text(atom_text)
    restored["label_reason"] = (
        "This atom has bounded supporting influence on the practical solution."
        if label == "B"
        else "This atom controls a core decision or externally visible behavior."
    )
    restored["construction_target"] = {
        "task_goal": (
            "Explain the original practical software-engineering solution in "
            "natural language."
        ),
        "memory_role": f"{role.capitalize()} influence on the answer.",
        "usage_boundary": (
            "Use exactly the requirement stated by this atom without importing "
            "technology, identifiers, providers, or conclusions from another atom."
        ),
        "failure_direction": (
            "Under-use omits or contradicts the atom; over-use extends it beyond "
            "its stated scope."
        ),
    }
    restored["counterfactual_contract"] = {
        "without_memory_behavior": (
            "The answer may omit or contradict this atom-specific requirement."
        ),
        "with_memory_behavior": expected,
        "observable_delta": atom_text,
        "minimal_evidence": [atom_text],
    }
    restored["usage_rubric"] = {
        "expected_answer_behavior": expected,
        "memory_usage_weight": role,
        "validity_scope": (
            "The complete natural-language answer to the original practical "
            "software-engineering request."
        ),
        "correct_use": expected,
        "under_use": (
            "The answer omits, weakens, or contradicts this requirement: " + atom_text
        ),
        "over_use": (
            "The answer attributes unsupported details or additional requirements "
            "to this atom beyond: "
            + atom_text
        ),
        "forbidden_memory_role": (
            "This atom must not import another atom's technology, provider, path, "
            "recommendation, application domain, or conclusion."
        ),
        "failure_direction": (
            "Missing the stated requirement is under-use; adding unsupported "
            "atom-specific details is over-use."
        ),
        "observable_checks": [
            "The answer explicitly contains this same-atom evidence: " + atom_text,
            (
                "Every technology, identifier, provider, path, recommendation, "
                "domain, and conclusion attributed to this atom is supported by "
                "the atom text."
            ),
        ],
    }
    restored["v241_same_atom_supervision"] = {
        "schema_version": "memcalib-v241-same-atom-supervision-v1",
        "source": "atom_text_only",
        "source_fingerprint": canonical_sha256(atom_text),
    }
    return restored


def build_reference_answer(
    source: dict[str, Any],
    memories: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    original_question = clean_text(str(source.get("question") or ""))
    if not original_question:
        raise ValueError(f"source question is empty: {source.get('id')}")
    parts: list[str] = []
    original_prose = prose_outside_fences(str(source.get("source_answer") or ""))
    if len(norm_text(original_prose)) >= 40:
        parts.append(original_prose)
    else:
        parts.append(
            "Implement the requested behavior by identifying its inputs and "
            "dependencies, following the required control flow, producing the "
            "specified outputs, and handling the stated failure conditions."
        )
    parts.append(
        "The solution must preserve every explicit practical requirement in this "
        f"original specification: {original_question}"
    )

    evidence: list[str] = []
    for atom in memories:
        if atom.get("u_star") not in {"B", "C"}:
            continue
        fragments = atom_required_fragments(atom)
        evidence.extend(fragments)
        parts.extend(fragment.rstrip(".") + "." for fragment in fragments)
    reference = "\n\n".join(parts)
    if CODE_FENCE_RE.search(reference):
        raise ValueError(f"reference contains a code fence: {source.get('id')}")
    if BENCHMARK_META_RE.search(reference):
        raise ValueError(f"reference leaks benchmark metadata: {source.get('id')}")
    for fragment in evidence:
        if norm_text(fragment).casefold() not in norm_text(reference).casefold():
            raise ValueError(
                f"reference omits required evidence for {source.get('id')}: {fragment}"
            )
    return reference, evidence


def restore_record(
    source: dict[str, Any],
    prior: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    record = copy.deepcopy(prior if prior is not None else source)
    family = infer_task_family(str(source.get("question") or ""))
    stem = direct_task_stem(str(source.get("question") or ""), family)
    question = materialize_question(stem, family)
    memories = [
        rebuild_atom_supervision(atom) for atom in source.get("memories") or []
    ]
    reference, evidence = build_reference_answer(source, memories)

    record["schema_version"] = "crk-2-canonical-memory-v2.4.1"
    record["question"] = question
    record["source_answer"] = reference
    record["memory_blocks"] = copy.deepcopy(source.get("memory_blocks") or [])
    record["memories"] = memories
    for stale_key in (
        "v24_coding_independent_qc",
        "v241_alignment_consensus",
    ):
        record.pop(stale_key, None)
    record["coding_text_observability_revision"] = {
        "schema_version": "memcalib-v241-direct-supervision-repair-v1",
        "task_family": family,
        "source_record_fingerprint": canonical_sha256(source),
        "prior_record_fingerprint": (
            canonical_sha256(prior) if prior is not None else None
        ),
        "question_contract": "natural_language_only_no_code_blocks",
        "repair_policy": (
            "restore_v23_labels_actions_and_same_atom_supervision_then_convert_"
            "response_form_only"
        ),
        "labels_and_actions_restored_from_v23": True,
        "rubrics_and_counterfactuals_restored_from_v23": False,
        "apply_rubrics_rebuilt_from_same_atom_text_only": True,
        "correct_rubrics_restored_from_v23_correction_contract": True,
        "reference_contains_all_original_bc_minimal_evidence": True,
    }
    audit = {
        "schema_version": "memcalib-v241-direct-supervision-repair-audit-v1",
        "record_id": record["id"],
        "had_prior_candidate": prior is not None,
        "task_family": family,
        "source_record_fingerprint": canonical_sha256(source),
        "prior_record_fingerprint": (
            canonical_sha256(prior) if prior is not None else None
        ),
        "output_record_fingerprint": canonical_sha256(record),
        "restored_label_distribution": dict(
            sorted(
                Counter(
                    str(atom.get("u_star") or "")
                    for atom in record.get("memories") or []
                ).items()
            )
        ),
        "required_evidence_count": len(evidence),
    }
    return record, audit


def selection_ids(path: Path) -> list[str]:
    values = [
        str(row.get("id") or row.get("record_id") or "")
        for row in iter_jsonl(path)
    ]
    if "" in values or len(values) != len(set(values)):
        raise ValueError(f"selection IDs must be non-empty and unique: {path}")
    return values


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Directly restore original atom supervision and practical task scope "
            "for the final residual MemCalib v2.4.1 coding repairs."
        )
    )
    parser.add_argument("--source-benchmark", type=Path, default=V23_RELEASE)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument(
        "--repair-selection", type=Path, default=DEFAULT_REPAIR_SELECTION
    )
    parser.add_argument("--unresolved-selection", type=Path, default=DEFAULT_UNRESOLVED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    repair_ids = selection_ids(args.repair_selection)
    unresolved_ids = selection_ids(args.unresolved_selection)
    if set(repair_ids) & set(unresolved_ids):
        raise ValueError("repair and unresolved selections overlap")
    selected = set(repair_ids) | set(unresolved_ids)
    candidates = {
        str(row.get("id") or ""): row for row in iter_jsonl(args.candidates)
    }
    sources = [
        row
        for row in iter_jsonl(args.source_benchmark)
        if str(row.get("id") or "") in selected
    ]
    source_ids = {str(row.get("id") or "") for row in sources}
    missing = selected - source_ids
    if missing:
        raise ValueError(f"selected records missing from source: {sorted(missing)[:20]}")

    output: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for source in sources:
        record_id = str(source["id"])
        prior = candidates.get(record_id) if record_id in set(repair_ids) else None
        repaired, audit = restore_record(source, prior)
        output.append(repaired)
        audits.append(audit)
    if len(output) != len(selected):
        raise ValueError("output coverage mismatch")

    audit_path = args.audit_output or args.output.with_suffix(".audit.jsonl")
    manifest_path = args.manifest or args.output.with_suffix(".manifest.json")
    write_jsonl(args.output, output)
    write_jsonl(audit_path, audits)
    manifest = {
        "schema_version": "memcalib-v241-direct-supervision-repair-manifest-v1",
        "policy": {
            "broad_generation": False,
            "labels_actions": "restored_from_v23",
            "atom_supervision": (
                "apply_contracts_rebuilt_from_same_atom_text_only_and_correct_"
                "contracts_restored_from_v23"
            ),
            "question": "original_scope_natural_language_response_form",
            "reference": "original_practical_prose_plus_all_bc_minimal_evidence",
        },
        "inputs": {
            key: {
                "path": portable_path(path),
                "sha256": file_sha256(path),
            }
            for key, path in {
                "source_benchmark": args.source_benchmark,
                "candidates": args.candidates,
                "repair_selection": args.repair_selection,
                "unresolved_selection": args.unresolved_selection,
            }.items()
        },
        "counts": {
            "repair_selection": len(repair_ids),
            "unresolved_selection": len(unresolved_ids),
            "output": len(output),
            "with_prior_candidate": sum(
                bool(row["had_prior_candidate"]) for row in audits
            ),
            "restored_labels": dict(
                sorted(
                    Counter(
                        str(atom.get("u_star") or "")
                        for row in output
                        for atom in row.get("memories") or []
                    ).items()
                )
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
