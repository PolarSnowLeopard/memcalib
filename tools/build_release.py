#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import heapq
import json
import shutil
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO, Iterator


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "memcalib-release-manifest-v1"
BENCHMARK_NAME = "MemCalib"
DEFAULT_RELEASE_VERSION = "v0.1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_entry(path: Path, release_dir: Path, **extra: Any) -> dict[str, Any]:
    return {
        "path": path.relative_to(release_dir).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        **extra,
    }


@contextmanager
def deterministic_gzip_writer(path: Path) -> Iterator[BinaryIO]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw_handle:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            compresslevel=9,
            fileobj=raw_handle,
            mtime=0,
        ) as gzip_handle:
            yield gzip_handle


def shard_row_targets(total_rows: int, shard_count: int) -> list[int]:
    if shard_count <= 0:
        raise ValueError("shard_count must be positive")
    quotient, remainder = divmod(total_rows, shard_count)
    return [quotient + int(index < remainder) for index in range(shard_count)]


def write_shards(
    source: Path,
    output_dir: Path,
    shard_count: int,
    *,
    release_version: str = DEFAULT_RELEASE_VERSION,
) -> list[dict[str, Any]]:
    with source.open("rb") as count_handle:
        total_rows = sum(1 for line in count_handle if line.strip())
    targets = shard_row_targets(total_rows, shard_count)
    metadata: list[dict[str, Any]] = []
    with source.open("rb") as source_handle:
        for index, target in enumerate(targets):
            path = output_dir / f"memcalib-{release_version}-{index:05d}-of-{shard_count:05d}.jsonl.gz"
            with deterministic_gzip_writer(path) as output_handle:
                for _ in range(target):
                    line = source_handle.readline()
                    while line and not line.strip():
                        line = source_handle.readline()
                    if not line:
                        raise ValueError("source ended before declared shard boundary")
                    output_handle.write(line)
            metadata.append(
                {
                    "path": path.name,
                    "rows": target,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
        if source_handle.read(1):
            raise ValueError("source contains rows beyond declared shard boundaries")
    return metadata


def sample_features(row: dict[str, Any]) -> set[str]:
    features = {
        f"source:{row.get('source_dataset', '')}",
        f"topic:{row.get('source_topic', '')}",
    }
    audit = row.get("construction_audit") if isinstance(row.get("construction_audit"), dict) else {}
    complexity = audit.get("seed_complexity")
    source_seed = audit.get("source_seed") if isinstance(audit.get("source_seed"), dict) else {}
    raw_selection = source_seed.get("raw_selection") if isinstance(source_seed.get("raw_selection"), dict) else {}
    complexity = complexity or raw_selection.get("seed_complexity")
    if complexity:
        features.add(f"complexity:{complexity}")

    mixed = any(block.get("parent_label_mode") == "mixed" for block in row.get("memory_blocks") or [])
    features.add(f"mixed:{str(mixed).lower()}")
    for memory in row.get("memories") or []:
        label = memory.get("u_star")
        family = memory.get("hard_a_family")
        if label:
            features.add(f"label:{label}")
        if family:
            features.add(f"hard_a:{family}")
    return features


def stable_score(sample_id: str) -> int:
    digest = hashlib.sha256(f"memcalib-review-v1\0{sample_id}".encode("utf-8")).digest()
    return int.from_bytes(digest, "big")


def _push_bounded(
    heap: list[tuple[int, str, dict[str, Any], frozenset[str]]],
    row: dict[str, Any],
    features: set[str],
    limit: int,
) -> None:
    sample_id = str(row.get("id") or "")
    item = (-stable_score(sample_id), sample_id, row, frozenset(features))
    if len(heap) < limit:
        heapq.heappush(heap, item)
        return
    if item > heap[0]:
        heapq.heapreplace(heap, item)


def select_review_sample(source: Path, sample_size: int) -> list[dict[str, Any]]:
    if sample_size <= 0:
        return []
    global_heap: list[tuple[int, str, dict[str, Any], frozenset[str]]] = []
    strata: dict[str, list[tuple[int, str, dict[str, Any], frozenset[str]]]] = defaultdict(list)
    with source.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            features = sample_features(row)
            mixed = "mixed:true" in features
            stratum = f"{row.get('source_dataset', '')}\0{row.get('source_topic', '')}\0{mixed}"
            _push_bounded(strata[stratum], row, features, 4)
            _push_bounded(global_heap, row, features, max(300, sample_size * 3))

    candidates: dict[str, tuple[int, dict[str, Any], frozenset[str]]] = {}
    for heap in [global_heap, *strata.values()]:
        for neg_score, sample_id, row, features in heap:
            candidates[sample_id] = (-neg_score, row, features)

    selected: list[dict[str, Any]] = []
    covered: set[str] = set()
    remaining = dict(candidates)
    while remaining and len(selected) < sample_size:
        sample_id, (score, row, features) = min(
            remaining.items(),
            key=lambda item: (-len(item[1][2] - covered), item[1][0], item[0]),
        )
        selected.append(row)
        covered.update(features)
        del remaining[sample_id]
    return selected


def count_release_records(source: Path) -> dict[str, Any]:
    sample_ids: set[str] = set()
    labels: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    topics: Counter[str] = Counter()
    hard_a_families: Counter[str] = Counter()
    memory_types: Counter[str] = Counter()
    samples = 0
    parent_memories = 0
    atomic_memories = 0
    mixed_parents = 0
    with source.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            sample_id = str(row.get("id") or "")
            if not sample_id:
                raise ValueError(f"missing sample id at line {line_number}")
            if sample_id in sample_ids:
                raise ValueError(f"duplicate sample id: {sample_id}")
            sample_ids.add(sample_id)
            samples += 1
            sources[str(row.get("source_dataset") or "unknown")] += 1
            topics[str(row.get("source_topic") or "unknown")] += 1
            blocks = row.get("memory_blocks") or []
            memories = row.get("memories") or []
            parent_memories += len(blocks)
            atomic_memories += len(memories)
            mixed_parents += sum(block.get("parent_label_mode") == "mixed" for block in blocks)
            for memory in memories:
                labels[str(memory.get("u_star") or "unknown")] += 1
                if memory.get("hard_a_family"):
                    hard_a_families[str(memory["hard_a_family"])] += 1
                memory_types[str(memory.get("memory_type") or "unknown")] += 1
    return {
        "samples": samples,
        "unique_sample_ids": len(sample_ids),
        "parent_memories": parent_memories,
        "atomic_memories": atomic_memories,
        "mixed_parents": mixed_parents,
        "labels": dict(sorted(labels.items())),
        "sources": dict(sorted(sources.items())),
        "topics": dict(sorted(topics.items())),
        "hard_a_families": dict(sorted(hard_a_families.items())),
        "memory_types": dict(sorted(memory_types.items())),
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def build_release(
    source: Path,
    release_dir: Path,
    *,
    shard_count: int = 2,
    sample_size: int = 100,
    release_version: str = DEFAULT_RELEASE_VERSION,
    artifacts: dict[str, Path] | None = None,
    expected_source_sha256: str | None = None,
) -> dict[str, Any]:
    source = source.resolve()
    release_dir = release_dir.resolve()
    source_sha256 = sha256_file(source)
    if expected_source_sha256 and source_sha256 != expected_source_sha256:
        raise ValueError(f"source sha256 mismatch: expected {expected_source_sha256}, got {source_sha256}")
    counts = count_release_records(source)
    review_rows = select_review_sample(source, min(sample_size, counts["samples"]))

    release_dir.mkdir(parents=True, exist_ok=True)
    for generated_dir in (release_dir / "data", release_dir / "samples"):
        if generated_dir.exists():
            shutil.rmtree(generated_dir)
    manifest_path = release_dir / "manifest.json"
    if manifest_path.exists():
        manifest_path.unlink()
    data_dir = release_dir / "data"
    shard_entries = write_shards(source, data_dir, shard_count, release_version=release_version)
    for entry in shard_entries:
        entry["path"] = f"data/{entry['path']}"

    sample_path = release_dir / "samples" / f"memcalib-{release_version}-sample-{len(review_rows)}.jsonl"
    write_jsonl(sample_path, review_rows)

    artifact_entries: dict[str, dict[str, Any]] = {}
    for relative_path, input_path in sorted((artifacts or {}).items()):
        if not input_path.exists():
            raise FileNotFoundError(input_path)
        target = release_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if input_path.resolve() != target.resolve():
            shutil.copyfile(input_path, target)
        artifact_entries[relative_path] = file_entry(target, release_dir)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "benchmark": BENCHMARK_NAME,
        "release_version": release_version,
        "release_status": "private_coauthor_review",
        "source_file": source.name,
        "source_sha256": source_sha256,
        "counts": counts,
        "files": {
            "data_shards": shard_entries,
            "review_sample": file_entry(sample_path, release_dir, rows=len(review_rows)),
            "artifacts": artifact_entries,
        },
        "packaging": {
            "shard_count": shard_count,
            "sample_size": len(review_rows),
            "gzip_mtime": 0,
            "gzip_compresslevel": 9,
            "packaging_script_sha256": sha256_file(Path(__file__)),
        },
        "review_state": {
            "response_level_human_validation": "pending",
            "pii_and_sensitive_content_review": "required_before_public_release",
            "chatdoctor_redistribution_rights": "unresolved",
            "public_redistribution": "not_cleared",
        },
    }
    write_json(release_dir / "manifest.json", manifest)
    return manifest


def default_pipeline_data_dir() -> Path:
    for name in ("pipeline", "med_rpeval_pipeline"):
        candidate = REPO_ROOT / name / "data"
        if candidate.exists():
            return candidate
    return REPO_ROOT / "pipeline" / "data"


def default_artifacts(data_dir: Path, release_dir: Path) -> dict[str, Path]:
    pipeline_artifacts = {
        "review/memcalib-v0.1-audit-100.html": data_dir / "crk2_canonical_memory_benchmark_en_15528.audit_100.html",
        "reports/memcalib-v0.1-statistics.html": data_dir / "crk2_formal_benchmark_analysis_report.html",
        "statistics/benchmark-summary.json": data_dir / "crk2_canonical_memory_benchmark_en_15528.summary.json",
        "statistics/analysis-snapshot.json": data_dir / "crk2_formal_benchmark_analysis.snapshot.json",
        "provenance/generation-run.lock.json": data_dir / "crk2_canonical_generation_run_en_15577.lock.json",
        "provenance/generation-input.manifest.json": data_dir / "crk2_canonical_generation_input_en_15577.manifest.json",
        "provenance/source-admission.manifest.json": data_dir / "crk2_source_semantic_admission_15577.manifest.json",
        "provenance/source-candidate-pool.manifest.json": data_dir / "crk2_source_candidate_pool_30000.manifest.json",
    }
    targets = {"README.md": release_dir / "README.md", **pipeline_artifacts}
    return {
        relative_path: source if source.exists() else release_dir / relative_path
        for relative_path, source in targets.items()
    }


def locked_benchmark_sha256(run_lock: Path) -> str:
    data = json.loads(run_lock.read_text(encoding="utf-8"))
    return str((data.get("expected_outputs") or {}).get("benchmark_sha256") or "")


def main() -> None:
    data_dir = default_pipeline_data_dir()
    parser = argparse.ArgumentParser(description="Build the deterministic MemCalib private-review release.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--shards", type=int, default=2)
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--run-lock", type=Path)
    args = parser.parse_args()

    artifacts = default_artifacts(data_dir, args.release_dir)
    pipeline_run_lock = data_dir / "crk2_canonical_generation_run_en_15577.lock.json"
    run_lock = args.run_lock or (
        pipeline_run_lock
        if pipeline_run_lock.exists()
        else args.release_dir / "provenance" / "generation-run.lock.json"
    )
    expected_sha256 = locked_benchmark_sha256(run_lock)
    manifest = build_release(
        args.source,
        args.release_dir,
        shard_count=args.shards,
        sample_size=args.sample_size,
        artifacts=artifacts,
        expected_source_sha256=expected_sha256,
    )
    print(
        json.dumps(
            {
                "release_dir": str(args.release_dir),
                "source_sha256": manifest["source_sha256"],
                "counts": manifest["counts"],
                "shards": manifest["files"]["data_shards"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
