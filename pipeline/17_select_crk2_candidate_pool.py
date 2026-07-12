#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from utils import iter_jsonl, load_json, resolve_config_path, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR / "config.json"
RAW_SELECTOR_PATH = SCRIPT_DIR / "15_select_crk2_raw_seeds.py"
SCHEMA_VERSION = "crk2-source-candidate-pool-v1"


def load_raw_selector():
    spec = importlib.util.spec_from_file_location("crk2_raw_seed_selector", RAW_SELECTOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RAW_SELECTOR = load_raw_selector()


def file_sha256(path: Path) -> str:
    return RAW_SELECTOR.file_sha256(path)


def verify_parent_manifest(eligible_path: Path, parent_manifest_path: Path) -> dict[str, Any]:
    parent = load_json(parent_manifest_path)
    expected = str((((parent.get("outputs") or {}).get("eligible_pool") or {}).get("sha256") or ""))
    actual = file_sha256(eligible_path)
    if not expected or actual != expected:
        raise ValueError("eligible pool hash does not match parent manifest")
    return parent


def verify_current_lineage(parent: dict[str, Any], config_path: Path) -> None:
    implementation = parent.get("implementation") or {}
    expected_config = str(implementation.get("config_sha256") or "")
    expected_selector = str(implementation.get("selector_sha256") or "")
    if not expected_config or expected_config != file_sha256(config_path):
        raise ValueError("current config hash does not match parent manifest")
    if not expected_selector or expected_selector != file_sha256(RAW_SELECTOR_PATH):
        raise ValueError("current raw selector hash does not match parent manifest")


def select_candidate_pool(
    eligible_rows: list[dict[str, Any]],
    per_source: int,
    seed: int,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    if per_source <= 0:
        raise ValueError("per_source must be positive")
    source_counts = Counter(str(row.get("source_dataset") or "unknown") for row in eligible_rows)
    if not source_counts:
        raise ValueError("eligible pool is empty")
    for source, count in sorted(source_counts.items()):
        if count < per_source:
            raise ValueError(f"{source} has {count} eligible rows; requires {per_source}")
    target = per_source * len(source_counts)
    selected = RAW_SELECTOR.select_stratified(eligible_rows, target=target, seed=seed, config=config)
    selected_counts = Counter(str(row.get("source_dataset") or "unknown") for row in selected)
    expected_counts = {source: per_source for source in source_counts}
    if dict(selected_counts) != expected_counts:
        raise ValueError(f"selected source quotas do not match: expected={expected_counts}, actual={dict(selected_counts)}")
    return selected


def distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    source_topic: dict[str, Counter[str]] = defaultdict(Counter)
    source_complexity: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        source = str(row.get("source_dataset") or "unknown")
        topic = str(row.get("topic") or "general_other")
        complexity = str((row.get("raw_selection") or {}).get("seed_complexity") or "unknown")
        source_topic[source][topic] += 1
        source_complexity[source][complexity] += 1
    return {
        "source_dataset": dict(sorted(Counter(str(row.get("source_dataset") or "unknown") for row in rows).items())),
        "topic": dict(sorted(Counter(str(row.get("topic") or "general_other") for row in rows).items())),
        "seed_complexity": dict(
            sorted(
                Counter(
                    str((row.get("raw_selection") or {}).get("seed_complexity") or "unknown")
                    for row in rows
                ).items()
            )
        ),
        "source_topic": {
            source: dict(sorted(counts.items())) for source, counts in sorted(source_topic.items())
        },
        "source_complexity": {
            source: dict(sorted(counts.items())) for source, counts in sorted(source_complexity.items())
        },
    }


def ordered_id_sha256(rows: list[dict[str, Any]]) -> str:
    ordered_ids = "\n".join(str(row.get("id") or "") for row in rows)
    return hashlib.sha256(ordered_ids.encode("utf-8")).hexdigest()


def build_candidate_manifest(
    eligible_rows: list[dict[str, Any]],
    selected_rows: list[dict[str, Any]],
    eligible_path: Path,
    parent_manifest_path: Path,
    output_path: Path,
    per_source: int,
    seed: int,
    config: dict[str, Any],
) -> dict[str, Any]:
    parent = load_json(parent_manifest_path)
    return {
        "schema_version": SCHEMA_VERSION,
        "parent": {
            "manifest_path": str(parent_manifest_path),
            "manifest_sha256": file_sha256(parent_manifest_path),
            "schema_version": str(parent.get("schema_version") or ""),
        },
        "input": {
            "eligible_path": str(eligible_path),
            "eligible_sha256": file_sha256(eligible_path),
            "eligible_rows": len(eligible_rows),
        },
        "implementation": {
            "candidate_selector_path": str(Path(__file__).resolve()),
            "candidate_selector_sha256": file_sha256(Path(__file__).resolve()),
            "raw_selector_path": str(RAW_SELECTOR_PATH.resolve()),
            "raw_selector_sha256": file_sha256(RAW_SELECTOR_PATH),
        },
        "parameters": {
            "per_source": per_source,
            "target": per_source * len({str(row.get("source_dataset") or "unknown") for row in eligible_rows}),
            "seed": seed,
            "topic_alpha": float(config.get("topic_alpha", 0.5)),
            "quality_weight_beta": float(config.get("quality_weight_beta", 2.0)),
            "complexity_targets": dict(config.get("complexity_targets") or {}),
        },
        "counts": {
            "eligible": len(eligible_rows),
            "selected": len(selected_rows),
            "unique_selected_ids": len({str(row.get("id") or "") for row in selected_rows}),
        },
        "score_summary": RAW_SELECTOR._score_summary(selected_rows),
        "distributions": distribution(selected_rows),
        "output": {
            "path": str(output_path),
            "sha256": file_sha256(output_path),
            "ordered_id_sha256": ordered_id_sha256(selected_rows),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Select an equal-per-source CRK-2 candidate pool from a fixed eligible pool.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--eligible-input", type=Path)
    parser.add_argument("--parent-manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--per-source", type=int, default=15000)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--progress-every", type=int, default=50000)
    args = parser.parse_args()

    cfg = load_json(args.config)
    output_dir = resolve_config_path(args.config, str(cfg["output_dir"]))
    eligible_path = args.eligible_input or output_dir / "crk2_raw_eligible_pool.jsonl"
    parent_manifest_path = args.parent_manifest or output_dir / "crk2_raw_selection_100.manifest.json"
    seed = int(args.seed if args.seed is not None else cfg.get("sampling", {}).get("seed", 42))
    selection_cfg = dict(cfg.get("raw_selection") or {})

    parent = verify_parent_manifest(eligible_path, parent_manifest_path)
    verify_current_lineage(parent, args.config)
    parent_count = int((parent.get("counts") or {}).get("eligible_after_dedup", 0))

    started = time.monotonic()
    eligible_rows = []
    for index, row in enumerate(iter_jsonl(eligible_path), start=1):
        eligible_rows.append(row)
        if args.progress_every > 0 and index % args.progress_every == 0:
            print(
                json.dumps({"stage": "load_eligible", "done": index, "elapsed_s": round(time.monotonic() - started, 1)}),
                flush=True,
            )
    if parent_count and len(eligible_rows) != parent_count:
        raise ValueError(f"eligible row count does not match parent manifest: {len(eligible_rows)} != {parent_count}")

    selected = select_candidate_pool(eligible_rows, args.per_source, seed, selection_cfg)
    source_count = len({str(row.get("source_dataset") or "unknown") for row in eligible_rows})
    target = args.per_source * source_count
    output_path = args.output or output_dir / f"crk2_source_candidate_pool_{target}.jsonl"
    manifest_path = args.manifest or output_dir / f"crk2_source_candidate_pool_{target}.manifest.json"
    write_jsonl(output_path, selected)
    manifest = build_candidate_manifest(
        eligible_rows=eligible_rows,
        selected_rows=selected,
        eligible_path=eligible_path,
        parent_manifest_path=parent_manifest_path,
        output_path=output_path,
        per_source=args.per_source,
        seed=seed,
        config=selection_cfg,
    )
    write_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "eligible": len(eligible_rows),
                "selected": len(selected),
                "per_source": args.per_source,
                "source_counts": manifest["distributions"]["source_dataset"],
                "output": str(output_path),
                "manifest": str(manifest_path),
                "elapsed_s": round(time.monotonic() - started, 1),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
