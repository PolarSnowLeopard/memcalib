#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from utils import iter_jsonl, load_json, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
SELECTOR_PATH = SCRIPT_DIR / "15_select_crk2_raw_seeds.py"
SCHEMA_VERSION = "memcalib-multidomain-source-admission-v2"


def load_selector():
    spec = importlib.util.spec_from_file_location("multidomain_source_admission_selector", SELECTOR_PATH)
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


def parse_domain_targets(values: list[str]) -> dict[str, int]:
    targets: dict[str, int] = {}
    for value in values:
        domain, separator, count_text = value.rpartition("=")
        if not separator or not domain or not count_text.isdigit():
            raise ValueError(f"invalid domain target {value!r}; expected DOMAIN=COUNT")
        count = int(count_text)
        if count <= 0 or domain in targets:
            raise ValueError(f"domain target must be unique and positive: {value!r}")
        targets[domain] = count
    if not targets:
        raise ValueError("at least one domain target is required")
    return targets


def distribution(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    return {
        "domain": dict(sorted(Counter(str(row.get("domain") or "unknown") for row in rows).items())),
        "source_dataset": dict(sorted(Counter(str(row.get("source_dataset") or "unknown") for row in rows).items())),
        "topic": dict(sorted(Counter(str(row.get("topic") or "unknown") for row in rows).items())),
    }


def select_admitted(
    records: list[dict[str, Any]],
    domain_targets: dict[str, int],
    seed: int,
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    admitted: list[dict[str, Any]] = []
    capacity: dict[str, int] = {}
    for domain, target in sorted(domain_targets.items()):
        strict = [
            row
            for row in records
            if str(row.get("domain") or "") == domain
            and str((row.get("semantic_qc") or {}).get("state") or "") == "strict_pass"
        ]
        capacity[domain] = len(strict)
        if len(strict) < target:
            raise ValueError(f"domain {domain!r} has {len(strict)} strict source records; requires {target}")
        selected = SELECTOR.select_stratified(strict, target=target, seed=seed, config=config)
        if len(selected) != target:
            raise ValueError(f"domain {domain!r} selection returned {len(selected)} rows; expected {target}")
        for row in selected:
            output = dict(row)
            output["semantic_admission"] = {
                "schema_version": SCHEMA_VERSION,
                "decision": "admitted_strict",
                "domain_target": target,
            }
            admitted.append(output)
    return admitted, {"strict_capacity": capacity, "distribution": distribution(admitted)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Select strict source-QA records for multi-domain v2 construction.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--domain-target", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260715)
    args = parser.parse_args()

    domain_targets = parse_domain_targets(args.domain_target)
    config = load_json(args.config)
    records = list(iter_jsonl(args.input))
    admitted, audit = select_admitted(
        records,
        domain_targets,
        args.seed,
        dict(config.get("raw_selection") or {}),
    )
    write_jsonl(args.output, admitted)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "input": {"path": str(args.input), "sha256": file_sha256(args.input), "records": len(records)},
        "implementation": {"path": str(Path(__file__).resolve()), "sha256": file_sha256(Path(__file__).resolve())},
        "config": {"path": str(args.config), "sha256": file_sha256(args.config)},
        "parameters": {"seed": args.seed, "domain_targets": domain_targets},
        **audit,
        "output": {"path": str(args.output), "sha256": file_sha256(args.output), "records": len(admitted)},
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
