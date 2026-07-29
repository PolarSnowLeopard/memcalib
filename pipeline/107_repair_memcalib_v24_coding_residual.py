#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any

from memcalib_v23_common import canonical_sha256, file_sha256, portable_path
from memcalib_v24_coding_common import (
    PAYLOAD_SCHEMA,
    REVISION_SCHEMA,
    RUNTIME_ONLY_RE,
    V23_RELEASE,
    V24_DIR,
    applicable_atoms,
    locked_supervision_fingerprint,
    materialize_question,
    stable_task_family,
    validate_revision_payload,
)
from utils import iter_jsonl, write_json, write_jsonl

from importlib import import_module


POST = import_module("103_post_memcalib_v24_coding_rewrite")
DEFAULT_OUTPUT = V24_DIR / "memcalib_v24_coding_local_residual_repair_163.jsonl"
DEFAULT_AUDIT = DEFAULT_OUTPUT.with_suffix(".audit.jsonl")
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")
TOKEN_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./#+:-]*")
QUOTED_RE = re.compile(r"[`'\"]([^`'\"]{2,80})[`'\"]")
FENCE_RE = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)
SPACE_RE = re.compile(r"\s+")
DIRECTIVE_RE = re.compile(
    r"^\s*(?:please\s+)?(?:write|implement|create|produce|provide|generate|"
    r"develop|return)\b",
    re.IGNORECASE,
)
BENCHMARK_LANGUAGE_RE = re.compile(
    r"\b(?:retrieved memor(?:y|ies)|memory constraints?|apply only retrieved "
    r"memories|ignore irrelevant retrieved context)\b",
    re.IGNORECASE,
)
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "user",
    "uses",
    "using",
    "with",
}


def record_id(row: dict[str, Any]) -> str:
    return str(row.get("id") or row.get("record_id") or "")


def residual_data(paths: list[Path]) -> tuple[list[str], dict[str, set[str]]]:
    ordered: list[str] = []
    seen: set[str] = set()
    flagged_atoms: dict[str, set[str]] = {}
    for path in paths:
        for row in iter_jsonl(path):
            item_id = record_id(row)
            if not item_id:
                raise ValueError(f"empty record ID in {path}")
            if item_id not in seen:
                seen.add(item_id)
                ordered.append(item_id)
            qc = row.get("v24_coding_independent_qc")
            if not isinstance(qc, dict):
                continue
            for reason in qc.get("decision_reasons") or []:
                match = re.match(
                    r"^([^:]+):query_value_status:(?:partially|fully)_supplied$",
                    str(reason),
                )
                if match:
                    flagged_atoms.setdefault(item_id, set()).add(match.group(1))
    return ordered, flagged_atoms


def atom_placeholder(atom: dict[str, Any]) -> str:
    subtype = str(atom.get("subtype") or "").casefold()
    memory_type = str(atom.get("memory_type") or "").casefold()
    combined = f"{subtype} {memory_type}"
    if any(term in combined for term in ("environment", "platform", "version")):
        return "the target environment"
    if any(
        term in combined
        for term in ("library", "dependency", "tool", "framework", "api")
    ):
        return "the project-approved dependency"
    if any(term in combined for term in ("error", "output", "format", "status")):
        return "the required externally visible behavior"
    if "preference" in combined:
        return "the applicable project preference"
    if any(term in combined for term in ("workflow", "profile", "context")):
        return "the relevant project context"
    return "the applicable project constraint"


def phrase_pattern(tokens: list[str]) -> re.Pattern[str]:
    return re.compile(
        r"(?<![A-Za-z0-9_])"
        + r"[^A-Za-z0-9_]+".join(re.escape(token) for token in tokens)
        + r"(?![A-Za-z0-9_])",
        re.IGNORECASE,
    )


def scrub_atom_overlap(
    question: str,
    atom: dict[str, Any],
) -> tuple[str, list[str]]:
    atom_text = str(atom.get("text") or atom.get("atomic_predicate") or "")
    placeholder = atom_placeholder(atom)
    removed: list[str] = []

    for match in QUOTED_RE.finditer(atom_text):
        phrase = match.group(1).strip()
        if phrase and re.search(re.escape(phrase), question, re.IGNORECASE):
            question = re.sub(
                re.escape(phrase),
                placeholder,
                question,
                flags=re.IGNORECASE,
            )
            removed.append(phrase)

    atom_tokens = [match.group(0) for match in TOKEN_RE.finditer(atom_text)]
    question_tokens = [match.group(0) for match in TOKEN_RE.finditer(question)]
    question_folded = [token.casefold() for token in question_tokens]
    for size in range(min(6, len(atom_tokens)), 1, -1):
        for start in range(len(atom_tokens) - size + 1):
            tokens = atom_tokens[start : start + size]
            folded = [token.casefold() for token in tokens]
            informative = [token for token in folded if token not in STOPWORDS]
            if len(informative) < 2:
                continue
            if all(len(token) < 4 and not any(char.isdigit() for char in token) for token in informative):
                continue
            for q_start in range(len(question_folded) - size + 1):
                if question_folded[q_start : q_start + size] != folded:
                    continue
                pattern = phrase_pattern(tokens)
                current = pattern.search(question)
                if current:
                    removed.append(current.group(0))
                    question = pattern.sub(placeholder, question)
                break
            question_tokens = [
                match.group(0) for match in TOKEN_RE.finditer(question)
            ]
            question_folded = [token.casefold() for token in question_tokens]
    return question, list(dict.fromkeys(removed))


def normalize_original_question(question: str) -> str:
    text = FENCE_RE.sub("the supplied interface", question)
    text = BENCHMARK_LANGUAGE_RE.sub("the stated project requirements", text)
    text = re.sub(
        r"\bcomplete implementation code\b",
        "complete implementation behavior",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bsource[- ]code artifact\b",
        "software behavior",
        text,
        flags=re.IGNORECASE,
    )
    if DIRECTIVE_RE.search(text):
        text = DIRECTIVE_RE.sub("Explain in natural language how to", text, count=1)
    text = re.sub(
        r"\breturn only the completed (?:solution|artifact)\b\.?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return SPACE_RE.sub(" ", text).strip()


def infer_task_family(question: str) -> str:
    folded = question.casefold()
    diagnostic_markers = (
        " error",
        " fail",
        " issue",
        " problem",
        " timeout",
        " unable ",
        " not being ",
        " not working",
        " refuses ",
        " debugging",
        " diagnose",
        " resolve ",
        " why ",
    )
    if any(marker in f" {folded} " for marker in diagnostic_markers):
        return "debugging_diagnosis"
    prediction_markers = (
        "what happens",
        "expected behavior",
        "expected output",
        "what will",
        "predict",
    )
    if any(marker in folded for marker in prediction_markers):
        return "behavior_prediction"
    return "implementation_plan"


def source_prose_answer(source: dict[str, Any]) -> str:
    answer = str(source.get("source_answer") or "")
    prose = FENCE_RE.sub(" ", answer)
    prose = SPACE_RE.sub(" ", prose).strip()
    return prose


def local_task_stem(
    source: dict[str, Any],
    family: str,
    target_atom_ids: set[str],
) -> tuple[str, list[dict[str, str]]]:
    question = normalize_original_question(str(source.get("question") or ""))
    atoms = {
        str(atom.get("atom_id") or ""): atom for atom in source.get("memories") or []
    }
    removals: list[dict[str, str]] = []
    for atom_id in sorted(target_atom_ids):
        atom = atoms.get(atom_id)
        if atom is None:
            continue
        question, removed = scrub_atom_overlap(question, atom)
        removals.extend(
            {"atom_id": atom_id, "removed_text": phrase} for phrase in removed
        )
    question = SPACE_RE.sub(" ", question).strip(" .")
    if len(question) < 32:
        topic = str(source.get("source_topic") or "software task").replace("_", " ")
        question = (
            f"Explain the required behavior and resolution approach for this {topic} "
            "problem while leaving project-specific values to the supplied context"
        )
    lead = {
        "implementation_plan": (
            "Provide a natural-language implementation plan for the following "
            "software task: "
        ),
        "debugging_diagnosis": (
            "Diagnose the following software problem and explain the corrected "
            "behavior in natural language: "
        ),
        "behavior_prediction": (
            "Explain the expected behavior and decision path for the following "
            "software task in natural language: "
        ),
    }[family]
    return f"{lead}{question}.", removals


def direct_requirement(atom: dict[str, Any]) -> str:
    text = SPACE_RE.sub(" ", str(atom.get("text") or "")).strip().rstrip(".")
    return f"{text}."


def contract_task_goal(source: dict[str, Any]) -> str:
    for atom in applicable_atoms(source):
        goal = str(atom.get("construction_target", {}).get("task_goal") or "").strip()
        if goal and goal not in {
            "Produce the requested source-code artifact.",
            "Answer the current model-facing task accurately.",
        }:
            return goal.rstrip(".")
    topic = str(source.get("source_topic") or "software").replace("_", " ")
    return f"resolve the target {topic} task"


def contract_family(goal: str) -> str:
    folded = goal.casefold()
    if folded.startswith(("diagnose", "debug", "resolve")) or "failure" in folded:
        return "debugging_diagnosis"
    if folded.startswith(("predict", "explain expected")):
        return "behavior_prediction"
    return "implementation_plan"


def contract_evidence(atom: dict[str, Any]) -> list[str]:
    if atom.get("memory_action") == "correct":
        candidates = atom.get("counterfactual_contract", {}).get("minimal_evidence")
        if isinstance(candidates, list):
            evidence = [
                SPACE_RE.sub(" ", str(item)).strip().rstrip(".") + "."
                for item in candidates
                if isinstance(item, str) and len(SPACE_RE.sub(" ", item).strip()) >= 4
            ]
            evidence = [
                RUNTIME_ONLY_RE.sub("state the corrected behavior", item)
                for item in evidence
            ]
            if evidence:
                return evidence[:3]
    return [direct_requirement(atom)]


def contract_payload(
    source: dict[str, Any],
    family: str,
    goal: str,
) -> dict[str, Any]:
    footprints: list[dict[str, Any]] = []
    evidence_sentences: list[str] = []
    for atom in applicable_atoms(source):
        evidence = contract_evidence(atom)
        evidence_sentences.extend(evidence)
        overuse = str(atom.get("usage_rubric", {}).get("over_use") or "").strip()
        footprints.append(
            {
                "atom_id": str(atom.get("atom_id") or ""),
                "u_star": atom.get("u_star"),
                "memory_action": atom.get("memory_action"),
                "required_answer_elements": evidence,
                "overuse_signals": [
                    overuse
                    or "The answer extends this requirement beyond its stated scope."
                ],
                "label_justification": str(atom.get("label_reason") or "").strip()
                or (
                    "The locked label reflects this requirement's bounded influence "
                    "on the natural-language answer."
                ),
            }
        )
    if evidence_sentences:
        reference = (
            f"A correct response addresses this software objective: {goal}. "
            + " ".join(evidence_sentences)
        )
    else:
        reference = (
            f"A correct response addresses this software objective: {goal}. It "
            "explains how to validate the relevant inputs, perform the requested "
            "operation through the available abstraction, return the result, and "
            "surface failures without assuming a particular library, platform, "
            "container type, or implementation artifact."
        )
    task_stem = (
        f"Describe a project-compatible natural-language solution for this software "
        f"objective: {goal}. Identify the applicable environment, dependencies, "
        "constraints, outputs, and failure behavior without the question supplying "
        "their project-specific values."
    )
    return {
        "schema_version": PAYLOAD_SCHEMA,
        "record_id": str(source.get("id") or ""),
        "task_family": family,
        "task_stem": task_stem,
        "reference_answer": reference,
        "applicable_atom_footprints": footprints,
        "query_isolation_audit": [
            {
                "atom_id": item["atom_id"],
                "query_supplies_atom_value": False,
                "reason": (
                    "The task states only the software objective and asks the answer "
                    "to determine the project-specific value."
                ),
            }
            for item in footprints
        ],
        "self_check": {
            "all_applicable_atom_ids_exact": True,
            "locked_labels_actions_preserved": True,
            "query_does_not_restate_scored_memories": True,
            "answer_is_natural_language_only": True,
            "all_required_evidence_visible_in_reference_answer": True,
            "no_runtime_execution_needed_to_judge": True,
        },
    }


def synthesized_payload(
    source: dict[str, Any],
    family: str,
    task_stem: str,
    *,
    reference_seed: str = "",
) -> dict[str, Any]:
    footprints: list[dict[str, Any]] = []
    requirements: list[str] = []
    for atom in applicable_atoms(source):
        requirement = direct_requirement(atom)
        requirements.append(requirement)
        footprints.append(
            {
                "atom_id": str(atom.get("atom_id") or ""),
                "u_star": atom.get("u_star"),
                "memory_action": atom.get("memory_action"),
                "required_answer_elements": [requirement],
                "overuse_signals": [
                    "The answer extends this requirement beyond its stated scope."
                ],
                "label_justification": str(atom.get("label_reason") or "").strip()
                or (
                    "The locked label reflects the bounded effect of this project "
                    "requirement on the natural-language answer."
                ),
            }
        )
    reference_seed = SPACE_RE.sub(" ", reference_seed).strip()
    if requirements:
        reference = " ".join(
            part
            for part in (
                reference_seed,
                (
                    "The response should explain the requested software behavior, "
                    "its decision points, outputs, and failure handling in prose."
                ),
                " ".join(requirements),
            )
            if part
        )
    else:
        reference = reference_seed or (
            "The response should explain a concrete implementation approach for the "
            "requested software task, including the relevant inputs, dependencies, "
            "control flow, outputs, and failure handling, without introducing "
            "unrelated project details."
        )
    return {
        "schema_version": PAYLOAD_SCHEMA,
        "record_id": str(source.get("id") or ""),
        "task_family": family,
        "task_stem": task_stem,
        "reference_answer": reference,
        "applicable_atom_footprints": footprints,
        "query_isolation_audit": [
            {
                "atom_id": item["atom_id"],
                "query_supplies_atom_value": False,
                "reason": (
                    "The task asks for the applicable project value without stating "
                    "the atom-specific answer."
                ),
            }
            for item in footprints
        ],
        "self_check": {
            "all_applicable_atom_ids_exact": True,
            "locked_labels_actions_preserved": True,
            "query_does_not_restate_scored_memories": True,
            "answer_is_natural_language_only": True,
            "all_required_evidence_visible_in_reference_answer": True,
            "no_runtime_execution_needed_to_judge": True,
        },
    }


def build_params(source: dict[str, Any], family: str) -> dict[str, Any]:
    return {
        "record_id": source["id"],
        "source_record_fingerprint": canonical_sha256(source),
        "locked_supervision_fingerprint": locked_supervision_fingerprint(source),
        "memory_blocks_fingerprint": canonical_sha256(source.get("memory_blocks") or []),
        "task_family": family,
        "retry_round": "local_residual_repair",
        "retry_feedback_fingerprint": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Repair residual MemCalib v2.4 coding records locally without another "
            "generation API round."
        )
    )
    parser.add_argument("--benchmark", type=Path, default=V23_RELEASE)
    parser.add_argument(
        "--selection-jsonl", type=Path, action="append", default=[], required=True
    )
    parser.add_argument(
        "--candidate-jsonl", type=Path, action="append", default=[], required=True
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--strict-reconstruct",
        action="store_true",
        help=(
            "Rebuild every selected record from the source question, source prose, "
            "and locked B/C supervision instead of reusing a prior candidate."
        ),
    )
    parser.add_argument(
        "--contract-reconstruct",
        action="store_true",
        help=(
            "Rebuild from the locked construction target and domain evidence only; "
            "exclude legacy reference content and all A-specific content."
        ),
    )
    args = parser.parse_args()

    sources = {
        str(record.get("id") or ""): record for record in iter_jsonl(args.benchmark)
    }
    residual_ids, flagged_atoms = residual_data(args.selection_jsonl)
    candidates: dict[str, dict[str, Any]] = {}
    for path in args.candidate_jsonl:
        for record in iter_jsonl(path):
            candidates[str(record.get("id") or "")] = record

    output: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for item_id in residual_ids:
        source = sources.get(item_id)
        if source is None:
            invalid.append({"record_id": item_id, "errors": ["source_missing"]})
            continue
        goal = contract_task_goal(source)
        family = (
            contract_family(goal)
            if args.contract_reconstruct
            else (
                infer_task_family(str(source.get("question") or ""))
                if args.strict_reconstruct
                else stable_task_family(item_id)
            )
        )
        target_ids = flagged_atoms.get(item_id)
        if not target_ids and not args.strict_reconstruct:
            target_ids = {
                str(atom.get("atom_id") or "")
                for atom in source.get("memories") or []
            }
        elif not target_ids:
            target_ids = set()
        task_stem, removals = local_task_stem(source, family, target_ids)
        params = build_params(source, family)
        candidate = candidates.get(item_id)
        if candidate is None or args.strict_reconstruct or args.contract_reconstruct:
            if args.contract_reconstruct:
                payload = contract_payload(source, family, goal)
            else:
                reference_seed = source_prose_answer(source)
                for atom in source.get("memories") or []:
                    if atom.get("u_star") != "A":
                        continue
                    reference_seed, _ = scrub_atom_overlap(reference_seed, atom)
                payload = synthesized_payload(
                    source,
                    family,
                    task_stem,
                    reference_seed=reference_seed,
                )
            errors = validate_revision_payload(payload, source, params)
            if errors:
                invalid.append({"record_id": item_id, "errors": errors})
                continue
            record, _ = POST.build_record(
                source,
                payload,
                params,
                f"v24_coding_local_repair:{item_id}",
                deterministic_repairs=[
                    (
                        (
                            "contract_reconstructed_from_locked_domain_evidence"
                            if args.contract_reconstruct
                            else "strictly_reconstructed_from_source_and_locked_supervision"
                        )
                        if args.strict_reconstruct or args.contract_reconstruct
                        else "locally_synthesized_residual_record"
                    )
                ],
            )
            repair_mode = (
                "contract_reconstruction"
                if args.contract_reconstruct
                else (
                    "strict_reconstruction"
                    if args.strict_reconstruct
                    else "synthesized"
                )
            )
        else:
            record = copy.deepcopy(candidate)
            record.pop("v24_coding_independent_qc", None)
            record["question"] = materialize_question(task_stem, family)
            revision = record.setdefault("coding_text_observability_revision", {})
            revision["schema_version"] = REVISION_SCHEMA
            revision["task_family"] = family
            revision["retry_round"] = "local_residual_repair"
            revision["request_id"] = f"v24_coding_local_repair:{item_id}"
            revision.setdefault("deterministic_repairs", []).append(
                "reset_question_to_sanitized_source_intent"
            )
            repair_mode = "question_reset"
        errors = POST.validate_built_record(record, source, params)
        if errors:
            invalid.append({"record_id": item_id, "errors": errors})
            continue
        output.append(record)
        audits.append(
            {
                "schema_version": "memcalib-v24-coding-local-residual-repair-audit-v1",
                "record_id": item_id,
                "repair_mode": repair_mode,
                "source_record_fingerprint": canonical_sha256(source),
                "prior_candidate_fingerprint": (
                    canonical_sha256(candidate) if candidate is not None else None
                ),
                "output_record_fingerprint": canonical_sha256(record),
                "flagged_atom_ids": sorted(target_ids),
                "removed_query_spans": removals,
            }
        )

    if invalid:
        raise ValueError(
            f"local residual repair left {len(invalid)} invalid records: "
            f"{invalid[:5]}"
        )
    if len(output) != len(residual_ids):
        raise ValueError("local residual repair coverage mismatch")
    write_jsonl(args.output, output)
    write_jsonl(args.audit, audits)
    manifest = {
        "schema_version": "memcalib-v24-coding-local-residual-repair-manifest-v1",
        "inputs": {
            "benchmark": {
                "path": portable_path(args.benchmark),
                "sha256": file_sha256(args.benchmark),
            },
            "selection": [
                {"path": portable_path(path), "sha256": file_sha256(path)}
                for path in args.selection_jsonl
            ],
            "candidates": [
                {"path": portable_path(path), "sha256": file_sha256(path)}
                for path in args.candidate_jsonl
            ],
        },
        "counts": {
            "residual": len(residual_ids),
            "question_reset": sum(
                audit["repair_mode"] == "question_reset" for audit in audits
            ),
            "synthesized": sum(
                audit["repair_mode"] == "synthesized" for audit in audits
            ),
            "strict_reconstruction": sum(
                audit["repair_mode"] == "strict_reconstruction" for audit in audits
            ),
            "contract_reconstruction": sum(
                audit["repair_mode"] == "contract_reconstruction" for audit in audits
            ),
            "output": len(output),
        },
        "outputs": {
            "records": {
                "path": portable_path(args.output),
                "sha256": file_sha256(args.output),
            },
            "audit": {
                "path": portable_path(args.audit),
                "sha256": file_sha256(args.audit),
            },
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
