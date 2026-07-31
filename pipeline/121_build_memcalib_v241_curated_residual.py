#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import importlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from memcalib_v23_common import canonical_sha256, file_sha256, norm_text, portable_path
from memcalib_v24_alignment import analyze_atom_alignment
from memcalib_v24_coding_common import CODE_FENCE_RE, V23_RELEASE, V24_DIR
from utils import extract_json_object, iter_jsonl, write_json, write_jsonl


AUDIT_DIR = V24_DIR / "audit"
DEFAULT_SELECTION = AUDIT_DIR / "memcalib_v241_direct_supervision_repair_554.jsonl"
DEFAULT_VALID_CANDIDATES = AUDIT_DIR / "memcalib_v241_repaired_candidates_687.jsonl"
DEFAULT_UNRESOLVED = AUDIT_DIR / "memcalib_v241_repaired_candidates_unresolved_98.jsonl"
DEFAULT_BASELINE = V24_DIR / "memcalib_v24_coding_complete_3750.jsonl"
DEFAULT_OUTPUT = AUDIT_DIR / "memcalib_v241_curated_residual_554.jsonl"

FENCED_BLOCK_RE = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)
INLINE_TICK_RE = re.compile(r"`([^`\n]+)`")
SPACE_RE = re.compile(r"\s+")

DEBUG_MARKERS = (
    " error",
    " exception",
    " fail",
    " bug",
    " crash",
    " incorrect",
    " wrong",
    " not work",
    " doesn't work",
    " does not work",
    " troubleshoot",
    " debug",
    " fix ",
)
BEHAVIOR_MARKERS = (
    "what happens",
    "what will happen",
    "expected behavior",
    "expected output",
    "what output",
    "what result",
    "return value",
    "evaluate to",
)
RECOMMENDATION_MARKERS = (
    "recommend",
    "best ",
    "good idea",
    "better ",
    "which tool",
    "which library",
    "which framework",
    "what tool",
    "what library",
    "what framework",
    "what are effective",
    "pros and cons",
    "trade-off",
    "tradeoff",
    "worth ",
)
CONCEPTUAL_PREFIXES = (
    "what is ",
    "what are ",
    "how does ",
    "how do ",
    "explain ",
    "describe ",
    "compare ",
    "why ",
)
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
QUERY_LEAK_REASONS = {
    "probable_query_atom_value_leakage",
    "probable_query_rubric_value_leakage",
}


def clean_inline_text(value: str) -> str:
    value = INLINE_TICK_RE.sub(r"\1", value)
    value = CODE_FENCE_RE.sub("", value)
    return SPACE_RE.sub(" ", value).strip()


def strip_code_blocks(value: str) -> str:
    return SPACE_RE.sub(" ", FENCED_BLOCK_RE.sub(" ", value)).strip()


def infer_response_family(original_question: str) -> str:
    lowered = f" {clean_inline_text(original_question).casefold()} "
    stripped = lowered.strip()
    if any(marker in lowered for marker in DEBUG_MARKERS):
        return "debugging_diagnosis"
    if any(marker in lowered for marker in BEHAVIOR_MARKERS):
        return "behavior_prediction"
    if any(marker in lowered for marker in RECOMMENDATION_MARKERS):
        return "recommendation_or_evaluation"
    if stripped.startswith(IMPLEMENTATION_PREFIXES):
        return "implementation_plan"
    if stripped.startswith(CONCEPTUAL_PREFIXES):
        return "conceptual_explanation"
    if stripped.startswith(("is ", "are ", "should ", "can ")):
        return "recommendation_or_evaluation"
    return "conceptual_explanation"


def response_form_question(original_question: str, family: str) -> str:
    original = clean_inline_text(original_question)
    if not original:
        raise ValueError("original question is empty")
    if family == "implementation_plan":
        lead = (
            "Instead of writing source code, describe a concrete implementation "
            "approach for the following original software-engineering request. "
            "Preserve its stated inputs, outputs, constraints, and failure behavior:"
        )
    elif family == "debugging_diagnosis":
        lead = (
            "Diagnose the following original software-engineering issue in prose. "
            "Explain the faulty assumption, corrected behavior, and relevant failure "
            "handling:"
        )
    elif family == "behavior_prediction":
        lead = (
            "Explain the expected behavior for the following original "
            "software-engineering question in prose, including the relevant inputs, "
            "decision points, outputs, and failure cases:"
        )
    elif family == "recommendation_or_evaluation":
        lead = (
            "Answer the following original software-engineering recommendation or "
            "evaluation question directly in prose. Give the recommendation, its "
            "reasoning, and material trade-offs:"
        )
    else:
        lead = (
            "Answer the following original software-engineering question directly "
            "in prose. Explain the relevant mechanism and conclusions:"
        )
    return (
        f"{lead}\n\n{original}\n\n"
        "Do not provide executable code, a patch, or a code block. The response "
        "must be understandable and scoreable from its text alone."
    )


def response_text(row: dict[str, Any]) -> str:
    for key in ("response", "output", "content", "text", "answer"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    raw = row.get("raw_response")
    if isinstance(raw, dict):
        choices = raw.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            message = choices[0].get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
    raise ValueError("candidate result has no output text")


def query_demotes_atom(
    atom: dict[str, Any],
    applicable: list[dict[str, Any]],
    question: str,
) -> bool:
    rubric = atom.get("usage_rubric")
    expected = (
        str(rubric.get("expected_answer_behavior") or "")
        if isinstance(rubric, dict)
        else ""
    )
    analysis = analyze_atom_alignment(atom, expected, applicable, question)
    predicate = str(atom.get("atomic_predicate") or atom.get("text") or "")
    exact_in_query = (
        len(norm_text(predicate)) >= 12
        and norm_text(predicate).casefold() in norm_text(question).casefold()
    )
    return bool(QUERY_LEAK_REASONS & set(analysis["reasons"])) or exact_in_query


def query_supplied_a_supervision(atom: dict[str, Any]) -> dict[str, Any]:
    predicate = clean_inline_text(
        str(atom.get("atomic_predicate") or atom.get("text") or "")
    )
    return {
        "label_reason": (
            "The current question independently supplies this proposition, so the "
            "retrieved atom adds no counterfactual influence to the ideal answer."
        ),
        "construction_target": {
            "task_goal": "Answer the current natural-language software task.",
            "memory_role": "No additional role beyond information already in the query.",
            "usage_boundary": (
                "The answer may discuss the proposition because the question supplies "
                "it, but must not attribute any extra detail to this memory atom."
            ),
            "failure_direction": (
                "Any answer change beyond what the question itself warrants is "
                "over-personalization."
            ),
        },
        "counterfactual_contract": {
            "without_memory_behavior": (
                "The answer uses the proposition already supplied by the question."
            ),
            "with_memory_behavior": (
                "The answer remains identical because the atom supplies no new value."
            ),
            "observable_delta": "none",
            "minimal_evidence": [],
        },
        "usage_rubric": {
            "expected_answer_behavior": (
                "The answer is counterfactually unchanged by this atom."
            ),
            "memory_usage_weight": "none",
            "validity_scope": "The full answer to the current question.",
            "correct_use": (
                "Do not add any atom-specific detail beyond the proposition already "
                "present in the question."
            ),
            "under_use": "A has no under-use error because the atom adds no value.",
            "over_use": (
                "The answer adds a detail, caveat, recommendation, or decision that "
                f"is justified only by this atom: {predicate}"
            ),
            "forbidden_memory_role": (
                "The atom must not alter the answer independently of the query."
            ),
            "failure_direction": (
                "Any counterfactual answer change caused only by this atom is OPB."
            ),
            "observable_checks": [
                "Removing this atom leaves the ideal answer unchanged.",
                (
                    "Any mention of the proposition is independently warranted by "
                    "the question rather than by this atom."
                ),
            ],
        },
    }


def ensure_sentence(text: str) -> str:
    value = clean_inline_text(text).rstrip()
    if not value:
        return ""
    return value if value.endswith((".", "!", "?")) else value + "."


def same_atom_supervision(
    atom: dict[str, Any],
    reference: str,
) -> tuple[dict[str, Any], str]:
    updated = copy.deepcopy(atom)
    label = str(updated.get("u_star") or "")
    action = str(updated.get("memory_action") or "")
    if label not in {"B", "C"}:
        return updated, reference

    predicate = ensure_sentence(
        str(updated.get("atomic_predicate") or updated.get("text") or "")
    )
    if not predicate:
        raise ValueError(f"empty scored atom text: {updated.get('atom_id')}")
    existing_contract = updated.get("counterfactual_contract")
    existing_evidence = (
        [
            ensure_sentence(str(item))
            for item in existing_contract.get("minimal_evidence") or []
            if ensure_sentence(str(item))
        ]
        if isinstance(existing_contract, dict)
        else []
    )
    if action == "correct" and existing_evidence:
        evidence = existing_evidence
    else:
        evidence = [predicate]

    normalized_reference = norm_text(reference).casefold()
    missing = [
        item
        for item in evidence
        if norm_text(item).casefold() not in normalized_reference
    ]
    if missing:
        transition = (
            "The memory-conditioned answer must also make the following "
            "user or project context explicit: "
        )
        reference = reference.rstrip() + "\n\n" + transition + " ".join(missing)

    role = "supporting" if label == "B" else "controlling"
    evidence_text = " ".join(evidence)
    if action == "correct":
        expected = (
            "The answer must explicitly reject or correct the atom's mistaken claim "
            f"and state the supported correction: {evidence_text}"
        )
        use_verb = "corrects"
    else:
        expected = (
            "The answer must explicitly state or operationalize this same-atom fact "
            f"without importing details from another memory: {predicate}"
        )
        use_verb = "uses"
    label_reason = clean_inline_text(str(updated.get("label_reason") or ""))
    if not label_reason:
        label_reason = (
            "This fact has bounded supporting influence on the answer."
            if label == "B"
            else "This fact controls a core answer decision or behavior."
        )

    updated["label_reason"] = label_reason
    updated["construction_target"] = {
        "task_goal": "Answer the current software-engineering question in prose.",
        "memory_role": f"{role.capitalize()} answer influence.",
        "usage_boundary": (
            f"The answer {use_verb} only the proposition supported by this atom."
        ),
        "failure_direction": (
            f"Under-use omits or contradicts: {evidence_text} Over-use imports "
            "unsupported atom-specific detail."
        ),
    }
    updated["counterfactual_contract"] = {
        "without_memory_behavior": (
            "The answer may omit or contradict this atom-specific information."
        ),
        "with_memory_behavior": expected,
        "observable_delta": evidence_text,
        "minimal_evidence": evidence,
    }
    updated["usage_rubric"] = {
        "expected_answer_behavior": expected,
        "memory_usage_weight": role,
        "validity_scope": "The complete natural-language answer.",
        "correct_use": expected,
        "under_use": f"The answer omits or contradicts: {evidence_text}",
        "over_use": (
            "The answer attributes a technology, provider, path, requirement, or "
            "conclusion to this atom that its own text does not support."
        ),
        "forbidden_memory_role": (
            "This atom cannot supply another atom's facts or unsupported external "
            "requirements."
        ),
        "failure_direction": (
            "Missing the same-atom evidence is under-use; unsupported expansion is "
            "over-use."
        ),
        "observable_checks": [
            *[
                f"The answer explicitly contains or unambiguously paraphrases: {item}"
                for item in evidence
            ],
            (
                "All details attributed to this atom are entailed by this atom's "
                "own text or correction contract."
            ),
        ],
    }
    updated["v241_curated_same_atom_supervision"] = {
        "schema_version": "memcalib-v241-curated-same-atom-supervision-v1",
        "atom_support_fingerprint": canonical_sha256(predicate),
        "minimal_evidence_fingerprint": canonical_sha256(evidence),
    }
    return updated, reference


def curate_record(
    source: dict[str, Any],
    candidate: dict[str, Any],
    channel: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    record = copy.deepcopy(candidate)
    family = infer_response_family(str(source.get("question") or ""))
    question = response_form_question(str(source.get("question") or ""), family)
    memories = copy.deepcopy(record.get("memories") or [])
    applicable = [atom for atom in memories if atom.get("u_star") in {"B", "C"}]
    demoted: list[dict[str, Any]] = []
    for atom in memories:
        if atom.get("u_star") not in {"B", "C"}:
            continue
        if not query_demotes_atom(atom, applicable, question):
            continue
        demoted.append(
            {
                "atom_id": atom.get("atom_id"),
                "old_u_star": atom.get("u_star"),
                "new_u_star": "A",
                "old_memory_action": atom.get("memory_action"),
                "new_memory_action": "ignore",
                "reason": (
                    "The current question independently supplies this proposition; "
                    "the memory adds no counterfactual answer value."
                ),
            }
        )
        atom["u_star"] = "A"
        atom["memory_action"] = "ignore"
        atom.update(query_supplied_a_supervision(atom))

    if not any(atom.get("u_star") in {"B", "C"} for atom in memories):
        raise ValueError(f"curation removed every scored atom: {record.get('id')}")

    reference = strip_code_blocks(str(record.get("source_answer") or ""))
    if len(norm_text(reference)) < 80:
        reference = strip_code_blocks(str(source.get("source_answer") or ""))
    if len(norm_text(reference)) < 80:
        raise ValueError(f"reference answer is too short: {record.get('id')}")
    rebuilt: list[dict[str, Any]] = []
    for atom in memories:
        updated, reference = same_atom_supervision(atom, reference)
        rebuilt.append(updated)
    if CODE_FENCE_RE.search(reference):
        raise ValueError(f"reference still contains a code fence: {record.get('id')}")

    record["schema_version"] = "crk-2-canonical-memory-v2.4.1"
    record["question"] = question
    record["source_answer"] = reference
    record["memories"] = rebuilt
    record["memory_blocks"] = copy.deepcopy(source.get("memory_blocks") or [])
    record.pop("v24_coding_independent_qc", None)
    record.pop("v241_alignment_consensus", None)
    prior_revision = copy.deepcopy(record.get("coding_text_observability_revision") or {})
    record["coding_text_observability_revision"] = {
        "schema_version": "memcalib-v241-curated-residual-v1",
        "task_family": family,
        "question_contract": "natural_language_only_no_code_blocks",
        "source_record_fingerprint": canonical_sha256(source),
        "candidate_record_fingerprint": canonical_sha256(candidate),
        "candidate_channel": channel,
        "labels_and_actions_rejudged": True,
        "query_supplied_atoms_demoted_to_a": len(demoted),
        "same_atom_supervision_rebuilt": True,
        "prior_revision": prior_revision,
    }
    audit = {
        "schema_version": "memcalib-v241-curated-residual-audit-v1",
        "record_id": record.get("id"),
        "candidate_channel": channel,
        "response_family": family,
        "source_record_fingerprint": canonical_sha256(source),
        "candidate_record_fingerprint": canonical_sha256(candidate),
        "output_record_fingerprint": canonical_sha256(record),
        "query_supplied_atom_demotions": demoted,
        "label_distribution": dict(
            sorted(Counter(str(atom.get("u_star") or "") for atom in rebuilt).items())
        ),
    }
    return record, audit


def rows_by_id(path: Path) -> dict[str, dict[str, Any]]:
    rows = list(iter_jsonl(path))
    ids = [str(row.get("id") or "") for row in rows]
    if "" in ids or len(ids) != len(set(ids)):
        raise ValueError(f"record IDs must be non-empty and unique: {path}")
    return dict(zip(ids, rows, strict=True))


def load_result_candidates(
    *,
    sources: dict[str, dict[str, Any]],
    selected_ids: set[str],
    requests_path: Path,
    results_path: Path,
    channel: str,
) -> dict[str, list[tuple[int, str, dict[str, Any], list[str]]]]:
    post = importlib.import_module("117_post_memcalib_v241_relabel_aware_repair")
    requests = list(iter_jsonl(requests_path))
    results = {
        str(row.get("request_id") or ""): row for row in iter_jsonl(results_path)
    }
    output: dict[str, list[tuple[int, str, dict[str, Any], list[str]]]] = {}
    for request in requests:
        params = post.request_params(request)
        record_id = str(params.get("record_id") or "")
        if record_id not in selected_ids:
            continue
        result = results.get(str(request.get("request_id") or ""))
        source = sources.get(record_id)
        if result is None or source is None:
            continue
        try:
            payload = extract_json_object(response_text(result))
            payload, repairs = post.normalize_model_payload(payload, source)
            errors, corrected, revision_audit = post.validate_custom_payload(
                payload, source, params
            )
            record, _ = post.build_record(
                corrected,
                payload,
                params,
                str(request.get("request_id") or ""),
                revision_audit,
                repairs,
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
        output.setdefault(record_id, []).append(
            (len(errors), channel, record, errors)
        )
    return output


def merge_candidate_sets(
    target_ids: set[str],
    valid_candidates: dict[str, dict[str, Any]],
    salvaged: dict[str, list[tuple[int, str, dict[str, Any], list[str]]]],
    baseline: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, str], dict[str, list[str]]]:
    selected: dict[str, dict[str, Any]] = {}
    channels: dict[str, str] = {}
    salvage_errors: dict[str, list[str]] = {}
    for record_id in target_ids:
        if record_id in valid_candidates:
            selected[record_id] = valid_candidates[record_id]
            channels[record_id] = "validated_relabel_aware_candidate"
            continue
        options = salvaged.get(record_id) or []
        if options:
            best = min(
                options,
                key=lambda item: (
                    item[0],
                    -len(norm_text(str(item[2].get("source_answer") or ""))),
                    item[1],
                ),
            )
            selected[record_id] = best[2]
            channels[record_id] = f"salvaged_{best[1]}"
            salvage_errors[record_id] = best[3]
            continue
        if record_id not in baseline:
            raise ValueError(f"record missing from every candidate source: {record_id}")
        selected[record_id] = baseline[record_id]
        channels[record_id] = "v24_baseline_fallback"
        salvage_errors[record_id] = ["no_buildable_relabel_candidate"]
    return selected, channels, salvage_errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Curate the final MemCalib v2.4.1 coding residual without broad "
            "generation: retain the best existing natural-language answer, repair "
            "response-family fidelity, demote query-supplied atoms, and rebuild "
            "same-atom supervision."
        )
    )
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--source-benchmark", type=Path, default=V23_RELEASE)
    parser.add_argument(
        "--valid-candidates", type=Path, default=DEFAULT_VALID_CANDIDATES
    )
    parser.add_argument("--unresolved", type=Path, default=DEFAULT_UNRESOLVED)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument(
        "--relabel-requests",
        type=Path,
        default=AUDIT_DIR / "memcalib_v241_relabel_aware_input_785.jsonl",
    )
    parser.add_argument(
        "--relabel-results",
        type=Path,
        default=AUDIT_DIR / "memcalib_v241_relabel_aware_result_785.jsonl",
    )
    parser.add_argument(
        "--aux-requests",
        type=Path,
        default=AUDIT_DIR / "memcalib_v241_reclassify_aux_a_input_562.jsonl",
    )
    parser.add_argument(
        "--aux-results",
        type=Path,
        default=AUDIT_DIR / "memcalib_v241_reclassify_aux_a_result_562.jsonl",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    selection_order = [
        str(row.get("id") or "") for row in iter_jsonl(args.selection)
    ]
    if "" in selection_order or len(selection_order) != len(set(selection_order)):
        raise ValueError("selection IDs must be non-empty and unique")
    target_ids = set(selection_order)
    unresolved_ids = {
        str(row.get("id") or "") for row in iter_jsonl(args.unresolved)
    }
    sources = {
        str(row.get("id") or ""): row
        for row in iter_jsonl(args.source_benchmark)
        if str(row.get("id") or "") in target_ids
    }
    if set(sources) != target_ids:
        raise ValueError("source benchmark does not cover the full selection")
    valid_candidates = {
        record_id: row
        for record_id, row in rows_by_id(args.valid_candidates).items()
        if record_id in target_ids
    }
    baseline = {
        record_id: row
        for record_id, row in rows_by_id(args.baseline).items()
        if record_id in target_ids
    }
    salvaged: dict[str, list[tuple[int, str, dict[str, Any], list[str]]]] = {}
    for channel, requests_path, results_path in (
        ("relabel_aware", args.relabel_requests, args.relabel_results),
        ("aux_reclassification", args.aux_requests, args.aux_results),
    ):
        current = load_result_candidates(
            sources=sources,
            selected_ids=unresolved_ids,
            requests_path=requests_path,
            results_path=results_path,
            channel=channel,
        )
        for record_id, options in current.items():
            salvaged.setdefault(record_id, []).extend(options)

    candidates, channels, salvage_errors = merge_candidate_sets(
        target_ids, valid_candidates, salvaged, baseline
    )
    records: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for record_id in selection_order:
        record, audit = curate_record(
            sources[record_id], candidates[record_id], channels[record_id]
        )
        if str(record.get("id") or "") != record_id:
            raise ValueError(f"record identity changed during curation: {record_id}")
        audit["salvaged_candidate_validation_errors"] = salvage_errors.get(
            record_id, []
        )
        records.append(record)
        audits.append(audit)

    audit_path = args.audit_output or args.output.with_suffix(".audit.jsonl")
    manifest_path = args.manifest or args.output.with_suffix(".manifest.json")
    write_jsonl(args.output, records)
    write_jsonl(audit_path, audits)
    manifest = {
        "schema_version": "memcalib-v241-curated-residual-manifest-v1",
        "inputs": {
            key: {
                "path": portable_path(path),
                "sha256": file_sha256(path),
            }
            for key, path in {
                "selection": args.selection,
                "source_benchmark": args.source_benchmark,
                "valid_candidates": args.valid_candidates,
                "unresolved": args.unresolved,
                "baseline": args.baseline,
                "relabel_requests": args.relabel_requests,
                "relabel_results": args.relabel_results,
                "aux_requests": args.aux_requests,
                "aux_results": args.aux_results,
            }.items()
        },
        "counts": {
            "records": len(records),
            "candidate_channels": dict(sorted(Counter(channels.values()).items())),
            "response_families": dict(
                sorted(Counter(row["response_family"] for row in audits).items())
            ),
            "query_supplied_atom_demotions": sum(
                len(row["query_supplied_atom_demotions"]) for row in audits
            ),
            "salvaged_candidates_with_prior_validation_errors": len(
                salvage_errors
            ),
            "labels": dict(
                sorted(
                    Counter(
                        str(atom.get("u_star") or "")
                        for record in records
                        for atom in record.get("memories") or []
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
