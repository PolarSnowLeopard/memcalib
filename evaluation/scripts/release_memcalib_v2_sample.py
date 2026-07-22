#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from evaluation.common import display_path, iter_jsonl, sha256_file, stable_hash, write_json, write_jsonl
from evaluation.scripts.release_multidomain_pilot import artifact, model_facing_row, write_gzip


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = (
    ROOT
    / "pipeline"
    / "data"
    / "multidomain"
    / "full-v2"
    / "memcalib_v02_multidomain_benchmark_15000.jsonl"
)
DEFAULT_CONFIG = ROOT / "evaluation" / "configs" / "memcalib-v2-multidomain-500.json"
DEFAULT_OUTPUT = ROOT / "evaluation" / "releases" / "memcalib-v2-multidomain-500"
SCHEMA_VERSION = "memcalib-v2-multidomain-sample-release-v1"


def atom_count_bucket(row: dict[str, Any]) -> str:
    count = len(row.get("memories") or [])
    if count <= 3:
        return "2-3"
    if count <= 5:
        return "4-5"
    if count <= 7:
        return "6-7"
    return "8+"


def admission_decision(row: dict[str, Any]) -> str:
    for field in (
        "v23_independent_qc",
        "revision_release_admission",
        "release_admission",
        "semantic_admission",
    ):
        decision = str((row.get(field) or {}).get("decision") or "").strip()
        if decision:
            return decision
    return "unknown"


def difficulty_level(row: dict[str, Any]) -> str:
    return str(
        (row.get("composite_block_revision") or {}).get("difficulty_level")
        or "unassigned"
    )


def within_admission_stratum(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row["source_dataset"]),
        str(row.get("source_topic") or "unknown"),
        atom_count_bucket(row),
        difficulty_level(row),
    )


def proportional_quotas(counts: Counter[tuple[str, ...]], total: int) -> dict[tuple[str, ...], int]:
    population = sum(counts.values())
    if total <= 0 or total > population:
        raise ValueError(f"invalid sample target {total} for population {population}")
    exact = {key: total * count / population for key, count in counts.items()}
    quotas = {key: math.floor(value) for key, value in exact.items()}
    remaining = total - sum(quotas.values())
    order = sorted(counts, key=lambda key: (-(exact[key] - quotas[key]), key))
    for key in order[:remaining]:
        quotas[key] += 1
    return quotas


def select_sample(
    rows: list[dict[str, Any]],
    domain_counts: dict[str, int],
    *,
    seed: int,
    domain_difficulty_counts: dict[str, dict[str, int]] | None = None,
    preferred_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    preferred_ids = preferred_ids or set()
    rows_by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        rows_by_domain[str(row.get("domain") or "")].append(row)
    if set(rows_by_domain) != set(domain_counts):
        raise ValueError(
            f"configured domains do not match source: configured={sorted(domain_counts)}, "
            f"source={sorted(rows_by_domain)}"
        )

    selected: list[dict[str, Any]] = []
    for domain, target in domain_counts.items():
        domain_rows = rows_by_domain[domain]
        difficulty_targets = (domain_difficulty_counts or {}).get(domain)
        if difficulty_targets is None:
            partitions = [("all", domain_rows, target)]
        else:
            if sum(difficulty_targets.values()) != target:
                raise ValueError(
                    f"difficulty counts for {domain} must sum to its domain target"
                )
            rows_by_difficulty: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in domain_rows:
                rows_by_difficulty[difficulty_level(row)].append(row)
            unavailable = {
                level: level_target
                for level, level_target in difficulty_targets.items()
                if level_target > len(rows_by_difficulty[level])
            }
            if unavailable:
                raise ValueError(
                    f"insufficient difficulty capacity for {domain}: {unavailable}"
                )
            partitions = [
                (level, rows_by_difficulty[level], level_target)
                for level, level_target in sorted(difficulty_targets.items())
                if level_target > 0
            ]

        for difficulty, partition_rows, partition_target in partitions:
            rows_by_admission: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in partition_rows:
                rows_by_admission[admission_decision(row)].append(row)
            admission_quotas = proportional_quotas(
                Counter({(key,): len(value) for key, value in rows_by_admission.items()}),
                partition_target,
            )
            for (admission,), admission_target in sorted(admission_quotas.items()):
                if admission_target <= 0:
                    continue
                cells: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
                for row in rows_by_admission[admission]:
                    cells[within_admission_stratum(row)].append(row)
                quotas = proportional_quotas(
                    Counter({key: len(value) for key, value in cells.items()}),
                    admission_target,
                )
                for cell, quota in sorted(quotas.items()):
                    ordered = sorted(
                        cells[cell],
                        key=lambda row: (
                            str(row["id"]) not in preferred_ids,
                            stable_hash(
                                seed,
                                f"{domain}:{difficulty}:{row['id']}",
                            ),
                            str(row["id"]),
                        ),
                    )
                    selected.extend(ordered[:quota])

    selected = sorted(selected, key=lambda row: (stable_hash(seed, str(row["id"])), str(row["id"])))
    ids = [str(row.get("id") or "") for row in selected]
    if len(selected) != sum(domain_counts.values()) or "" in ids or len(ids) != len(set(ids)):
        raise ValueError("sample selection did not produce the requested number of unique IDs")
    actual_domains = Counter(str(row["domain"]) for row in selected)
    if actual_domains != Counter(domain_counts):
        raise ValueError(f"sample domain mismatch: {dict(actual_domains)}")
    return selected


def hidden_row(row: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(row)
    value["panel"] = str(row["domain"])
    value["evaluation"] = {
        "panel": str(row["domain"]),
        "sampling_stratum": {
            "source_dataset": str(row["source_dataset"]),
            "source_topic": str(row.get("source_topic") or "unknown"),
            "release_admission": admission_decision(row),
            "atom_count_bucket": atom_count_bucket(row),
            "difficulty_level": difficulty_level(row),
        },
    }
    return value


def distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "domains": dict(sorted(Counter(str(row["domain"]) for row in rows).items())),
        "sources": dict(sorted(Counter(str(row["source_dataset"]) for row in rows).items())),
        "topics": dict(sorted(Counter(str(row.get("source_topic") or "unknown") for row in rows).items())),
        "release_admission": dict(sorted(Counter(admission_decision(row) for row in rows).items())),
        "atom_count_buckets": dict(sorted(Counter(atom_count_bucket(row) for row in rows).items())),
        "difficulty_levels": dict(sorted(Counter(difficulty_level(row) for row in rows).items())),
        "memory_labels": dict(
            sorted(
                Counter(
                    str(memory.get("u_star") or "unknown")
                    for row in rows
                    for memory in row.get("memories") or []
                ).items()
            )
        ),
    }


def ordered_id_sha256(rows: list[dict[str, Any]]) -> str:
    payload = "\n".join(str(row["id"]) for row in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_release(
    input_path: Path,
    output_dir: Path,
    config_path: Path,
) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    expected_source_hash = str((config.get("source_inputs") or {}).get("benchmark_sha256") or "")
    actual_source_hash = sha256_file(input_path)
    if expected_source_hash != actual_source_hash:
        raise ValueError(
            f"benchmark hash mismatch: expected={expected_source_hash}, actual={actual_source_hash}"
        )

    rows = list(iter_jsonl(input_path))
    ids = [str(row.get("id") or "") for row in rows]
    expected_source_count = int(config["source_count"])
    if len(rows) != expected_source_count or "" in ids or len(ids) != len(set(ids)):
        raise ValueError(
            f"source benchmark must contain {expected_source_count:,} unique nonempty IDs"
        )
    domain_counts = {str(key): int(value) for key, value in config["domain_counts"].items()}
    if sum(domain_counts.values()) != int(config["sample_count"]):
        raise ValueError("configured domain counts must sum to sample_count")

    raw_domain_difficulty_counts = config.get("domain_difficulty_counts")
    domain_difficulty_counts = None
    if raw_domain_difficulty_counts is not None:
        domain_difficulty_counts = {
            str(domain): {str(level): int(count) for level, count in levels.items()}
            for domain, levels in raw_domain_difficulty_counts.items()
        }
        if set(domain_difficulty_counts) != set(domain_counts):
            raise ValueError("domain_difficulty_counts must cover every configured domain")
    preferred_ids: set[str] = set()
    preferred_ids_path = None
    if config.get("preferred_sample_ids"):
        preferred_ids_path = (ROOT / str(config["preferred_sample_ids"])).resolve()
        preferred_rows = [
            value.strip()
            for value in preferred_ids_path.read_text(encoding="utf-8").splitlines()
            if value.strip()
        ]
        preferred_ids = set(preferred_rows)
        if len(preferred_ids) != len(preferred_rows):
            raise ValueError("preferred_sample_ids contains duplicate IDs")
    selected = select_sample(
        rows,
        domain_counts,
        seed=int(config["seed"]),
        domain_difficulty_counts=domain_difficulty_counts,
        preferred_ids=preferred_ids,
    )
    hidden = [hidden_row(row) for row in selected]
    facing = [model_facing_row(row) for row in selected]
    for row in facing:
        if not row["question"] or not row["memory_blocks"]:
            raise ValueError(f"model-facing row is incomplete: {row['id']}")
        if any(not block["memory_text"] for block in row["memory_blocks"]):
            raise ValueError(f"model-facing row contains an empty memory: {row['id']}")

    output_dir.mkdir(parents=True, exist_ok=True)
    hidden_path = output_dir / "hidden-evaluation.jsonl"
    facing_path = output_dir / "model-facing.jsonl"
    sample_ids_path = output_dir / "sample-ids.txt"
    write_jsonl(hidden_path, hidden)
    write_jsonl(facing_path, facing)
    write_gzip(output_dir / "hidden-evaluation.jsonl.gz", hidden_path)
    write_gzip(output_dir / "model-facing.jsonl.gz", facing_path)
    sample_ids_path.write_text("".join(f"{row['id']}\n" for row in selected), encoding="utf-8")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "release": str(config["release"]),
        "status": "internal_diagnostic",
        "samples": len(selected),
        "seed": int(config["seed"]),
        "ordered_id_sha256": ordered_id_sha256(selected),
        "sampling": config["sampling"],
        "preferred_query_id_overlap": {
            "path": display_path(preferred_ids_path, ROOT) if preferred_ids_path else None,
            "preferred_query_ids": len(preferred_ids),
            "selected_query_ids": sum(str(row["id"]) in preferred_ids for row in selected),
            "semantics": (
                "shared query/source identity only; benchmark memory blocks and model-facing "
                "rows may differ across versions"
            ),
        },
        "distribution": distribution(selected),
        "source": {
            "path": display_path(input_path, ROOT),
            "rows": len(rows),
            "sha256": actual_source_hash,
        },
        "config": {
            "path": display_path(config_path, ROOT),
            "sha256": sha256_file(config_path),
        },
        "artifacts": {
            "hidden": artifact(hidden_path, rows=len(hidden)),
            "hidden_gzip": artifact(output_dir / "hidden-evaluation.jsonl.gz"),
            "model_facing": artifact(facing_path, rows=len(facing)),
            "model_facing_gzip": artifact(output_dir / "model-facing.jsonl.gz"),
            "sample_ids": artifact(sample_ids_path, rows=len(selected)),
        },
        "privacy_contract": {
            "model_facing_fields": [
                "id",
                "domain",
                "panel",
                "source_dataset",
                "source_topic",
                "question",
                "memory_blocks.parent_memory_id",
                "memory_blocks.memory_text",
            ],
            "hidden_only": [
                "source_answer",
                "memories",
                "usage_rubric",
                "raw_selection",
                "semantic_qc",
                "independent_qc",
                "revision_release_admission",
                "release_admission",
            ],
        },
    }
    write_json(output_dir / "release-manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lock a deterministic stratified sample of the MemCalib v2 multidomain release."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = build_release(args.input.resolve(), args.output_dir.resolve(), args.config.resolve())
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
