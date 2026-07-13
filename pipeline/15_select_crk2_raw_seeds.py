#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import time
import zlib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable

from utils import iter_jsonl, load_json, resolve_config_path, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR / "config.json"
SCHEMA_VERSION = "crk2-raw-selection-v1"
SCORING_VERSION = "crk2-seed-quality-v1"
COMPLEXITY_ORDER = ("simple", "medium", "complex")

WORD_RE = re.compile(r"[a-z]+(?:'[a-z]+)?|\d+(?:\.\d+)?", re.I)
CODE_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|[^\s\w]")
SENTENCE_RE = re.compile(r"[.!?]+")
REPEATED_NOISE_RE = re.compile(r"(.)\1{5,}", re.I)
RELATION_RE = re.compile(
    r"\b(after|before|because|since|when|while|but|however|although|then|despite|unless|if)\b",
    re.I,
)
ANSWER_SUBSTANCE_RE = re.compile(
    r"\b(advise|recommend|should|need|because|suggest|likely|may|consider|review|evaluate|test|"
    r"discuss|monitor|diagnos|treat|avoid|continue|seek|consult|refer|implement|return|create|"
    r"explain|use|write|fix|validate|handle|configure)\w*\b",
    re.I,
)
QUESTION_INTENT_RE = re.compile(
    r"(?:^|[.!]\s+)(?:what|why|how|when|where|which|who|can|could|should|would|is|are|do|does|did|will)\b|"
    r"(?:^|[.!]\s+)(?:implement|write|create|build|fix|explain|design|provide|generate|refactor|debug|convert|complete|develop)\b|"
    r"\b(?:what should i|is it|do i|can i|could you|would you|any advice|need advice|want to know|"
    r"suggest (?:a )?remedy|please (?:advise|help|tell|suggest|recommend)|kindly (?:advise|help|tell)|"
    r"reason for|cause of)\b",
    re.I,
)

HEALTH_SIGNAL_PATTERNS: dict[str, re.Pattern[str]] = {
    "personal_entity": re.compile(
        r"\b(i|i'm|i've|i'd|me|my|mine|we|our|husband|wife|partner|son|daughter|mother|father|"
        r"sister|brother|child|baby|infant)\b",
        re.I,
    ),
    "temporal_history": re.compile(
        r"\b(ago|since|recently|previously|formerly|history of|used to|for the past|recurrent|"
        r"recurring|again|last (?:week|month|year)|\d+\s*(?:days?|weeks?|months?|years?)\b)",
        re.I,
    ),
    "condition_history": re.compile(
        r"\b(diagnosed|diagnosis|history of|suffer(?:ing|ed)? from|chronic|condition|disease|"
        r"disorder|syndrome|previous episode|past episode)\b",
        re.I,
    ),
    "treatment": re.compile(
        r"\b(take|takes|taking|taken|prescribed|prescription|medication|medicine|tablet|capsule|pill|"
        r"dose|dosage|surgery|therapy|treatment|insulin|metformin|antibiotic|injection|physiotherapy)\b",
        re.I,
    ),
    "measurement": re.compile(
        r"(?:\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|kg|mmol/l|mmol|mmhg|bpm|cm|mm|%|degrees?)\b)|"
        r"\b(test|result|scan|x-ray|mri|ct|ultrasound|blood pressure|glucose|hba1c|cholesterol|level)\b",
        re.I,
    ),
    "event_exposure": re.compile(
        r"\b(after|before|ate|eaten|eating|drank|drinking|travel(?:led|ed)?|injury|injured|fell|fall|"
        r"contact|exposed|exposure|accident|bitten|stung)\b",
        re.I,
    ),
    "preference_constraint": re.compile(
        r"\b(prefer|preference|avoid|cannot|can't|unable|don't want|do not want|allergic|allergy|"
        r"vegetarian|vegan|religious|cost|afford|available|concerned about)\b",
        re.I,
    ),
    "symptom_course": re.compile(
        r"\b(started|began|worsen(?:ed|ing|s)?|improv(?:ed|ing|es)?|persistent|persisting|constant|"
        r"intermittent|comes and goes|returned|resolved|relieved|risen|increased|decreased|progressive)\b",
        re.I,
    ),
}

GENERAL_SIGNAL_PATTERNS: dict[str, re.Pattern[str]] = {
    "personal_entity": HEALTH_SIGNAL_PATTERNS["personal_entity"],
    "temporal_history": HEALTH_SIGNAL_PATTERNS["temporal_history"],
    "preference_constraint": HEALTH_SIGNAL_PATTERNS["preference_constraint"],
    "goal_plan": re.compile(
        r"\b(my goal|i am planning|i'm planning|i plan to|i need to|i have to|i am trying|i'm trying|"
        r"working toward|deadline|upcoming|next week|next month)\b",
        re.I,
    ),
    "experience_history": re.compile(
        r"\b(i tried|i have tried|i've tried|previous attempt|in the past|my experience|i learned|"
        r"i have been|i've been|recently|last time|used to)\b",
        re.I,
    ),
    "resource_constraint": re.compile(
        r"\b(my budget|within budget|cannot afford|can't afford|limited time|only have|available to me|"
        r"my schedule|work schedule|live in|located in|access to|without access)\b",
        re.I,
    ),
    "relationship_context": re.compile(
        r"\b(my partner|my spouse|my friend|my family|my child|my manager|my colleague|my team|"
        r"our household|our relationship)\b",
        re.I,
    ),
}

CODING_SIGNAL_PATTERNS: dict[str, re.Pattern[str]] = {
    "project_environment": re.compile(
        r"\b(project|repository|repo|codebase|application|service|runtime|operating system|linux|windows|macos)\b",
        re.I,
    ),
    "language_version": re.compile(
        r"\b(python|javascript|typescript|java|c\+\+|c#|rust|go|ruby|php|swift|kotlin|node(?:\.js)?)"
        r"(?:\s*(?:version\s*)?\d+(?:\.\d+)*)?\b",
        re.I,
    ),
    "dependency_framework": re.compile(
        r"\b(library|package|dependency|framework|sdk|django|flask|fastapi|react|vue|angular|spring|"
        r"pandas|numpy|pytest|express)\b",
        re.I,
    ),
    "interface_contract": re.compile(
        r"\b(function signature|method signature|input|output|return type|schema|endpoint|api|interface|"
        r"class|method|function|parameter|argument)\b",
        re.I,
    ),
    "failure_history": re.compile(
        r"\b(error|exception|traceback|failing|failed|does not work|doesn't work|bug|incorrect|"
        r"previous attempt|tried|currently returns)\b",
        re.I,
    ),
    "implementation_constraint": re.compile(
        r"\b(must|must not|cannot|can't|without using|do not use|don't use|required|constraint|"
        r"time complexity|space complexity|thread-safe|backward compatible)\b",
        re.I,
    ),
    "style_preference": re.compile(
        r"\b(prefer|style|type hints|docstring|format|naming convention|functional style|object-oriented)\b",
        re.I,
    ),
    "deployment_context": re.compile(
        r"\b(docker|kubernetes|lambda|aws|azure|gcp|deployment|production|ci/cd|github actions|container)\b",
        re.I,
    ),
}

BOILERPLATE_PATTERNS = tuple(
    re.compile(pattern, re.I)
    for pattern in (
        r"hello(?: and welcome)?",
        r"thank you for (?:your|the) query",
        r"thanks for (?:your|the) query",
        r"hope (?:this|it) (?:helps|has helped you)",
        r"please (?:do not hesitate to )?contact (?:us|me) again",
        r"if you have (?:any |another )?(?:further )?(?:query|queries|questions?)",
        r"let me know if i can assist you further",
        r"thanks for choosing (?:our service|health care magic)",
        r"welcome to (?:ask a doctor|health care magic)(?: service)?",
        r"wishing you (?:an )?(?:early|speedy)? ?recovery",
        r"regards",
        r"take care",
    )
)


def words(text: str) -> list[str]:
    return WORD_RE.findall((text or "").lower())


def english_letter_ratio(text: str) -> float:
    letters = [char for char in (text or "") if char.isalpha()]
    if not letters:
        return 0.0
    return sum(char.isascii() for char in letters) / len(letters)


def boilerplate_ratio(text: str) -> tuple[float, int]:
    original_tokens = words(text)
    if not original_tokens:
        return 1.0, 0
    cleaned = text
    for pattern in BOILERPLATE_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    content_tokens = words(cleaned)
    ratio = 1.0 - len(content_tokens) / len(original_tokens)
    return max(0.0, min(1.0, ratio)), len(content_tokens)


def has_text_noise(text: str, *, punctuation_threshold: float = 0.18) -> bool:
    if REPEATED_NOISE_RE.search(text or ""):
        return True
    compact = re.sub(r"\s+", "", text or "")
    if not compact:
        return True
    punctuation = sum(not char.isalnum() for char in compact)
    return punctuation / len(compact) > punctuation_threshold


def answer_ngram_containment(question: str, answer: str, width: int = 10) -> float:
    question_tokens = CODE_TOKEN_RE.findall((question or "").casefold())
    answer_tokens = CODE_TOKEN_RE.findall((answer or "").casefold())
    if len(answer_tokens) < width:
        return 0.0
    question_ngrams = {
        tuple(question_tokens[index : index + width])
        for index in range(max(0, len(question_tokens) - width + 1))
    }
    answer_ngrams = {
        tuple(answer_tokens[index : index + width])
        for index in range(len(answer_tokens) - width + 1)
    }
    return len(question_ngrams & answer_ngrams) / len(answer_ngrams) if answer_ngrams else 0.0


def signal_patterns_for_domain(domain: str) -> dict[str, re.Pattern[str]]:
    if domain == "general":
        return GENERAL_SIGNAL_PATTERNS
    if domain == "coding":
        return CODING_SIGNAL_PATTERNS
    return HEALTH_SIGNAL_PATTERNS


def matched_signal_families(question: str, domain: str = "health_seed") -> list[str]:
    return [name for name, pattern in signal_patterns_for_domain(domain).items() if pattern.search(question or "")]


def has_question_intent(question: str) -> bool:
    return "?" in (question or "") or bool(QUESTION_INTENT_RE.search(question or ""))


def _score_question(question_tokens: int, sentence_count: int, relation_count: int) -> int:
    length_score = round(15 * min(question_tokens, 80) / 80)
    structure_score = 5 if sentence_count >= 2 else 0
    relation_score = 5 if relation_count >= 2 else 0
    return min(25, length_score + structure_score + relation_score)


def _score_answer(content_tokens: int, sentence_count: int, answer: str) -> int:
    if content_tokens >= 80:
        length_score = 20
    elif content_tokens >= 40:
        length_score = 15
    elif content_tokens >= 20:
        length_score = 10
    elif content_tokens >= 8:
        length_score = 5
    else:
        length_score = 0
    substance_score = 5 if ANSWER_SUBSTANCE_RE.search(answer or "") else 0
    structure_score = 5 if sentence_count >= 2 else 0
    return min(25, length_score + substance_score + structure_score)


def classify_seed_complexity(
    family_count: int,
    question_tokens: int,
    sentence_count: int,
    relation_count: int,
) -> tuple[str, int]:
    points = min(family_count, 6)
    points += int(question_tokens >= 50) + int(question_tokens >= 100)
    points += int(sentence_count >= 3) + int(relation_count >= 2)
    if points <= 3:
        return "simple", points
    if points <= 6:
        return "medium", points
    return "complex", points


def assess_record(row: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    question = str(row.get("raw_question") or "").strip()
    answer = str(row.get("source_answer") or row.get("doctor_answer") or "").strip()
    source_context = str(row.get("source_context") or "").strip()
    domain = str(row.get("domain") or "health_seed")
    question_tokens = words(question)
    answer_tokens = words(answer)
    question_sentences = max(1, len([part for part in SENTENCE_RE.split(question) if part.strip()]))
    answer_sentences = max(1, len([part for part in SENTENCE_RE.split(answer) if part.strip()]))
    relation_count = len(RELATION_RE.findall(question))
    signal_families = matched_signal_families(f"{source_context}\n{question}", domain)
    question_intent = has_question_intent(question)
    answer_boilerplate_ratio, answer_content_tokens = boilerplate_ratio(answer)
    question_english_ratio = english_letter_ratio(question)
    answer_english_ratio = english_letter_ratio(answer)
    punctuation_threshold = 0.45 if domain == "coding" else 0.18
    noisy = has_text_noise(question, punctuation_threshold=punctuation_threshold) or has_text_noise(
        answer,
        punctuation_threshold=punctuation_threshold,
    )
    reference_answer_containment = answer_ngram_containment(question, answer) if domain == "coding" else 0.0

    hard_reasons: list[str] = []
    for field in ("id", "source_dataset", "raw_question"):
        if not str(row.get(field) or "").strip():
            hard_reasons.append(f"missing_{field}")
    if not answer:
        hard_reasons.append("missing_source_answer")
    if len(question) < int(config["min_question_chars"]):
        hard_reasons.append("question_too_short")
    if len(question) > int(config["max_question_chars"]):
        hard_reasons.append("question_too_long")
    if len(answer) < int(config["min_answer_chars"]):
        hard_reasons.append("answer_too_short")
    if len(answer) > int(config["max_answer_chars"]):
        hard_reasons.append("answer_too_long")
    if len(question_tokens) < int(config["min_question_tokens"]):
        hard_reasons.append("question_too_few_tokens")
    if len(answer_tokens) < int(config["min_answer_tokens"]):
        hard_reasons.append("answer_too_few_tokens")
    min_english_ratio = float(config["min_english_letter_ratio"])
    if question_english_ratio < min_english_ratio:
        hard_reasons.append("question_language_mismatch")
    if answer_english_ratio < min_english_ratio:
        hard_reasons.append("answer_language_mismatch")
    if answer_boilerplate_ratio > float(config["max_boilerplate_ratio"]):
        hard_reasons.append("answer_boilerplate_dominated")
    if noisy:
        hard_reasons.append("text_noise")
    if not signal_families:
        hard_reasons.append("no_memory_signal")
    if not question_intent:
        hard_reasons.append("missing_question_intent")
    if domain == "coding" and reference_answer_containment >= 0.8:
        hard_reasons.append("reference_answer_in_question")

    question_score = _score_question(len(question_tokens), question_sentences, relation_count)
    answer_score = _score_answer(answer_content_tokens, answer_sentences, answer)
    family_count = len(signal_families)
    if family_count == 0:
        suitability_score = 0
    elif family_count == 1:
        suitability_score = 20
    elif family_count == 2:
        suitability_score = 30
    elif family_count == 3:
        suitability_score = 35
    else:
        suitability_score = 40
    cleanliness_score = 0
    if question_english_ratio >= 0.9 and answer_english_ratio >= 0.9:
        cleanliness_score += 4
    if answer_boilerplate_ratio <= 0.25:
        cleanliness_score += 3
    if not noisy:
        cleanliness_score += 3
    components = {
        "question_informativeness": question_score,
        "answer_substance": answer_score,
        "memory_suitability": suitability_score,
        "cleanliness_coherence": cleanliness_score,
    }
    quality_score = min(100, sum(components.values()))
    complexity, complexity_points = classify_seed_complexity(
        family_count, len(question_tokens), question_sentences, relation_count
    )
    hard_pass = not hard_reasons
    score_pass = quality_score >= int(config["min_quality_score"])
    eligible = hard_pass and score_pass
    result["raw_selection"] = {
        "schema_version": str(config.get("schema_version", SCHEMA_VERSION)),
        "scoring_version": str(config.get("scoring_version", SCORING_VERSION)),
        "hard_filter_pass": hard_pass,
        "hard_rejection_reasons": hard_reasons,
        "score_pass": score_pass,
        "eligible": eligible,
        "quality_score": quality_score,
        "quality_components": components,
        "memory_signal_families": signal_families,
        "seed_complexity": complexity,
        "seed_complexity_points": complexity_points,
        "features": {
            "question_chars": len(question),
            "answer_chars": len(answer),
            "question_tokens": len(question_tokens),
            "answer_tokens": len(answer_tokens),
            "answer_content_tokens": answer_content_tokens,
            "question_sentences": question_sentences,
            "answer_sentences": answer_sentences,
            "relation_count": relation_count,
            "question_intent": question_intent,
            "question_english_letter_ratio": round(question_english_ratio, 4),
            "answer_english_letter_ratio": round(answer_english_ratio, 4),
            "answer_boilerplate_ratio": round(answer_boilerplate_ratio, 4),
            "text_noise": noisy,
            "domain": domain,
            "source_context_chars": len(source_context),
            "reference_answer_ngram_containment": round(reference_answer_containment, 4),
        },
        "dedup_status": "not_evaluated" if eligible else "ineligible",
        "duplicate_cluster_id": None,
        "duplicate_of": None,
        "selection_status": "eligible" if eligible else ("rejected_hard_filter" if not hard_pass else "rejected_quality_score"),
    }
    return result


def canonical_question(text: str) -> str:
    return " ".join(words(text))


def _shingle_hashes(text: str, width: int = 5, signature_size: int = 10) -> tuple[int, ...]:
    tokens = words(text)
    if len(tokens) < width:
        return (zlib.crc32(" ".join(tokens).encode("utf-8")),) if tokens else ()
    hashes = {
        zlib.crc32(" ".join(tokens[index : index + width]).encode("utf-8"))
        for index in range(len(tokens) - width + 1)
    }
    return tuple(sorted(hashes)[:signature_size])


def _token_jaccard(first: str, second: str) -> float:
    first_tokens = set(words(first))
    second_tokens = set(words(second))
    if not first_tokens or not second_tokens:
        return 0.0
    return len(first_tokens & second_tokens) / len(first_tokens | second_tokens)


def mark_duplicate_records(
    records: list[dict[str, Any]],
    threshold: float,
    progress_every: int = 0,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    rows = [dict(row, raw_selection=dict(row.get("raw_selection") or {})) for row in records]
    eligible_indices = [index for index, row in enumerate(rows) if row["raw_selection"].get("eligible")]
    exact_groups: dict[str, list[int]] = defaultdict(list)
    canonical_cache: dict[int, str] = {}
    for index in eligible_indices:
        canonical = canonical_question(str(rows[index].get("raw_question") or ""))
        canonical_cache[index] = canonical
        exact_groups[canonical].append(index)

    def quality_key(index: int) -> tuple[int, str]:
        return (-int(rows[index]["raw_selection"].get("quality_score", 0)), str(rows[index].get("id", "")))

    exact_representatives = [min(members, key=quality_key) for members in exact_groups.values()]
    exact_representatives.sort(key=quality_key)
    signatures: dict[int, list[int]] = defaultdict(list)
    question_cache: dict[int, str] = {}
    token_count_cache: dict[int, int] = {}
    final_representative: dict[int, int] = {}
    total_representatives = len(exact_representatives)
    kept_representative_count = 0
    for position, index in enumerate(exact_representatives, start=1):
        question = str(rows[index].get("raw_question") or "")
        question_cache[index] = question
        token_count_cache[index] = len(words(question))
        signature = _shingle_hashes(question)
        candidate_counts: Counter[int] = Counter()
        for signature_hash in signature:
            candidate_counts.update(signatures[signature_hash])
        near_candidates: list[int] = []
        for candidate, shared_hashes in candidate_counts.items():
            if shared_hashes < 2:
                continue
            shorter = min(token_count_cache[index], token_count_cache[candidate])
            longer = max(token_count_cache[index], token_count_cache[candidate])
            if not longer or shorter / longer < threshold:
                continue
            if _token_jaccard(question, question_cache[candidate]) >= threshold:
                near_candidates.append(candidate)
        if near_candidates:
            final_representative[index] = min(near_candidates, key=quality_key)
        else:
            final_representative[index] = index
            kept_representative_count += 1
            for signature_hash in signature:
                signatures[signature_hash].append(index)
        if progress_callback and (position == total_representatives or (progress_every > 0 and position % progress_every == 0)):
            progress_callback(
                {
                    "stage": "deduplicate",
                    "done": position,
                    "total": total_representatives,
                    "kept_representatives": kept_representative_count,
                }
            )

    clusters: dict[int, list[int]] = defaultdict(list)
    for members in exact_groups.values():
        exact_representative = min(members, key=quality_key)
        clusters[final_representative[exact_representative]].extend(members)

    for representative, members in clusters.items():
        if len(members) == 1:
            rows[members[0]]["raw_selection"]["dedup_status"] = "unique"
            continue
        member_ids = sorted(str(rows[index].get("id", "")) for index in members)
        cluster_digest = hashlib.sha256("\n".join(member_ids).encode("utf-8")).hexdigest()[:16]
        cluster_id = f"dup_{cluster_digest}"
        representative_question = str(rows[representative].get("raw_question") or "")
        for index in members:
            selection = rows[index]["raw_selection"]
            selection["duplicate_cluster_id"] = cluster_id
            if index == representative:
                selection["dedup_status"] = "representative"
            else:
                selection["dedup_status"] = "duplicate"
                selection["duplicate_of"] = str(rows[representative].get("id", ""))
                selection["duplicate_match_type"] = (
                    "exact" if canonical_cache[index] == canonical_cache[representative] else "near"
                )
                selection["duplicate_similarity"] = round(
                    _token_jaccard(str(rows[index].get("raw_question") or ""), representative_question), 4
                )
                selection["eligible"] = False
                selection["selection_status"] = "rejected_duplicate"
    return rows


def _quality_sampling_values(
    row: dict[str, Any], seed: int, config: dict[str, Any]
) -> tuple[float, float]:
    score = int((row.get("raw_selection") or {}).get("quality_score", 0))
    minimum = int(config.get("min_quality_score", 55))
    beta = float(config.get("quality_weight_beta", 2.0))
    normalized = max(0.0, min(1.0, (score - minimum) / max(1, 100 - minimum)))
    weight = math.exp(beta * normalized)
    digest = hashlib.sha256(f"{seed}:{row.get('id', '')}".encode("utf-8")).digest()
    uniform = (int.from_bytes(digest[:8], "big") + 1) / (2**64 + 1)
    priority = -math.log(uniform) / weight
    return weight, priority


def _rank_rows(
    rows: Iterable[dict[str, Any]], seed: int, config: dict[str, Any]
) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            _quality_sampling_values(row, seed, config)[1],
            str(row.get("id", "")),
        ),
    )


def allocate_quotas(total: int, weights: dict[str, float], capacities: dict[str, int]) -> dict[str, int]:
    keys = sorted(key for key, capacity in capacities.items() if capacity > 0)
    quotas = {key: 0 for key in capacities}
    total = min(total, sum(capacities.values()))
    if total <= 0 or not keys:
        return quotas
    effective_weights = {key: max(0.0, float(weights.get(key, 0.0))) for key in keys}
    if sum(effective_weights.values()) <= 0:
        effective_weights = {key: 1.0 for key in keys}
    weight_sum = sum(effective_weights.values())
    raw = {key: total * effective_weights[key] / weight_sum for key in keys}
    for key in keys:
        quotas[key] = min(capacities[key], math.floor(raw[key]))
    remaining = total - sum(quotas.values())
    priority = sorted(keys, key=lambda key: (-(raw[key] - math.floor(raw[key])), key))
    while remaining > 0:
        progressed = False
        for key in priority:
            if quotas[key] < capacities[key] and remaining > 0:
                quotas[key] += 1
                remaining -= 1
                progressed = True
        if not progressed:
            break
    return quotas


def select_stratified(
    records: list[dict[str, Any]],
    target: int,
    seed: int,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    eligible = [
        dict(row, raw_selection=dict(row.get("raw_selection") or {}))
        for row in records
        if (row.get("raw_selection") or {}).get("eligible")
    ]
    if target <= 0 or not eligible:
        return []
    target = min(target, len(eligible))
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        by_source[str(row.get("source_dataset") or "unknown")].append(row)
    source_capacities = {source: len(rows) for source, rows in by_source.items()}
    source_quotas = allocate_quotas(target, {source: 1.0 for source in by_source}, source_capacities)

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    topic_alpha = float(config.get("topic_alpha", 0.5))
    complexity_targets = dict(config.get("complexity_targets") or {})

    def take(row: dict[str, Any], source: str, topic: str, complexity: str, phase: str) -> None:
        row_id = str(row.get("id", ""))
        if row_id in selected_ids:
            return
        selection = row["raw_selection"]
        weight, priority = _quality_sampling_values(row, seed, config)
        selection["selection_status"] = "selected"
        selection["quality_sampling_weight"] = round(weight, 6)
        selection["selection_priority"] = round(priority, 12)
        selection["selection_stratum"] = {
            "source_dataset": source,
            "topic": topic,
            "seed_complexity": complexity,
            "fill_phase": phase,
        }
        selected.append(row)
        selected_ids.add(row_id)

    for source in sorted(by_source):
        source_rows = by_source[source]
        source_target = source_quotas[source]
        by_topic: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in source_rows:
            by_topic[str(row.get("topic") or "general_other")].append(row)
        topic_capacities = {topic: len(rows) for topic, rows in by_topic.items()}
        topic_weights = {topic: capacity**topic_alpha for topic, capacity in topic_capacities.items()}
        topic_quotas = allocate_quotas(source_target, topic_weights, topic_capacities)

        for topic in sorted(by_topic):
            topic_rows = by_topic[topic]
            topic_target = topic_quotas[topic]
            by_complexity: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in topic_rows:
                complexity = str((row.get("raw_selection") or {}).get("seed_complexity") or "medium")
                by_complexity[complexity].append(row)
            complexity_capacities = {name: len(rows) for name, rows in by_complexity.items()}
            complexity_weights = {
                name: float(complexity_targets.get(name, 0.0)) for name in complexity_capacities
            }
            complexity_quotas = allocate_quotas(topic_target, complexity_weights, complexity_capacities)
            for complexity in sorted(by_complexity, key=lambda name: (COMPLEXITY_ORDER.index(name) if name in COMPLEXITY_ORDER else 99, name)):
                ranked = _rank_rows(by_complexity[complexity], seed, config)
                for row in ranked[: complexity_quotas[complexity]]:
                    take(row, source, topic, complexity, "stratum_quota")

        source_selected = sum(row["source_dataset"] == source for row in selected)
        if source_selected < source_target:
            remaining = [row for row in source_rows if str(row.get("id", "")) not in selected_ids]
            for row in _rank_rows(remaining, seed, config)[: source_target - source_selected]:
                selection = row.get("raw_selection") or {}
                take(
                    row,
                    source,
                    str(row.get("topic") or "general_other"),
                    str(selection.get("seed_complexity") or "medium"),
                    "source_fill",
                )

    if len(selected) < target:
        remaining = [row for row in eligible if str(row.get("id", "")) not in selected_ids]
        for row in _rank_rows(remaining, seed, config)[: target - len(selected)]:
            selection = row.get("raw_selection") or {}
            take(
                row,
                str(row.get("source_dataset") or "unknown"),
                str(row.get("topic") or "general_other"),
                str(selection.get("seed_complexity") or "medium"),
                "global_fill",
            )

    for rank, row in enumerate(selected, start=1):
        row["raw_selection"]["selection_rank"] = rank
    return selected


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _distribution(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, int]]:
    row_list = list(rows)
    return {
        "source_dataset": dict(sorted(Counter(str(row.get("source_dataset") or "unknown") for row in row_list).items())),
        "topic": dict(sorted(Counter(str(row.get("topic") or "general_other") for row in row_list).items())),
        "seed_complexity": dict(
            sorted(
                Counter(
                    str((row.get("raw_selection") or {}).get("seed_complexity") or "unknown")
                    for row in row_list
                ).items()
            )
        ),
    }


def _score_summary(rows: Iterable[dict[str, Any]]) -> dict[str, float | int | None]:
    scores = sorted(int((row.get("raw_selection") or {}).get("quality_score", 0)) for row in rows)
    if not scores:
        return {"min": None, "p25": None, "median": None, "p75": None, "max": None, "mean": None}

    def percentile(fraction: float) -> int:
        return scores[round((len(scores) - 1) * fraction)]

    return {
        "min": scores[0],
        "p25": percentile(0.25),
        "median": percentile(0.5),
        "p75": percentile(0.75),
        "max": scores[-1],
        "mean": round(sum(scores) / len(scores), 3),
    }


def _duplicate_summary(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    clusters: dict[str, dict[str, Any]] = {}
    match_types: Counter[str] = Counter()
    duplicate_records = 0
    for row in rows:
        selection = row.get("raw_selection") or {}
        cluster_id = selection.get("duplicate_cluster_id")
        if cluster_id:
            cluster = clusters.setdefault(str(cluster_id), {"size": 0, "sources": set()})
            cluster["size"] += 1
            cluster["sources"].add(str(row.get("source_dataset") or "unknown"))
        if selection.get("dedup_status") == "duplicate":
            duplicate_records += 1
            match_types[str(selection.get("duplicate_match_type") or "unknown")] += 1
    sizes = [int(cluster["size"]) for cluster in clusters.values()]
    return {
        "clusters": len(clusters),
        "records_marked_duplicate": duplicate_records,
        "cross_source_clusters": sum(len(cluster["sources"]) > 1 for cluster in clusters.values()),
        "max_cluster_size": max(sizes, default=0),
        "match_type_counts": dict(sorted(match_types.items())),
    }


def build_manifest(
    assessed_rows: list[dict[str, Any]],
    eligible_rows: list[dict[str, Any]],
    selected_rows: list[dict[str, Any]],
    input_path: Path,
    target: int,
    seed: int,
    config: dict[str, Any],
    config_path: Path | None = None,
) -> dict[str, Any]:
    hard_pass = [row for row in assessed_rows if (row.get("raw_selection") or {}).get("hard_filter_pass")]
    score_pass = [row for row in assessed_rows if (row.get("raw_selection") or {}).get("score_pass")]
    rejection_reasons: Counter[str] = Counter()
    dedup_status: Counter[str] = Counter()
    for row in assessed_rows:
        selection = row.get("raw_selection") or {}
        rejection_reasons.update(selection.get("hard_rejection_reasons") or [])
        if selection.get("hard_filter_pass") and not selection.get("score_pass"):
            rejection_reasons["quality_score_below_threshold"] += 1
        if selection.get("selection_status") == "rejected_duplicate":
            rejection_reasons["duplicate"] += 1
        dedup_status[str(selection.get("dedup_status") or "unknown")] += 1
    return {
        "schema_version": str(config.get("schema_version", SCHEMA_VERSION)),
        "scoring_version": str(config.get("scoring_version", SCORING_VERSION)),
        "input": {
            "path": str(input_path),
            "sha256": file_sha256(input_path),
            "rows": len(assessed_rows),
        },
        "implementation": {
            "selector_path": str(Path(__file__).resolve()),
            "selector_sha256": file_sha256(Path(__file__).resolve()),
            **(
                {"config_path": str(config_path), "config_sha256": file_sha256(config_path)}
                if config_path is not None
                else {}
            ),
        },
        "parameters": {
            "target": target,
            "seed": seed,
            **{key: value for key, value in config.items() if key not in {"schema_version", "scoring_version"}},
        },
        "selection_algorithm": {
            "source_allocation": "equal_with_capacity_aware_largest_remainder",
            "topic_allocation": "eligible_count_power_alpha",
            "complexity_allocation": "configured_proportions_with_capacity_aware_largest_remainder",
            "within_stratum": "seeded_exponential_quality_weighting",
            "near_duplicate_assignment": "greedy_best_representative_no_transitive_chain",
        },
        "counts": {
            "assessed": len(assessed_rows),
            "hard_filter_pass": len(hard_pass),
            "score_pass": len(score_pass),
            "eligible_after_dedup": len(eligible_rows),
            "selected": len(selected_rows),
        },
        "rejection_reasons": dict(sorted(rejection_reasons.items())),
        "dedup_status": dict(sorted(dedup_status.items())),
        "duplicates": _duplicate_summary(assessed_rows),
        "score_summary": {
            "assessed": _score_summary(assessed_rows),
            "eligible": _score_summary(eligible_rows),
            "selected": _score_summary(selected_rows),
        },
        "distributions": {
            "assessed": _distribution(assessed_rows),
            "eligible": _distribution(eligible_rows),
            "selected": _distribution(selected_rows),
        },
    }


def _merge_selected_status(assessed: list[dict[str, Any]], selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected_by_id = {str(row.get("id", "")): row["raw_selection"] for row in selected}
    merged = []
    for row in assessed:
        copy = dict(row, raw_selection=dict(row.get("raw_selection") or {}))
        selected_status = selected_by_id.get(str(row.get("id", "")))
        if selected_status:
            copy["raw_selection"].update(selected_status)
        merged.append(copy)
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Filter, score, deduplicate, and stratify CRK-2 raw source seeds.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--quality-audit", type=Path)
    parser.add_argument("--eligible-output", type=Path)
    parser.add_argument("--selected-output", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--target", type=int, default=100)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--progress-every", type=int, default=10000)
    args = parser.parse_args()

    cfg = load_json(args.config)
    selection_cfg = dict(cfg.get("raw_selection") or {})
    output_dir = resolve_config_path(args.config, str(cfg["output_dir"]))
    input_path = args.input or output_dir / "normalized_raw_full.jsonl"
    target = int(args.target)
    seed = int(args.seed if args.seed is not None else cfg.get("sampling", {}).get("seed", 42))
    quality_audit_path = args.quality_audit or output_dir / "crk2_raw_quality_audit.jsonl"
    eligible_path = args.eligible_output or output_dir / "crk2_raw_eligible_pool.jsonl"
    selected_path = args.selected_output or output_dir / f"crk2_selected_raw_seeds_{target}.jsonl"
    manifest_path = args.manifest or output_dir / f"crk2_raw_selection_{target}.manifest.json"

    started = time.monotonic()

    def emit_progress(event: dict[str, Any]) -> None:
        payload = dict(event)
        payload["elapsed_s"] = round(time.monotonic() - started, 1)
        print(json.dumps(payload, ensure_ascii=False), flush=True)

    assessed = []
    for index, row in enumerate(iter_jsonl(input_path), start=1):
        assessed.append(assess_record(row, selection_cfg))
        if args.progress_every > 0 and index % args.progress_every == 0:
            emit_progress({"stage": "assess", "done": index})
    emit_progress({"stage": "assess", "done": len(assessed), "status": "complete"})
    deduplicated = mark_duplicate_records(
        assessed,
        float(selection_cfg["near_duplicate_jaccard"]),
        progress_every=args.progress_every,
        progress_callback=emit_progress,
    )
    emit_progress({"stage": "deduplicate", "done": len(deduplicated), "status": "complete"})
    eligible = [row for row in deduplicated if (row.get("raw_selection") or {}).get("eligible")]
    selected = select_stratified(eligible, target, seed, selection_cfg)
    audit_rows = _merge_selected_status(deduplicated, selected)

    emit_progress({"stage": "write_outputs", "status": "started"})
    write_jsonl(quality_audit_path, audit_rows)
    write_jsonl(eligible_path, eligible)
    write_jsonl(selected_path, selected)
    manifest = build_manifest(
        audit_rows,
        eligible,
        selected,
        input_path,
        target,
        seed,
        selection_cfg,
        config_path=args.config,
    )
    manifest["outputs"] = {
        "quality_audit": {"path": str(quality_audit_path), "sha256": file_sha256(quality_audit_path)},
        "eligible_pool": {"path": str(eligible_path), "sha256": file_sha256(eligible_path)},
        "selected_seeds": {"path": str(selected_path), "sha256": file_sha256(selected_path)},
    }
    write_json(manifest_path, manifest)
    emit_progress({"stage": "write_outputs", "status": "complete"})
    print(
        json.dumps(
            {
                "input": str(input_path),
                "assessed": len(audit_rows),
                "eligible": len(eligible),
                "selected": len(selected),
                "selected_output": str(selected_path),
                "manifest": str(manifest_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
