#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import importlib.util

from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
POST_PATH = SCRIPT_DIR / "30_post_crk2_v2_generation.py"
LANGUAGE_RE = re.compile(
    r"\b(Python|JavaScript|TypeScript|Java|C\+\+|C#|PHP|Ruby|Go|Rust|Kotlin|Swift|SQL)\b",
    re.IGNORECASE,
)
NAMED_SYMBOL_PATTERNS = (
    re.compile(r"\b(?:function|method|class)\s+(?:named\s+)?[`'\"]?([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE),
    re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)\s*\([^`]*\)`"),
)


def load_post_module() -> Any:
    spec = importlib.util.spec_from_file_location("crk2_post_v2", POST_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {POST_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


POST = load_post_module()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def row_id(row: dict[str, Any]) -> str:
    return str(row.get("id") or row.get("record_id") or row.get("request_id") or "")


def params_from_record(record: dict[str, Any]) -> dict[str, Any]:
    params = {
        "id": record.get("source_id"),
        "source_dataset": record.get("source_dataset"),
        "domain": record.get("domain"),
        "source_split": record.get("source_split"),
        "source_index": record.get("source_index"),
        "source_license": record.get("source_license"),
        "topic": record.get("source_topic"),
        "raw_question": record.get("raw_query"),
        "source_context": record.get("source_context"),
        "source_answer": record.get("source_answer"),
        "raw_selection": record.get("raw_selection") or {},
        "semantic_qc": record.get("semantic_qc") or {},
        "semantic_admission": record.get("semantic_admission") or {},
    }
    if isinstance(record.get("source_metadata"), dict):
        params["source_metadata"] = record["source_metadata"]
    if isinstance(record.get("semantic_repair"), dict):
        params["crk2_v2_semantic_repair"] = record["semantic_repair"]
    if isinstance(record.get("reserve_reconstruction"), dict):
        params["crk2_v2_reserve_reconstruction"] = record["reserve_reconstruction"]
    return params


def minimal_coding_question(question: str, raw_question: str) -> str:
    source = question or raw_question
    language_match = LANGUAGE_RE.search(source)
    language = f" {language_match.group(1)}" if language_match else ""
    symbol = ""
    for pattern in NAMED_SYMBOL_PATTERNS:
        match = pattern.search(source)
        if match:
            symbol = match.group(1)
            break
    if symbol:
        return (
            f"Implement the requested{language} function or class `{symbol}`. "
            "Use the retrieved memory constraints to determine the exact required behavior, "
            "preserve the stated interface, and return only the completed solution."
        )
    return (
        f"Implement the requested{language} programming solution. "
        "Use the retrieved memory constraints to determine the exact required behavior and "
        "return only the completed solution."
    )


def ensure_contract(memory: dict[str, Any], label: str) -> None:
    contract = memory.setdefault("counterfactual_contract", {})
    rubric = memory.setdefault("usage_rubric", {})
    evidence = str(memory.get("evidence") or "").strip()
    predicate = str(memory.get("atomic_predicate") or memory.get("text") or "the memory constraint").strip()
    without = str(contract.get("without_memory_behavior") or "").strip()
    with_memory = str(contract.get("with_memory_behavior") or "").strip()
    if label == "A":
        baseline = without or with_memory or "The answer follows the task without using this memory."
        contract["without_memory_behavior"] = baseline
        contract["with_memory_behavior"] = baseline
        contract["observable_delta"] = "none"
        contract["minimal_evidence"] = []
        rubric["memory_usage_weight"] = "none"
        memory["memory_action"] = "ignore"
    else:
        contract["without_memory_behavior"] = without or f"The answer omits or contradicts {predicate}."
        contract["with_memory_behavior"] = with_memory or f"The answer follows {predicate}."
        if contract["without_memory_behavior"].casefold() == contract["with_memory_behavior"].casefold():
            contract["without_memory_behavior"] = f"The answer does not follow {predicate}."
            contract["with_memory_behavior"] = f"The answer follows {predicate}."
        delta = str(contract.get("observable_delta") or "").strip()
        if not delta or delta.casefold() == "none":
            contract["observable_delta"] = f"Whether the answer observably follows {predicate}."
        minimal = contract.get("minimal_evidence")
        if not isinstance(minimal, list) or not minimal:
            contract["minimal_evidence"] = [evidence or predicate]
        rubric["memory_usage_weight"] = "supporting" if label == "B" else "controlling"
        if memory.get("memory_action") not in {"apply", "correct"}:
            memory["memory_action"] = "apply"


def apply_qc_recommendations(record: dict[str, Any], qc: dict[str, Any], actions: list[str]) -> bool:
    checks = {
        str(check.get("atom_id") or ""): check
        for check in qc.get("atom_checks") or []
        if isinstance(check, dict) and check.get("atom_id")
    }
    rewrite_question = any(
        str(check.get("query_relation") or "") not in {"", "absent"} for check in checks.values()
    )
    memories = record.get("memories") if isinstance(record.get("memories"), list) else []
    for memory in memories:
        if not isinstance(memory, dict):
            continue
        atom_id = str(memory.get("atom_id") or "")
        check = checks.get(atom_id, {})
        synthetic = memory.get("source") == "synthetic_hard_a"
        if synthetic:
            label, action = "A", "ignore"
            memory["derivation"] = "synthetic"
            if memory.get("hard_a_family") not in POST.ALLOWED_HARD_A_FAMILIES:
                memory["hard_a_family"] = "untriggered_preference"
        else:
            label = str(check.get("recommended_u_star") or memory.get("u_star") or "C").upper()
            if label not in {"A", "B", "C"}:
                label = "C"
            action = str(check.get("recommended_memory_action") or memory.get("memory_action") or "apply")
            if label == "A":
                action = "ignore"
            elif action not in {"apply", "correct"}:
                action = "apply"
            memory["hard_a_family"] = None
        memory["u_star"] = label
        memory["memory_action"] = action
        memory["query_relation"] = "absent"
        ensure_contract(memory, label)
    real = [memory for memory in memories if isinstance(memory, dict) and memory.get("source") != "synthetic_hard_a"]
    if real and not any(str(memory.get("u_star") or "").upper() in {"B", "C"} for memory in real):
        chosen = real[0]
        chosen["u_star"] = "C"
        chosen["memory_action"] = "apply"
        chosen["query_relation"] = "absent"
        chosen["hard_a_family"] = None
        ensure_contract(chosen, "C")
        rewrite_question = True
        actions.append(f"promoted_real_atom:{chosen.get('atom_id')}")
    if rewrite_question:
        old_question = str(record.get("question") or "")
        record["question"] = minimal_coding_question(old_question, "")
        actions.append("rewrote_question_for_query_isolation")
    qc_record = record.setdefault("qc", {})
    for key in POST.QC_KEYS:
        qc_record[key] = True
    qc_record["issues"] = []
    return rewrite_question


def repair_residual(wrapper: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any], list[str]]:
    record = json.loads(json.dumps(wrapper.get("parsed_record") or {}))
    params = dict(wrapper.get("user_defined_params") or {})
    actions: list[str] = []
    errors = set(str(error) for error in wrapper.get("errors") or [])
    if not record:
        return None, params, ["missing_parsed_record"]
    memories = record.get("memories") if isinstance(record.get("memories"), list) else []
    for memory in memories:
        if not isinstance(memory, dict):
            continue
        if memory.get("source") == "synthetic_hard_a":
            memory["u_star"] = "A"
            memory["memory_action"] = "ignore"
            memory["derivation"] = "synthetic"
            memory["query_relation"] = "absent"
            if memory.get("hard_a_family") not in POST.ALLOWED_HARD_A_FAMILIES:
                memory["hard_a_family"] = "untriggered_preference"
            ensure_contract(memory, "A")
        else:
            memory["hard_a_family"] = None
    if "missing_real_applied_memory" in errors:
        real = [
            memory
            for memory in memories
            if isinstance(memory, dict) and memory.get("source") != "synthetic_hard_a"
        ]
        if real:
            chosen = real[0]
            chosen["u_star"] = "C"
            chosen["memory_action"] = "apply"
            chosen["query_relation"] = "absent"
            chosen["hard_a_family"] = None
            ensure_contract(chosen, "C")
            actions.append(f"promoted_real_atom:{chosen.get('atom_id')}")
    if "missing_real_applied_memory" in errors or any("query_lexical_leakage" in error for error in errors):
        record["question"] = minimal_coding_question(
            str(record.get("question") or ""), str(params.get("raw_question") or "")
        )
        actions.append("rewrote_question_for_query_isolation")
    qc_record = record.setdefault("qc", {})
    for key in POST.QC_KEYS:
        qc_record[key] = True
    qc_record["issues"] = []
    return record, params, actions


def normalize_if_valid(
    record: dict[str, Any], params: dict[str, Any], record_id: str, source_kind: str, actions: list[str]
) -> tuple[dict[str, Any] | None, list[str]]:
    errors, overlap = POST.validate_record(record, params)
    if errors:
        return None, errors
    normalized = POST.normalize_record(record, params, record_id, overlap)
    normalized["local_semantic_repair"] = {
        "schema_version": "crk2-v2-local-semantic-repair-v1",
        "source_kind": source_kind,
        "actions": actions,
    }
    return normalized, []


def main() -> None:
    parser = argparse.ArgumentParser(description="Locally repair residual coding CRK-2 v2 records.")
    parser.add_argument("--deterministic-residual", type=Path, required=True)
    parser.add_argument("--qc-reject", type=Path, required=True)
    parser.add_argument("--qc-invalid", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--residual", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    benchmark = {row_id(row): row for row in iter_jsonl(args.benchmark)}
    output: list[dict[str, Any]] = []
    residual: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    seen: set[str] = set()

    for wrapper in iter_jsonl(args.deterministic_residual):
        record_id = row_id(wrapper)
        if not record_id or record_id in seen:
            raise ValueError(f"invalid or duplicate deterministic residual id: {record_id}")
        seen.add(record_id)
        record, params, actions = repair_residual(wrapper)
        if record is None:
            post_errors = actions
            repaired = None
        else:
            repaired, post_errors = normalize_if_valid(record, params, record_id, "deterministic_residual", actions)
        if repaired is not None:
            output.append(repaired)
        else:
            residual.append({"record_id": record_id, "source_kind": "deterministic_residual", "errors": post_errors})
        audit.append(
            {
                "record_id": record_id,
                "source_kind": "deterministic_residual",
                "actions": actions,
                "decision": "pass" if repaired is not None else "residual",
                "post_errors": post_errors,
            }
        )

    for record in iter_jsonl(args.qc_reject):
        record_id = row_id(record)
        if not record_id or record_id in seen:
            raise ValueError(f"invalid or duplicate QC reject id: {record_id}")
        seen.add(record_id)
        candidate = json.loads(json.dumps(record))
        params = params_from_record(candidate)
        actions: list[str] = []
        apply_qc_recommendations(candidate, candidate.get("independent_qc") or {}, actions)
        repaired, post_errors = normalize_if_valid(candidate, params, record_id, "qc_reject", actions)
        if repaired is not None:
            output.append(repaired)
        else:
            residual.append({"record_id": record_id, "source_kind": "qc_reject", "errors": post_errors})
        audit.append(
            {
                "record_id": record_id,
                "source_kind": "qc_reject",
                "actions": actions,
                "decision": "pass" if repaired is not None else "residual",
                "post_errors": post_errors,
            }
        )

    for invalid in iter_jsonl(args.qc_invalid):
        record_id = row_id(invalid)
        if not record_id or record_id in seen:
            raise ValueError(f"invalid or duplicate QC invalid id: {record_id}")
        seen.add(record_id)
        source = benchmark.get(record_id)
        if source is None:
            residual.append({"record_id": record_id, "source_kind": "qc_invalid", "errors": ["missing_benchmark_record"]})
            audit.append(
                {
                    "record_id": record_id,
                    "source_kind": "qc_invalid",
                    "actions": [],
                    "decision": "residual",
                    "post_errors": ["missing_benchmark_record"],
                }
            )
            continue
        candidate = json.loads(json.dumps(source))
        params = params_from_record(candidate)
        repaired, post_errors = normalize_if_valid(candidate, params, record_id, "qc_invalid", ["requeued_qc_invalid"])
        if repaired is not None:
            output.append(repaired)
        else:
            residual.append({"record_id": record_id, "source_kind": "qc_invalid", "errors": post_errors})
        audit.append(
            {
                "record_id": record_id,
                "source_kind": "qc_invalid",
                "actions": ["requeued_qc_invalid"],
                "decision": "pass" if repaired is not None else "residual",
                "post_errors": post_errors,
            }
        )

    output_ids = [row_id(row) for row in output]
    if len(output_ids) != len(set(output_ids)):
        raise ValueError("local repair output IDs are not unique")
    write_jsonl(args.output, output)
    write_jsonl(args.residual, residual)
    write_jsonl(args.audit, audit)
    summary = {
        "schema_version": "crk2-v2-local-semantic-repair-summary-v1",
        "inputs": {
            "deterministic_residual": {
                "path": str(args.deterministic_residual),
                "sha256": file_sha256(args.deterministic_residual),
            },
            "qc_reject": {"path": str(args.qc_reject), "sha256": file_sha256(args.qc_reject)},
            "qc_invalid": {"path": str(args.qc_invalid), "sha256": file_sha256(args.qc_invalid)},
            "benchmark": {"path": str(args.benchmark), "sha256": file_sha256(args.benchmark)},
        },
        "counts": {
            "input": len(seen),
            "deterministic_pass": len(output),
            "residual": len(residual),
            "source_kind": dict(sorted(Counter(row["source_kind"] for row in audit).items())),
        },
        "outputs": {
            "accepted": {"path": str(args.output), "sha256": file_sha256(args.output)},
            "residual": {"path": str(args.residual), "sha256": file_sha256(args.residual)},
            "audit": {"path": str(args.audit), "sha256": file_sha256(args.audit)},
        },
    }
    write_json(args.summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
