#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from utils import iter_jsonl, write_json, write_jsonl


SCHEMA_VERSION = "memcalib-multidomain-construction-seeds-v2"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def merge_seeds(medical: list[dict[str, Any]], multidomain: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for row in medical:
        output = dict(row)
        output["domain"] = "health_seed"
        merged.append(output)
    for row in multidomain:
        domain = str(row.get("domain") or "")
        if domain not in {"general", "coding"}:
            raise ValueError(f"unexpected new-domain seed: {domain!r}")
        merged.append(dict(row))
    ids = [str(row.get("id") or "") for row in merged]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("merged construction seed IDs must be non-empty and unique")
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge locked medical and newly admitted General/Coding construction seeds.")
    parser.add_argument("--medical", type=Path, required=True)
    parser.add_argument("--multidomain", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    medical = list(iter_jsonl(args.medical))
    multidomain = list(iter_jsonl(args.multidomain))
    merged = merge_seeds(medical, multidomain)
    write_jsonl(args.output, merged)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "inputs": {
            "medical": {"path": str(args.medical), "sha256": file_sha256(args.medical), "records": len(medical)},
            "multidomain": {
                "path": str(args.multidomain),
                "sha256": file_sha256(args.multidomain),
                "records": len(multidomain),
            },
        },
        "implementation": {"path": str(Path(__file__).resolve()), "sha256": file_sha256(Path(__file__).resolve())},
        "distribution": {
            "domain": dict(sorted(Counter(str(row.get("domain") or "unknown") for row in merged).items())),
            "source_dataset": dict(
                sorted(Counter(str(row.get("source_dataset") or "unknown") for row in merged).items())
            ),
        },
        "output": {"path": str(args.output), "sha256": file_sha256(args.output), "records": len(merged)},
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
