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
    / "revision-longtail-blocks"
    / "release"
    / "memcalib_v22_multidomain_benchmark_15000.jsonl"
)
DEFAULT_CONFIG = ROOT / "evaluation" / "archive" / "configs" / "memcalib-v22-codex-pilot-100.json"
DEFAULT_OUTPUT = ROOT / "evaluation" / "archive" / "releases" / "memcalib-v22-codex-pilot-100"
SCHEMA_VERSION = "memcalib-v22-codex-pilot-release-v1"
BLOCK_BUCKETS = ("3-4", "5-6", "7-10", "11-20")


def block_count_bucket(row: dict[str, Any]) -> str:
    count = len(row.get("memory_blocks") or [])
    if 3 <= count <= 4:
        return "3-4"
    if 5 <= count <= 6:
        return "5-6"
    if 7 <= count <= 10:
        return "7-10"
    if 11 <= count <= 20:
        return "11-20"
    raise ValueError(f"record {row.get('id')} has block count outside 3-20: {count}")


def atom_count_bucket(row: dict[str, Any]) -> str:
    count = len(row.get("memories") or [])
    if count <= 7:
        return "5-7"
    if count <= 10:
        return "8-10"
    if count <= 15:
        return "11-15"
    return "16+"


def admission_decision(row: dict[str, Any]) -> str:
    for field in ("revision_release_admission", "release_admission", "semantic_admission"):
        decision = str((row.get(field) or {}).get("decision") or "").strip()
        if decision:
            return decision
    return "unknown"


def hard_a_family(row: dict[str, Any]) -> str:
    families = sorted(
        {
            str(memory["hard_a_family"])
            for memory in row.get("memories") or []
            if memory.get("hard_a_family")
        }
    )
    return "+".join(families) if families else "none"


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


def within_bucket_stratum(row: dict[str, Any]) -> tuple[str, ...]:
    return (
        str(row.get("source_topic") or "unknown"),
        hard_a_family(row),
        admission_decision(row),
    )


def allocate_source_bucket_quotas(
    rows: list[dict[str, Any]],
    source_targets: dict[str, int],
    bucket_targets: dict[str, int],
) -> Counter[tuple[str, str]]:
    if sum(source_targets.values()) != sum(bucket_targets.values()):
        raise ValueError("source and block-bucket margins must have the same total")
    availability = Counter(
        (str(row["source_dataset"]), block_count_bucket(row))
        for row in rows
    )
    remaining_sources = dict(source_targets)
    remaining_buckets = dict(bucket_targets)
    quotas: Counter[tuple[str, str]] = Counter()
    for _ in range(sum(source_targets.values())):
        choices = []
        for cell, available in availability.items():
            source, bucket = cell
            if source not in source_targets or bucket not in bucket_targets:
                continue
            if quotas[cell] >= available:
                continue
            if remaining_sources[source] <= 0 or remaining_buckets[bucket] <= 0:
                continue
            score = (
                remaining_sources[source] / source_targets[source]
                + remaining_buckets[bucket] / bucket_targets[bucket]
                + (available - quotas[cell]) / max(sum(availability.values()), 1)
            )
            choices.append((score, cell))
        if not choices:
            raise ValueError("configured source and block-bucket margins are infeasible")
        _, cell = max(choices, key=lambda item: (item[0], tuple(reversed(item[1]))))
        quotas[cell] += 1
        remaining_sources[cell[0]] -= 1
        remaining_buckets[cell[1]] -= 1
    if any(remaining_sources.values()) or any(remaining_buckets.values()):
        raise ValueError("source and block-bucket allocation did not close exactly")
    return quotas


def select_sample(
    rows: list[dict[str, Any]],
    block_bucket_counts: dict[str, dict[str, int]],
    source_counts: dict[str, dict[str, int]],
    *,
    seed: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    rows_by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        rows_by_domain[str(row["domain"])].append(row)

    for domain, bucket_targets in block_bucket_counts.items():
        if set(bucket_targets) != set(BLOCK_BUCKETS):
            raise ValueError(f"{domain} must configure all block buckets: {BLOCK_BUCKETS}")
        if domain not in source_counts:
            raise ValueError(f"missing source targets for {domain}")
        cell_quotas = allocate_source_bucket_quotas(
            rows_by_domain[domain],
            source_counts[domain],
            bucket_targets,
        )
        for (source, bucket), target in sorted(cell_quotas.items()):
            candidates = [
                row
                for row in rows_by_domain[domain]
                if str(row["source_dataset"]) == source and block_count_bucket(row) == bucket
            ]
            cells: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
            for row in candidates:
                cells[within_bucket_stratum(row)].append(row)
            quotas = proportional_quotas(
                Counter({cell: len(cell_rows) for cell, cell_rows in cells.items()}),
                target,
            )
            for cell, quota in sorted(quotas.items()):
                ordered = sorted(
                    cells[cell],
                    key=lambda row: (
                        stable_hash(seed, f"{domain}:{bucket}:{row['id']}"),
                        str(row["id"]),
                    ),
                )
                selected.extend(ordered[:quota])

    expected = sum(sum(bucket.values()) for bucket in block_bucket_counts.values())
    selected = sorted(selected, key=lambda row: (stable_hash(seed, str(row["id"])), str(row["id"])))
    ids = [str(row.get("id") or "") for row in selected]
    if len(selected) != expected or "" in ids or len(ids) != len(set(ids)):
        raise ValueError("sample selection did not produce the requested number of unique IDs")
    actual = Counter((str(row["domain"]), block_count_bucket(row)) for row in selected)
    configured = Counter(
        {
            (domain, bucket): int(target)
            for domain, bucket_targets in block_bucket_counts.items()
            for bucket, target in bucket_targets.items()
        }
    )
    if actual != configured:
        raise ValueError(f"sample domain/block distribution mismatch: {dict(actual)}")
    actual_sources = Counter((str(row["domain"]), str(row["source_dataset"])) for row in selected)
    configured_sources = Counter(
        {
            (domain, source): int(target)
            for domain, targets in source_counts.items()
            for source, target in targets.items()
        }
    )
    if actual_sources != configured_sources:
        raise ValueError(f"sample domain/source distribution mismatch: {dict(actual_sources)}")
    return selected


def hidden_row(row: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(row)
    value["panel"] = str(row["domain"])
    value["evaluation"] = {
        "panel": str(row["domain"]),
        "sampling_stratum": {
            "source_dataset": str(row["source_dataset"]),
            "source_topic": str(row.get("source_topic") or "unknown"),
            "block_count_bucket": block_count_bucket(row),
            "atom_count_bucket": atom_count_bucket(row),
            "hard_a_family": hard_a_family(row),
            "release_admission": admission_decision(row),
        },
    }
    return value


def distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "domains": dict(sorted(Counter(str(row["domain"]) for row in rows).items())),
        "block_counts": dict(
            sorted(Counter(str(len(row.get("memory_blocks") or [])) for row in rows).items())
        ),
        "block_count_buckets": dict(sorted(Counter(block_count_bucket(row) for row in rows).items())),
        "atom_count_buckets": dict(sorted(Counter(atom_count_bucket(row) for row in rows).items())),
        "sources": dict(sorted(Counter(str(row["source_dataset"]) for row in rows).items())),
        "topics": dict(
            sorted(Counter(str(row.get("source_topic") or "unknown") for row in rows).items())
        ),
        "hard_a_families": dict(sorted(Counter(hard_a_family(row) for row in rows).items())),
        "release_admission": dict(sorted(Counter(admission_decision(row) for row in rows).items())),
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


def build_release(input_path: Path, output_dir: Path, config_path: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    expected_source_hash = str((config.get("source_inputs") or {}).get("benchmark_sha256") or "")
    actual_source_hash = sha256_file(input_path)
    if expected_source_hash != actual_source_hash:
        raise ValueError(
            f"benchmark hash mismatch: expected={expected_source_hash}, actual={actual_source_hash}"
        )

    rows = list(iter_jsonl(input_path))
    ids = [str(row.get("id") or "") for row in rows]
    if len(rows) != int(config["source_count"]) or "" in ids or len(ids) != len(set(ids)):
        raise ValueError("source benchmark does not match configured count and uniqueness")
    block_bucket_counts = {
        str(domain): {str(bucket): int(target) for bucket, target in targets.items()}
        for domain, targets in config["block_bucket_counts"].items()
    }
    source_counts = {
        str(domain): {str(source): int(target) for source, target in targets.items()}
        for domain, targets in config["source_counts"].items()
    }
    if sum(sum(targets.values()) for targets in block_bucket_counts.values()) != int(
        config["sample_count"]
    ):
        raise ValueError("configured block bucket counts must sum to sample_count")
    if sum(sum(targets.values()) for targets in source_counts.values()) != int(config["sample_count"]):
        raise ValueError("configured source counts must sum to sample_count")

    selected = select_sample(
        rows,
        block_bucket_counts,
        source_counts,
        seed=int(config["seed"]),
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
        "configured_block_bucket_counts": block_bucket_counts,
        "configured_source_counts": source_counts,
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
        description="Lock a deterministic 100-record v2.2 long-tail sample for Codex evaluation."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = build_release(args.input.resolve(), args.output_dir.resolve(), args.config.resolve())
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
