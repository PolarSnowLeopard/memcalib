#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
V22_DIR = SCRIPT_DIR / "data" / "multidomain" / "full-v2" / "revision-longtail-blocks"
DEFAULT_REJECTED = V22_DIR / "memcalib_v22_longtail_benchmark_15000.rejected.jsonl"
DEFAULT_OUTPUT = V22_DIR / "memcalib_v22_longtail_augmentation_retry1_input.jsonl"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")
RETRY_SCHEMA = "memcalib-v22-longtail-augmentation-retry-requests-v1"


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


def repair_instruction(errors: list[str]) -> str:
    rendered = "\n".join(f"- {error}" for error in errors)
    return (
        "\n\nREPAIR INSTRUCTION\n"
        "The previous response failed the deterministic checks listed below. Return the entire JSON object again, "
        "not a patch. Preserve every planned block and atom ID exactly. Correct every listed failure and recheck all "
        "required phrases, domain guardrails, uniqueness constraints, and self-check fields before responding.\n"
        f"{rendered}\n"
    )


def retry_request(rejected: dict[str, Any]) -> dict[str, Any]:
    request = rejected.get("request")
    errors = rejected.get("errors")
    if not isinstance(request, dict) or not isinstance(errors, list) or not errors:
        raise ValueError("rejected row must contain its request and at least one error")
    request_id = str(request.get("request_id") or "")
    if not request_id or request_id != str(rejected.get("request_id") or ""):
        raise ValueError("rejected row request ID mismatch")
    prompt = request.get("prompt")
    if (
        not isinstance(prompt, list)
        or len(prompt) != 1
        or not isinstance(prompt[0], dict)
        or not isinstance(prompt[0].get("content"), str)
    ):
        raise ValueError(f"request {request_id} has unsupported prompt shape")
    output = json.loads(json.dumps(request, ensure_ascii=False))
    output["prompt"][0]["content"] += repair_instruction(
        sorted({str(error) for error in errors})
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare targeted retries for deterministic MemCalib v2.2 long-tail failures."
    )
    parser.add_argument("--rejected", type=Path, default=DEFAULT_REJECTED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    rejected = list(iter_jsonl(args.rejected))
    requests = [retry_request(row) for row in rejected]
    request_ids = [str(row.get("request_id") or "") for row in requests]
    if "" in request_ids or len(request_ids) != len(set(request_ids)):
        raise ValueError("retry request IDs must be non-empty and unique")
    write_jsonl(args.output, requests)
    manifest = {
        "schema_version": RETRY_SCHEMA,
        "input": {
            "path": portable_path(args.rejected),
            "sha256": file_sha256(args.rejected),
            "rejected_records": len(rejected),
        },
        "issue_counts": dict(
            sorted(
                Counter(
                    str(error)
                    for row in rejected
                    for error in row.get("errors") or []
                ).items()
            )
        ),
        "output": {
            "path": portable_path(args.output),
            "sha256": file_sha256(args.output),
            "requests": len(requests),
            "unique_request_ids": len(set(request_ids)),
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
