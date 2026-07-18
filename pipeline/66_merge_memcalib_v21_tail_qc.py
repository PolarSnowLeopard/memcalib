#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path
from typing import Any

from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
REVISION_DIR = SCRIPT_DIR / "data" / "multidomain" / "full-v2" / "revision-composite-harda"
DEFAULT_INPUT = (
    REVISION_DIR
    / "direct-tail-repair-v5"
    / "memcalib_v21_benchmark_15000.direct5.jsonl"
)
DEFAULT_OUTPUT = (
    REVISION_DIR
    / "final-adjudication"
    / "memcalib_v21_benchmark_15000.strict_adjudicated.jsonl"
)
DEFAULT_AUDIT = (
    REVISION_DIR
    / "final-adjudication"
    / "memcalib_v21_tail_qc_93.audit.jsonl"
)
DEFAULT_SUMMARY = (
    REVISION_DIR
    / "final-adjudication"
    / "memcalib_v21_tail_qc_93.summary.json"
)
SCHEMA_VERSION = "memcalib-v21-multi-judge-tail-adjudication-v1"


QC_STAGES = (
    {
        "name": "direct_v2_full_tail",
        "records": (
            REVISION_DIR
            / "direct-tail-repair-v2"
            / "memcalib_v21_tail_repaired_93.jsonl"
        ),
        "deepseek": (
            REVISION_DIR
            / "direct-tail-repair-v2"
            / "qc-deepseek"
            / "memcalib_v21_tail_qc_93"
        ),
        "kimi": (
            REVISION_DIR
            / "direct-tail-repair-v2"
            / "qc-kimi"
            / "memcalib_v21_tail_qc_93"
        ),
    },
    {
        "name": "direct_v3_changed_8",
        "records": (
            REVISION_DIR
            / "direct-tail-repair-v3"
            / "memcalib_v21_tail_changed_8.jsonl"
        ),
        "deepseek": (
            REVISION_DIR
            / "direct-tail-repair-v3"
            / "qc-deepseek"
            / "memcalib_v21_tail_qc_8"
        ),
        "kimi": (
            REVISION_DIR
            / "direct-tail-repair-v3"
            / "qc-kimi"
            / "memcalib_v21_tail_qc_8"
        ),
    },
    {
        "name": "direct_v4_changed_1",
        "records": (
            REVISION_DIR
            / "direct-tail-repair-v4"
            / "memcalib_v21_tail_changed_1.jsonl"
        ),
        "deepseek": (
            REVISION_DIR
            / "direct-tail-repair-v4"
            / "qc-deepseek"
            / "memcalib_v21_tail_qc_1"
        ),
        "kimi": (
            REVISION_DIR
            / "direct-tail-repair-v4"
            / "qc-kimi"
            / "memcalib_v21_tail_qc_1"
        ),
    },
    {
        "name": "direct_v5_changed_4",
        "records": (
            REVISION_DIR
            / "direct-tail-repair-v5"
            / "memcalib_v21_tail_changed_4.jsonl"
        ),
        "deepseek": (
            REVISION_DIR
            / "direct-tail-repair-v5"
            / "qc-deepseek"
            / "memcalib_v21_tail_qc_4"
        ),
        "kimi": (
            REVISION_DIR
            / "direct-tail-repair-v5"
            / "qc-kimi"
            / "memcalib_v21_tail_qc_4"
        ),
    },
)


# These are the only records for which exactly one independent judge returned
# strict_pass. Each was manually checked against raw_query, source_context, and
# source_answer, and then passed the deterministic validator. The other judge's
# full output and reasons remain in the audit.
MANUAL_TIEBREAK_IDS = {
    "crk2_v2_raw_66a047421d148d71",
    "crk2_v2_raw_69d27d969d6c83d0",
    "crk2_v2_raw_87c1591ec86168dd",
    "crk2_v2_raw_883971c4bbade41b",
    "crk2_v2_raw_ab677c86405633ee",
    "crk2_v2_raw_ad7584be911bfdb6",
    "crk2_v2_raw_bb847900cd8291ed",
    "crk2_v2_raw_cc6dc9209c16a98a",
    "crk2_v2_raw_coding_64faae1f212bd368",
    "crk2_v2_raw_coding_78aeecfd114d0c67",
    "crk2_v2_raw_coding_981fa5600979dcf0",
    "crk2_v2_raw_coding_df65e7c3402d8f6c",
    "crk2_v2_raw_general_8a326d9de341b5c3",
    "crk2_v2_raw_general_dbba5c5157b5402d",
}


def load_direct_validator():
    path = SCRIPT_DIR / "65_direct_repair_memcalib_v21_tail.py"
    spec = importlib.util.spec_from_file_location("memcalib_v21_direct_tail", path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("could not load direct-tail validator")
    spec.loader.exec_module(module)
    return module


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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


def load_qc_categories(prefix: Path) -> dict[str, dict[str, Any]]:
    decisions: dict[str, dict[str, Any]] = {}
    for decision, suffix in (
        ("strict_pass", "strict"),
        ("review", "review"),
        ("reject", "reject"),
        ("invalid", "invalid"),
    ):
        path = prefix.with_suffix(f".{suffix}.jsonl")
        for row in iter_jsonl(path):
            qc = row.get("revision_independent_qc") or row
            record_id = str(row.get("id") or qc.get("record_id") or "")
            if not record_id or record_id in decisions:
                raise ValueError(f"{path}: missing or duplicate record_id")
            if str(qc.get("computed_decision") or "") != decision:
                raise ValueError(f"{path}: category/decision mismatch for {record_id}")
            decisions[record_id] = copy.deepcopy(qc)
    return decisions


def adjudicate_pair(
    record: dict[str, Any],
    *,
    stage_name: str,
    deepseek_qc: dict[str, Any],
    kimi_qc: dict[str, Any],
    deterministic_errors: list[str],
    manual_tiebreak_ids: set[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    record_id = str(record.get("id") or "")
    deepseek_decision = str(deepseek_qc.get("computed_decision") or "")
    kimi_decision = str(kimi_qc.get("computed_decision") or "")
    decisions = {
        "deepseek-v4-pro": deepseek_decision,
        "kimi-k2.6": kimi_decision,
    }
    strict_count = sum(value == "strict_pass" for value in decisions.values())
    if deterministic_errors:
        raise ValueError(f"{record_id}: deterministic errors: {deterministic_errors}")
    if strict_count == 2:
        mode = "dual_judge_strict_consensus"
        manual = None
    elif strict_count == 1:
        if record_id not in manual_tiebreak_ids:
            raise ValueError(f"{record_id}: unapproved one-strict judge disagreement")
        mode = "manual_deterministic_tiebreak"
        manual = {
            "decision": "strict_pass",
            "review_scope": [
                "raw_query",
                "source_context",
                "source_answer",
                "real_atom evidence and label/action contracts",
                "exact composite reconstruction",
                "Hard-A family boundary and zero-footprint contract",
            ],
            "basis": (
                "One independent judge passed the record. The non-strict output was "
                "reviewed against the full source evidence and deterministic invariants; "
                "no shared non-strict finding remained."
            ),
        }
    else:
        raise ValueError(f"{record_id}: no independent judge returned strict_pass: {decisions}")

    fingerprint = canonical_sha256(record)
    final_qc = {
        "schema_version": SCHEMA_VERSION,
        "record_id": record_id,
        "record_fingerprint_before_qc": fingerprint,
        "computed_decision": "strict_pass",
        "computed_reasons": [],
        "adjudication_mode": mode,
        "qc_stage": stage_name,
        "judges": {
            "deepseek-v4-pro": deepseek_qc,
            "kimi-k2.6": kimi_qc,
        },
        "deterministic_validation": {
            "decision": "pass",
            "errors": [],
        },
        "manual_adjudication": manual,
    }
    audit = {
        "schema_version": SCHEMA_VERSION,
        "record_id": record_id,
        "record_fingerprint": fingerprint,
        "domain": record.get("domain"),
        "hard_a_family": next(
            (
                atom.get("hard_a_family")
                for atom in record.get("memories") or []
                if atom.get("source") == "synthetic_hard_a"
            ),
            None,
        ),
        "qc_stage": stage_name,
        "judge_decisions": decisions,
        "judge_reasons": {
            "deepseek-v4-pro": deepseek_qc.get("computed_reasons") or [],
            "kimi-k2.6": kimi_qc.get("computed_reasons") or [],
        },
        "adjudication_mode": mode,
        "manual_adjudication": manual,
        "decision": "strict_pass",
    }
    return final_qc, audit


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge staged two-judge QC and explicitly adjudicate the repaired v2.1 tail."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()

    direct = load_direct_validator()
    rows = list(iter_jsonl(args.input))
    ids = [str(row.get("id") or "") for row in rows]
    if "" in ids or len(ids) != len(set(ids)):
        raise ValueError("input record IDs must be non-empty and unique")
    tail_ids = {
        str(row["id"])
        for row in rows
        if isinstance(row.get("direct_tail_repair"), dict)
    }
    if len(tail_ids) != 93:
        raise ValueError(f"expected 93 direct-tail records, found {len(tail_ids)}")

    stage_index: dict[tuple[str, str], dict[str, Any]] = {}
    stage_manifest = []
    for stage in QC_STAGES:
        stage_rows = list(iter_jsonl(stage["records"]))
        deepseek = load_qc_categories(stage["deepseek"])
        kimi = load_qc_categories(stage["kimi"])
        stage_ids = {str(row.get("id") or "") for row in stage_rows}
        if stage_ids != set(deepseek) or stage_ids != set(kimi):
            raise ValueError(f"{stage['name']}: record/QC coverage mismatch")
        for row in stage_rows:
            record_id = str(row["id"])
            key = (record_id, canonical_sha256(row))
            if key in stage_index:
                raise ValueError(f"{stage['name']}: duplicate record fingerprint across stages")
            stage_index[key] = {
                "name": stage["name"],
                "deepseek": deepseek[record_id],
                "kimi": kimi[record_id],
            }
        stage_manifest.append(
            {
                "name": stage["name"],
                "records": {
                    "path": portable_path(stage["records"]),
                    "sha256": file_sha256(stage["records"]),
                    "count": len(stage_rows),
                },
                "deepseek_prefix": portable_path(stage["deepseek"]),
                "kimi_prefix": portable_path(stage["kimi"]),
            }
        )

    output: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    matched_tiebreak_ids: set[str] = set()
    for row in rows:
        record_id = str(row["id"])
        if record_id not in tail_ids:
            if (row.get("revision_independent_qc") or {}).get("computed_decision") != "strict_pass":
                raise ValueError(f"{record_id}: non-tail record is not strict_pass")
            output.append(row)
            continue
        key = (record_id, canonical_sha256(row))
        stage = stage_index.get(key)
        if stage is None:
            raise ValueError(f"{record_id}: no QC stage matches the final record fingerprint")
        deterministic_errors = direct.validate_record(row)
        final_qc, audit = adjudicate_pair(
            row,
            stage_name=stage["name"],
            deepseek_qc=stage["deepseek"],
            kimi_qc=stage["kimi"],
            deterministic_errors=deterministic_errors,
            manual_tiebreak_ids=MANUAL_TIEBREAK_IDS,
        )
        if final_qc["adjudication_mode"] == "manual_deterministic_tiebreak":
            matched_tiebreak_ids.add(record_id)
        finalized = copy.deepcopy(row)
        finalized["revision_independent_qc"] = final_qc
        output.append(finalized)
        audits.append(audit)

    if matched_tiebreak_ids != MANUAL_TIEBREAK_IDS:
        raise ValueError(
            "manual tiebreak coverage mismatch: "
            f"missing={sorted(MANUAL_TIEBREAK_IDS - matched_tiebreak_ids)} "
            f"extra={sorted(matched_tiebreak_ids - MANUAL_TIEBREAK_IDS)}"
        )
    if len(audits) != 93:
        raise ValueError(f"expected 93 tail audits, found {len(audits)}")
    if any(
        (row.get("revision_independent_qc") or {}).get("computed_decision") != "strict_pass"
        for row in output
    ):
        raise ValueError("final output contains non-strict records")

    write_jsonl(args.output, output)
    write_jsonl(args.audit, audits)
    modes = Counter(audit["adjudication_mode"] for audit in audits)
    judge_pairs = Counter(
        (
            audit["judge_decisions"]["deepseek-v4-pro"],
            audit["judge_decisions"]["kimi-k2.6"],
        )
        for audit in audits
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "input": {
            "path": portable_path(args.input),
            "sha256": file_sha256(args.input),
            "records": len(rows),
        },
        "qc_stages": stage_manifest,
        "counts": {
            "output_records": len(output),
            "unique_record_ids": len({str(row["id"]) for row in output}),
            "preexisting_strict_records": len(output) - len(audits),
            "tail_records": len(audits),
            "tail_strict_records": sum(audit["decision"] == "strict_pass" for audit in audits),
            "dual_judge_strict_consensus": modes["dual_judge_strict_consensus"],
            "manual_deterministic_tiebreak": modes["manual_deterministic_tiebreak"],
            "both_judges_non_strict": sum(
                all(value != "strict_pass" for value in audit["judge_decisions"].values())
                for audit in audits
            ),
        },
        "judge_decision_pairs": {
            f"deepseek={deepseek}|kimi={kimi}": count
            for (deepseek, kimi), count in sorted(judge_pairs.items())
        },
        "outputs": {
            "benchmark": {
                "path": portable_path(args.output),
                "sha256": file_sha256(args.output),
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
