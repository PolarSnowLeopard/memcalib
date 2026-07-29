#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from evaluation.common import display_path, load_release_records, sha256_file, stable_hash, write_json, write_jsonl


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RELEASE = ROOT / "release" / "archive" / "memcalib-v0.1"
DEFAULT_CONFIG = ROOT / "evaluation" / "archive" / "configs" / "memcalib-v0.1-500.json"
DEFAULT_METADATA = ROOT / "evaluation" / "metadata" / "memcalib-v0.1-seed-complexity.jsonl"
DEFAULT_OUTPUT = ROOT / "evaluation" / "archive" / "releases" / "memcalib-v0.1-500"


def largest_remainder_quotas(counts: dict[str, int], total: int) -> dict[str, int]:
    population = sum(counts.values())
    if population <= 0 or total < 0:
        raise ValueError("counts and total must be positive")
    exact = {key: total * value / population for key, value in counts.items()}
    quotas = {key: math.floor(value) for key, value in exact.items()}
    remaining = total - sum(quotas.values())
    order = sorted(counts, key=lambda key: (-(exact[key] - quotas[key]), key))
    for key in order[:remaining]:
        quotas[key] += 1
    return quotas


def record_features(row: dict[str, Any], high_atom_threshold: int | None = None) -> dict[str, Any]:
    memories = row.get("memories") or []
    blocks = row.get("memory_blocks") or []
    rare = {str(memory["hard_a_family"]) for memory in memories if memory.get("hard_a_family")}
    return {
        "source": str(row["source_dataset"]),
        "topic": str(row["source_topic"]),
        "complexity": str(row["_seed_complexity"]),
        "mixed": any(block.get("parent_label_mode") == "mixed" for block in blocks),
        "rare": rare,
        "safety": any(memory.get("memory_type") == "safety_sensitive" for memory in memories),
        "high_atom": high_atom_threshold is not None and len(memories) >= high_atom_threshold,
        "atom_count": len(memories),
        "labels": Counter(str(memory.get("u_star")) for memory in memories),
        "memory_types": Counter(str(memory.get("memory_type")) for memory in memories),
    }


def _cell_quotas(
    records: list[dict[str, Any]],
    source_targets: dict[str, int],
    topic_targets: dict[str, int],
    complexity_targets: dict[str, int],
) -> Counter[tuple[str, str, str]]:
    availability = Counter(
        (str(row["source_dataset"]), str(row["source_topic"]), str(row["_seed_complexity"])) for row in records
    )
    remaining_source = dict(source_targets)
    remaining_topic = dict(topic_targets)
    remaining_complexity = dict(complexity_targets)
    quotas: Counter[tuple[str, str, str]] = Counter()
    target_size = sum(source_targets.values())
    for _ in range(target_size):
        choices = []
        for cell, available in availability.items():
            source, topic, complexity = cell
            if quotas[cell] >= available:
                continue
            if remaining_source.get(source, 0) <= 0 or remaining_topic.get(topic, 0) <= 0:
                continue
            if remaining_complexity.get(complexity, 0) <= 0:
                continue
            score = (
                remaining_source[source] / source_targets[source]
                + remaining_topic[topic] / topic_targets[topic]
                + remaining_complexity[complexity] / complexity_targets[complexity]
                + min(available - quotas[cell], 1000) / 1_000_000
            )
            choices.append((score, cell))
        if not choices:
            raise ValueError("representative margins are infeasible for the available source/topic/complexity cells")
        _, cell = max(choices, key=lambda item: (item[0], tuple(reversed(item[1]))))
        quotas[cell] += 1
        remaining_source[cell[0]] -= 1
        remaining_topic[cell[1]] -= 1
        remaining_complexity[cell[2]] -= 1
    if any(remaining_source.values()) or any(remaining_topic.values()) or any(remaining_complexity.values()):
        raise ValueError("representative margin allocation did not close exactly")
    return quotas


def _projected_distribution_loss(
    label_counts: Counter[str],
    type_counts: Counter[str],
    mixed_count: int,
    selected_count: int,
    candidate_features: dict[str, Any],
    target_label: dict[str, float],
    target_types: dict[str, float],
    target_mixed: float,
) -> float:
    label_total = sum(label_counts.values()) + sum(candidate_features["labels"].values()) or 1
    type_total = sum(type_counts.values()) + sum(candidate_features["memory_types"].values()) or 1
    return (
        sum(
            abs((label_counts[key] + candidate_features["labels"][key]) / label_total - value)
            for key, value in target_label.items()
        )
        + sum(
            abs((type_counts[key] + candidate_features["memory_types"][key]) / type_total - value)
            for key, value in target_types.items()
        )
        + abs((mixed_count + int(candidate_features["mixed"])) / (selected_count + 1) - target_mixed)
    )


def select_representative(records: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    section = config["representative"]
    size = int(section["size"])
    source_targets = {str(k): int(v) for k, v in section["source_quotas"].items()}
    complexity_targets = {str(k): int(v) for k, v in section["complexity_quotas"].items()}
    topic_counts = Counter(str(row["source_topic"]) for row in records)
    topic_targets = largest_remainder_quotas(dict(topic_counts), size)
    if sum(source_targets.values()) != size or sum(complexity_targets.values()) != size:
        raise ValueError("representative quotas must sum to panel size")
    cell_targets = _cell_quotas(records, source_targets, topic_targets, complexity_targets)
    labels = Counter(str(memory.get("u_star")) for row in records for memory in row.get("memories") or [])
    types = Counter(str(memory.get("memory_type")) for row in records for memory in row.get("memories") or [])
    label_total = sum(labels.values()) or 1
    type_total = sum(types.values()) or 1
    target_label = {key: value / label_total for key, value in labels.items()}
    target_types = {key: value / type_total for key, value in types.items()}
    features_by_id = {str(row["id"]): record_features(row) for row in records}
    target_mixed = sum(feature["mixed"] for feature in features_by_id.values()) / len(records)
    by_cell: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        by_cell[(str(row["source_dataset"]), str(row["source_topic"]), str(row["_seed_complexity"]))].append(row)
    selected: list[dict[str, Any]] = []
    selected_labels: Counter[str] = Counter()
    selected_types: Counter[str] = Counter()
    selected_mixed = 0
    seed = int(config["seed"])
    for cell in sorted(cell_targets):
        candidates = list(by_cell[cell])
        for _ in range(cell_targets[cell]):
            candidate = min(
                candidates,
                key=lambda row: (
                    _projected_distribution_loss(
                        selected_labels,
                        selected_types,
                        selected_mixed,
                        len(selected),
                        features_by_id[str(row["id"])],
                        target_label,
                        target_types,
                        target_mixed,
                    ),
                    stable_hash(seed, str(row["id"])),
                ),
            )
            selected.append(candidate)
            feature = features_by_id[str(candidate["id"])]
            selected_labels.update(feature["labels"])
            selected_types.update(feature["memory_types"])
            selected_mixed += int(feature["mixed"])
            candidates.remove(candidate)
    return sorted(selected, key=lambda row: stable_hash(seed, str(row["id"])))


def _diagnostic_summary(rows: list[dict[str, Any]], threshold: int, rare_families: list[str]) -> dict[str, Any]:
    features = [record_features(row, threshold) for row in rows]
    rare_sample_counts = {family: sum(family in feature["rare"] for feature in features) for family in rare_families}
    return {
        "size": len(rows),
        "sources": dict(sorted(Counter(feature["source"] for feature in features).items())),
        "topics": dict(sorted(Counter(feature["topic"] for feature in features).items())),
        "mixed_parent_samples": sum(feature["mixed"] for feature in features),
        "rare_hard_a_samples": rare_sample_counts,
        "rare_hard_a_union_samples": sum(bool(set(rare_families).intersection(feature["rare"])) for feature in features),
        "safety_sensitive_samples": sum(feature["safety"] for feature in features),
        "high_atom_samples": sum(feature["high_atom"] for feature in features),
        "high_atom_threshold": threshold,
    }


def _validate_diagnostic(rows: list[dict[str, Any]], section: dict[str, Any], threshold: int) -> dict[str, Any]:
    rare_families = [str(value) for value in section["rare_hard_a_families"]]
    summary = _diagnostic_summary(rows, threshold, rare_families)
    errors = []
    if summary["size"] != int(section["size"]):
        errors.append("size")
    if summary["sources"] != {str(k): int(v) for k, v in section["source_quotas"].items()}:
        errors.append("source_quotas")
    topic_minimum = int(section["topic_minimum"])
    if not summary["topics"] or min(summary["topics"].values()) < topic_minimum:
        errors.append("topic_minimum")
    if summary["mixed_parent_samples"] < int(section["mixed_parent_minimum"]):
        errors.append("mixed_parent_minimum")
    for family in rare_families:
        if summary["rare_hard_a_samples"].get(family, 0) < int(section["rare_hard_a_each_minimum"]):
            errors.append(f"rare:{family}")
    if summary["rare_hard_a_union_samples"] < int(section["rare_hard_a_union_minimum"]):
        errors.append("rare_union")
    if summary["safety_sensitive_samples"] < int(section["safety_sensitive_minimum"]):
        errors.append("safety_sensitive_minimum")
    if summary["high_atom_samples"] < int(section["high_atom_minimum"]):
        errors.append("high_atom_minimum")
    if errors:
        raise ValueError(f"diagnostic quotas unmet: {', '.join(errors)}; summary={summary}")
    return summary


def select_diagnostic(records: list[dict[str, Any]], excluded_ids: set[str], config: dict[str, Any]) -> list[dict[str, Any]]:
    section = config["diagnostic"]
    candidates = [row for row in records if str(row["id"]) not in excluded_ids]
    atom_counts = sorted(len(row.get("memories") or []) for row in candidates)
    threshold = int(section.get("high_atom_threshold") or atom_counts[math.ceil(0.75 * len(atom_counts)) - 1])
    rare_families = [str(value) for value in section["rare_hard_a_families"]]
    source_targets = {str(k): int(v) for k, v in section["source_quotas"].items()}
    size = int(section["size"])
    if sum(source_targets.values()) != size:
        raise ValueError("diagnostic source quotas must sum to panel size")
    seed = int(config["seed"])
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    source_counts: Counter[str] = Counter()
    topic_counts: Counter[str] = Counter()
    rare_counts: Counter[str] = Counter()
    mixed_count = 0
    rare_union_count = 0
    safety_count = 0
    high_atom_count = 0
    features_by_id = {str(row["id"]): record_features(row, threshold) for row in candidates}

    def gain(row: dict[str, Any]) -> float:
        feature = features_by_id[str(row["id"])]
        value = 0.0
        if topic_counts[feature["topic"]] < int(section["topic_minimum"]):
            value += 8.0
        if feature["mixed"] and mixed_count < int(section["mixed_parent_minimum"]):
            value += 4.0
        if set(rare_families).intersection(feature["rare"]) and rare_union_count < int(section["rare_hard_a_union_minimum"]):
            value += 3.0
        for family in rare_families:
            if family in feature["rare"] and rare_counts[family] < int(section["rare_hard_a_each_minimum"]):
                value += 7.0
        if feature["safety"] and safety_count < int(section["safety_sensitive_minimum"]):
            value += 5.0
        if feature["high_atom"] and high_atom_count < int(section["high_atom_minimum"]):
            value += 3.0
        value += 0.25 * int(feature["mixed"]) + 0.1 * int(feature["high_atom"])
        source_deficit = source_targets[feature["source"]] - source_counts[feature["source"]]
        value += source_deficit / max(source_targets[feature["source"]], 1)
        return value

    for _ in range(size):
        available = [
            row
            for row in candidates
            if str(row["id"]) not in selected_ids
            and source_counts[str(row["source_dataset"])] < source_targets.get(str(row["source_dataset"]), 0)
        ]
        if not available:
            raise ValueError("diagnostic source quotas are infeasible")
        choice = max(available, key=lambda row: (gain(row), stable_hash(seed, str(row["id"]))))
        selected.append(choice)
        selected_ids.add(str(choice["id"]))
        feature = features_by_id[str(choice["id"])]
        source_counts[feature["source"]] += 1
        topic_counts[feature["topic"]] += 1
        mixed_count += int(feature["mixed"])
        has_rare = bool(set(rare_families).intersection(feature["rare"]))
        rare_union_count += int(has_rare)
        for family in rare_families:
            rare_counts[family] += int(family in feature["rare"])
        safety_count += int(feature["safety"])
        high_atom_count += int(feature["high_atom"])
    _validate_diagnostic(selected, section, threshold)
    return sorted(selected, key=lambda row: stable_hash(seed, str(row["id"])))


def _selection_tags(row: dict[str, Any], threshold: int, rare_families: list[str]) -> list[str]:
    feature = record_features(row, threshold)
    tags = []
    if feature["mixed"]:
        tags.append("mixed_parent")
    tags.extend(f"hard_a:{family}" for family in sorted(set(rare_families).intersection(feature["rare"])))
    if feature["safety"]:
        tags.append("safety_sensitive")
    if feature["high_atom"]:
        tags.append("high_atom")
    return tags


def build_selection_artifacts(
    representative: list[dict[str, Any]], diagnostic: list[dict[str, Any]], output_dir: Path, config: dict[str, Any]
) -> dict[str, Any]:
    all_rows: list[dict[str, Any]] = []
    model_rows: list[dict[str, Any]] = []
    threshold = int(config.get("diagnostic", {}).get("high_atom_threshold", 0))
    rare_families = [str(value) for value in config.get("diagnostic", {}).get("rare_hard_a_families", [])]
    for panel, rows in (("representative", representative), ("diagnostic", diagnostic)):
        for row in rows:
            hidden = dict(row)
            complexity = hidden.pop("_seed_complexity", "unknown")
            hidden["panel"] = panel
            hidden["evaluation"] = {
                "panel": panel,
                "seed_complexity": complexity,
                "selection_tags": _selection_tags(row, threshold, rare_families) if threshold else [],
            }
            all_rows.append(hidden)
            model_rows.append(
                {
                    "id": str(row["id"]),
                    "panel": panel,
                    "seed_complexity": complexity,
                    "source_dataset": str(row["source_dataset"]),
                    "source_topic": str(row["source_topic"]),
                    "question": str(row["question"]),
                    "memory_blocks": [
                        {
                            "parent_memory_id": str(block["parent_memory_id"]),
                            "memory_text": str(block["memory_text"]),
                        }
                        for block in row.get("memory_blocks") or []
                    ],
                }
            )
    output_dir.mkdir(parents=True, exist_ok=True)
    hidden_path = output_dir / "hidden-evaluation.jsonl"
    model_path = output_dir / "model-facing.jsonl"
    heldout_path = output_dir / "held-out-ids.txt"
    write_jsonl(hidden_path, all_rows)
    write_jsonl(model_path, model_rows)
    heldout_path.write_text("".join(f"{row['id']}\n" for row in all_rows), encoding="utf-8")
    manifest = {
        "schema_version": "memcalib-eval-selection-v1",
        "seed": int(config["seed"]),
        "counts": {
            "total": len(all_rows),
            "representative": len(representative),
            "diagnostic": len(diagnostic),
            "unique_ids": len({str(row["id"]) for row in all_rows}),
        },
        "distributions": {
            "source": dict(sorted(Counter(str(row["source_dataset"]) for row in all_rows).items())),
            "topic": dict(sorted(Counter(str(row["source_topic"]) for row in all_rows).items())),
            "complexity": dict(sorted(Counter(str(row["evaluation"]["seed_complexity"]) for row in all_rows).items())),
        },
        "artifacts": {
            "hidden-evaluation.jsonl": sha256_file(hidden_path),
            "model-facing.jsonl": sha256_file(model_path),
            "held-out-ids.txt": sha256_file(heldout_path),
        },
    }
    write_json(output_dir / "selection-manifest.json", manifest)
    return manifest


def build_complexity_metadata(records: list[dict[str, Any]], admission_path: Path, output_path: Path) -> str:
    complexity_by_source_id: dict[str, str] = {}
    with admission_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            complexity_by_source_id[str(row["id"])] = str(row["raw_selection"]["seed_complexity"])
    metadata = []
    missing = []
    for row in records:
        source_id = str(row.get("source_id") or row.get("source_record_id"))
        complexity = complexity_by_source_id.get(source_id)
        if not complexity:
            missing.append(source_id)
        else:
            metadata.append({"id": str(row["id"]), "seed_complexity": complexity})
    if missing:
        raise ValueError(f"missing complexity metadata for {len(missing)} records")
    write_jsonl(output_path, metadata)
    return sha256_file(output_path)


def attach_complexity(records: list[dict[str, Any]], metadata_path: Path, expected_sha: str) -> list[dict[str, Any]]:
    actual_sha = sha256_file(metadata_path)
    if expected_sha and actual_sha != expected_sha:
        raise ValueError(f"complexity metadata hash mismatch: {actual_sha} != {expected_sha}")
    metadata = {}
    with metadata_path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                metadata[str(row["id"])] = str(row["seed_complexity"])
    enriched = []
    for row in records:
        sample_id = str(row["id"])
        if sample_id not in metadata:
            raise ValueError(f"missing complexity metadata for {sample_id}")
        value = dict(row)
        value["_seed_complexity"] = metadata[sample_id]
        enriched.append(value)
    return enriched


def main() -> None:
    parser = argparse.ArgumentParser(description="Select the locked MemCalib 500-sample validation set.")
    parser.add_argument("--release-dir", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--admission", type=Path, help="Construction admission JSONL, used only to create metadata.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    records, source_sha = load_release_records(args.release_dir)
    if source_sha != config["source_sha256"]:
        raise SystemExit(f"locked source mismatch: {source_sha}")
    if args.admission:
        metadata_sha = build_complexity_metadata(records, args.admission, args.metadata)
        print(json.dumps({"complexity_metadata": str(args.metadata), "sha256": metadata_sha}, indent=2))
    records = attach_complexity(records, args.metadata, str(config.get("complexity_metadata_sha256") or ""))
    representative = select_representative(records, config)
    representative_ids = {str(row["id"]) for row in representative}
    diagnostic = select_diagnostic(records, representative_ids, config)
    manifest = build_selection_artifacts(representative, diagnostic, args.output_dir, config)
    manifest["source"] = {"release": display_path(args.release_dir, ROOT), "sha256": source_sha, "records": len(records)}
    manifest["complexity_metadata"] = {"path": display_path(args.metadata, ROOT), "sha256": sha256_file(args.metadata)}
    manifest["diagnostic_coverage"] = _validate_diagnostic(
        diagnostic,
        config["diagnostic"],
        int(config["diagnostic"]["high_atom_threshold"]),
    )
    write_json(args.output_dir / "selection-manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
