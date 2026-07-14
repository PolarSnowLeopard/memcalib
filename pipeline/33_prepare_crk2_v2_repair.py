#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_REJECTED = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_100.rejected.jsonl"
DEFAULT_OUTPUT = SCRIPT_DIR / "data" / "crk2_v2_generation_repair1_input.jsonl"
DEFAULT_MANIFEST = SCRIPT_DIR / "data" / "crk2_v2_generation_repair1_input.manifest.json"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_repair_request(row: dict[str, Any], retry_round: int) -> dict[str, Any]:
    params = dict(row.get("user_defined_params") or row.get("params") or {})
    source_id = str(params.get("id") or params.get("source_raw_id") or "")
    if not source_id:
        raise ValueError("rejected row has no source id")
    errors = list(row.get("errors") or [])
    original = row.get("parsed_record") if isinstance(row.get("parsed_record"), dict) else {}
    prompt = f"""You are repairing one CRK-2 canonical-memory-v2 construction record that failed deterministic validation.

Return exactly one JSON object with schema_version crk-2-canonical-memory-v2 and no Markdown. Preserve valid task semantics, parent memories, atomic labels, memory_action values, counterfactual contracts, and complete judge rubrics. Correct every listed error and re-run all QC checks.

Mandatory repair rules:
- Real raw_evidence and evidence must each be a non-empty contiguous substring copied character-for-character from RAW QUESTION or SOURCE CONTEXT according to source. Do not paraphrase evidence.
- Never use the reference answer as memory evidence or as a source of user facts.
- memory_id must equal atom_id. Atom IDs must be unique, every block atom_id must resolve to exactly one memory, and every unordered atom pair must appear exactly once with relation independent.
- The final question must not state, paraphrase, entail, or presuppose any scored memory atom. Rewrite the question when leakage is reported.
- memory_type must be one of case_fact, constraint, preference, profile_fact, safety_sensitive.
- A requires memory_action=ignore, observable_delta=none, and empty minimal_evidence.
- B/C requires memory_action=apply or correct and a non-empty observable answer delta with concrete minimal_evidence.
- Explicitly correcting or rejecting a false, unsafe, stale, or incompatible memory is B/C + correct, never A.
- Keep exactly one synthetic_hard_a parent. It must be A + ignore and must not be a dangerous or false claim that deserves correction.

FAILED VALIDATION ERRORS
{json.dumps(errors, ensure_ascii=False, indent=2)}

SOURCE CONTEXT
{params.get('dialogue_context') or params.get('source_context') or ''}

RAW QUESTION
{params.get('raw_question') or ''}

REFERENCE ANSWER (task interpretation only; forbidden as memory source)
{params.get('doctor_answer') or params.get('source_answer') or ''}

ORIGINAL CONSTRUCTION JSON
{json.dumps(original, ensure_ascii=False, indent=2)}
"""
    params["crk2_v2_repair_round"] = retry_round
    params["crk2_v2_repair_errors"] = errors
    return {
        "request_id": f"crk2_v2_{source_id}",
        "prompt": [{"role": "user", "content": prompt}],
        "user_defined_params": params,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare targeted repair requests for CRK-2 v2 deterministic rejects.")
    parser.add_argument("--rejected", type=Path, default=DEFAULT_REJECTED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--retry-round", type=int, default=1)
    args = parser.parse_args()
    if args.retry_round < 1:
        raise ValueError("retry-round must be positive")

    rejected = list(iter_jsonl(args.rejected))
    requests = [build_repair_request(row, args.retry_round) for row in rejected]
    request_ids = [str(request.get("request_id") or "") for request in requests]
    if len(set(request_ids)) != len(request_ids):
        raise ValueError("repair request IDs must be unique")
    write_jsonl(args.output, requests)
    manifest = {
        "schema_version": "crk2-v2-generation-repair-v1",
        "retry_round": args.retry_round,
        "input": {"path": str(args.rejected), "sha256": file_sha256(args.rejected), "records": len(rejected)},
        "output": {"path": str(args.output), "sha256": file_sha256(args.output), "records": len(requests)},
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
