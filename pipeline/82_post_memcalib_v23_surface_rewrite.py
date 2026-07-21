#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from memcalib_v23_common import (
    V23_DIR,
    atom_index,
    canonical_sha256,
    critical_tokens,
    file_sha256,
    norm_text,
    portable_path,
)
from utils import extract_json_object, iter_jsonl, write_json, write_jsonl


DEFAULT_BENCHMARK = V23_DIR / "memcalib_v23_expanded_benchmark_15000.jsonl"
DEFAULT_REQUESTS = V23_DIR / "memcalib_v23_surface_rewrite_input_15000.jsonl"
DEFAULT_RESULTS = V23_DIR / "memcalib_v23_surface_rewrite_result_15000.jsonl"
DEFAULT_OUTPUT = V23_DIR / "memcalib_v23_rewritten_benchmark_15000.jsonl"
DEFAULT_REJECTED = V23_DIR / "memcalib_v23_surface_rewrite_rejected_15000.jsonl"
DEFAULT_AUDIT = V23_DIR / "memcalib_v23_surface_rewrite_15000.audit.jsonl"
DEFAULT_SUMMARY = V23_DIR / "memcalib_v23_surface_rewrite_15000.summary.json"

PAYLOAD_SCHEMA = "memcalib-v23-surface-rewrite-v1"
RECORD_SCHEMA = "crk-2-canonical-memory-v2.3"
SELF_CHECK_KEYS = {
    "all_block_ids_exact",
    "all_propositions_preserved",
    "no_propositions_added",
    "no_numbered_or_bulleted_atom_boundaries",
    "critical_values_preserved",
    "single_paragraph_per_block",
}
LIST_MARKER_RE = re.compile(
    r"(?:^|\n)\s*(?:[-*\u2022]|\d{1,2}[.)])\s+|"
    r"(?:^|(?<=[.!?])\s+)\d{1,2}\.\s+(?=[A-Z])"
)
ATOM_META_RE = re.compile(
    r"\b(?:"
    r"atom(?:ic)?\s+(?:id|boundary|label)|"
    r"(?:first|second|third|fourth|next)\s+memory\s+atom|"
    r"u_star|memory_action|(?:usage|scoring)\s+rubric"
    r")\b",
    re.IGNORECASE,
)
NUMBER_WORDS = {
    0: "zero",
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
    11: "eleven",
    12: "twelve",
    13: "thirteen",
    14: "fourteen",
    15: "fifteen",
    16: "sixteen",
    17: "seventeen",
    18: "eighteen",
    19: "nineteen",
    20: "twenty",
}


def required_manifest_tokens(tokens: list[Any]) -> set[str]:
    required: set[str] = set()
    for raw_token in tokens:
        token = norm_text(str(raw_token))
        if not token:
            continue
        # v1 pilot manifests also contained every title-cased word. Lower-case
        # entries came from inline code and remain semantically significant.
        if token == token.casefold() or critical_tokens(token):
            required.add(token.casefold())
    return required


def literal_token_present(token: str, text: str) -> bool:
    normalized = norm_text(text).casefold()
    if token and token[0].isalnum() and token[-1].isalnum():
        if re.search(rf"(?<!\w){re.escape(token)}(?!\w)", normalized) is not None:
            return True
    elif token in normalized:
        return True
    if token.isdigit() and int(token) in NUMBER_WORDS:
        word = NUMBER_WORDS[int(token)]
        return re.search(rf"(?<!\w){word}(?!\w)", normalized) is not None
    range_match = re.fullmatch(r"(\d+)-(\d+)", token)
    if range_match:
        left, right = (int(value) for value in range_match.groups())
        if left in NUMBER_WORDS and right in NUMBER_WORDS:
            left_word = NUMBER_WORDS[left]
            right_word = NUMBER_WORDS[right]
            return re.search(
                rf"(?<!\w){left_word}(?:\s+(?:to|or|through)\s+|[-\u2013\u2014]){right_word}(?!\w)",
                normalized,
            ) is not None
    return False


def request_params(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("passParams") or row.get("user_defined_params") or row.get("params") or {}


def output_text(row: dict[str, Any]) -> str:
    for key in ("response", "output", "content", "text", "answer"):
        if isinstance(row.get(key), str) and row[key].strip():
            return row[key]
    raw = row.get("raw_response")
    if isinstance(raw, dict):
        choices = raw.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            message = choices[0].get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
    raise ValueError("no_model_output_text")


def source_block_index(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    blocks = {
        str(block.get("parent_memory_id") or ""): block
        for block in record.get("memory_blocks") or []
        if isinstance(block, dict)
    }
    if "" in blocks or len(blocks) != len(record.get("memory_blocks") or []):
        raise ValueError(f"record {record.get('id')} has invalid block IDs")
    return blocks


def validate_payload(
    payload: dict[str, Any], record: dict[str, Any], params: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != PAYLOAD_SCHEMA:
        errors.append("schema_version_mismatch")
    if str(payload.get("record_id") or "") != str(record.get("id") or ""):
        errors.append("record_id_mismatch")
    expected = params.get("expected_blocks")
    actual = payload.get("blocks")
    if not isinstance(expected, list) or not isinstance(actual, list):
        return errors + ["expected_or_actual_blocks_not_list"]
    expected_ids = [str(block.get("parent_memory_id") or "") for block in expected]
    actual_ids = [
        str(block.get("parent_memory_id") or "") if isinstance(block, dict) else ""
        for block in actual
    ]
    if actual_ids != expected_ids:
        errors.append("block_ids_or_order_mismatch")

    source_blocks = source_block_index(record)
    atoms = atom_index(record)
    for index, expected_block in enumerate(expected):
        if index >= len(actual) or not isinstance(actual[index], dict):
            errors.append(f"block_{index}_missing")
            continue
        parent_id = str(expected_block["parent_memory_id"])
        atom_ids = [str(atom_id) for atom_id in source_blocks[parent_id]["atom_ids"]]
        expected_atom_ids = [str(atom_id) for atom_id in expected_block["atom_ids"]]
        if atom_ids != expected_atom_ids:
            errors.append(f"block_{index}_atom_ids_changed")
        raw_atom_texts = [atoms[atom_id].get("text") for atom_id in atom_ids]
        if canonical_sha256(raw_atom_texts) != expected_block.get("atom_text_fingerprint"):
            errors.append(f"block_{index}_atom_text_fingerprint_mismatch")
        atom_texts = [norm_text(text) for text in raw_atom_texts]
        text = str(actual[index].get("memory_text") or "").strip()
        normalized = norm_text(text)
        if len(normalized) < 20:
            errors.append(f"block_{index}_memory_text_missing_or_short")
            continue
        if "\n" in text or "\r" in text:
            errors.append(f"block_{index}_not_single_paragraph")
        if LIST_MARKER_RE.search(text):
            errors.append(f"block_{index}_visible_atom_markers")
        if ATOM_META_RE.search(text):
            errors.append(f"block_{index}_hidden_metadata_leak")
        source_length = sum(len(atom_text) for atom_text in atom_texts)
        if len(normalized) < source_length * 0.45:
            errors.append(f"block_{index}_rewrite_too_short")
        if len(normalized) > source_length * 1.55 + 80:
            errors.append(f"block_{index}_rewrite_too_long")
        missing_tokens = sorted(
            token
            for token in required_manifest_tokens(
                expected_block.get("critical_tokens") or []
            )
            if not literal_token_present(token, normalized)
        )
        if missing_tokens:
            errors.append(
                f"block_{index}_critical_tokens_missing:{'|'.join(missing_tokens)}"
            )

    self_check = payload.get("self_check")
    if not isinstance(self_check, dict):
        errors.append("self_check_not_object")
    else:
        if set(self_check) != SELF_CHECK_KEYS:
            errors.append("self_check_keys_mismatch")
        for key in SELF_CHECK_KEYS:
            if self_check.get(key) is not True:
                errors.append(f"self_check.{key}_not_true")
    return errors


def build_record(
    source: dict[str, Any], payload: dict[str, Any], params: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    record = copy.deepcopy(source)
    rewrites = {
        str(block["parent_memory_id"]): norm_text(block["memory_text"])
        for block in payload["blocks"]
    }
    expected = {
        str(block["parent_memory_id"]): block for block in params["expected_blocks"]
    }
    audit_rows: list[dict[str, Any]] = []
    for block in record.get("memory_blocks") or []:
        parent_id = str(block.get("parent_memory_id") or "")
        if parent_id not in rewrites:
            continue
        before = str(block.get("memory_text") or "")
        after = rewrites[parent_id]
        block["memory_text"] = after
        block["surface_form"] = "natural_paragraph"
        block["surface_rewrite"] = {
            "schema_version": "memcalib-v23-block-surface-rewrite-v1",
            "request_id": f"v23_surface_rewrite:{source['id']}",
            "before_sha256": canonical_sha256(before),
            "after_sha256": canonical_sha256(after),
            "atom_text_fingerprint": expected[parent_id]["atom_text_fingerprint"],
            "label_blind": True,
        }
        block["atomization_notes"] = (
            "Hidden independently scored atoms are rendered as one label-blind natural paragraph; "
            "visible numbering and atom-boundary markers are forbidden."
        )
        audit_rows.append(
            {
                "record_id": source["id"],
                "parent_memory_id": parent_id,
                "atom_ids": expected[parent_id]["atom_ids"],
                "before_sha256": canonical_sha256(before),
                "after_sha256": canonical_sha256(after),
                "before_text": before,
                "after_text": after,
            }
        )
    record["schema_version"] = RECORD_SCHEMA
    revision = copy.deepcopy(record.get("composite_block_revision") or {})
    revision["surface_rewrite_pending"] = False
    revision["surface_rewrite_schema_version"] = "memcalib-v23-surface-rewrite-v1"
    revision["surface_rewrite_request_id"] = f"v23_surface_rewrite:{source['id']}"
    revision["surface_rewrite_fingerprint"] = canonical_sha256(
        {
            row["parent_memory_id"]: row["after_sha256"]
            for row in audit_rows
        }
    )
    revision["model_facing_atom_boundaries_hidden"] = True
    record["composite_block_revision"] = revision
    record["deterministic_qc"] = {
        "schema_version": "memcalib-v23-surface-rewrite-deterministic-qc-v1",
        "decision": "pass",
        "checks": [],
    }
    return record, audit_rows


def validate_record(record: dict[str, Any], source: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if record.get("memories") != source.get("memories"):
        errors.append("hidden_atoms_changed")
    if record.get("atom_pair_relations") != source.get("atom_pair_relations"):
        errors.append("atom_pair_relations_changed")
    source_blocks = source_block_index(source)
    built_blocks = source_block_index(record)
    if list(built_blocks) != list(source_blocks):
        errors.append("block_ids_or_order_changed")
    for parent_id, source_block in source_blocks.items():
        built = built_blocks[parent_id]
        for key, value in source_block.items():
            if key in {"memory_text", "surface_form", "surface_rewrite", "atomization_notes"}:
                continue
            if built.get(key) != value:
                errors.append(f"block_metadata_changed:{parent_id}:{key}")
        ids = source_block.get("atom_ids") or []
        text = str(built.get("memory_text") or "")
        if len(ids) == 1:
            if text != str(source_block.get("memory_text") or ""):
                errors.append(f"singleton_block_changed:{parent_id}")
        else:
            if LIST_MARKER_RE.search(text):
                errors.append(f"visible_atom_markers:{parent_id}")
            if built.get("surface_form") != "natural_paragraph":
                errors.append(f"surface_form_missing:{parent_id}")
    if record.get("composite_block_revision", {}).get("surface_rewrite_pending") is not False:
        errors.append("surface_rewrite_still_pending")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate and apply MemCalib v2.3 natural paragraph rewrites."
    )
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--rejected", type=Path, default=DEFAULT_REJECTED)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()

    benchmarks = {
        str(record.get("id") or ""): record for record in iter_jsonl(args.benchmark)
    }
    requests = list(iter_jsonl(args.requests))
    results = {
        str(result.get("request_id") or ""): result for result in iter_jsonl(args.results)
    }
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for request in requests:
        request_id = str(request.get("request_id") or "")
        params = request_params(request)
        record_id = str(params.get("record_id") or "")
        source = benchmarks.get(record_id)
        result = results.get(request_id)
        errors: list[str] = []
        if source is None:
            errors.append("source_record_missing")
        elif canonical_sha256(source) != params.get("record_fingerprint"):
            errors.append("source_record_fingerprint_mismatch")
        if result is None:
            errors.append("api_result_missing")
        payload: dict[str, Any] | None = None
        if result is not None:
            if request_params(result) and request_params(result) != params:
                errors.append("result_params_mismatch")
            try:
                payload = extract_json_object(output_text(result))
            except (ValueError, json.JSONDecodeError) as exc:
                errors.append(f"invalid_json:{exc}")
        if source is not None and payload is not None:
            errors.extend(validate_payload(payload, source, params))
        built: dict[str, Any] | None = None
        record_audits: list[dict[str, Any]] = []
        if not errors and source is not None and payload is not None:
            try:
                built, record_audits = build_record(source, payload, params)
                errors.extend(validate_record(built, source))
            except (KeyError, TypeError, ValueError, AssertionError) as exc:
                errors.append(f"build_failed:{exc}")
        if errors:
            rejected.append(
                {
                    "request_id": request_id,
                    "record_id": record_id,
                    "errors": errors,
                    "result_present": result is not None,
                }
            )
            continue
        assert built is not None
        accepted.append(built)
        audits.extend(record_audits)

    write_jsonl(args.output, accepted)
    write_jsonl(args.rejected, rejected)
    write_jsonl(args.audit, audits)
    summary = {
        "schema_version": "memcalib-v23-surface-rewrite-post-summary-v1",
        "inputs": {
            "benchmark": {
                "path": portable_path(args.benchmark),
                "sha256": file_sha256(args.benchmark),
            },
            "requests": {
                "path": portable_path(args.requests),
                "sha256": file_sha256(args.requests),
                "count": len(requests),
            },
            "results": {
                "path": portable_path(args.results),
                "sha256": file_sha256(args.results),
                "count": len(results),
            },
        },
        "counts": {
            "accepted": len(accepted),
            "rejected": len(rejected),
            "rewritten_blocks": len(audits),
            "difficulty": dict(
                sorted(
                    Counter(
                        record["composite_block_revision"]["difficulty_level"]
                        for record in accepted
                    ).items()
                )
            ),
        },
        "outputs": {
            "accepted": {
                "path": portable_path(args.output),
                "sha256": file_sha256(args.output),
            },
            "rejected": {
                "path": portable_path(args.rejected),
                "sha256": file_sha256(args.rejected),
            },
            "audit": {
                "path": portable_path(args.audit),
                "sha256": file_sha256(args.audit),
            },
        },
    }
    write_json(args.summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
