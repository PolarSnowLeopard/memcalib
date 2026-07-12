#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

import pandas as pd

from utils import load_json, norm_text, resolve_config_path, stable_id, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR / "config.json"


TOPIC_RULES: list[tuple[str, tuple[str, ...]]] = [
    (
        "pregnancy_reproductive",
        (
            "pregnant",
            "pregnancy",
            "conceive",
            "fertility",
            "infertility",
            "period",
            "menstrual",
            "ovulation",
            "pcos",
            "fetal",
            "foetus",
            "miscarriage",
            "breastfeeding",
            "lactation",
            "vaginal",
            "uterus",
            "ovary",
            "sperm",
            "semen",
        ),
    ),
    (
        "pediatrics",
        (
            "baby",
            "infant",
            "newborn",
            "toddler",
            "child",
            "children",
            "kid",
            "pediatric",
            "paediatric",
            "my son",
            "my daughter",
            "months old",
            "years old boy",
            "years old girl",
        ),
    ),
    (
        "medication_treatment",
        (
            "medicine",
            "medication",
            "drug",
            "tablet",
            "capsule",
            "pill",
            "dose",
            "dosage",
            "antibiotic",
            "side effect",
            "metformin",
            "amoxicillin",
            "ibuprofen",
            "paracetamol",
            "tylenol",
            "aspirin",
            "benadryl",
            "insulin",
            "treatment",
            "prescribed",
        ),
    ),
    (
        "chronic_disease",
        (
            "diabetes",
            "hypertension",
            "blood pressure",
            "thyroid",
            "asthma",
            "copd",
            "kidney disease",
            "renal failure",
            "cancer",
            "tumor",
            "tumour",
            "arthritis",
            "cholesterol",
            "liver disease",
        ),
    ),
    (
        "skin_allergy",
        (
            "rash",
            "acne",
            "itch",
            "itching",
            "hives",
            "eczema",
            "skin",
            "allergy",
            "allergic",
            "swelling of face",
        ),
    ),
    (
        "digestive",
        (
            "stomach",
            "abdominal",
            "abdomen",
            "diarrhea",
            "diarrhoea",
            "constipation",
            "vomit",
            "vomiting",
            "nausea",
            "gastric",
            "bowel",
            "colon",
            "rectum",
            "blood in stool",
        ),
    ),
    (
        "respiratory_ent",
        (
            "cough",
            "cold",
            "sore throat",
            "throat",
            "runny nose",
            "nasal",
            "sinus",
            "breathing",
            "wheezing",
            "ear",
            "tonsil",
        ),
    ),
    (
        "cardio",
        (
            "chest pain",
            "heart",
            "palpitation",
            "pulse",
            "ecg",
            "ekg",
            "cardiac",
            "shortness of breath",
        ),
    ),
    (
        "neuro",
        (
            "headache",
            "migraine",
            "dizziness",
            "vertigo",
            "seizure",
            "numbness",
            "tingling",
            "stroke",
            "memory",
            "weakness",
        ),
    ),
    (
        "mental_sleep",
        (
            "anxiety",
            "depression",
            "panic",
            "stress",
            "insomnia",
            "sleep",
            "suicidal",
            "mental",
        ),
    ),
    (
        "acute_symptoms",
        (
            "pain",
            "fever",
            "swelling",
            "lump",
            "bleeding",
            "infection",
            "injury",
            "burning",
            "cramp",
            "ache",
            "sick",
        ),
    ),
]


def classify_topic(question: str, answer: str = "") -> str:
    text = f"{question} {answer}".lower()
    for topic, keywords in TOPIC_RULES:
        if any(keyword in text for keyword in keywords):
            return topic
    return "general_other"


def keep_record(question: str, answer: str, cfg: dict[str, Any]) -> bool:
    filters = cfg["filters"]
    q_len = len(question)
    a_len = len(answer)
    return (
        filters["min_question_chars"] <= q_len <= filters["max_question_chars"]
        and filters["min_answer_chars"] <= a_len
    )


def load_meddialog(root: Path, split: str, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    path = root / "MedDialog" / f"{split}.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for idx, row in enumerate(rows):
        question = norm_text(row.get("patient_message", ""))
        answer = norm_text(row.get("doctor_response", ""))
        if not keep_record(question, answer, cfg):
            continue
        out.append(
            {
                "id": stable_id("OpenMed/MedDialog", split, str(idx), question, prefix="raw"),
                "source_dataset": "OpenMed/MedDialog",
                "source_split": split,
                "source_index": idx,
                "raw_question": question,
                "doctor_answer": answer,
                "topic": classify_topic(question, answer),
                "dialogue_context": norm_text(row.get("dialogue_context", "")),
            }
        )
    return out


def load_chatdoctor(root: Path, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    data_dir = root / "ChatDoctor-HealthCareMagic-100k" / "data"
    files = sorted(data_dir.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No parquet files found under {data_dir}")
    out = []
    for file in files:
        df = pd.read_parquet(file)
        for idx, row in df.iterrows():
            question = norm_text(str(row.get("input", "")))
            answer = norm_text(str(row.get("output", "")))
            if not keep_record(question, answer, cfg):
                continue
            out.append(
                {
                    "id": stable_id("lavita/ChatDoctor-HealthCareMagic-100k", str(idx), question, prefix="raw"),
                    "source_dataset": "lavita/ChatDoctor-HealthCareMagic-100k",
                    "source_split": "train",
                    "source_index": int(idx),
                    "raw_question": question,
                    "doctor_answer": answer,
                    "topic": classify_topic(question, answer),
                    "instruction": norm_text(str(row.get("instruction", ""))),
                }
            )
    return out


def maybe_sample(rows: list[dict[str, Any]], max_count: int, seed: int) -> list[dict[str, Any]]:
    if max_count <= 0 or len(rows) <= max_count:
        return rows
    rng = random.Random(seed)
    rows = list(rows)
    rng.shuffle(rows)
    return rows[:max_count]


def balanced_sample_by_topic(rows: list[dict[str, Any]], max_count: int, seed: int, topic_order: list[str]) -> list[dict[str, Any]]:
    if max_count <= 0 or len(rows) <= max_count:
        return rows
    rng = random.Random(seed)
    buckets: dict[str, list[dict[str, Any]]] = {topic: [] for topic in topic_order}
    buckets.setdefault("general_other", [])
    for row in rows:
        buckets.setdefault(row.get("topic", "general_other"), []).append(row)
    for bucket in buckets.values():
        rng.shuffle(bucket)

    active_topics = [topic for topic in topic_order if buckets.get(topic)]
    if not active_topics:
        return maybe_sample(rows, max_count, seed)
    per_topic = max(1, max_count // len(active_topics))
    selected: list[dict[str, Any]] = []
    leftovers: list[dict[str, Any]] = []
    for topic in active_topics:
        bucket = buckets[topic]
        selected.extend(bucket[:per_topic])
        leftovers.extend(bucket[per_topic:])
    if len(selected) < max_count:
        rng.shuffle(leftovers)
        selected.extend(leftovers[: max_count - len(selected)])
    elif len(selected) > max_count:
        rng.shuffle(selected)
        selected = selected[:max_count]
    rng.shuffle(selected)
    return selected


def sample_rows(rows: list[dict[str, Any]], max_count: int, seed: int, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    sampling_cfg = cfg.get("sampling", {})
    if sampling_cfg.get("balance_topics", True):
        topic_order = list(sampling_cfg.get("topic_order") or [topic for topic, _ in TOPIC_RULES] + ["general_other"])
        return balanced_sample_by_topic(rows, max_count, seed, topic_order)
    return maybe_sample(rows, max_count, seed)


def split_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        split = str(row.get("source_split", "unknown"))
        counts[split] = counts.get(split, 0) + 1
    return dict(sorted(counts.items()))


def topic_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        topic = str(row.get("topic", "general_other"))
        counts[topic] = counts.get(topic, 0) + 1
    return dict(sorted(counts.items()))


def sample_meddialog(train_rows: list[dict[str, Any]], val_rows: list[dict[str, Any]], limit: int, seed: int, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    rows = train_rows + val_rows
    if limit <= 0 or len(rows) <= limit:
        return rows
    ratios = cfg.get("sampling", {}).get("meddialog_split_ratios", {"train": 0.5, "validation": 0.5})
    train_ratio = float(ratios.get("train", 0.5))
    val_ratio = float(ratios.get("validation", 0.5))
    total_ratio = train_ratio + val_ratio
    if total_ratio <= 0:
        train_target = limit // 2
    else:
        train_target = round(limit * train_ratio / total_ratio)
    val_target = limit - train_target
    train_kept = sample_rows(train_rows, train_target, seed, cfg)
    val_kept = sample_rows(val_rows, val_target, seed + 1, cfg)
    if len(train_kept) + len(val_kept) < limit:
        selected_ids = {row["id"] for row in train_kept + val_kept}
        remaining = [row for row in rows if row["id"] not in selected_ids]
        fill = sample_rows(remaining, limit - len(train_kept) - len(val_kept), seed + 2, cfg)
        return train_kept + val_kept + fill
    return train_kept + val_kept


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize downloaded public medical QA data into one JSONL.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-per-source", type=int, default=None)
    args = parser.parse_args()

    cfg = load_json(args.config)
    root = resolve_config_path(args.config, str(cfg["source_root"]))
    output_dir = resolve_config_path(args.config, str(cfg["output_dir"]))
    output = args.output or output_dir / "normalized_raw_full.jsonl"
    max_per_source = args.max_per_source
    if max_per_source is None:
        max_per_source = int(cfg["filters"].get("max_raw_records_per_source", 0))

    meddialog_train = load_meddialog(root, "train", cfg)
    meddialog_validation = load_meddialog(root, "validation", cfg)
    chatdoctor_train = load_chatdoctor(root, cfg)
    groups = {
        "OpenMed/MedDialog": (meddialog_train, meddialog_validation),
        "lavita/ChatDoctor-HealthCareMagic-100k": chatdoctor_train,
    }
    split_stats = {
        "meddialog_train": len(meddialog_train),
        "meddialog_validation": len(meddialog_validation),
        "chatdoctor_train": len(chatdoctor_train),
    }
    source_limits = cfg.get("sampling", {}).get("source_limits", {})
    sampled = []
    stats = {}
    for name, group_rows in groups.items():
        limit = max_per_source if max_per_source > 0 else int(source_limits.get(name, 0))
        if name == "OpenMed/MedDialog":
            train_rows, val_rows = group_rows
            loaded_rows = train_rows + val_rows
            kept = sample_meddialog(train_rows, val_rows, limit, args.seed, cfg)
        else:
            loaded_rows = group_rows
            kept = sample_rows(loaded_rows, limit, args.seed, cfg)
        sampled.extend(kept)
        stats[name] = {
            "loaded": len(loaded_rows),
            "kept": len(kept),
            "limit": limit,
            "split_counts": split_counts(kept),
            "topic_counts": topic_counts(kept),
        }

    write_jsonl(output, sampled)
    report = {"total": len(sampled), "groups": stats, "loaded_splits": split_stats}
    write_json(output.with_suffix(".stats.json"), report)
    print(json.dumps({"output": str(output), **report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
