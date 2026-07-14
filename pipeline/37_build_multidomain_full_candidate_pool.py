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
SCHEMA_VERSION = "memcalib-multidomain-full-candidate-pool-v1"


def load_selector():
    spec = importlib.util.spec_from_file_location("multidomain_full_pool_selector", SELECTOR_PATH)
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


def _eligible(row: dict[str, Any]) -> bool:
    return bool((row.get("raw_selection") or {}).get("eligible"))


def distribution(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    return {
        "domain": dict(sorted(Counter(str(row.get("domain") or "unknown") for row in rows).items())),
        "source_dataset": dict(sorted(Counter(str(row.get("source_dataset") or "unknown") for row in rows).items())),
        "topic": dict(sorted(Counter(str(row.get("topic") or "unknown") for row in rows).items())),
        "seed_complexity": dict(
            sorted(
                Counter(
                    str((row.get("raw_selection") or {}).get("seed_complexity") or "unknown") for row in rows
                ).items()
            )
        ),
    }


def build_pool(
    rows: list[dict[str, Any]],
    source_quotas: dict[str, int],
    seed: int,
    selection_config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ids = [str(row.get("id") or "") for row in rows]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("input candidate IDs must be non-empty and unique")
    observed_sources = {str(row.get("source_dataset") or "") for row in rows}
    missing_sources = sorted(set(source_quotas) - observed_sources)
    if missing_sources:
        raise ValueError(f"quota sources missing from inputs: {missing_sources}")

    deduplicated = SELECTOR.mark_duplicate_records(
        rows,
        threshold=float(selection_config["near_duplicate_jaccard"]),
    )
    eligible_rows = [row for row in deduplicated if _eligible(row)]
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    domains_by_source: dict[str, set[str]] = defaultdict(set)
    for row in eligible_rows:
        source = str(row.get("source_dataset") or "")
        by_source[source].append(row)
        domains_by_source[source].add(str(row.get("domain") or "unknown"))
    ambiguous = {source: sorted(domains) for source, domains in domains_by_source.items() if len(domains) != 1}
    if ambiguous:
        raise ValueError(f"each source must map to one domain: {ambiguous}")

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    requested_by_domain: Counter[str] = Counter()
    for source, quota in sorted(source_quotas.items()):
        domain = next(iter(domains_by_source[source]))
        requested_by_domain[domain] += quota
        source_rows = by_source[source]
        chosen = SELECTOR.select_stratified(
            source_rows,
            target=min(quota, len(source_rows)),
            seed=seed,
            config=selection_config,
        )
        for row in chosen:
            selected.append(row)
            selected_ids.add(str(row.get("id") or ""))

    selected_by_domain = Counter(str(row.get("domain") or "unknown") for row in selected)
    for domain, target in sorted(requested_by_domain.items()):
        shortfall = target - selected_by_domain[domain]
        if shortfall <= 0:
            continue
        fallback = [
            row
            for row in eligible_rows
            if str(row.get("domain") or "unknown") == domain and str(row.get("id") or "") not in selected_ids
        ]
        topup = SELECTOR.select_stratified(
            fallback,
            target=min(shortfall, len(fallback)),
            seed=seed + 1,
            config=selection_config,
        )
        for row in topup:
            selected.append(row)
            selected_ids.add(str(row.get("id") or ""))
        if len(topup) != shortfall:
            raise ValueError(f"domain {domain!r} cannot meet target {target}; short by {shortfall - len(topup)}")

    random.Random(f"{seed}:final-order").shuffle(selected)
    final_domains = Counter(str(row.get("domain") or "unknown") for row in selected)
    if final_domains != requested_by_domain:
        raise ValueError(f"domain quota mismatch: expected {dict(requested_by_domain)}, got {dict(final_domains)}")
    audit = {
        "input_records": len(rows),
        "eligible_before_cross_source_dedup": sum(1 for row in rows if _eligible(row)),
        "eligible_after_cross_source_dedup": len(eligible_rows),
        "cross_source_duplicates_removed": sum(1 for row in deduplicated if (row.get("raw_selection") or {}).get("dedup_status") == "duplicate"),
        "requested_source_quotas": dict(sorted(source_quotas.items())),
        "requested_domain_quotas": dict(sorted(requested_by_domain.items())),
        "actual_distribution": distribution(selected),
    }
    return selected, audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and lock the full General/Coding source-QA candidate pool.")
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--source-quota", action="append", required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260715)
    args = parser.parse_args()

    source_quotas = parse_source_quotas(args.source_quota)
    config = load_json(args.config)
    selection_config = dict(config.get("raw_selection") or {})
    rows: list[dict[str, Any]] = []
    input_metadata: list[dict[str, Any]] = []
    for path in args.input:
        input_rows = list(iter_jsonl(path))
        rows.extend(input_rows)
        input_metadata.append({"path": str(path), "sha256": file_sha256(path), "records": len(input_rows)})

    selected, audit = build_pool(rows, source_quotas, args.seed, selection_config)
    write_jsonl(args.output, selected)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "inputs": input_metadata,
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
