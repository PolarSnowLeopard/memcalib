#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_EXPECTED = {
    "samples": 15528,
    "parent_memories": 56044,
    "atomic_memories": 78734,
    "source_sha256": "1cfd0334255266e6b8d4c234c615ade42b40c91bb86cb7c061a285261c363cb4",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_release_path(release_dir: Path, relative_path: str) -> Path:
    path = (release_dir / relative_path).resolve()
    try:
        path.relative_to(release_dir.resolve())
    except ValueError as exc:
        raise ValueError(f"release path escapes root: {relative_path}") from exc
    return path


def verify_file_entry(release_dir: Path, entry: dict[str, Any]) -> Path:
    path = resolve_release_path(release_dir, str(entry.get("path") or ""))
    if not path.is_file():
        raise ValueError(f"release file missing: {entry.get('path')}")
    actual_bytes = path.stat().st_size
    if actual_bytes != int(entry.get("bytes", -1)):
        raise ValueError(f"bytes mismatch for {entry.get('path')}: expected {entry.get('bytes')}, got {actual_bytes}")
    actual_sha256 = sha256_file(path)
    if actual_sha256 != entry.get("sha256"):
        raise ValueError(
            f"sha256 mismatch for {entry.get('path')}: expected {entry.get('sha256')}, got {actual_sha256}"
        )
    return path


def _final_counts(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "samples": state["samples"],
        "unique_sample_ids": len(state["sample_ids"]),
        "parent_memories": state["parent_memories"],
        "atomic_memories": state["atomic_memories"],
        "mixed_parents": state["mixed_parents"],
        "labels": dict(sorted(state["labels"].items())),
        "sources": dict(sorted(state["sources"].items())),
        "topics": dict(sorted(state["topics"].items())),
        "hard_a_families": dict(sorted(state["hard_a_families"].items())),
        "memory_types": dict(sorted(state["memory_types"].items())),
    }


def verify_release(release_dir: Path, expected: dict[str, Any] | None = DEFAULT_EXPECTED) -> dict[str, Any]:
    release_dir = release_dir.resolve()
    manifest_path = release_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "memcalib-release-manifest-v1":
        raise ValueError(f"unsupported schema_version: {manifest.get('schema_version')}")

    files = manifest.get("files") or {}
    shard_entries = files.get("data_shards") or []
    if not shard_entries:
        raise ValueError("manifest contains no data shards")
    shard_paths = [verify_file_entry(release_dir, entry) for entry in shard_entries]
    verify_file_entry(release_dir, files.get("review_sample") or {})
    for entry in (files.get("artifacts") or {}).values():
        verify_file_entry(release_dir, entry)

    reconstructed_sha256 = hashlib.sha256()
    state = {
        "samples": 0,
        "sample_ids": set(),
        "parent_memories": 0,
        "atomic_memories": 0,
        "mixed_parents": 0,
        "labels": Counter(),
        "sources": Counter(),
        "topics": Counter(),
        "hard_a_families": Counter(),
        "memory_types": Counter(),
    }
    for shard_entry, shard_path in zip(shard_entries, shard_paths):
        shard_rows = 0
        with gzip.open(shard_path, "rb") as handle:
            for line in handle:
                if not line.strip():
                    continue
                reconstructed_sha256.update(line)
                row = json.loads(line)
                sample_id = str(row.get("id") or "")
                if not sample_id:
                    raise ValueError(f"missing sample id in {shard_entry['path']}")
                if sample_id in state["sample_ids"]:
                    raise ValueError(f"duplicate sample id: {sample_id}")
                state["sample_ids"].add(sample_id)
                state["samples"] += 1
                shard_rows += 1
                state["sources"][str(row.get("source_dataset") or "unknown")] += 1
                state["topics"][str(row.get("source_topic") or "unknown")] += 1
                blocks = row.get("memory_blocks") or []
                memories = row.get("memories") or []
                state["parent_memories"] += len(blocks)
                state["atomic_memories"] += len(memories)
                state["mixed_parents"] += sum(block.get("parent_label_mode") == "mixed" for block in blocks)
                for memory in memories:
                    state["labels"][str(memory.get("u_star") or "unknown")] += 1
                    if memory.get("hard_a_family"):
                        state["hard_a_families"][str(memory["hard_a_family"])] += 1
                    state["memory_types"][str(memory.get("memory_type") or "unknown")] += 1
        if shard_rows != int(shard_entry.get("rows", -1)):
            raise ValueError(
                f"row count mismatch for {shard_entry['path']}: expected {shard_entry.get('rows')}, got {shard_rows}"
            )

    counts = _final_counts(state)
    if counts != manifest.get("counts"):
        raise ValueError("recomputed benchmark counts do not match manifest")
    reconstructed = reconstructed_sha256.hexdigest()
    if reconstructed != manifest.get("source_sha256"):
        raise ValueError(
            f"reconstructed source sha256 mismatch: expected {manifest.get('source_sha256')}, got {reconstructed}"
        )
    if expected is not None:
        for key in ("samples", "parent_memories", "atomic_memories"):
            if counts[key] != expected[key]:
                raise ValueError(f"expected {key}={expected[key]}, got {counts[key]}")
        if reconstructed != expected["source_sha256"]:
            raise ValueError(f"expected source_sha256={expected['source_sha256']}, got {reconstructed}")
    return {
        "status": "passed",
        "release_dir": str(release_dir),
        "source_sha256": reconstructed,
        "counts": counts,
        "verified_files": len(shard_entries) + 1 + len(files.get("artifacts") or {}),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a packaged MemCalib release.")
    parser.add_argument("--release-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify_release(args.release_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
