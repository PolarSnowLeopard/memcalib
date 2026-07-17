#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import pyarrow.parquet as pq

from utils import norm_text, stable_id, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "data" / "multidomain"
SCHEMA_VERSION = "memcalib-domain-source-v1"
STACK_EXCHANGE_DATASET_REVISION = "c7bda74048748f55749cd663c3d8d1025a841fd9"

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


class _StackExchangeHTMLParser(HTMLParser):
    BLOCK_TAGS = {
        "blockquote",
        "br",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "ol",
        "p",
        "pre",
        "table",
        "tr",
        "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.pre_depth = 0
        self.inline_code_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag == "pre":
            self.parts.append("\n```\n")
            self.pre_depth += 1
        elif tag == "code" and self.pre_depth == 0:
            self.parts.append("`")
            self.inline_code_depth += 1
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "pre":
            self.pre_depth = max(0, self.pre_depth - 1)
            self.parts.append("\n```\n")
        elif tag == "code" and self.pre_depth == 0 and self.inline_code_depth > 0:
            self.parts.append("`")
            self.inline_code_depth -= 1
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def stack_exchange_html_to_text(value: str) -> str:
    parser = _StackExchangeHTMLParser()
    parser.feed(value or "")
    parser.close()
    text = html.unescape("".join(parser.parts)).replace("\xa0", " ")
    lines = []
    in_fence = False
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        line = raw_line.rstrip() if in_fence else re.sub(r"[ \t]+", " ", raw_line).strip()
        if line == "```":
            in_fence = not in_fence
        lines.append(line)
    return clean_source_text("\n".join(lines))


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


def normalize_oasst(path: Path, source_dataset: str) -> Iterable[dict[str, Any]]:
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
            source_id=stable_id(source_dataset, message_id, question, prefix="raw_general"),
            domain="general",
            source_dataset=source_dataset,
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


def normalize_oasst1(path: Path) -> Iterable[dict[str, Any]]:
    return normalize_oasst(path, "OpenAssistant/oasst1")


def normalize_oasst2(path: Path) -> Iterable[dict[str, Any]]:
    return normalize_oasst(path, "OpenAssistant/oasst2")


def _format_chat_context(messages: list[dict[str, Any]], max_chars: int = 6000) -> str:
    lines = []
    for message in messages:
        role = str(message.get("role") or "").lower()
        content = clean_source_text(str(message.get("content") or ""))
        if role not in {"user", "assistant"} or not content:
            continue
        lines.append(f"{'User' if role == 'user' else 'Assistant'}: {content}")
    context = "\n".join(lines)
    if len(context) <= max_chars:
        return context
    return context[-max_chars:].lstrip()


def normalize_ultrachat(path: Path) -> Iterable[dict[str, Any]]:
    parquet = pq.ParquetFile(path)
    row_number = 0
    for batch in parquet.iter_batches(columns=["prompt_id", "messages"], batch_size=1024):
        for row in batch.to_pylist():
            prompt_id = str(row.get("prompt_id") or row_number)
            messages = row.get("messages") or []
            for turn_index, assistant in enumerate(messages):
                if turn_index == 0 or str(assistant.get("role") or "").lower() != "assistant":
                    continue
                user = messages[turn_index - 1]
                if str(user.get("role") or "").lower() != "user":
                    continue
                question = clean_source_text(str(user.get("content") or ""))
                answer = clean_source_text(str(assistant.get("content") or ""))
                context = _format_chat_context(messages[: turn_index - 1])
                if not question or not answer:
                    continue
                combined = f"{context} {question} {answer}"
                if HEALTH_EXCLUSION_RE.search(combined) or CODING_EXCLUSION_RE.search(combined):
                    continue
                source_index = f"{prompt_id}:{turn_index}"
                yield _source_record(
                    source_id=stable_id(
                        "HuggingFaceH4/ultrachat_200k",
                        source_index,
                        question,
                        prefix="raw_general",
                    ),
                    domain="general",
                    source_dataset="HuggingFaceH4/ultrachat_200k",
                    source_split="train_sft",
                    source_index=source_index,
                    question=question,
                    answer=answer,
                    context=context,
                    source_license="MIT",
                    source_metadata={
                        "prompt_id": prompt_id,
                        "turn_index": turn_index,
                        "conversation_depth": turn_index + 1,
                        "synthetic_dialogue": True,
                    },
                )
            row_number += 1


def normalize_apps(path: Path) -> Iterable[dict[str, Any]]:
    parquet = pq.ParquetFile(path)
    columns = ["problem_id", "question", "solutions", "input_output", "difficulty", "url", "starter_code"]
    for batch in parquet.iter_batches(columns=columns, batch_size=512):
        for row in batch.to_pylist():
            question = clean_source_text(str(row.get("question") or ""))
            try:
                solutions = json.loads(str(row.get("solutions") or "[]"))
            except json.JSONDecodeError:
                solutions = []
            if not question or not isinstance(solutions, list) or not solutions:
                continue
            answer = clean_source_text(str(solutions[0] or ""))
            if not answer:
                continue
            starter_code = clean_source_text(str(row.get("starter_code") or ""))
            context = f"Starter code:\n{starter_code}" if starter_code else ""
            input_output = str(row.get("input_output") or "")
            has_function_name = bool(re.search(r'"fn_name"\s*:\s*"[^"\\]+"', input_output))
            raw_problem_id = row.get("problem_id")
            problem_id = "" if raw_problem_id is None else str(raw_problem_id)
            yield _source_record(
                source_id=stable_id("codeparrot/apps", problem_id, question, prefix="raw_coding"),
                domain="coding",
                source_dataset="codeparrot/apps",
                source_split="train",
                source_index=problem_id,
                question=question,
                answer=answer,
                context=context,
                source_license="MIT",
                source_metadata={
                    "problem_id": problem_id,
                    "difficulty": str(row.get("difficulty") or "unknown"),
                    "source_url": str(row.get("url") or ""),
                    "solution_count": len(solutions),
                    "has_function_name": has_function_name,
                    "has_starter_code": bool(starter_code),
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


def _best_stack_exchange_answer(answers: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [answer for answer in answers if str(answer.get("text") or "").strip()]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda answer: (
            bool(answer.get("selected")),
            int(answer.get("pm_score") or -1),
            -int(answer.get("answer_id") or 0),
        ),
    )


def normalize_stack_exchange(path: Path) -> Iterable[dict[str, Any]]:
    parquet = pq.ParquetFile(path)
    columns = ["qid", "question", "answers", "date", "metadata"]
    for batch in parquet.iter_batches(columns=columns, batch_size=512):
        for row in batch.to_pylist():
            qid = str(row.get("qid") or "")
            question = stack_exchange_html_to_text(str(row.get("question") or ""))
            answers = row.get("answers") or []
            chosen = _best_stack_exchange_answer(answers)
            if not qid or not question or chosen is None:
                continue
            answer = stack_exchange_html_to_text(str(chosen.get("text") or ""))
            if not answer:
                continue
            metadata = [str(value or "") for value in (row.get("metadata") or [])]
            question_url = metadata[0] if len(metadata) > 0 else f"https://stackoverflow.com/questions/{qid}"
            site_url = metadata[1] if len(metadata) > 1 else "https://stackoverflow.com"
            question_author_profile = metadata[2] if len(metadata) > 2 else ""
            question_author_name = ""
            answer_author = str(chosen.get("author") or "")
            answer_author_profile = str(chosen.get("author_profile") or "")
            attribution_complete = bool(
                question_author_name and question_author_profile and answer_author and answer_author_profile
            )
            yield _source_record(
                source_id=stable_id(
                    "HuggingFaceH4/stack-exchange-preferences",
                    qid,
                    question,
                    prefix="raw_coding",
                ),
                domain="coding",
                source_dataset="HuggingFaceH4/stack-exchange-preferences",
                source_split="data/Stackoverflow.com/train",
                source_index=qid,
                question=question,
                answer=answer,
                context="",
                source_license="CC-BY-SA-4.0",
                source_metadata={
                    "qid": qid,
                    "question_url": question_url,
                    "question_author_profile": question_author_profile,
                    "question_author_name": question_author_name,
                    "answer_id": str(chosen.get("answer_id") or ""),
                    "answer_author": answer_author,
                    "answer_author_id": str(chosen.get("author_id") or ""),
                    "answer_author_profile": answer_author_profile,
                    "answer_selected": bool(chosen.get("selected")),
                    "answer_pm_score": int(chosen.get("pm_score") or -1),
                    "answer_count": len(answers),
                    "question_date": str(row.get("date") or ""),
                    "site_url": site_url,
                    "dataset_revision": STACK_EXCHANGE_DATASET_REVISION,
                    "dataset_shard": path.name,
                    "attribution_complete": attribution_complete,
                    "attribution_note": "question author display name must be resolved before release",
                },
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize General or Coding sources into the MemCalib source schema.")
    parser.add_argument(
        "--source",
        choices=("oasst1", "oasst2", "ultrachat", "apps", "magicoder", "stack_exchange"),
        required=True,
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--max-records", type=int, default=0)
    args = parser.parse_args()

    domain = "general" if args.source in {"oasst1", "oasst2", "ultrachat"} else "coding"
    output = args.output or DEFAULT_OUTPUT_DIR / f"{domain}_normalized.jsonl"
    manifest = args.manifest or output.with_suffix(".manifest.json")
    normalizers = {
        "oasst1": normalize_oasst1,
        "oasst2": normalize_oasst2,
        "ultrachat": normalize_ultrachat,
        "apps": normalize_apps,
        "magicoder": normalize_magicoder,
        "stack_exchange": normalize_stack_exchange,
    }
    iterator = normalizers[args.source](args.input)
    record_count = 0
    topic_counts: Counter[str] = Counter()
    license_counts: Counter[str] = Counter()

    def counted_rows() -> Iterable[dict[str, Any]]:
        nonlocal record_count
        for row in iterator:
            record_count += 1
            topic_counts[str(row.get("topic"))] += 1
            license_counts[str(row.get("source_license"))] += 1
            yield row
            if args.max_records > 0 and record_count >= args.max_records:
                break

    write_jsonl(output, counted_rows())
    summary = {
        "schema_version": SCHEMA_VERSION,
        "source": args.source,
        "domain": domain,
        "input": str(args.input),
        "output": str(output),
        "records": record_count,
        "topics": dict(sorted(topic_counts.items())),
        "licenses": dict(sorted(license_counts.items())),
    }
    write_json(manifest, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
