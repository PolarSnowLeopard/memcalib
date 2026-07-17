#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from utils import iter_jsonl, norm_text, write_json


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_repair3.rejected.jsonl"
DEFAULT_OUTPUT = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_grounding_repair.jsonl"
DEFAULT_RESIDUAL = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_grounding_repair.residual.jsonl"
DEFAULT_AUDIT = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_grounding_repair.audit.jsonl"
DEFAULT_SUMMARY = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_grounding_repair.summary.json"
GROUNDING_ERROR_RE = re.compile(r"^(block|memory)_(\d+)_ungrounded_evidence$")
SENTENCE_RE = re.compile(r"\s*[^.!?\n]+(?:[.!?]+(?=\s|$)|$)")
TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "by", "for", "from", "has", "have",
    "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "user", "was", "were",
    "with", "you", "your",
}


def load_post_module():
    path = SCRIPT_DIR / "30_post_crk2_v2_generation.py"
    spec = importlib.util.spec_from_file_location("post_crk2_v2_generation", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load validator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


POST = load_post_module()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_grounding_only(errors: list[str]) -> bool:
    return bool(errors) and all(
        GROUNDING_ERROR_RE.match(error) or error == "qc_failed_evidence_grounding_pass" for error in errors
    )


def source_text(item: dict[str, Any], params: dict[str, Any]) -> str:
    source = str(item.get("source") or "")
    if source == "from_question":
        return str(params.get("raw_question") or "")
    if source == "from_context":
        return str(params.get("dialogue_context") or params.get("source_context") or "")
    return ""


def content_tokens(value: Any) -> set[str]:
    return {
        token.casefold()
        for token in TOKEN_RE.findall(str(value or ""))
        if token.casefold() not in STOPWORDS
    }


def candidate_spans(source: str, max_sentences: int = 3) -> list[str]:
    spans: list[tuple[int, int]] = []
    for match in SENTENCE_RE.finditer(source):
        start, end = match.span()
        while start < end and source[start].isspace():
            start += 1
        while end > start and source[end - 1].isspace():
            end -= 1
        if start < end:
            spans.append((start, end))
    if not spans and source.strip():
        start = len(source) - len(source.lstrip())
        end = len(source.rstrip())
        spans.append((start, end))

    result: list[str] = []
    seen: set[str] = set()
    for left in range(len(spans)):
        for width in range(1, max_sentences + 1):
            right = left + width - 1
            if right >= len(spans):
                break
            candidate = source[spans[left][0] : spans[right][1]].strip()
            normalized = norm_text(candidate).casefold()
            if candidate and normalized not in seen:
                seen.add(normalized)
                result.append(candidate)
    return result


def span_score(candidate: str, target: str) -> float:
    candidate_norm = norm_text(candidate).casefold()
    target_norm = norm_text(target).casefold()
    if not candidate_norm or not target_norm:
        return 0.0
    candidate_tokens = content_tokens(candidate_norm)
    target_tokens = content_tokens(target_norm)
    overlap = len(candidate_tokens & target_tokens)
    precision = overlap / len(candidate_tokens) if candidate_tokens else 0.0
    recall = overlap / len(target_tokens) if target_tokens else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    sequence = SequenceMatcher(None, candidate_norm, target_norm, autojunk=False).ratio()
    return round(0.45 * f1 + 0.35 * recall + 0.20 * sequence, 6)


def choose_grounded_span(source: str, target: str, min_score: float) -> tuple[str, float] | None:
    scored = [(span_score(candidate, target), candidate) for candidate in candidate_spans(source)]
    if not scored:
        return None
    score, candidate = max(scored, key=lambda item: (item[0], -len(item[1]), item[1]))
    if score < min_score:
        return None
    return candidate, score


def repair_record(
    rejected: dict[str, Any], min_score: float
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    errors = [str(error) for error in rejected.get("errors") or []]
    if not is_grounding_only(errors):
        return {}, [], ["not_grounding_only"]
    params = rejected.get("user_defined_params") or {}
    record = copy.deepcopy(rejected.get("parsed_record") or {})
    actions: list[dict[str, Any]] = []
    failures: list[str] = []

    question = str(params.get("raw_question") or "")
    context = str(params.get("dialogue_context") or params.get("source_context") or "")
    for collection_name in ("memory_blocks", "memories"):
        collection = record.get(collection_name)
        if not isinstance(collection, list):
            continue
        for index, item in enumerate(collection):
            if not isinstance(item, dict):
                continue
            current_source = str(item.get("source") or "")
            replacement_source = ""
            if current_source == "from_context" and not norm_text(context) and norm_text(question):
                replacement_source = "from_question"
            elif current_source == "from_question" and not norm_text(question) and norm_text(context):
                replacement_source = "from_context"
            if replacement_source:
                item["source"] = replacement_source
                actions.append(
                    {
                        "path": f"{collection_name}[{index}].source",
                        "source": current_source,
                        "original": current_source,
                        "replacement": replacement_source,
                        "score": 1.0,
                        "reason": "declared_source_empty",
                    }
                )

    for error in errors:
        match = GROUNDING_ERROR_RE.match(error)
        if not match:
            continue
        kind, index_text = match.groups()
        index = int(index_text)
        collection_name = "memory_blocks" if kind == "block" else "memories"
        evidence_key = "raw_evidence" if kind == "block" else "evidence"
        collection = record.get(collection_name)
        if not isinstance(collection, list) or index >= len(collection) or not isinstance(collection[index], dict):
            failures.append(f"{error}:missing_target")
            continue
        item = collection[index]
        source = source_text(item, params)
        target_parts = [item.get(evidence_key)]
        if kind == "block":
            target_parts.append(item.get("memory_text"))
        else:
            target_parts.extend((item.get("atomic_predicate"), item.get("text")))
        target = " ".join(norm_text(str(part or "")) for part in target_parts if part)
        selected = choose_grounded_span(source, target, min_score)
        if selected is None:
            failures.append(f"{error}:no_confident_span")
            continue
        replacement, score = selected
        original = str(item.get(evidence_key) or "")
        item[evidence_key] = replacement
        actions.append(
            {
                "path": f"{collection_name}[{index}].{evidence_key}",
                "source": item.get("source"),
                "original": original,
                "replacement": replacement,
                "score": score,
            }
        )

    qc = record.get("qc")
    if isinstance(qc, dict) and not failures:
        qc["evidence_grounding_pass"] = True
    return record, actions, failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministically repair grounding-only CRK-2 v2 rejects.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--residual", type=Path, default=DEFAULT_RESIDUAL)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--min-score", type=float, default=0.25)
    args = parser.parse_args()
    if not 0 <= args.min_score <= 1:
        raise ValueError("min-score must be between 0 and 1")

    accepted_count = 0
    residual_count = 0
    input_count = 0
    domains: Counter[str] = Counter()
    for path in (args.output, args.residual, args.audit):
        path.parent.mkdir(parents=True, exist_ok=True)
    with (
        args.output.open("w", encoding="utf-8") as accepted_handle,
        args.residual.open("w", encoding="utf-8") as residual_handle,
        args.audit.open("w", encoding="utf-8") as audit_handle,
    ):
        for row in iter_jsonl(args.input):
            input_count += 1
            request_id = str(row.get("request_id") or "")
            params = row.get("user_defined_params") or {}
            record, actions, repair_failures = repair_record(row, args.min_score)
            post_errors: list[str] = []
            overlap_audit: list[dict[str, Any]] = []
            if record and not repair_failures:
                post_errors, overlap_audit = POST.validate_record(record, params)
            if record and not repair_failures and not post_errors:
                normalized = POST.normalize_record(record, params, request_id, overlap_audit)
                normalized["deterministic_qc"]["evidence_grounding_repair"] = {
                    "schema_version": "crk2-evidence-grounding-repair-v1",
                    "strategy": "closest_contiguous_source_span",
                    "min_score": args.min_score,
                    "replacement_count": len(actions),
                }
                accepted_handle.write(json.dumps(normalized, ensure_ascii=False) + "\n")
                accepted_count += 1
                domains[str(normalized.get("domain") or "")] += 1
                decision = "pass"
            else:
                residual_handle.write(
                    json.dumps(
                        {
                            **row,
                            "grounding_repair": {
                                "repair_failures": repair_failures,
                                "post_repair_errors": post_errors,
                                "actions": actions,
                            },
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                residual_count += 1
                decision = "residual"
            audit_handle.write(
                json.dumps(
                    {
                        "request_id": request_id,
                        "domain": params.get("domain"),
                        "decision": decision,
                        "original_errors": row.get("errors") or [],
                        "repair_failures": repair_failures,
                        "post_repair_errors": post_errors,
                        "actions": actions,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    summary = {
        "schema_version": "crk2-evidence-grounding-repair-summary-v1",
        "input": {"path": str(args.input), "sha256": file_sha256(args.input), "records": input_count},
        "settings": {"min_score": args.min_score, "strategy": "closest_contiguous_source_span"},
        "counts": {
            "deterministic_pass": accepted_count,
            "residual": residual_count,
            "domains": dict(sorted(domains.items())),
        },
        "outputs": {
            "accepted": {"path": str(args.output), "sha256": file_sha256(args.output)},
            "residual": {"path": str(args.residual), "sha256": file_sha256(args.residual)},
            "audit": {"path": str(args.audit), "sha256": file_sha256(args.audit)},
        },
    }
    write_json(args.summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
