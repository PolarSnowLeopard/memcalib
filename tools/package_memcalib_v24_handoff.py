#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V24_DIR = (
    ROOT
    / "pipeline"
    / "data"
    / "multidomain"
    / "full-v2"
    / "revision-coding-text-observable-v24"
)
RELEASE_DIR = V24_DIR / "release"
CURRENT_DOCS = ROOT / "docs" / "current" / "v2.4"
DEFAULT_DATASET = RELEASE_DIR / "memcalib_v24_multidomain_benchmark_15000.jsonl"
DEFAULT_OUTPUT = V24_DIR / "handoff"
PACKAGE_NAME = "MemCalib-v2.4-coauthor-20260729"
FIXED_ZIP_TIME = (2026, 7, 29, 0, 0, 0)
EXPECTED_ROWS = 15000
EXPECTED_SHA256 = "377770f0048114db4cf40e95783f05789f1a024d1e6c90ff77881e170c0e111b"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def deterministic_gzip(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as input_stream, destination.open("wb") as raw_output:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw_output,
            mtime=0,
            compresslevel=9,
        ) as output_stream:
            shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)


def count_nonempty_lines(path: Path) -> int:
    with path.open("rb") as stream:
        return sum(1 for line in stream if line.strip())


def artifact(path: Path, package_dir: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(package_dir).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def write_deterministic_zip(package_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", allowZip64=True) as archive:
        for path in sorted(value for value in package_dir.rglob("*") if value.is_file()):
            relative = Path(package_dir.name) / path.relative_to(package_dir)
            info = zipfile.ZipInfo(relative.as_posix(), date_time=FIXED_ZIP_TIME)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = (
                zipfile.ZIP_STORED if path.suffix == ".gz" else zipfile.ZIP_DEFLATED
            )
            with path.open("rb") as source, archive.open(info, "w") as destination:
                shutil.copyfileobj(source, destination, length=1024 * 1024)


def build_package(dataset: Path, output_root: Path) -> dict[str, object]:
    rows = count_nonempty_lines(dataset)
    dataset_sha = sha256_file(dataset)
    if rows != EXPECTED_ROWS:
        raise ValueError(f"expected {EXPECTED_ROWS} rows, found {rows}: {dataset}")
    if dataset_sha != EXPECTED_SHA256:
        raise ValueError(
            f"dataset SHA-256 mismatch: expected {EXPECTED_SHA256}, found {dataset_sha}"
        )

    package_dir = output_root / PACKAGE_NAME
    zip_path = output_root / f"{PACKAGE_NAME}.zip"
    external_manifest = output_root / f"{PACKAGE_NAME}.zip.manifest.json"
    zip_sha256_path = output_root / f"{PACKAGE_NAME}.zip.sha256"
    if package_dir.exists():
        shutil.rmtree(package_dir)
    for path in (zip_path, external_manifest, zip_sha256_path):
        if path.exists():
            path.unlink()
    package_dir.mkdir(parents=True)

    dataset_gzip = package_dir / "data" / "memcalib-v2.4-multidomain-15000.jsonl.gz"
    deterministic_gzip(dataset, dataset_gzip)
    fixed_files = [
        (
            RELEASE_DIR / "memcalib_v24_multidomain_benchmark_15000.manifest.json",
            package_dir / "metadata" / "release-manifest.json",
        ),
        (
            RELEASE_DIR / "memcalib_v24_multidomain_benchmark_15000.statistics.json",
            package_dir / "metadata" / "statistics.json",
        ),
        (
            RELEASE_DIR / "memcalib_v24_multidomain_benchmark_review.html",
            package_dir / "review" / "record-review.html",
        ),
        (
            V24_DIR / "memcalib_v24_coding_complete_3750.manifest.json",
            package_dir / "metadata" / "coding-merge-manifest.json",
        ),
        (
            V24_DIR / "memcalib_v24_coding_complete_3750.audit.jsonl",
            package_dir / "audit" / "coding-merge-audit-3750.jsonl",
        ),
        (
            V24_DIR / "memcalib_v24_coding_manual_adjudication_15.manifest.json",
            package_dir / "metadata" / "manual-adjudication-manifest.json",
        ),
        (
            V24_DIR / "memcalib_v24_coding_manual_adjudication_15.audit.jsonl",
            package_dir / "audit" / "manual-adjudication-audit-15.jsonl",
        ),
        (ROOT / "DATA_CARD.md", package_dir / "DATA_CARD.md"),
        (ROOT / "NOTICE.md", package_dir / "NOTICE.md"),
        (
            CURRENT_DOCS / "MEMCALIB_V24_COAUTHOR_HANDOFF.md",
            package_dir / "README.md",
        ),
        (
            CURRENT_DOCS / "benchmark-schema-v2.4.md",
            package_dir / "docs" / "benchmark-schema-v2.4.md",
        ),
        (
            CURRENT_DOCS / "reports" / "memcalib-v24-coding-text-observability.md",
            package_dir
            / "docs"
            / "reports"
            / "memcalib-v24-coding-text-observability.md",
        ),
        (
            CURRENT_DOCS
            / "samples"
            / "memcalib-v24-coding-review-sample-30.full.jsonl",
            package_dir
            / "samples"
            / "memcalib-v24-coding-review-sample-30.full.jsonl",
        ),
        (
            CURRENT_DOCS
            / "samples"
            / "memcalib-v24-coding-review-sample-30.model-facing.jsonl",
            package_dir
            / "samples"
            / "memcalib-v24-coding-review-sample-30.model-facing.jsonl",
        ),
        (
            CURRENT_DOCS
            / "samples"
            / "memcalib-v24-coding-review-sample-30.manifest.json",
            package_dir
            / "samples"
            / "memcalib-v24-coding-review-sample-30.manifest.json",
        ),
        (
            CURRENT_DOCS
            / "samples"
            / "memcalib-v24-coding-review-sample-30.README.md",
            package_dir / "samples" / "README.md",
        ),
    ]
    for source, destination in fixed_files:
        copy_file(source, destination)

    packaged_files = sorted(path for path in package_dir.rglob("*") if path.is_file())
    manifest = {
        "schema_version": "memcalib-v24-coauthor-package-v1",
        "package": PACKAGE_NAME,
        "status": "dataset_complete_v24",
        "source_dataset": {
            "path": str(dataset.relative_to(ROOT)),
            "bytes": dataset.stat().st_size,
            "rows": rows,
            "sha256": dataset_sha,
        },
        "compressed_dataset": artifact(dataset_gzip, package_dir),
        "files": [artifact(path, package_dir) for path in packaged_files],
    }
    manifest_path = package_dir / "package-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_deterministic_zip(package_dir, zip_path)
    manifest["package_manifest"] = artifact(manifest_path, package_dir)
    manifest["zip"] = {
        "path": zip_path.name,
        "bytes": zip_path.stat().st_size,
        "sha256": sha256_file(zip_path),
    }
    manifest["external_manifest"] = external_manifest.name
    manifest["zip_sha256_file"] = zip_sha256_path.name
    external_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    zip_sha256_path.write_text(
        f"{manifest['zip']['sha256']}  {zip_path.name}\n",
        encoding="ascii",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the deterministic MemCalib v2.4 coauthor handoff package."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = build_package(args.dataset.resolve(), args.output_root.resolve())
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
