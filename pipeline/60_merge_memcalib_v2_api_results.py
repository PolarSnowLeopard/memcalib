#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
SCHEMA_VERSION = "memcalib-api-result-overlay-v1"


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
    parser = argparse.ArgumentParser(description="Overlay retry API results onto a base result JSONL by request_id.")
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--retry", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    base = list(iter_jsonl(args.base))
    base_ids = [str(row.get("request_id") or "") for row in base]
    if "" in base_ids or len(base_ids) != len(set(base_ids)):
        raise ValueError("base request IDs must be non-empty and unique")
    order = list(base_ids)
    resolved = {str(row["request_id"]): row for row in base}
    overlays = 0
    appended = 0
    retry_inputs = []
    for path in args.retry:
        rows = list(iter_jsonl(path))
        ids = [str(row.get("request_id") or "") for row in rows]
        if "" in ids or len(ids) != len(set(ids)):
            raise ValueError(f"retry request IDs must be non-empty and unique: {path}")
        for row, request_id in zip(rows, ids):
            if request_id in resolved:
                overlays += 1
            else:
                order.append(request_id)
                appended += 1
            resolved[request_id] = row
        retry_inputs.append(
            {"path": portable_path(path), "sha256": file_sha256(path), "records": len(rows)}
        )
    output = [resolved[request_id] for request_id in order]
    write_jsonl(args.output, output)
    manifest_path = args.manifest or args.output.with_suffix(".manifest.json")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "inputs": {
            "base": {
                "path": portable_path(args.base),
                "sha256": file_sha256(args.base),
                "records": len(base),
            },
            "retry": retry_inputs,
        },
        "counts": {
            "overlays": overlays,
            "appended": appended,
            "output": len(output),
            "unique_request_ids": len(resolved),
        },
        "output": {"path": portable_path(args.output), "sha256": file_sha256(args.output)},
    }
    write_json(manifest_path, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
