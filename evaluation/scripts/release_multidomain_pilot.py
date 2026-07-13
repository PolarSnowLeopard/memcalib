#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation.common import display_path, iter_jsonl, sha256_file, write_json, write_jsonl


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PILOT = ROOT / "release" / "memcalib-multidomain-pilot-v0.2" / "data"
DEFAULT_OUTPUT = ROOT / "evaluation" / "releases" / "memcalib-ordered-v2.1-multidomain-pilot-200"
DEFAULT_CONFIG = ROOT / "evaluation" / "configs" / "memcalib-ordered-v2.1-multidomain-pilot-200.json"
SCHEMA_VERSION = "memcalib-multidomain-evaluation-release-v1"


def model_facing_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "domain": str(row["domain"]),
        "panel": str(row["domain"]),
        "source_dataset": str(row["source_dataset"]),
        "source_topic": str(row.get("source_topic") or "unknown"),
        "question": str(row["question"]),
        "memory_blocks": [
            {
                "parent_memory_id": str(block["parent_memory_id"]),
                "memory_text": str(block.get("memory_text") or block.get("text") or ""),
            }
            for block in row.get("memory_blocks") or []
        ],
    }


def hidden_row(row: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(row)
    value["panel"] = str(row["domain"])
    return value


def ordered_id_sha256(rows: list[dict[str, Any]]) -> str:
    payload = "\n".join(str(row["id"]) for row in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_gzip(path: Path, source: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as input_handle, path.open("wb") as raw_output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_output, mtime=0) as output_handle:
            for chunk in iter(lambda: input_handle.read(1024 * 1024), b""):
                output_handle.write(chunk)


def artifact(path: Path, *, rows: int | None = None) -> dict[str, Any]:
    value = {
        "path": display_path(path, ROOT),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    if rows is not None:
        value["rows"] = rows
    return value


def build_release(general_path: Path, coding_path: Path, output_dir: Path, config_path: Path | None = None) -> dict[str, Any]:
    source_rows = [*iter_jsonl(general_path), *iter_jsonl(coding_path)]
    ids = [str(row.get("id") or "") for row in source_rows]
    if len(source_rows) != 200:
        raise ValueError(f"expected 200 source rows, found {len(source_rows)}")
    if "" in ids or len(ids) != len(set(ids)):
        raise ValueError("source sample IDs must be non-empty and unique")
    domains = Counter(str(row.get("domain") or "") for row in source_rows)
    if domains != Counter({"general": 100, "coding": 100}):
        raise ValueError(f"unexpected domain distribution: {dict(domains)}")

    hidden = [hidden_row(row) for row in source_rows]
    facing = [model_facing_row(row) for row in source_rows]
    for row in facing:
        if not row["question"] or not row["memory_blocks"]:
            raise ValueError(f"model-facing row is incomplete: {row['id']}")
        if any(not block["memory_text"] for block in row["memory_blocks"]):
            raise ValueError(f"model-facing row contains an empty memory: {row['id']}")

    output_dir.mkdir(parents=True, exist_ok=True)
    hidden_path = output_dir / "hidden-evaluation.jsonl"
    facing_path = output_dir / "model-facing.jsonl"
    write_jsonl(hidden_path, hidden)
    write_jsonl(facing_path, facing)
    write_gzip(output_dir / "hidden-evaluation.jsonl.gz", hidden_path)
    write_gzip(output_dir / "model-facing.jsonl.gz", facing_path)
    (output_dir / "sample-ids.txt").write_text("".join(f"{sample_id}\n" for sample_id in ids), encoding="utf-8")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "release": "memcalib-ordered-v2.1-multidomain-pilot-200",
        "status": "internal_diagnostic",
        "samples": len(source_rows),
        "domains": dict(sorted(domains.items())),
        "ordered_id_sha256": ordered_id_sha256(source_rows),
        "sources": [
            {"path": display_path(general_path, ROOT), "sha256": sha256_file(general_path), "rows": 100},
            {"path": display_path(coding_path, ROOT), "sha256": sha256_file(coding_path), "rows": 100},
        ],
        "artifacts": {
            "hidden": artifact(hidden_path, rows=200),
            "hidden_gzip": artifact(output_dir / "hidden-evaluation.jsonl.gz"),
            "model_facing": artifact(facing_path, rows=200),
            "model_facing_gzip": artifact(output_dir / "model-facing.jsonl.gz"),
            "sample_ids": artifact(output_dir / "sample-ids.txt", rows=200),
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
            "hidden_only": ["source_answer", "memories", "usage_rubric", "lineage", "qc"],
        },
    }
    if config_path:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        expected = config.get("source_inputs") or {}
        actual = {
            "general_sha256": sha256_file(general_path),
            "coding_sha256": sha256_file(coding_path),
            "hidden_evaluation_sha256": sha256_file(hidden_path),
            "model_facing_sha256": sha256_file(facing_path),
        }
        mismatches = {
            key: {"expected": expected.get(key), "actual": value}
            for key, value in actual.items()
            if expected.get(key) != value
        }
        if mismatches:
            raise ValueError(f"evaluation config hash mismatch: {mismatches}")
        manifest["config"] = {"path": display_path(config_path, ROOT), "sha256": sha256_file(config_path)}
    write_json(output_dir / "release-manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Lock the 100+100 multi-domain pilot as an evaluation release.")
    parser.add_argument("--general", type=Path, default=DEFAULT_PILOT / "general-hidden-construction-100.jsonl")
    parser.add_argument("--coding", type=Path, default=DEFAULT_PILOT / "coding-hidden-construction-100.jsonl")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    manifest = build_release(
        args.general.resolve(),
        args.coding.resolve(),
        args.output_dir.resolve(),
        args.config.resolve() if args.config else None,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
