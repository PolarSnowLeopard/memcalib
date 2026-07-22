#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from evaluation.common import display_path, iter_jsonl, sha256_file, stable_hash, write_json


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = (
    ROOT
    / "pipeline/data/multidomain/full-v2/revision-composite-blocks-v23/release"
    / "memcalib_v23_multidomain_benchmark_15000.jsonl"
)
DEFAULT_LOCKED_TEST = (
    ROOT / "evaluation/releases/memcalib-v23-multidomain-500-nine-models/hidden-evaluation.jsonl"
)
DEFAULT_OUTPUT = ROOT / "sft/releases/memcalib-v23-sft-12000-1500-1500"
DEFAULT_SEED = 20260722


def difficulty(row: dict[str, Any]) -> str:
    return str((row.get("composite_block_revision") or {}).get("difficulty_level") or "unassigned")


def atom_bucket(row: dict[str, Any]) -> str:
    count = len(row.get("memories") or [])
    if count <= 9:
        return "06-09"
    if count <= 14:
        return "10-14"
    if count <= 20:
        return "15-20"
    return "21+"


def label_profile(row: dict[str, Any]) -> str:
    labels = sorted({str(item.get("u_star") or "") for item in row.get("memories") or []})
    return "".join(labels) or "none"


def primary_cell(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("domain") or "unknown"), difficulty(row)


def balance_profile(row: dict[str, Any]) -> tuple[str, str]:
    actions = {str(item.get("memory_action") or "") for item in row.get("memories") or []}
    return label_profile(row), "has_correct" if "correct" in actions else "no_correct"


def secondary_cell(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("source_dataset") or "unknown"),
        atom_bucket(row),
    )


def proportional_quotas(counts: Counter[Any], total: int) -> dict[Any, int]:
    population = sum(counts.values())
    if total < 0 or total > population:
        raise ValueError(f"invalid target {total} for population {population}")
    if total == 0:
        return {key: 0 for key in counts}
    exact = {key: total * count / population for key, count in counts.items()}
    quotas = {key: math.floor(value) for key, value in exact.items()}
    remaining = total - sum(quotas.values())
    order = sorted(counts, key=lambda key: (-(exact[key] - quotas[key]), key))
    for key in order[:remaining]:
        quotas[key] += 1
    return quotas


def _profile_quotas(
    rows: list[dict[str, Any]], target: int, fixed_ids: set[str]
) -> dict[tuple[str, str], int]:
    counts = Counter(balance_profile(row) for row in rows)
    quotas = proportional_quotas(counts, target)
    fixed = Counter(balance_profile(row) for row in rows if str(row["id"]) in fixed_ids)
    for key, count in fixed.items():
        quotas[key] = max(quotas[key], count)

    while sum(quotas.values()) > target:
        candidates = [key for key in quotas if quotas[key] > fixed[key]]
        if not candidates:
            raise ValueError("fixed profile counts exceed the cell target")
        key = max(candidates, key=lambda value: (quotas[value] - target * counts[value] / len(rows), value))
        quotas[key] -= 1
    while sum(quotas.values()) < target:
        candidates = [key for key in quotas if quotas[key] < counts[key]]
        if not candidates:
            raise ValueError("profile pools exhausted before reaching the cell target")
        key = max(candidates, key=lambda value: (target * counts[value] / len(rows) - quotas[value], value))
        quotas[key] += 1
    return quotas


def _select_profile(
    rows: list[dict[str, Any]],
    target: int,
    *,
    seed: int,
    fixed_ids: set[str] | None = None,
) -> set[str]:
    fixed_ids = set(fixed_ids or set())
    row_ids = {str(row["id"]) for row in rows}
    if not fixed_ids.issubset(row_ids):
        raise ValueError("fixed IDs are not contained in the selection cell")
    if len(fixed_ids) > target:
        raise ValueError(f"fixed selection exceeds target: {len(fixed_ids)} > {target}")

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if str(row["id"]) not in fixed_ids:
            groups[secondary_cell(row)].append(row)
    for key, values in groups.items():
        values.sort(key=lambda row: stable_hash(seed, f"{key}:{row['id']}"), reverse=True)

    population_counts = Counter(secondary_cell(row) for row in rows)
    desired = {key: target * count / len(rows) for key, count in population_counts.items()}
    current = Counter(secondary_cell(row) for row in rows if str(row["id"]) in fixed_ids)
    selected = set(fixed_ids)

    while len(selected) < target:
        available = [key for key, values in groups.items() if values]
        if not available:
            raise ValueError("selection pool exhausted before reaching target")
        key = min(
            available,
            key=lambda value: (
                -(desired[value] - current[value]),
                stable_hash(seed + len(selected), repr(value)),
            ),
        )
        row = groups[key].pop()
        selected.add(str(row["id"]))
        current[key] += 1
    return selected


def select_cell(
    rows: list[dict[str, Any]],
    target: int,
    *,
    seed: int,
    fixed_ids: set[str] | None = None,
) -> set[str]:
    fixed_ids = set(fixed_ids or set())
    by_profile: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_profile[balance_profile(row)].append(row)
    quotas = _profile_quotas(rows, target, fixed_ids)
    selected: set[str] = set()
    for index, (key, values) in enumerate(sorted(by_profile.items())):
        value_ids = {str(row["id"]) for row in values}
        selected.update(
            _select_profile(
                values,
                quotas[key],
                seed=seed + index,
                fixed_ids=fixed_ids.intersection(value_ids),
            )
        )
    if len(selected) != target:
        raise ValueError("profile selection did not reach the cell target")
    return selected


def select_partition(
    rows: list[dict[str, Any]],
    total: int,
    *,
    seed: int,
    fixed_ids: set[str] | None = None,
) -> set[str]:
    fixed_ids = set(fixed_ids or set())
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_domain[str(row.get("domain") or "unknown")].append(row)
    domain_quotas = proportional_quotas(Counter({key: len(values) for key, values in by_domain.items()}), total)
    selected: set[str] = set()
    for domain_index, (domain, domain_rows) in enumerate(sorted(by_domain.items())):
        by_level: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in domain_rows:
            by_level[difficulty(row)].append(row)
        level_quotas = proportional_quotas(
            Counter({key: len(values) for key, values in by_level.items()}), domain_quotas[domain]
        )
        for level_index, (level, values) in enumerate(sorted(by_level.items())):
            value_ids = {str(row["id"]) for row in values}
            selected.update(
                select_cell(
                    values,
                    level_quotas[level],
                    seed=seed + domain_index * 10 + level_index,
                    fixed_ids=fixed_ids.intersection(value_ids),
                )
            )
    if len(selected) != total or not fixed_ids.issubset(selected):
        raise ValueError("partition selection failed integrity checks")
    return selected


def write_ids(path: Path, ordered_ids: Iterable[str]) -> None:
    values = list(ordered_ids)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{value}\n" for value in values), encoding="utf-8")


def distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    atoms = [len(row.get("memories") or []) for row in rows]
    return {
        "records": len(rows),
        "domain": dict(sorted(Counter(str(row.get("domain") or "unknown") for row in rows).items())),
        "difficulty": dict(sorted(Counter(difficulty(row) for row in rows).items())),
        "domain_difficulty": {
            f"{domain}:{level}": count
            for (domain, level), count in sorted(Counter(primary_cell(row) for row in rows).items())
        },
        "source_dataset": dict(
            sorted(Counter(str(row.get("source_dataset") or "unknown") for row in rows).items())
        ),
        "atom_bucket": dict(sorted(Counter(atom_bucket(row) for row in rows).items())),
        "label_profile": dict(sorted(Counter(label_profile(row) for row in rows).items())),
        "records_with_correct": sum(
            any(str(item.get("memory_action") or "") == "correct" for item in row.get("memories") or [])
            for row in rows
        ),
        "atoms": {
            "min": min(atoms) if atoms else 0,
            "mean": sum(atoms) / len(atoms) if atoms else 0,
            "max": max(atoms) if atoms else 0,
        },
    }


def build_split(
    rows: list[dict[str, Any]], locked_test_ids: set[str], *, seed: int
) -> tuple[dict[str, set[str]], dict[str, Any]]:
    ids = [str(row["id"]) for row in rows]
    if len(ids) != 15000 or len(ids) != len(set(ids)):
        raise ValueError("SFT split requires exactly 15,000 unique records")
    if len(locked_test_ids) != 500 or not locked_test_ids.issubset(set(ids)):
        raise ValueError("locked test must contain exactly 500 source record IDs")

    test_ids = select_partition(rows, 1500, seed=seed, fixed_ids=locked_test_ids)
    remaining_after_test = [row for row in rows if str(row["id"]) not in test_ids]
    dev_ids = select_partition(remaining_after_test, 1500, seed=seed + 1)
    train_ids = set(ids).difference(test_ids, dev_ids)
    train_rows = [row for row in rows if str(row["id"]) in train_ids]
    pilot_ids = select_partition(train_rows, 500, seed=seed + 2)

    splits = {"train": train_ids, "dev": dev_ids, "test": test_ids, "pilot_train": pilot_ids}
    if len(train_ids) != 12000 or len(dev_ids) != 1500 or len(test_ids) != 1500 or len(pilot_ids) != 500:
        raise ValueError("unexpected split sizes")
    if train_ids & dev_ids or train_ids & test_ids or dev_ids & test_ids:
        raise ValueError("train/dev/test overlap detected")
    if not pilot_ids.issubset(train_ids) or not locked_test_ids.issubset(test_ids):
        raise ValueError("pilot or locked test containment failed")

    report = {
        name: distribution([row for row in rows if str(row["id"]) in selected])
        for name, selected in splits.items()
    }
    return splits, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--locked-test", type=Path, default=DEFAULT_LOCKED_TEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()

    rows = list(iter_jsonl(args.input))
    locked_rows = list(iter_jsonl(args.locked_test))
    locked_ids = {str(row["id"]) for row in locked_rows}
    splits, report = build_split(rows, locked_ids, seed=args.seed)
    ordered_ids = [str(row["id"]) for row in rows]

    artifacts = {}
    for name, selected in splits.items():
        path = args.output_dir / f"{name}-ids.txt"
        write_ids(path, (value for value in ordered_ids if value in selected))
        artifacts[path.name] = {"rows": len(selected), "sha256": sha256_file(path)}

    manifest = {
        "schema_version": "memcalib-v23-sft-split-v1",
        "seed": args.seed,
        "source": {
            "path": display_path(args.input, ROOT),
            "rows": len(rows),
            "sha256": sha256_file(args.input),
        },
        "locked_existing_test": {
            "path": display_path(args.locked_test, ROOT),
            "rows": len(locked_ids),
            "sha256": sha256_file(args.locked_test),
            "contained_in_test": True,
        },
        "counts": {name: len(values) for name, values in splits.items()},
        "distributions": report,
        "artifacts": artifacts,
    }
    write_json(args.output_dir / "split-manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
