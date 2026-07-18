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
DATA_DIR = SCRIPT_DIR / "data" / "multidomain" / "full-v2"
REVISION_DIR = DATA_DIR / "revision-composite-harda"
DEFAULT_REQUESTS = REVISION_DIR / "composite_harda_patch_input_15000.jsonl"
DEFAULT_REJECTED = REVISION_DIR / "memcalib_v21_composite_harda_benchmark_15000.rejected.jsonl"
DEFAULT_OUTPUT = REVISION_DIR / "deterministic-repair1" / "composite_harda_patch_deterministic_repair1_input.jsonl"
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")
SCHEMA_VERSION = "memcalib-composite-harda-deterministic-repair-requests-v1"


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


def result_text(row: dict[str, Any]) -> str:
    value = row.get("response")
    return value if isinstance(value, str) else ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare targeted retries for deterministic v2.1 patch rejections.")
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--rejected", type=Path, default=DEFAULT_REJECTED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--repair-round", type=int, default=1)
    args = parser.parse_args()

    requests = list(iter_jsonl(args.requests))
    request_by_id = {str(row.get("request_id") or ""): row for row in requests}
    if "" in request_by_id or len(request_by_id) != len(requests):
        raise ValueError("request IDs must be non-empty and unique")
    rejected = list(iter_jsonl(args.rejected))

    repair_requests: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()
    domains: Counter[str] = Counter()
    families: Counter[str] = Counter()
    seen_record_ids: set[str] = set()
    for rejection in rejected:
        prior_request_id = str(rejection.get("request_id") or "")
        prior_request = request_by_id.get(prior_request_id)
        if prior_request is None:
            raise ValueError(f"missing original request for {prior_request_id!r}")
        params = dict(prior_request.get("user_defined_params") or {})
        record_id = str(params.get("record_id") or "")
        if not record_id or record_id in seen_record_ids:
            raise ValueError(f"duplicate or empty rejected record ID: {record_id!r}")
        seen_record_ids.add(record_id)
        errors = sorted({str(value) for value in rejection.get("errors") or []})
        for error in errors:
            reasons[error] += 1

        prompt = prior_request.get("prompt")
        if not isinstance(prompt, list) or not prompt or not isinstance(prompt[0], dict):
            raise ValueError(f"request {prior_request_id!r} has invalid prompt")
        repaired_prompt = [dict(message) for message in prompt]
        feedback = {
            "record_id_must_equal": record_id,
            "hard_a_family_must_equal": params.get("hard_a_family"),
            "strict_validation_errors": errors,
            "literal_constraints": {
                "hard_a.construction_target.memory_role": "none",
                "hard_a.counterfactual_contract.observable_delta": "none",
                "hard_a.counterfactual_contract.minimal_evidence": [],
                "hard_a.usage_rubric.memory_usage_weight": "none",
                "hard_a.family_audit.explicit_correction_test": "not_required",
            },
            "previous_output": result_text(rejection.get("raw_result") or {}),
        }
        repaired_prompt[0]["content"] = str(repaired_prompt[0].get("content") or "") + (
            "\n\n## Mandatory deterministic repair\n\n"
            "The previous output failed strict deterministic validation. Return the ENTIRE JSON object again, not a "
            "partial patch. Preserve the assigned family and copy the required record_id exactly. Fix every listed "
            "validation error. Literal constraints are exact strings, not descriptions. All explanatory prose fields "
            "must be substantive English. Do not change the real atoms or invent any additional answer role.\n\n"
            f"{json.dumps(feedback, ensure_ascii=False, indent=2)}\n"
        )

        new_params = dict(params)
        new_params.update(
            {
                "deterministic_repair_schema_version": SCHEMA_VERSION,
                "deterministic_repair_round": args.repair_round,
                "prior_request_id": prior_request_id,
                "prior_validation_errors": errors,
            }
        )
        repair_requests.append(
            {
                **{key: value for key, value in prior_request.items() if key not in {"request_id", "prompt", "user_defined_params"}},
                "request_id": f"composite_harda_patch_deterministic_repair{args.repair_round}:{record_id}",
                "prompt": repaired_prompt,
                "user_defined_params": new_params,
            }
        )
        domains[str(params.get("domain") or "health_seed")] += 1
        families[str(params.get("hard_a_family") or "")] += 1

    write_jsonl(args.output, repair_requests)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "repair_round": args.repair_round,
        "inputs": {
            "requests": {
                "path": portable_path(args.requests),
                "sha256": file_sha256(args.requests),
                "records": len(requests),
            },
            "rejected": {
                "path": portable_path(args.rejected),
                "sha256": file_sha256(args.rejected),
                "records": len(rejected),
            },
        },
        "counts": {
            "repair_requests": len(repair_requests),
            "unique_request_ids": len({str(row["request_id"]) for row in repair_requests}),
            "unique_record_ids": len(seen_record_ids),
        },
        "distribution": {
            "domain": dict(sorted(domains.items())),
            "hard_a_family": dict(sorted(families.items())),
            "validation_errors": dict(sorted(reasons.items())),
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
