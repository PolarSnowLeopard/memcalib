#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from memcalib_v23_common import canonical_sha256, file_sha256, portable_path
from memcalib_v24_coding_common import (
    TASK_FAMILIES,
    V23_RELEASE,
    V24_DIR,
    stable_task_family,
)
from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
AUDIT_DIR = V24_DIR / "audit"
DEFAULT_PROMPT = (
    SCRIPT_DIR / "prompts" / "rewrite_memcalib_v241_relabel_aware_en.txt"
)
DEFAULT_OUTPUT = AUDIT_DIR / "memcalib_v241_relabel_aware_input_785.jsonl"
REQUEST_SCHEMA = "memcalib-v241-relabel-aware-repair-requests-v1"


def atom_identity_fingerprint(record: dict[str, Any]) -> str:
    return canonical_sha256(
        [
            {
                "atom_id": atom.get("atom_id"),
                "text": atom.get("text"),
                "atomic_predicate": atom.get("atomic_predicate"),
                "evidence": atom.get("evidence"),
                "memory_action": atom.get("memory_action"),
                "parent_memory_id": atom.get("parent_memory_id"),
            }
            for atom in record.get("memories") or []
        ]
    )


def compact_blocks(record: dict[str, Any]) -> list[dict[str, Any]]:
    atoms = {
        str(atom.get("atom_id") or ""): atom for atom in record.get("memories") or []
    }
    output: list[dict[str, Any]] = []
    for block in record.get("memory_blocks") or []:
        compact_atoms: list[dict[str, Any]] = []
        for raw_atom_id in block.get("atom_ids") or []:
            atom_id = str(raw_atom_id)
            atom = atoms.get(atom_id)
            if atom is None:
                continue
            compact_atoms.append(
                {
                    "atom_id": atom_id,
                    "text": atom.get("text"),
                    "u_star": atom.get("u_star"),
                    "memory_action": atom.get("memory_action"),
                }
            )
        output.append(
            {
                "parent_memory_id": block.get("parent_memory_id"),
                "memory_text": block.get("memory_text"),
                "atoms": compact_atoms,
            }
        )
    return output


def load_selection(paths: list[Path]) -> tuple[list[str], dict[str, list[str]]]:
    order: list[str] = []
    feedback: dict[str, list[str]] = {}
    seen: set[str] = set()
    for path in paths:
        for row in iter_jsonl(path):
            record_id = str(row.get("id") or row.get("record_id") or "")
            if not record_id:
                raise ValueError(f"empty record ID in {path}")
            if record_id not in seen:
                seen.add(record_id)
                order.append(record_id)
            details = feedback.setdefault(record_id, [])
            for error in row.get("errors") or []:
                if isinstance(error, str) and error not in details:
                    details.append(error)
            for item in row.get("feedback") or []:
                if isinstance(item, str) and item not in details:
                    details.append(item)
    return order, feedback


def load_candidates(paths: list[Path]) -> dict[str, dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    for path in paths:
        for row in iter_jsonl(path):
            record_id = str(row.get("id") or "")
            if not record_id:
                raise ValueError(f"empty candidate ID in {path}")
            candidates[record_id] = row
    return candidates


def render_prompt(
    template: str,
    source: dict[str, Any],
    candidate: dict[str, Any] | None,
    family: str,
    feedback: list[str],
) -> str:
    replacements = {
        "{record_id}": str(source["id"]),
        "{task_family}": family,
        "{original_question}": str(source.get("question") or ""),
        "{original_reference_answer}": str(source.get("source_answer") or ""),
        "{candidate_question}": (
            str(candidate.get("question") or "") if candidate else "None."
        ),
        "{candidate_reference_answer}": (
            str(candidate.get("source_answer") or "") if candidate else "None."
        ),
        "{blocks_json}": json.dumps(
            compact_blocks(source), ensure_ascii=False, indent=2
        ),
        "{repair_feedback}": json.dumps(
            feedback or ["No valid prior candidate; rebuild from the original record."],
            ensure_ascii=False,
            indent=2,
        ),
    }
    content = template
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    return content


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare relabel-aware direct repairs for residual v2.4 coding rows."
    )
    parser.add_argument("--benchmark", type=Path, default=V23_RELEASE)
    parser.add_argument("--selection-jsonl", type=Path, action="append", required=True)
    parser.add_argument("--candidate-jsonl", type=Path, action="append", default=[])
    parser.add_argument("--prompt-template", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    selection_order, feedback = load_selection(args.selection_jsonl)
    selected = set(selection_order)
    candidates = load_candidates(args.candidate_jsonl)
    sources = {
        str(record.get("id") or ""): record
        for record in iter_jsonl(args.benchmark)
        if str(record.get("id") or "") in selected
    }
    missing = selected - set(sources)
    if missing:
        raise ValueError(f"selected IDs missing from benchmark: {sorted(missing)[:20]}")
    template = args.prompt_template.read_text(encoding="utf-8")
    requests: list[dict[str, Any]] = []
    label_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    for record_id in selection_order:
        source = sources[record_id]
        if source.get("domain") != "coding":
            raise ValueError(f"non-coding record selected: {record_id}")
        family = stable_task_family(record_id)
        if family not in TASK_FAMILIES:
            raise ValueError(f"unsupported task family: {family}")
        family_counts[family] += 1
        label_counts.update(
            str(atom.get("u_star") or "") for atom in source.get("memories") or []
        )
        params = {
            "schema_version": REQUEST_SCHEMA,
            "record_id": record_id,
            "source_record_fingerprint": canonical_sha256(source),
            "memory_blocks_fingerprint": canonical_sha256(
                source.get("memory_blocks") or []
            ),
            "atom_identity_fingerprint": atom_identity_fingerprint(source),
            "task_family": family,
            "expected_atom_ids": [
                str(atom.get("atom_id") or "")
                for atom in source.get("memories") or []
            ],
            "expected_bc_atom_ids": [
                str(atom.get("atom_id") or "")
                for atom in source.get("memories") or []
                if atom.get("u_star") in {"B", "C"}
            ],
            "expected_a_atom_ids": [
                str(atom.get("atom_id") or "")
                for atom in source.get("memories") or []
                if atom.get("u_star") == "A"
            ],
            "immutable_a_atom_ids": [
                str(atom.get("atom_id") or "")
                for atom in source.get("memories") or []
                if atom.get("u_star") == "A"
                and str(atom.get("atom_id") or "").startswith(
                    ("v22_harda_", "v22_noise_")
                )
            ],
            "revisable_a_atom_ids": [
                str(atom.get("atom_id") or "")
                for atom in source.get("memories") or []
                if atom.get("u_star") == "A"
                and not str(atom.get("atom_id") or "").startswith(
                    ("v22_harda_", "v22_noise_")
                )
            ],
            "feedback_fingerprint": canonical_sha256(feedback.get(record_id) or []),
        }
        requests.append(
            {
                "request_id": f"v241_relabel_aware:{record_id}",
                "prompt": [
                    {
                        "role": "user",
                        "content": render_prompt(
                            template,
                            source,
                            candidates.get(record_id),
                            family,
                            feedback.get(record_id) or [],
                        ),
                    }
                ],
                "user_defined_params": params,
            }
        )

    write_jsonl(args.output, requests)
    manifest_path = args.manifest or args.output.with_suffix(".manifest.json")
    manifest = {
        "schema_version": "memcalib-v241-relabel-aware-repair-manifest-v1",
        "inputs": {
            "benchmark": {
                "path": portable_path(args.benchmark),
                "sha256": file_sha256(args.benchmark),
            },
            "selection_jsonl": [
                {"path": portable_path(path), "sha256": file_sha256(path)}
                for path in args.selection_jsonl
            ],
            "candidate_jsonl": [
                {"path": portable_path(path), "sha256": file_sha256(path)}
                for path in args.candidate_jsonl
            ],
            "prompt_template": {
                "path": portable_path(args.prompt_template),
                "sha256": file_sha256(args.prompt_template),
            },
        },
        "output": {
            "path": portable_path(args.output),
            "sha256": file_sha256(args.output),
            "count": len(requests),
            "unique_request_ids": len(
                {str(request["request_id"]) for request in requests}
            ),
            "unique_record_ids": len(
                {
                    str(request["user_defined_params"]["record_id"])
                    for request in requests
                }
            ),
        },
        "task_family_counts": dict(sorted(family_counts.items())),
        "source_atom_label_counts": dict(sorted(label_counts.items())),
    }
    write_json(manifest_path, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
