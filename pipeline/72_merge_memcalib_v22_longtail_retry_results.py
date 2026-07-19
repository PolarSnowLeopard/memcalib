#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
V22_DIR = SCRIPT_DIR / "data" / "multidomain" / "full-v2" / "revision-longtail-blocks"
DEFAULT_BASE = V22_DIR / "memcalib_v22_longtail_augmentation_result_15000.jsonl"
DEFAULT_RETRY = V22_DIR / "memcalib_v22_longtail_augmentation_retry1_result.jsonl"
DEFAULT_OUTPUT = V22_DIR / "memcalib_v22_longtail_augmentation_resolved_result_15000.jsonl"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")
MERGE_SCHEMA = "memcalib-v22-longtail-augmentation-result-merge-v1"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(SCRIPT_DIR.parent))
    except ValueError:
        return str(resolved)


def index(rows: list[dict[str, Any]], name: str) -> dict[str, dict[str, Any]]:
    indexed = {str(row.get("request_id") or ""): row for row in rows}
    if "" in indexed or len(indexed) != len(rows):
        raise ValueError(f"{name} request IDs must be non-empty and unique")
    return indexed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replace failed MemCalib v2.2 API rows with targeted retry results."
    )
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--retry", type=Path, default=DEFAULT_RETRY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    base_rows = list(iter_jsonl(args.base))
    retry_rows = list(iter_jsonl(args.retry))
    base_by_id = index(base_rows, "base")
    retry_by_id = index(retry_rows, "retry")
    extra = set(retry_by_id) - set(base_by_id)
    if extra:
        raise ValueError(f"retry results contain {len(extra)} request IDs absent from base")
    merged = [
        retry_by_id.get(str(row["request_id"]), row)
        for row in base_rows
    ]
    write_jsonl(args.output, merged)
    manifest = {
        "schema_version": MERGE_SCHEMA,
        "inputs": {
            "base": {
                "path": portable_path(args.base),
                "sha256": file_sha256(args.base),
                "records": len(base_rows),
            },
            "retry": {
                "path": portable_path(args.retry),
                "sha256": file_sha256(args.retry),
                "records": len(retry_rows),
            },
        },
        "counts": {
            "base_records": len(base_rows),
            "replaced_records": len(retry_rows),
            "merged_records": len(merged),
            "unique_request_ids": len({str(row["request_id"]) for row in merged}),
        },
        "output": {
            "path": portable_path(args.output),
            "sha256": file_sha256(args.output),
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
