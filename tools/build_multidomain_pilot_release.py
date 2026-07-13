#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


COPY_MAP = {
    "general_benchmark_100.jsonl": "data/general-hidden-construction-100.jsonl",
    "coding_benchmark_100.jsonl": "data/coding-hidden-construction-100.jsonl",
    "general_benchmark_audit_100.html": "review/general-audit-100.html",
    "coding_benchmark_audit_100.html": "review/coding-audit-100.html",
    "general_benchmark_100.summary.json": "metadata/general-construction-summary.json",
    "coding_benchmark_100.summary.json": "metadata/coding-construction-summary.json",
    "multidomain_pilot_validation.json": "metadata/validation.json",
    "general_raw_selection_300.manifest.json": "metadata/general-source-selection.json",
    "coding_raw_selection_300.manifest.json": "metadata/coding-source-selection.json",
    "general_semantic_qc_resolved_summary_300.json": "metadata/general-semantic-qc.json",
    "coding_semantic_qc_resolved_summary_300.json": "metadata/coding-semantic-qc.json",
    "general_semantic_admission.manifest.json": "metadata/general-admission.json",
    "coding_semantic_admission.manifest.json": "metadata/coding-admission.json",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def jsonl_rows(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for line in handle if line.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the internal MemCalib multi-domain 100+100 pilot release.")
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for source_name, relative_destination in COPY_MAP.items():
        source = args.source_dir / source_name
        if not source.exists():
            raise FileNotFoundError(source)
        destination = args.output_dir / relative_destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    files = []
    for path in sorted(item for item in args.output_dir.rglob("*") if item.is_file() and item.name != "release-manifest.json"):
        relative = path.relative_to(args.output_dir)
        entry = {
            "path": str(relative),
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        }
        if path.suffix == ".jsonl":
            entry["rows"] = jsonl_rows(path)
        files.append(entry)
    manifest = {
        "schema_version": "memcalib-multidomain-pilot-release-v1",
        "release": "memcalib-multidomain-pilot-v0.2",
        "scope": {
            "general_dialogue_samples": 100,
            "coding_samples": 100,
            "status": "internal_research_pilot",
        },
        "files": files,
    }
    manifest_path = args.output_dir / "release-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output_dir), "files": len(files), "manifest": str(manifest_path)}, indent=2))


if __name__ == "__main__":
    main()
