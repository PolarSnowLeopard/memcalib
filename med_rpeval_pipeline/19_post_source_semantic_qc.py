#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

from utils import extract_json_object, norm_text, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
SCHEMA_VERSION = "crk2-source-semantic-qc-v1"
DIMENSION_NAMES = (
    "question_completeness",
    "answer_relevance",
    "answer_substantiveness",
    "memory_extractability",
    "text_integrity",
    "safety_plausibility",
)
LABELS = {"pass", "reject", "uncertain"}
VERDICTS = {"pass", "review", "reject"}
CONFIDENCE_LEVELS = {"high", "medium", "low"}
REJECT_REASONS = {
    "incomplete_question",
    "answer_irrelevant",
    "answer_non_substantive",
    "no_extractable_memory",
    "corrupted_text",
    "medical_safety_concern",
}
QUESTION_EVIDENCE_DIMENSIONS = {"question_completeness", "memory_extractability"}
ANSWER_EVIDENCE_DIMENSIONS = {"answer_relevance", "answer_substantiveness", "safety_plausibility"}
ELLIPSIS_RE = re.compile(r"(?:\.{3,}|…+)")
LITERAL_UNICODE_ESCAPE_RE = re.compile(r"\\u([0-9a-fA-F]{4})")
GROUNDING_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00a0": " ",
    }
)


def get_params(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("user_defined_params") or row.get("passParams") or row.get("params") or {}


def get_text(row: dict[str, Any]) -> str:
    for key in ("response", "output", "content", "text", "answer"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    choices = row.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first, dict) else None
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
    result = row.get("result")
    if isinstance(result, dict):
        return get_text(result)
    if isinstance(result, str) and result.strip():
        return result
    raise ValueError("No model output text found")


def normalize_grounding_text(text: str) -> str:
    text = LITERAL_UNICODE_ESCAPE_RE.sub(lambda match: chr(int(match.group(1), 16)), text or "")
    text = text.replace('\\"', '"').replace("\\'", "'")
    text = unicodedata.normalize("NFKC", text).translate(GROUNDING_TRANSLATION)
    return norm_text(text).lower()


def grounded(evidence: str, source: str) -> bool:
    evidence_norm = normalize_grounding_text(evidence)
    source_norm = normalize_grounding_text(source)
    if not evidence_norm or not source_norm:
        return False
    if evidence_norm in source_norm:
        return True

    fragments = [fragment.strip(" \t\r\n\"'") for fragment in ELLIPSIS_RE.split(evidence_norm)]
    if len(fragments) < 2 or any(len(re.sub(r"\W", "", fragment)) < 8 for fragment in fragments):
        return False

    cursor = 0
    for fragment in fragments:
        position = source_norm.find(fragment, cursor)
        if position < 0:
            return False
        cursor = position + len(fragment)
    return True


def classify_judgment(judgment: dict[str, Any]) -> str:
    dimensions = judgment.get("dimensions") or {}
    labels = [str((dimensions.get(name) or {}).get("label") or "") for name in DIMENSION_NAMES]
    if "reject" in labels or judgment.get("overall_verdict") == "reject":
        return "reject"
    if "uncertain" in labels or judgment.get("overall_verdict") == "review":
        return "review"
    if labels and all(label == "pass" for label in labels) and judgment.get("overall_verdict") == "pass":
        return "strict_pass"
    return "invalid"


def validate_judgment(judgment: dict[str, Any], params: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if judgment.get("schema_version") != SCHEMA_VERSION:
        errors.append("bad_schema_version")
    dimensions = judgment.get("dimensions")
    if not isinstance(dimensions, dict):
        return errors + ["dimensions_not_object"]
    if set(dimensions) != set(DIMENSION_NAMES):
        errors.append("dimension_set_mismatch")
    question = str(params.get("raw_question") or "")
    answer = str(params.get("doctor_answer") or "")
    for name in DIMENSION_NAMES:
        item = dimensions.get(name)
        if not isinstance(item, dict):
            errors.append(f"missing_dimension_{name}")
            continue
        label = item.get("label")
        evidence = str(item.get("evidence") or "")
        reason = norm_text(str(item.get("reason") or ""))
        if label not in LABELS:
            errors.append(f"bad_label_{name}")
        if len(reason) < 8:
            errors.append(f"missing_reason_{name}")
        if name in QUESTION_EVIDENCE_DIMENSIONS and not grounded(evidence, question):
            errors.append(f"ungrounded_evidence_{name}")
        elif name in ANSWER_EVIDENCE_DIMENSIONS and not grounded(evidence, answer):
            errors.append(f"ungrounded_evidence_{name}")
        elif name == "text_integrity" and not (grounded(evidence, question) or grounded(evidence, answer)):
            errors.append(f"ungrounded_evidence_{name}")

    verdict = judgment.get("overall_verdict")
    if verdict not in VERDICTS:
        errors.append("bad_overall_verdict")
    confidence = judgment.get("confidence")
    if confidence not in CONFIDENCE_LEVELS:
        errors.append("bad_confidence")
    reasons = judgment.get("reject_reasons")
    if not isinstance(reasons, list):
        errors.append("reject_reasons_not_list")
        reasons = []
    elif any(reason not in REJECT_REASONS for reason in reasons):
        errors.append("bad_reject_reason")
    if len(norm_text(str(judgment.get("summary") or ""))) < 8:
        errors.append("missing_summary")

    labels = [str((dimensions.get(name) or {}).get("label") or "") for name in DIMENSION_NAMES]
    expected_verdict = "reject" if "reject" in labels else "review" if "uncertain" in labels else "pass"
    if verdict in VERDICTS and verdict != expected_verdict:
        errors.append("verdict_dimension_inconsistent")
    if expected_verdict == "reject" and not reasons:
        errors.append("missing_reject_reason")
    if expected_verdict != "reject" and reasons:
        errors.append("unexpected_reject_reason")
    return errors


def wilson_lower_bound(successes: int, total: int, z: float = 1.959963984540054) -> float:
    if total <= 0:
        return 0.0
    successes = max(0, min(successes, total))
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = proportion + z * z / (2 * total)
    margin = z * math.sqrt((proportion * (1 - proportion) + z * z / (4 * total)) / total)
    return max(0.0, (centre - margin) / denominator)


def compute_admission_target(final_target: int, generation_successes: int, generation_total: int) -> int:
    lower = wilson_lower_bound(generation_successes, generation_total)
    if final_target <= 0:
        raise ValueError("final_target must be positive")
    if lower <= 0:
        raise ValueError("generation pilot does not provide a positive lower pass-rate bound")
    return math.ceil(final_target / lower)


def normalize_record(params: dict[str, Any], judgment: dict[str, Any], state: str) -> dict[str, Any]:
    record = dict(params)
    record["semantic_qc"] = {
        "schema_version": SCHEMA_VERSION,
        "state": state,
        "judgment": judgment,
        "validation_errors": [],
    }
    return record


def build_summary(records: list[dict[str, Any]], invalid_count: int) -> dict[str, Any]:
    states = Counter(str((record.get("semantic_qc") or {}).get("state") or "invalid") for record in records)
    dimension_counts: dict[str, Counter[str]] = {name: Counter() for name in DIMENSION_NAMES}
    reject_reasons: Counter[str] = Counter()
    confidence: Counter[str] = Counter()
    for record in records:
        judgment = (record.get("semantic_qc") or {}).get("judgment") or {}
        dimensions = judgment.get("dimensions") or {}
        for name in DIMENSION_NAMES:
            dimension_counts[name][str((dimensions.get(name) or {}).get("label") or "missing")] += 1
        reject_reasons.update(judgment.get("reject_reasons") or [])
        confidence[str(judgment.get("confidence") or "missing")] += 1
    total = len(records) + invalid_count
    strict_passes = states.get("strict_pass", 0)

    def states_by(key_fn) -> dict[str, dict[str, int]]:
        grouped: dict[str, Counter[str]] = {}
        for record in records:
            key = str(key_fn(record) or "unknown")
            grouped.setdefault(key, Counter())[str((record.get("semantic_qc") or {}).get("state") or "invalid")] += 1
        return {key: dict(sorted(counts.items())) for key, counts in sorted(grouped.items())}

    return {
        "schema_version": SCHEMA_VERSION,
        "total": total,
        "valid": len(records),
        "invalid": invalid_count,
        "strict_pass": strict_passes,
        "review": states.get("review", 0),
        "reject": states.get("reject", 0),
        "strict_pass_rate": round(strict_passes / total, 6) if total else 0.0,
        "strict_pass_wilson_lower_95": round(wilson_lower_bound(strict_passes, total), 6) if total else 0.0,
        "dimension_counts": {name: dict(sorted(counts.items())) for name, counts in dimension_counts.items()},
        "reject_reasons": dict(sorted(reject_reasons.items())),
        "confidence": dict(sorted(confidence.items())),
        "state_by_source": states_by(lambda record: record.get("source_dataset")),
        "state_by_topic": states_by(lambda record: record.get("topic")),
        "state_by_seed_complexity": states_by(
            lambda record: (record.get("raw_selection") or {}).get("seed_complexity")
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and classify source-QA semantic QC results.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--strict-pass", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--rejected", type=Path, required=True)
    parser.add_argument("--invalid", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    records: list[dict[str, Any]] = []
    invalid_rows: list[dict[str, Any]] = []
    with args.input.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            params = get_params(row)
            try:
                judgment = extract_json_object(get_text(row))
                errors = validate_judgment(judgment, params)
                state = classify_judgment(judgment)
                if errors or state == "invalid":
                    invalid_rows.append({"line": index, "errors": errors or ["invalid_state"], "source": row})
                    continue
                records.append(normalize_record(params, judgment, state))
            except Exception as exc:
                invalid_rows.append({"line": index, "errors": [f"parse_error:{exc}"], "source": row})

    strict_rows = [record for record in records if record["semantic_qc"]["state"] == "strict_pass"]
    review_rows = [record for record in records if record["semantic_qc"]["state"] == "review"]
    rejected_rows = [record for record in records if record["semantic_qc"]["state"] == "reject"]
    write_jsonl(args.output, records)
    write_jsonl(args.strict_pass, strict_rows)
    write_jsonl(args.review, review_rows)
    write_jsonl(args.rejected, rejected_rows)
    write_jsonl(args.invalid, invalid_rows)
    summary = build_summary(records, len(invalid_rows))
    write_json(args.summary, summary)
    print(json.dumps({"output": str(args.output), **summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
