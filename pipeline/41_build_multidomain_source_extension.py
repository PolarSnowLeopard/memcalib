#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from utils import iter_jsonl, load_json, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
SELECTOR_PATH = SCRIPT_DIR / "15_select_crk2_raw_seeds.py"
SCHEMA_VERSION = "memcalib-multidomain-source-extension-v1"


def load_selector():
    spec = importlib.util.spec_from_file_location("multidomain_source_extension_selector", SELECTOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SELECTOR = load_selector()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_source_quotas(values: list[str]) -> dict[str, int]:
    quotas: dict[str, int] = {}
    for value in values:
        source, separator, count_text = value.rpartition("=")
        if not separator or not source or not count_text.isdigit():
            raise ValueError(f"invalid source quota {value!r}; expected SOURCE=COUNT")
        count = int(count_text)
        if count <= 0 or source in quotas:
            raise ValueError(f"source quota must be unique and positive: {value!r}")
        quotas[source] = count
    if not quotas:
        raise ValueError("at least one source quota is required")
    return quotas


def _unique_ids(rows: list[dict[str, Any]], label: str) -> set[str]:
    ids = [str(row.get("id") or "") for row in rows]
    if any(not row_id for row_id in ids) or len(ids) != len(set(ids)):
        raise ValueError(f"{label} IDs must be non-empty and unique")
    return set(ids)


def distribution(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    return {
        "domain": dict(sorted(Counter(str(row.get("domain") or "unknown") for row in rows).items())),
        "source_dataset": dict(
            sorted(Counter(str(row.get("source_dataset") or "unknown") for row in rows).items())
        ),
        "topic": dict(sorted(Counter(str(row.get("topic") or "unknown") for row in rows).items())),
        "seed_complexity": dict(
            sorted(
                Counter(
                    str((row.get("raw_selection") or {}).get("seed_complexity") or "unknown")
                    for row in rows
                ).items()
            )
        ),
    }


def build_extension(
    locked_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    source_quotas: dict[str, int],
    seed: int,
    selection_config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    locked_ids = _unique_ids(locked_rows, "locked pool")
    _unique_ids(candidate_rows, "candidate pool")
    new_candidates = [row for row in candidate_rows if str(row.get("id") or "") not in locked_ids]
    removed_locked_ids = len(candidate_rows) - len(new_candidates)

    protected_locked = []
    for row in locked_rows:
        copy = dict(row, raw_selection=dict(row.get("raw_selection") or {}))
        copy["raw_selection"]["eligible"] = True
        copy["raw_selection"]["quality_score"] = 1_000_000
        protected_locked.append(copy)

    combined = protected_locked + new_candidates
    deduplicated = SELECTOR.mark_duplicate_records(
        combined,
        threshold=float(selection_config["near_duplicate_jaccard"]),
    )
    deduplicated_candidates = deduplicated[len(protected_locked) :]
    eligible_candidates = [
        row for row in deduplicated_candidates if (row.get("raw_selection") or {}).get("eligible")
    ]
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligible_candidates:
        by_source[str(row.get("source_dataset") or "")].append(row)

    missing_sources = sorted(set(source_quotas) - set(by_source))
    if missing_sources:
        raise ValueError(f"quota sources missing from eligible extension candidates: {missing_sources}")

    selected: list[dict[str, Any]] = []
    for offset, (source, quota) in enumerate(sorted(source_quotas.items())):
        available = by_source[source]
        if len(available) < quota:
            raise ValueError(f"source {source!r} has {len(available)} eligible candidates; needs {quota}")
        chosen = SELECTOR.select_stratified(
            available,
            target=quota,
            seed=seed + offset,
            config=selection_config,
        )
        if len(chosen) != quota:
            raise ValueError(f"source {source!r} selected {len(chosen)} rows; expected {quota}")
        selected.extend(chosen)

    random.Random(f"{seed}:extension-final-order").shuffle(selected)
    selected_ids = [str(row.get("id") or "") for row in selected]
    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError("selected extension IDs must be unique")

    duplicate_rows = [
        row
        for row in deduplicated_candidates
        if (row.get("raw_selection") or {}).get("dedup_status") == "duplicate"
    ]
    duplicates_of_locked = sum(
        str((row.get("raw_selection") or {}).get("duplicate_of") or "") in locked_ids
        for row in duplicate_rows
    )
    audit = {
        "locked_records": len(locked_rows),
        "candidate_records": len(candidate_rows),
        "candidate_ids_already_locked": removed_locked_ids,
        "new_candidates_before_global_dedup": len(new_candidates),
        "eligible_after_global_dedup": len(eligible_candidates),
        "duplicates_removed": len(duplicate_rows),
        "duplicates_of_locked_pool": duplicates_of_locked,
        "eligible_capacity_by_source": dict(sorted((source, len(rows)) for source, rows in by_source.items())),
        "requested_source_quotas": dict(sorted(source_quotas.items())),
        "selected_distribution": distribution(selected),
    }
    return selected, audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an append-only source-QA extension around a locked pool.")
    parser.add_argument("--base", type=Path, action="append", required=True)
    parser.add_argument("--candidate", type=Path, action="append", required=True)
    parser.add_argument("--source-quota", action="append", required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260715)
    args = parser.parse_args()

    locked_rows: list[dict[str, Any]] = []
    base_inputs = []
    for path in args.base:
        rows = list(iter_jsonl(path))
        locked_rows.extend(rows)
        base_inputs.append({"path": str(path), "sha256": file_sha256(path), "records": len(rows)})
    candidate_rows: list[dict[str, Any]] = []
    candidate_inputs = []
    for path in args.candidate:
        rows = list(iter_jsonl(path))
        candidate_rows.extend(rows)
        candidate_inputs.append({"path": str(path), "sha256": file_sha256(path), "records": len(rows)})

    config = load_json(args.config)
    selected, audit = build_extension(
        locked_rows,
        candidate_rows,
        parse_source_quotas(args.source_quota),
        args.seed,
        dict(config.get("raw_selection") or {}),
    )
    write_jsonl(args.output, selected)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "base_inputs": base_inputs,
        "locked_records": len(locked_rows),
        "candidate_inputs": candidate_inputs,
        "implementation": {"path": str(Path(__file__).resolve()), "sha256": file_sha256(Path(__file__).resolve())},
        "config": {"path": str(args.config), "sha256": file_sha256(args.config)},
        "parameters": {"seed": args.seed},
        **audit,
        "output": {"path": str(args.output), "sha256": file_sha256(args.output), "records": len(selected)},
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
