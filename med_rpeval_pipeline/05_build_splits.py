#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from utils import LABELS, compact_rpeval_record, iter_jsonl, label_counts, load_json, norm_text, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR / "config.json"


def combo(intent_type: str) -> str:
    present = set(intent_type)
    return "".join(label for label in LABELS if label in present)


def stats(records: list[dict[str, Any]]) -> dict[str, Any]:
    counts = label_counts(records)
    prefs = sum(counts.values())
    sequence_counts = Counter(r["intent_type"] for r in records)
    pref_len_counts = Counter(str(len(r.get("persona", []))) for r in records)
    a_sources: Counter = Counter()
    for rec in records:
        for item in rec.get("preference_reasons", []):
            if item.get("u_star") == "A":
                a_sources[item.get("source", "") or "unspecified"] += 1
    return {
        "records": len(records),
        "preferences": prefs,
        "label_counts": {label: counts[label] for label in LABELS},
        "label_ratios": {label: counts[label] / max(prefs, 1) for label in LABELS},
        "combo_counts": dict(Counter(combo(r["intent_type"]) for r in records)),
        "preference_count_distribution": dict(sorted(pref_len_counts.items(), key=lambda kv: int(kv[0]))),
        "intent_sequence_counts_top50": dict(sequence_counts.most_common(50)),
        "a_source_counts": dict(a_sources),
        "source_counts": dict(Counter(r.get("source_dataset", "") for r in records)),
        "source_split_counts": dict(Counter(r.get("source_split", "") for r in records)),
        "source_topic_counts": dict(Counter(r.get("source_topic", "") for r in records)),
        "avg_preferences_per_record": prefs / len(records) if records else 0,
    }


def dedup_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_questions = set()
    seen_items = set()
    out = []
    for rec in records:
        q = norm_text(rec["question"]).lower()
        if q in seen_questions:
            continue
        items = tuple((p.lower(), l) for p, l in zip(rec["persona"], rec["intent_type"]))
        key = (q, items)
        if key in seen_items:
            continue
        seen_questions.add(q)
        seen_items.add(key)
        out.append(rec)
    return out


def stratified_split_named(records: list[dict[str, Any]], split_sizes: dict[str, int], seed: int) -> dict[str, list[dict[str, Any]]]:
    rng = random.Random(seed)
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in records:
        buckets[combo(rec["intent_type"])].append(rec)
    for values in buckets.values():
        rng.shuffle(values)

    splits = {name: [] for name in split_sizes}
    splits["unused"] = []
    total = len(records)
    for values in buckets.values():
        n = len(values)
        offset = 0
        for name, target_size in split_sizes.items():
            take = round(target_size * n / max(total, 1))
            splits[name].extend(values[offset : offset + take])
            offset += take
        splits["unused"].extend(values[offset:])

    for values in splits.values():
        rng.shuffle(values)
    return splits


def write_parquet(path: Path, records: list[dict[str, Any]]) -> None:
    import pandas as pd

    rows = []
    for rec in records:
        rows.append(
            {
                "question": rec["question"],
                "persona": json.dumps(rec["persona"], ensure_ascii=False),
                "intent_type": rec["intent_type"],
                "preference_reasons": json.dumps(rec.get("preference_reasons", []), ensure_ascii=False),
                "source_id": rec.get("source_id", ""),
                "source_dataset": rec.get("source_dataset", ""),
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build RPEval-style train/val/test JSON and parquet files.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--write-parquet", action="store_true")
    args = parser.parse_args()

    cfg = load_json(args.config)
    input_path = args.input or Path(cfg["output_dir"]) / "verified_records.jsonl"
    output_dir = args.output_dir or Path(cfg["output_dir"]) / "rpeval_med_public"
    split_cfg = cfg["split"]

    source_records = list(iter_jsonl(input_path))
    compact = [compact_rpeval_record(r) for r in source_records]
    compact = dedup_records(compact)
    split_sizes = {
        "rl_train": int(split_cfg.get("rl_train_size", split_cfg.get("train_size", 10000))),
        "sft_reserved": int(split_cfg.get("sft_size", 4000)),
        "test": int(split_cfg.get("test_size", 500)),
    }
    splits = stratified_split_named(compact, split_sizes, split_cfg["seed"])
    rl_train = splits["rl_train"]
    sft_reserved = splits["sft_reserved"]
    test = splits["test"]
    unused = splits["unused"]

    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "rpeval_med_public_all.json", compact)
    write_json(output_dir / "rpeval_med_public_rl_train.json", rl_train)
    write_json(output_dir / "rpeval_med_public_sft_reserved.json", sft_reserved)
    write_json(output_dir / "rpeval_med_public_test.json", test)
    write_json(output_dir / "rpeval_med_public_unused.json", unused)
    write_json(output_dir / "rpeval_med_public_train.json", rl_train)
    write_json(output_dir / "rpeval_med_public_val.json", sft_reserved)
    write_jsonl(output_dir / "rpeval_med_public_audit.jsonl", source_records)

    report = {
        "all": stats(compact),
        "rl_train": stats(rl_train),
        "sft_reserved": stats(sft_reserved),
        "test": stats(test),
        "unused": stats(unused),
    }
    write_json(output_dir / "stats.json", report)
    if args.write_parquet:
        write_parquet(output_dir / "rpeval_med_public_rl_train.parquet", rl_train)
        write_parquet(output_dir / "rpeval_med_public_sft_reserved.parquet", sft_reserved)
        write_parquet(output_dir / "rpeval_med_public_test.parquet", test)
        write_parquet(output_dir / "rpeval_med_public_train.parquet", rl_train)
        write_parquet(output_dir / "rpeval_med_public_val.parquet", sft_reserved)
    print(json.dumps({"output_dir": str(output_dir), **report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
