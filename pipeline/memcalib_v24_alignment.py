from __future__ import annotations

import re
from typing import Any

from memcalib_v23_common import norm_text


TOKEN_RE = re.compile(r"\.?[A-Za-z0-9][A-Za-z0-9_.+/#:-]*")
CAMEL_OR_MARKED_RE = re.compile(
    r"(?:[a-z]+[A-Z][A-Za-z0-9]*|[A-Z]{2,}[A-Za-z0-9]*|"
    r"[A-Za-z]+[0-9][A-Za-z0-9.]*|[A-Za-z0-9_.-]+[/][A-Za-z0-9_./-]+)"
)
STOPWORDS = {
    "a",
    "all",
    "an",
    "and",
    "answer",
    "application",
    "applications",
    "as",
    "at",
    "be",
    "before",
    "behavior",
    "by",
    "can",
    "correct",
    "developer",
    "does",
    "for",
    "from",
    "has",
    "have",
    "how",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "must",
    "not",
    "of",
    "on",
    "or",
    "output",
    "plan",
    "project",
    "provide",
    "required",
    "requires",
    "script",
    "should",
    "specific",
    "states",
    "system",
    "task",
    "that",
    "the",
    "their",
    "this",
    "to",
    "use",
    "used",
    "user",
    "using",
    "when",
    "where",
    "which",
    "with",
    "without",
}


def tokens(text: str) -> set[str]:
    return {
        token.casefold().strip("._-/")
        for token in TOKEN_RE.findall(norm_text(text))
        if token.casefold().strip("._-/") not in STOPWORDS
        and len(token.casefold().strip("._-/")) >= 2
    }


def marked_tokens(text: str) -> set[str]:
    return {
        token.casefold().strip(".,;:()[]{}")
        for token in TOKEN_RE.findall(norm_text(text))
        if token.startswith(".")
        or token.lstrip(".").isdigit()
        or CAMEL_OR_MARKED_RE.fullmatch(token)
    }


def overlap(left: str, right: str) -> float:
    left_tokens = tokens(left)
    right_tokens = tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(right_tokens)


def atom_support_text(atom: dict[str, Any]) -> str:
    parts = [
        str(atom.get(key) or "")
        for key in ("text", "atomic_predicate", "evidence")
    ]
    if atom.get("memory_action") == "correct":
        parts.append(str(atom.get("label_reason") or ""))
        contract = atom.get("counterfactual_contract")
        if isinstance(contract, dict):
            parts.extend(
                str(contract.get(key) or "")
                for key in (
                    "without_memory_behavior",
                    "with_memory_behavior",
                    "observable_delta",
                )
            )
            evidence = contract.get("minimal_evidence")
            if isinstance(evidence, list):
                parts.extend(str(item) for item in evidence)
    return " ".join(parts)


def analyze_atom_alignment(
    atom: dict[str, Any],
    expected: str,
    applicable_atoms: list[dict[str, Any]],
    question: str,
) -> dict[str, Any]:
    support = atom_support_text(atom)
    own_overlap = overlap(support, expected)
    other_scores = [
        (
            str(other.get("atom_id") or ""),
            overlap(atom_support_text(other), expected),
        )
        for other in applicable_atoms
        if other is not atom
    ]
    best_other_id, best_other_overlap = (
        max(other_scores, key=lambda item: item[1])
        if other_scores
        else ("", 0.0)
    )
    unsupported_marked = sorted(marked_tokens(expected) - tokens(support))
    atom_question_overlap = overlap(question, support)
    rubric_question_overlap = overlap(question, expected)
    atom_marked = marked_tokens(support)
    rubric_marked = marked_tokens(expected)
    question_tokens = tokens(question)
    atom_values_present = not atom_marked or atom_marked <= question_tokens
    rubric_values_present = (
        not rubric_marked or rubric_marked <= question_tokens
    )
    reasons: list[str] = []
    if best_other_overlap >= 0.34 and best_other_overlap >= own_overlap + 0.20:
        reasons.append("probable_cross_atom_rubric_swap")
    if own_overlap < 0.15 and unsupported_marked:
        reasons.append("rubric_introduces_unsupported_identifier")
    if own_overlap < 0.10 and len(tokens(expected)) >= 3:
        reasons.append("very_low_atom_rubric_overlap")
    if (
        atom_question_overlap >= 0.72
        and len(tokens(support)) >= 3
        and atom_values_present
    ):
        reasons.append("probable_query_atom_value_leakage")
    if (
        rubric_question_overlap >= 0.82
        and len(tokens(expected)) >= 3
        and rubric_values_present
    ):
        reasons.append("probable_query_rubric_value_leakage")
    return {
        "reasons": reasons,
        "atom_rubric_overlap": round(own_overlap, 6),
        "best_other_atom_id": best_other_id or None,
        "best_other_atom_overlap": round(best_other_overlap, 6),
        "atom_question_overlap": round(atom_question_overlap, 6),
        "rubric_question_overlap": round(rubric_question_overlap, 6),
        "unsupported_marked_tokens": unsupported_marked,
    }
