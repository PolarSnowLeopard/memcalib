#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from utils import iter_jsonl, write_json, write_jsonl


SCHEMA_VERSION = "memcalib-generation-repair-v1"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_repair_request(
    row: dict[str, Any],
    retry_round: int,
    original_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    params = dict(row.get("params") or {})
    source_id = str(params.get("id") or params.get("source_raw_id") or row.get("row_index") or "unknown")
    errors = list(row.get("errors") or [])
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    repair_instructions = f"""You are repairing one MemCalib construction record that failed deterministic validation.

Return one strict JSON object only. Preserve the original task, memory semantics, A/B/C labels, parent-to-atom links, and complete judge rubrics whenever they are valid. Correct every listed error.

Evidence rules are mandatory:
- A from_question raw_evidence/evidence value must be one non-empty contiguous exact substring copied character-for-character from CURRENT QUESTION.
- A from_context raw_evidence/evidence value must be one non-empty contiguous exact substring copied character-for-character from SOURCE CONTEXT.
- synthetic_hard_a evidence may be an explicit synthetic rationale; its label must be A and derivation must be synthetic.
- Never use REFERENCE ANSWER as memory evidence or as a source of memory facts.
- If a parent block combines facts that cannot share one contiguous source span, split it into coherent parent blocks and update all parent IDs, atom IDs, indexes, counts, and links.
- If an affected proposition cannot be grounded, replace or remove it while retaining at least one real B/C atom and one coherent synthetic hard A atom.
- The decontextualized question must remain coherent and must not reveal the stored memory.

FAILED VALIDATION ERRORS
{json.dumps(errors, ensure_ascii=False)}

DOMAIN
{params.get('domain', 'health_seed')}

SOURCE CONTEXT
{params.get('source_context', '')}

CURRENT QUESTION
{params.get('raw_question', '')}

REFERENCE ANSWER (validation only; forbidden as memory source)
{params.get('source_answer') or params.get('doctor_answer') or ''}

ORIGINAL CONSTRUCTION JSON
{json.dumps(raw, ensure_ascii=False)}
"""
    original_usable = bool(raw.get("memory_blocks") and raw.get("memories") and raw.get("accepted") is not False)
    if original_usable:
        prompt = repair_instructions
    elif original_request:
        messages = original_request.get("prompt")
        if not isinstance(messages, list) or not messages:
            raise ValueError(f"original request for {source_id} has no prompt")
        prompt = str(messages[-1].get("content") or "") + "\n\nRETRY AFTER VALIDATION FAILURE\n" + repair_instructions
    else:
        raise ValueError(f"rejected row {source_id} needs its original request for reconstruction")
    params["generation_repair_round"] = retry_round
    params["generation_repair_errors"] = errors
    return {
        "request_id": f"crk2_repair{retry_round}_{source_id}",
        "prompt": [{"role": "user", "content": prompt}],
        "user_defined_params": params,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare targeted repair requests for invalid MemCalib construction rows.")
    parser.add_argument("--rejected", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--original-requests", type=Path)
    parser.add_argument("--retry-round", type=int, default=1)
    args = parser.parse_args()
    if args.retry_round <= 0:
        raise ValueError("retry-round must be positive")
    rejected = list(iter_jsonl(args.rejected))
    original_by_id: dict[str, dict[str, Any]] = {}
    if args.original_requests:
        for request in iter_jsonl(args.original_requests):
            params = request.get("user_defined_params") or {}
            source_id = str(params.get("id") or params.get("source_raw_id") or "")
            if source_id:
                original_by_id[source_id] = request
    requests = []
    for row in rejected:
        params = row.get("params") or {}
        source_id = str(params.get("id") or params.get("source_raw_id") or "")
        requests.append(build_repair_request(row, args.retry_round, original_by_id.get(source_id)))
    request_ids = [str(row.get("request_id") or "") for row in requests]
    if len(set(request_ids)) != len(request_ids):
        raise ValueError("repair request IDs must be unique")
    write_jsonl(args.output, requests)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "retry_round": args.retry_round,
        "input": {"path": str(args.rejected), "sha256": file_sha256(args.rejected), "records": len(rejected)},
        "original_requests": (
            {"path": str(args.original_requests), "sha256": file_sha256(args.original_requests)}
            if args.original_requests
            else None
        ),
        "output": {"path": str(args.output), "sha256": file_sha256(args.output), "records": len(requests)},
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
