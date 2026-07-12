from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(seed: int, value: str) -> str:
    return hashlib.sha256(f"{seed}:{value}".encode("utf-8")).hexdigest()


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else Path.open
    kwargs = {"mode": "rt", "encoding": "utf-8"} if path.suffix == ".gz" else {"mode": "r", "encoding": "utf-8"}
    with opener(path, **kwargs) as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def load_release_records(release_dir: Path) -> tuple[list[dict[str, Any]], str]:
    manifest = json.loads((release_dir / "manifest.json").read_text(encoding="utf-8"))
    shard_entries = list(manifest["files"]["data_shards"])
    shard_entries.sort(key=lambda entry: entry["path"])
    source_digest = hashlib.sha256()
    records: list[dict[str, Any]] = []
    for entry in shard_entries:
        path = release_dir / entry["path"]
        if sha256_file(path) != entry["sha256"]:
            raise ValueError(f"release shard hash mismatch: {entry['path']}")
        with gzip.open(path, "rb") as handle:
            for line in handle:
                source_digest.update(line)
                if line.strip():
                    records.append(json.loads(line))
    source_sha = source_digest.hexdigest()
    expected_sha = manifest["source_sha256"]
    if source_sha != expected_sha:
        raise ValueError(f"release source hash mismatch: {source_sha} != {expected_sha}")
    expected_count = manifest["counts"]["samples"]
    if len(records) != expected_count:
        raise ValueError(f"release record count mismatch: {len(records)} != {expected_count}")
    ids = [str(row["id"]) for row in records]
    if len(ids) != len(set(ids)):
        raise ValueError("release contains duplicate sample IDs")
    return records, source_sha
