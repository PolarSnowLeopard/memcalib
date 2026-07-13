#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from utils import norm_text, stable_id, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "data" / "multidomain"
SCHEMA_VERSION = "memcalib-domain-source-v1"

GENERAL_TOPIC_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("writing_creative", re.compile(r"\b(write|rewrite|story|poem|essay|email|letter|tone|character|creative)\b", re.I)),
    ("planning_advice", re.compile(r"\b(plan|schedule|routine|goal|decision|advice|recommend|prepare|organize)\b", re.I)),
    ("learning_explanation", re.compile(r"\b(explain|learn|teach|understand|study|course|concept|example|summary)\b", re.I)),
    ("relationships_communication", re.compile(r"\b(friend|partner|family|colleague|manager|relationship|conversation|apolog)\w*\b", re.I)),
    ("travel_shopping_household", re.compile(r"\b(travel|trip|hotel|flight|buy|purchase|budget|cook|recipe|home|household)\b", re.I)),
    ("career_productivity", re.compile(r"\b(job|career|interview|resume|work|project|productivity|meeting|deadline)\b", re.I)),
)

CODING_TOPIC_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("debugging", re.compile(r"\b(error|bug|debug|traceback|exception|fail(?:s|ed|ing)?|incorrect|fix)\b", re.I)),
    ("testing_quality", re.compile(r"\b(test|pytest|unittest|assert|coverage|lint|static analysis|validation)\b", re.I)),
    ("api_library", re.compile(r"\b(api|endpoint|library|package|framework|sdk|dependency|module)\b", re.I)),
    ("data_algorithm", re.compile(r"\b(algorithm|array|list|tree|graph|sort|search|complexity|database|sql|data)\b", re.I)),
    ("systems_devops", re.compile(r"\b(docker|kubernetes|deploy|server|linux|shell|ci|cd|cloud|aws|process|thread)\b", re.I)),
    ("implementation", re.compile(r"\b(implement|function|class|method|program|code|script|refactor)\b", re.I)),
)

HEALTH_EXCLUSION_RE = re.compile(
    r"\b(symptom|diagnos|medicine|medication|disease|pain|pregnan|doctor|patient|treatment|blood pressure|fever)\w*\b",
    re.I,
)
CODING_EXCLUSION_RE = re.compile(
    r"```|\b(python|javascript|typescript|java|c\+\+|rust|golang|function|class|compile|runtime|api|debug|code)\b",
    re.I,
)


def clean_source_text(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = [line.rstrip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines))


def classify_topic(text: str, domain: str) -> str:
    patterns = GENERAL_TOPIC_PATTERNS if domain == "general" else CODING_TOPIC_PATTERNS
    for topic, pattern in patterns:
        if pattern.search(text or ""):
            return topic
    return "general_other" if domain == "general" else "coding_other"


def _source_record(
    *,
    source_id: str,
    domain: str,
    source_dataset: str,
    source_split: str,
    source_index: str | int,
    question: str,
    answer: str,
    context: str = "",
    source_license: str,
    source_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    question = clean_source_text(question)
    answer = clean_source_text(answer)
    context = clean_source_text(context)
    return {
        "id": source_id,
        "domain": domain,
        "source_dataset": source_dataset,
        "source_split": source_split,
        "source_index": source_index,
        "source_license": source_license,
        "raw_question": question,
        "source_context": context,
        "source_answer": answer,
        # Legacy alias retained for the locked medical pipeline utilities.
        "doctor_answer": answer,
        "topic": classify_topic(f"{context} {question} {answer}", domain),
        "source_metadata": source_metadata or {},
    }


def _ancestor_chain(message_id: str, by_id: dict[str, dict[str, Any]], max_depth: int = 12) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    seen: set[str] = set()
    current = by_id.get(message_id)
    while current and len(chain) < max_depth:
        current_id = str(current.get("message_id") or "")
        if not current_id or current_id in seen:
            break
        seen.add(current_id)
        chain.append(current)
        parent_id = current.get("parent_id")
        current = by_id.get(str(parent_id)) if parent_id else None
    chain.reverse()
    return chain


def normalize_oasst1(path: Path) -> Iterable[dict[str, Any]]:
    frame = pd.read_parquet(path)
    rows = frame.to_dict(orient="records")
    by_id = {str(row.get("message_id")): row for row in rows if row.get("message_id")}
    for assistant in rows:
        if assistant.get("role") != "assistant" or str(assistant.get("lang") or "") != "en":
            continue
        if assistant.get("deleted") is True or assistant.get("review_result") is False:
            continue
        parent = by_id.get(str(assistant.get("parent_id") or ""))
        if not parent or parent.get("role") != "prompter" or str(parent.get("lang") or "") != "en":
            continue
        if parent.get("deleted") is True or parent.get("review_result") is False:
            continue
        question = clean_source_text(str(parent.get("text") or ""))
        answer = clean_source_text(str(assistant.get("text") or ""))
        if not question or not answer:
            continue
        combined = f"{question} {answer}"
        if HEALTH_EXCLUSION_RE.search(combined) or CODING_EXCLUSION_RE.search(combined):
            continue
        chain = _ancestor_chain(str(parent.get("message_id")), by_id)
        prior = chain[:-1]
        context = "\n".join(
            f"{'User' if row.get('role') == 'prompter' else 'Assistant'}: {clean_source_text(str(row.get('text') or ''))}"
            for row in prior
            if clean_source_text(str(row.get("text") or ""))
        )
        message_id = str(assistant.get("message_id"))
        yield _source_record(
            source_id=stable_id("OpenAssistant/oasst1", message_id, question, prefix="raw_general"),
            domain="general",
            source_dataset="OpenAssistant/oasst1",
            source_split="train" if "train" in path.name else "validation",
            source_index=message_id,
            question=question,
            answer=answer,
            context=context,
            source_license="Apache-2.0",
            source_metadata={
                "message_id": message_id,
                "parent_message_id": str(parent.get("message_id") or ""),
                "message_tree_id": str(assistant.get("message_tree_id") or ""),
                "conversation_depth": len(chain),
            },
        )


def normalize_magicoder(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            question = clean_source_text(str(row.get("problem") or ""))
            answer = clean_source_text(str(row.get("solution") or ""))
            if not question or not answer:
                continue
            source_index = row.get("index", line_number - 1)
            language = norm_text(str(row.get("lang") or "unknown")).lower()
            yield _source_record(
                source_id=stable_id(
                    "ise-uiuc/Magicoder-OSS-Instruct-75K",
                    str(source_index),
                    question,
                    prefix="raw_coding",
                ),
                domain="coding",
                source_dataset="ise-uiuc/Magicoder-OSS-Instruct-75K",
                source_split="train",
                source_index=source_index,
                question=question,
                answer=answer,
                context="",
                source_license="MIT",
                source_metadata={
                    "language": language,
                    "raw_index": row.get("raw_index"),
                    "seed_sha_reference": stable_id(str(row.get("seed") or ""), prefix="seed"),
                },
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize General or Coding sources into the MemCalib source schema.")
    parser.add_argument("--source", choices=("oasst1", "magicoder"), required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--max-records", type=int, default=0)
    args = parser.parse_args()

    domain = "general" if args.source == "oasst1" else "coding"
    output = args.output or DEFAULT_OUTPUT_DIR / f"{domain}_normalized.jsonl"
    manifest = args.manifest or output.with_suffix(".manifest.json")
    iterator = normalize_oasst1(args.input) if args.source == "oasst1" else normalize_magicoder(args.input)
    rows: list[dict[str, Any]] = []
    for row in iterator:
        rows.append(row)
        if args.max_records > 0 and len(rows) >= args.max_records:
            break
    write_jsonl(output, rows)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "source": args.source,
        "domain": domain,
        "input": str(args.input),
        "output": str(output),
        "records": len(rows),
        "topics": dict(sorted(Counter(str(row.get("topic")) for row in rows).items())),
        "licenses": dict(sorted(Counter(str(row.get("source_license")) for row in rows).items())),
    }
    write_json(manifest, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
