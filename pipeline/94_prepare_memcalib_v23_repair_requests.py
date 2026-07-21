#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any

from memcalib_v23_common import V23_DIR, file_sha256, portable_path
from utils import iter_jsonl, write_json, write_jsonl


DEFAULT_EXPANSION_REQUESTS = V23_DIR / "memcalib_v23_expansion_input_15000.jsonl"
DEFAULT_REWRITE_REQUESTS = V23_DIR / "memcalib_v23_surface_rewrite_input_15000.jsonl"
DEFAULT_REJECTS = V23_DIR / "memcalib_v23_independent_qc_15000.reject.jsonl"
DEFAULT_EXPANSION_OUTPUT = V23_DIR / "memcalib_v23_semantic_repair_input.jsonl"
DEFAULT_REWRITE_OUTPUT = V23_DIR / "memcalib_v23_rewrite_only_repair_input.jsonl"
DEFAULT_MANIFEST = V23_DIR / "memcalib_v23_targeted_repair_requests.manifest.json"

ATOM_REJECT_SUFFIXES = (
    "atomicity_fail",
    "same_user_plausibility_fail",
    "query_relation_overlap",
    "query_relation_entailed",
    "answer_footprint_bounded",
    "answer_footprint_controlling",
    "explicit_correction_required",
    "distinct_from_block_atoms_fail",
    "block_coherence_fail",
)
BLOCK_REJECT_MARKERS = (
    ":not_entailed",
    ":critical_value_fidelity_fail",
    ":cross_block_contamination",
    ":visible_atom_boundaries",
    ":natural_paragraph_fail",
    ":extra_propositions_present",
)


def request_index(path: Path) -> dict[str, dict[str, Any]]:
    rows = list(iter_jsonl(path))
    ids = [str(row.get("request_id") or "") for row in rows]
    if "" in ids or len(ids) != len(set(ids)):
        raise ValueError(f"{path} request IDs must be non-empty and unique")
    return dict(zip(ids, rows, strict=True))


def reject_class(row: dict[str, Any]) -> str:
    qc = row.get("v23_independent_qc") or {}
    reasons = [str(reason) for reason in qc.get("decision_reasons") or []]
    atom_failure = any(reason.endswith(ATOM_REJECT_SUFFIXES) for reason in reasons)
    block_failure = any(
        marker in reason for reason in reasons for marker in BLOCK_REJECT_MARKERS
    )
    judge_declared = "judge_declared_reject" in reasons
    if judge_declared:
        explanation = " ".join(
            str(reason)
            for reason in (qc.get("judge_output") or {}).get("decision_reasons") or []
        ).lower()
        atom_failure = atom_failure or any(
            phrase in explanation
            for phrase in (
                "answer footprint",
                "zero-footprint",
                "zero legitimate answer footprint",
                "auxiliary a",
            )
        )
    if atom_failure:
        return "semantic_atom_repair"
    if block_failure:
        return "surface_rewrite_only"
    raise ValueError(
        f"cannot classify reject {row.get('id')}: {reasons or ['no computed reasons']}"
    )


def append_feedback(
    request: dict[str, Any], row: dict[str, Any], repair_class: str
) -> dict[str, Any]:
    amended = copy.deepcopy(request)
    prompt = amended.get("prompt")
    if not isinstance(prompt, list):
        raise ValueError(f"request {request.get('request_id')} prompt must be a list")
    qc = row.get("v23_independent_qc") or {}
    computed = "; ".join(str(reason) for reason in qc.get("decision_reasons") or [])
    declared = " ".join(
        str(reason)
        for reason in (qc.get("judge_output") or {}).get("decision_reasons") or []
    )
    if repair_class == "semantic_atom_repair":
        instruction = (
            "The previous auxiliary-atom set failed independent semantic QC. Regenerate the "
            "complete JSON response and replace every planned auxiliary atom while preserving "
            "the exact schema, record_id, block order, atom IDs, and requested counts. Do not "
            "reuse the failed propositions. Keep each new fact wholly outside the question's "
            "subject matter and outside every fact, factor, preference, constraint, example, "
            "or framing that could alter a competent answer. For coherence, prefer benign "
            "biographical, logistical, environmental, or episode-adjacent details that remain "
            "orthogonal to the question. A shared setting is allowed; answer relevance is not. "
            "Every atom must still be atomic, mutually distinct, plausible for the same user, "
            "and jointly removable without any change to the ideal answer."
        )
    else:
        instruction = (
            "The atoms are locked and semantically acceptable, but the previous model-facing "
            "paragraph failed surface-form QC. Return the complete JSON response from scratch. "
            "Preserve every atom exactly in meaning and critical values, add no proposition, "
            "omit none, avoid cross-block contamination and visible enumeration, and write each "
            "block as one natural coherent paragraph."
        )
    prompt.append(
        {
            "role": "user",
            "content": (
                f"{instruction}\n\nComputed QC failures: {computed or 'judge-declared reject'}."
                f"\nJudge explanation: {declared or 'No additional explanation.'}"
            ),
        }
    )
    return amended


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare semantic-atom and rewrite-only repairs for v2.3 QC rejects."
    )
    parser.add_argument("--expansion-requests", type=Path, default=DEFAULT_EXPANSION_REQUESTS)
    parser.add_argument("--rewrite-requests", type=Path, default=DEFAULT_REWRITE_REQUESTS)
    parser.add_argument("--rejects", type=Path, default=DEFAULT_REJECTS)
    parser.add_argument("--expansion-output", type=Path, default=DEFAULT_EXPANSION_OUTPUT)
    parser.add_argument("--rewrite-output", type=Path, default=DEFAULT_REWRITE_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    expansion = request_index(args.expansion_requests)
    rewrite = request_index(args.rewrite_requests)
    rejects = list(iter_jsonl(args.rejects))
    record_ids = [str(row.get("id") or "") for row in rejects]
    if "" in record_ids or len(record_ids) != len(set(record_ids)):
        raise ValueError("reject record IDs must be non-empty and unique")

    semantic_requests: list[dict[str, Any]] = []
    rewrite_requests: list[dict[str, Any]] = []
    classes: Counter[str] = Counter()
    domains: Counter[str] = Counter()
    for row in rejects:
        record_id = str(row["id"])
        repair_class = reject_class(row)
        classes[repair_class] += 1
        domains[f"{repair_class}:{row.get('domain')}"] += 1
        if repair_class == "semantic_atom_repair":
            request_id = f"v23_expansion:{record_id}"
            source = expansion.get(request_id)
            if source is None:
                raise ValueError(f"missing expansion request {request_id}")
            semantic_requests.append(append_feedback(source, row, repair_class))
        else:
            request_id = f"v23_surface_rewrite:{record_id}"
            source = rewrite.get(request_id)
            if source is None:
                raise ValueError(f"missing rewrite request {request_id}")
            rewrite_requests.append(append_feedback(source, row, repair_class))

    write_jsonl(args.expansion_output, semantic_requests)
    write_jsonl(args.rewrite_output, rewrite_requests)
    manifest = {
        "schema_version": "memcalib-v23-targeted-repair-requests-v1",
        "policy": {
            "semantic_failures": "regenerate_all_added_atoms_with_locked_ids_and_counts",
            "surface_only_failures": "rewrite_locked_atoms_without_semantic_changes",
            "strict_and_review_records_untouched": True,
        },
        "inputs": {
            "rejects": {
                "path": portable_path(args.rejects),
                "sha256": file_sha256(args.rejects),
                "count": len(rejects),
            },
            "expansion_requests": {
                "path": portable_path(args.expansion_requests),
                "sha256": file_sha256(args.expansion_requests),
            },
            "rewrite_requests": {
                "path": portable_path(args.rewrite_requests),
                "sha256": file_sha256(args.rewrite_requests),
            },
        },
        "selection": {
            "classes": dict(sorted(classes.items())),
            "class_domains": dict(sorted(domains.items())),
            "total": len(rejects),
        },
        "outputs": {
            "semantic_expansion": {
                "path": portable_path(args.expansion_output),
                "sha256": file_sha256(args.expansion_output),
                "count": len(semantic_requests),
            },
            "surface_rewrite_only": {
                "path": portable_path(args.rewrite_output),
                "sha256": file_sha256(args.rewrite_output),
                "count": len(rewrite_requests),
            },
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
