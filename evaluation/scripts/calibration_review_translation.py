#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evaluation.common import iter_jsonl, write_json, write_jsonl
from evaluation.scripts.postprocess_judgments import extract_json_object


ROOT = Path(__file__).resolve().parents[2]
RELEASE_ROOT = ROOT / "evaluation" / "releases" / "memcalib-ordered-v2-500"
RUN_ROOT = ROOT / "evaluation" / "runs" / "memcalib-ordered-v2-500" / "calibration" / "translation"
DEFAULT_INPUT = RELEASE_ROOT / "calibration-human-review-30.jsonl"
DEFAULT_REQUESTS = RUN_ROOT / "requests.zh.jsonl"
DEFAULT_API_OUTPUT = RUN_ROOT / "api.zh.jsonl"
DEFAULT_TRANSLATIONS = RELEASE_ROOT / "calibration-human-review-30.translations-zh.jsonl"
DEFAULT_SUMMARY = RELEASE_ROOT / "calibration-human-review-30.translations-zh.summary.json"

SYSTEM_PROMPT = """You are a faithful English-to-Simplified-Chinese translator for an academic benchmark audit interface.
Translate every supplied field completely and exactly once. Preserve medical meaning, uncertainty, negation, causal direction,
numbers, units, identifiers, A/B/C labels, and Markdown structure. Do not summarize, interpret, correct, or add advice.
Return exactly one JSON object with this shape:
{"translations":[{"field_id":"the unchanged input field_id","zh":"complete Simplified Chinese translation"}]}
Do not return Markdown fences or any text outside the JSON object."""


def collect_translation_items(record: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []

    def add(field_id: str, value: Any) -> None:
        if isinstance(value, str) and value.strip():
            items.append({"field_id": field_id, "english": value})

    add("question", record.get("question"))
    for index, block in enumerate(record.get("memory_blocks") or []):
        add(f"memory_blocks.{index}.memory_text", block.get("memory_text"))
    add("model_response", record.get("model_response"))
    for index, atom in enumerate(record.get("atomic_memories") or []):
        add(f"atomic_memories.{index}.text", atom.get("text"))
        for key, value in (atom.get("usage_rubric") or {}).items():
            if isinstance(value, list):
                for item_index, item in enumerate(value):
                    add(f"atomic_memories.{index}.usage_rubric.{key}.{item_index}", item)
            else:
                add(f"atomic_memories.{index}.usage_rubric.{key}", value)
    for role in ("primary_judgment", "secondary_judgment"):
        judgment = record.get(role)
        if not isinstance(judgment, dict):
            continue
        for index, atom in enumerate(judgment.get("atom_judgments") or []):
            add(f"{role}.atom_judgments.{index}.evidence_quote", atom.get("evidence_quote"))
            add(f"{role}.atom_judgments.{index}.reason", atom.get("reason"))
    return items


def chunk_items(items: list[dict[str, str]], max_source_chars: int) -> list[list[dict[str, str]]]:
    chunks: list[list[dict[str, str]]] = []
    current: list[dict[str, str]] = []
    current_chars = 0
    for item in items:
        item_chars = len(item["english"])
        if current and current_chars + item_chars > max_source_chars:
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(item)
        current_chars += item_chars
    if current:
        chunks.append(current)
    return chunks


def prepare(input_path: Path, requests_path: Path, manifest_path: Path, max_source_chars: int) -> None:
    requests: list[dict[str, Any]] = []
    record_count = 0
    field_count = 0
    for record in iter_jsonl(input_path):
        record_count += 1
        answer_id = str(record["answer_request_id"])
        items = collect_translation_items(record)
        field_count += len(items)
        for chunk_index, chunk in enumerate(chunk_items(items, max_source_chars), start=1):
            request_id = f"translate:{answer_id}:{chunk_index:02d}"
            requests.append(
                {
                    "request_id": request_id,
                    "prompt": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": json.dumps({"items": chunk}, ensure_ascii=False, separators=(",", ":")),
                        },
                    ],
                    "user_defined_params": {
                        "answer_request_id": answer_id,
                        "chunk_index": chunk_index,
                        "field_ids": [item["field_id"] for item in chunk],
                    },
                }
            )
    write_jsonl(requests_path, requests)
    summary = {
        "schema_version": "memcalib-calibration-translation-request-v1",
        "input": str(input_path),
        "requests": len(requests),
        "records": record_count,
        "fields": field_count,
        "max_source_chars": max_source_chars,
    }
    write_json(manifest_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def finalize(input_path: Path, api_output: Path, output_path: Path, summary_path: Path) -> None:
    records = list(iter_jsonl(input_path))
    expected = {
        str(record["answer_request_id"]): {item["field_id"] for item in collect_translation_items(record)}
        for record in records
    }
    translations: dict[str, dict[str, str]] = {answer_id: {} for answer_id in expected}
    errors: list[str] = []
    api_rows = list(iter_jsonl(api_output))
    for row in api_rows:
        params = row.get("user_defined_params") or {}
        answer_id = str(params.get("answer_request_id") or "")
        requested_ids = {str(value) for value in params.get("field_ids") or []}
        if answer_id not in expected:
            errors.append(f"unknown_answer_id:{answer_id}")
            continue
        try:
            value = extract_json_object(str(row.get("response") or ""))
        except (ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid_json:{row.get('request_id')}:{exc}")
            continue
        translated = value.get("translations")
        if not isinstance(translated, list):
            errors.append(f"translations_not_list:{row.get('request_id')}")
            continue
        seen: set[str] = set()
        for item in translated:
            if not isinstance(item, dict):
                continue
            field_id = str(item.get("field_id") or "")
            zh = item.get("zh")
            if field_id in requested_ids and isinstance(zh, str) and zh.strip():
                translations[answer_id][field_id] = zh.strip()
                seen.add(field_id)
        for missing in sorted(requested_ids.difference(seen)):
            errors.append(f"missing_translation:{row.get('request_id')}:{missing}")

    output_rows = []
    missing_by_answer: dict[str, list[str]] = {}
    for record in records:
        answer_id = str(record["answer_request_id"])
        missing = sorted(expected[answer_id].difference(translations[answer_id]))
        if missing:
            missing_by_answer[answer_id] = missing
        output_rows.append({"answer_request_id": answer_id, "translations_zh": translations[answer_id]})

    summary = {
        "schema_version": "memcalib-calibration-translation-v1",
        "purpose": "display_only",
        "source_language": "en",
        "target_language": "zh-CN",
        "authoritative_language": "en",
        "translation_model": "qwen3.7-plus",
        "temperature": 0,
        "records": len(records),
        "api_rows": len(api_rows),
        "expected_fields": sum(len(values) for values in expected.values()),
        "translated_fields": sum(len(values) for values in translations.values()),
        "complete_records": len(records) - len(missing_by_answer),
        "incomplete_records": len(missing_by_answer),
        "errors": errors,
        "missing_by_answer": missing_by_answer,
    }
    if missing_by_answer or errors:
        write_json(summary_path, summary)
        raise SystemExit(json.dumps(summary, ensure_ascii=False, indent=2))
    write_jsonl(output_path, output_rows)
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare or finalize bilingual calibration-review translations.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    prepare_parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    prepare_parser.add_argument("--manifest", type=Path, default=RUN_ROOT / "requests.zh.manifest.json")
    prepare_parser.add_argument("--max-source-chars", type=int, default=7000)
    finalize_parser = subparsers.add_parser("finalize")
    finalize_parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    finalize_parser.add_argument("--api-output", type=Path, default=DEFAULT_API_OUTPUT)
    finalize_parser.add_argument("--output", type=Path, default=DEFAULT_TRANSLATIONS)
    finalize_parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.input, args.requests, args.manifest, args.max_source_chars)
    else:
        finalize(args.input, args.api_output, args.output, args.summary)


if __name__ == "__main__":
    main()
