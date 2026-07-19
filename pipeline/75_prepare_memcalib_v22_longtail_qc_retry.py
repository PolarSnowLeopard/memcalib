#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
V22_DIR = SCRIPT_DIR / "data" / "multidomain" / "full-v2" / "revision-longtail-blocks"
DEFAULT_REQUESTS = V22_DIR / "memcalib_v22_longtail_independent_qc_input_15000.jsonl"
DEFAULT_INVALID = V22_DIR / "memcalib_v22_longtail_independent_qc_15000.invalid.jsonl"
DEFAULT_OUTPUT = V22_DIR / "memcalib_v22_longtail_independent_qc_retry1_input.jsonl"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")
RETRY_SCHEMA = "memcalib-v22-longtail-independent-qc-retry-requests-v1"


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


def retry_instruction(errors: list[str]) -> str:
    rendered = "\n".join(f"- {error}" for error in errors)
    return (
        "\n\nRETRY INSTRUCTION\n"
        "Your previous QC response was structurally invalid for the reasons below. "
        "Re-evaluate the same record and return the complete JSON object, not a patch. "
        "Copy the required record ID exactly. Include every expected atom and auxiliary "
        "block exactly once, use only allowed enum values, provide a substantive reason "
        "for every check, and use JSON booleans for all boolean fields.\n"
        f"{rendered}\n"
    )


def build_retry_request(
    request: dict[str, Any], invalid: dict[str, Any]
) -> dict[str, Any]:
    request_id = str(request.get("request_id") or "")
    if not request_id or request_id != str(invalid.get("request_id") or ""):
        raise ValueError("request and invalid audit IDs do not match")
    errors = invalid.get("validation_errors")
    if not isinstance(errors, list) or not errors:
        raise ValueError(f"invalid audit {request_id} has no validation errors")
    prompt = request.get("prompt")
    if (
        not isinstance(prompt, list)
        or len(prompt) != 1
        or not isinstance(prompt[0], dict)
        or not isinstance(prompt[0].get("content"), str)
    ):
        raise ValueError(f"request {request_id} has unsupported prompt shape")
    output = copy.deepcopy(request)
    output["prompt"][0]["content"] += retry_instruction(
        sorted({str(error) for error in errors})
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare targeted retries for invalid MemCalib v2.2 independent QC outputs."
    )
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--invalid", type=Path, default=DEFAULT_INVALID)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    requests = list(iter_jsonl(args.requests))
    request_by_id = {str(row.get("request_id") or ""): row for row in requests}
    if "" in request_by_id or len(request_by_id) != len(requests):
        raise ValueError("source request IDs must be non-empty and unique")
    invalid_rows = list(iter_jsonl(args.invalid))
    retries: list[dict[str, Any]] = []
    for row in invalid_rows:
        request_id = str(row.get("request_id") or "")
        request = request_by_id.get(request_id)
        if request is None:
            raise ValueError(f"invalid audit request absent from source: {request_id}")
        retries.append(build_retry_request(request, row))
    retry_ids = [str(row.get("request_id") or "") for row in retries]
    if "" in retry_ids or len(retry_ids) != len(set(retry_ids)):
        raise ValueError("retry request IDs must be non-empty and unique")

    write_jsonl(args.output, retries)
    manifest = {
        "schema_version": RETRY_SCHEMA,
        "inputs": {
            "requests": {
                "path": portable_path(args.requests),
                "sha256": file_sha256(args.requests),
                "records": len(requests),
            },
            "invalid": {
                "path": portable_path(args.invalid),
                "sha256": file_sha256(args.invalid),
                "records": len(invalid_rows),
            },
        },
        "error_counts": dict(
            sorted(
                Counter(
                    str(error)
                    for row in invalid_rows
                    for error in row.get("validation_errors") or []
                ).items()
            )
        ),
        "output": {
            "path": portable_path(args.output),
            "sha256": file_sha256(args.output),
            "requests": len(retries),
            "unique_request_ids": len(set(retry_ids)),
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
