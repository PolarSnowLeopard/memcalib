#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
REVISION_DIR = SCRIPT_DIR / "data" / "multidomain" / "full-v2" / "revision-composite-harda"
DEFAULT_REQUESTS = REVISION_DIR / "memcalib_v21_composite_harda_independent_qc_input_15000.jsonl"
DEFAULT_INVALID = REVISION_DIR / "memcalib_v21_composite_harda_independent_qc_15000.invalid.jsonl"
DEFAULT_OUTPUT = REVISION_DIR / "qc-retry1" / "memcalib_v21_composite_harda_independent_qc_retry1_input.jsonl"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")
SCHEMA_VERSION = "memcalib-composite-harda-independent-qc-retry-requests-v1"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(SCRIPT_DIR.parent))
    except ValueError:
        return str(resolved)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare targeted retries for structurally invalid independent QC rows.")
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--invalid", type=Path, default=DEFAULT_INVALID)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    requests = list(iter_jsonl(args.requests))
    request_by_id = {str(row.get("request_id") or ""): row for row in requests}
    if "" in request_by_id or len(request_by_id) != len(requests):
        raise ValueError("request IDs must be non-empty and unique")
    invalid = list(iter_jsonl(args.invalid))
    invalid_ids = [str(row.get("request_id") or "") for row in invalid]
    if "" in invalid_ids or len(invalid_ids) != len(set(invalid_ids)):
        raise ValueError("invalid audit request IDs must be non-empty and unique")
    missing = sorted(set(invalid_ids) - set(request_by_id))
    if missing:
        raise ValueError(f"{len(missing)} invalid request IDs are missing from the original requests")
    retry = [request_by_id[request_id] for request_id in invalid_ids]
    write_jsonl(args.output, retry)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "inputs": {
            "requests": {
                "path": portable_path(args.requests),
                "sha256": file_sha256(args.requests),
                "records": len(requests),
            },
            "invalid": {
                "path": portable_path(args.invalid),
                "sha256": file_sha256(args.invalid),
                "records": len(invalid),
            },
        },
        "output": {
            "path": portable_path(args.output),
            "sha256": file_sha256(args.output),
            "requests": len(retry),
            "unique_request_ids": len({str(row["request_id"]) for row in retry}),
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
