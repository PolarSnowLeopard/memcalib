#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from utils import iter_jsonl, load_json, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
SELECTOR_PATH = SCRIPT_DIR / "15_select_crk2_raw_seeds.py"
TARGET_PARSER_PATH = SCRIPT_DIR / "38_select_multidomain_source_admission.py"
SCHEMA_VERSION = "memcalib-multidomain-release-admission-v2"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SELECTOR = load_module(SELECTOR_PATH, "multidomain_release_selector")
TARGET_PARSER = load_module(TARGET_PARSER_PATH, "multidomain_release_target_parser")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _select(rows: list[dict[str, Any]], target: int, seed: int, config: dict[str, Any]) -> list[dict[str, Any]]:
    selected = SELECTOR.select_stratified(rows, target=target, seed=seed, config=config)
    if len(selected) != target:
        raise ValueError(f"selection returned {len(selected)} rows; expected {target}")
    return selected


def select_release(
    strict: list[dict[str, Any]],
    review: list[dict[str, Any]],
    domain_targets: dict[str, int],
    seed: int,
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    strict_ids = {str(row.get("id") or "") for row in strict}
    review_ids = {str(row.get("id") or "") for row in review}
    if "" in strict_ids | review_ids or strict_ids & review_ids:
        raise ValueError("strict/review record IDs must be non-empty and disjoint")
    admitted: list[dict[str, Any]] = []
    capacity: dict[str, dict[str, int]] = {}
    admission_states: Counter[str] = Counter()
    for domain, target in sorted(domain_targets.items()):
        strict_domain = [row for row in strict if str(row.get("domain") or "health_seed") == domain]
        review_domain = [row for row in review if str(row.get("domain") or "health_seed") == domain]
        capacity[domain] = {"strict": len(strict_domain), "review": len(review_domain)}
        strict_count = min(target, len(strict_domain))
        selected = _select(strict_domain, strict_count, seed, config) if strict_count else []
        shortfall = target - len(selected)
        if shortfall:
            if len(review_domain) < shortfall:
                raise ValueError(
                    f"domain {domain!r} cannot meet target {target}: strict={len(strict_domain)}, review={len(review_domain)}"
                )
            selected.extend(_select(review_domain, shortfall, seed + 1, config))
        for row in selected:
            output = dict(row)
            decision = str((row.get("independent_qc") or {}).get("decision") or "strict_pass")
            state = "admitted_strict" if decision == "strict_pass" else "admitted_nonblocking_review"
            admission_states[state] += 1
            output["release_admission"] = {
                "schema_version": SCHEMA_VERSION,
                "decision": state,
                "domain_target": target,
            }
            admitted.append(output)
    random.Random(f"{seed}:release-order").shuffle(admitted)
    labels: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    domains: Counter[str] = Counter()
    for row in admitted:
        domains[str(row.get("domain") or "health_seed")] += 1
        sources[str(row.get("source_dataset") or "unknown")] += 1
        labels.update(str(memory.get("u_star") or "unknown") for memory in row.get("memories", []))
    audit = {
        "capacity": capacity,
        "admission_states": dict(sorted(admission_states.items())),
        "distribution": {
            "domain": dict(sorted(domains.items())),
            "source_dataset": dict(sorted(sources.items())),
            "atomic_label": dict(sorted(labels.items())),
        },
    }
    return admitted, audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Select the final 15k multi-domain MemCalib release.")
    parser.add_argument("--strict", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--domain-target", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260715)
    args = parser.parse_args()

    strict = list(iter_jsonl(args.strict))
    review = list(iter_jsonl(args.review))
    config = load_json(args.config)
    targets = TARGET_PARSER.parse_domain_targets(args.domain_target)
    admitted, audit = select_release(
        strict,
        review,
        targets,
        args.seed,
        dict(config.get("raw_selection") or {}),
    )
    write_jsonl(args.output, admitted)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "inputs": {
            "strict": {"path": str(args.strict), "sha256": file_sha256(args.strict), "records": len(strict)},
            "review": {"path": str(args.review), "sha256": file_sha256(args.review), "records": len(review)},
        },
        "implementation": {"path": str(Path(__file__).resolve()), "sha256": file_sha256(Path(__file__).resolve())},
        "config": {"path": str(args.config), "sha256": file_sha256(args.config)},
        "parameters": {"seed": args.seed, "domain_targets": targets},
        **audit,
        "output": {"path": str(args.output), "sha256": file_sha256(args.output), "records": len(admitted)},
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
