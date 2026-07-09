#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


LABELS = ("A", "B", "C")
LABEL_NAME = {
    "A": "ignore",
    "B": "support",
    "C": "dominate",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def stable_id(*parts: str, prefix: str = "med") -> str:
    text = "\n".join(parts)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def extract_json_object(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise ValueError("No JSON object found")
    return json.loads(match.group(0))


def label_counts(records: Iterable[dict[str, Any]]) -> Counter:
    counts: Counter = Counter()
    for rec in records:
        for label in rec.get("intent_type", ""):
            counts[label] += 1
    return counts


def compact_rpeval_record(rec: dict[str, Any]) -> dict[str, Any]:
    return {
        "question": rec["question"],
        "persona": [p["preference"] for p in rec["preferences"]],
        "intent_type": "".join(p["u_star"] for p in rec["preferences"]),
        "preference_reasons": [
            {
                "preference": p["preference"],
                "u_star": p["u_star"],
                "reason": p["reason"],
                "source": p.get("source", ""),
                "verify_reason": p.get("verify_reason", ""),
                "boundary_case": p.get("boundary_case", "none"),
            }
            for p in rec["preferences"]
        ],
        "source_id": rec["id"],
        "source_dataset": rec.get("source_dataset", ""),
        "source_split": rec.get("source_split", ""),
        "source_topic": rec.get("topic", ""),
    }


def validate_candidate(
    rec: dict[str, Any],
    min_prefs: int,
    max_prefs: int,
    *,
    require_a_label: bool = False,
    require_applied_label: bool = True,
) -> list[str]:
    errors: list[str] = []
    question = norm_text(str(rec.get("question", "")))
    prefs = rec.get("preferences")
    if len(question) < 20:
        errors.append("question_too_short")
    if not isinstance(prefs, list):
        return errors + ["preferences_not_list"]
    if not (min_prefs <= len(prefs) <= max_prefs):
        errors.append("preference_count_out_of_range")
    seen = set()
    for idx, pref in enumerate(prefs):
        text = norm_text(str(pref.get("preference", "")))
        label = pref.get("u_star")
        reason = norm_text(str(pref.get("reason", "")))
        if not text:
            errors.append(f"empty_preference_{idx}")
        if text in seen:
            errors.append(f"duplicate_preference_{idx}")
        seen.add(text)
        if label not in LABELS:
            errors.append(f"bad_label_{idx}")
        if len(reason) < 8:
            errors.append(f"missing_reason_{idx}")
        if text and text.lower() in question.lower():
            errors.append(f"likely_question_leakage_{idx}")
    labels = [p.get("u_star") for p in prefs if isinstance(p, dict)]
    if require_a_label and "A" not in labels:
        errors.append("missing_A")
    if require_applied_label and not any(label in labels for label in ("B", "C")):
        errors.append("missing_applied_label")
    return errors
