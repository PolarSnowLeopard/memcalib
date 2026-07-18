#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = SCRIPT_DIR / "data" / "multidomain" / "full-v2" / "memcalib_v02_multidomain_benchmark_15000.jsonl"
DEFAULT_OUTPUT = (
    SCRIPT_DIR
    / "data"
    / "multidomain"
    / "full-v2"
    / "revision-composite-harda"
    / "composite_harda_patch_input_15000.jsonl"
)
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")
DEFAULT_PROMPT = SCRIPT_DIR / "prompts" / "reconstruct_memcalib_v2_composite_harda_patch_en.txt"
SCHEMA_VERSION = "memcalib-composite-harda-patch-requests-v2"
HARD_A_FAMILIES = (
    "factual_judgment_pollution",
    "scope_overreach",
    "current_evidence_conflict",
    "profile_style_near_neighbor",
    "untriggered_preference",
)
HARD_A_DEFINITIONS = {
    "factual_judgment_pollution": (
        "Factual judgment pollution. Construct a user belief, familiarity, preference, or prior choice that looks "
        "relevant to an objective factual question but is not evidence. The correct answer must be determined by "
        "verifiable facts or the current task, and it must not need to mention or explicitly correct the hidden synthetic "
        "belief. The memory may not be an allergy, diagnosis, treatment belief, safety claim, or other fact that a safe "
        "answer should acknowledge. Using the memory as evidence, weakening the factual conclusion, or personalizing the "
        "fact is the failure direction."
    ),
    "scope_overreach": (
        "Scope overreach. Construct a preference or constraint that is valid in another nearby object, audience, goal, "
        "or scenario but has no legitimate role in the current task. Verify that it cannot control recommendations, "
        "ordering, constraints, safety caveats, formatting, or explanatory emphasis here; if it has even a bounded valid "
        "role, it is B rather than A. In health tasks, allergies, medications, diagnoses, symptoms, contraindications, "
        "risk tolerances, and treatment preferences are disallowed whenever the question concerns care or safety."
    ),
    "current_evidence_conflict": (
        "Current-evidence conflict. Construct an older preference, familiar tool, prior experience, or personal judgment "
        "that is superseded by stronger current evidence, an explicit requirement, current data, or a concrete log in "
        "the question, reference answer, or locked atoms. The superseding anchor must actually be present and named in "
        "family_audit; never invent a current requirement. The ideal answer must follow that evidence without needing to "
        "discuss or explicitly correct the old memory."
    ),
    "profile_style_near_neighbor": (
        "Profile/style near-neighbor misuse. Construct a same-domain profile or style preference that is tempting but "
        "not needed for the current audience and task. Using it would distort required detail, tone, structure, or "
        "professional adequacy; completely ignoring it leaves the ideal answer unchanged. The current task must contain "
        "an audience, format, artifact, or adequacy boundary that makes the preference inapplicable. A general style "
        "preference that could still be honored without harming correctness is B, not A."
    ),
    "untriggered_preference": (
        "Untriggered preference. Construct a real-looking personalization preference that could matter for recommendation, "
        "selection, ranking, or customization, but the current task does not request any such decision. It must not alter "
        "answer structure, implementation syntax, formatting, ranking, or add an irrelevant personalized section. For "
        "artifact-generation tasks, do not choose a coding or presentation preference that could legitimately change the "
        "artifact."
    ),
}
DOMAIN_GUARDRAILS = {
    "health_seed": (
        "Health-domain guardrail: the synthetic memory must be non-clinical. Do not mention a medication, treatment, "
        "diagnosis, symptom attribution, allergy, contraindication, prognosis, referral threshold, urgency judgment, "
        "risk tolerance, or care preference. Prefer a nearby administrative, media, communication-for-another-audience, "
        "or setting-specific memory whose omission cannot alter triage, differential diagnosis, treatment, safety, "
        "formatting, reassurance, or follow-up advice. A hidden misconception about the exact condition or treatment in "
        "the question is disallowed because a responsible answer may need to address it."
    ),
    "coding": (
        "Coding-domain guardrail: if the task requests an artifact, do not create a library, syntax, formatting, comment, "
        "dependency, performance, naming, or implementation-style preference that could produce another valid artifact. "
        "Use either a preference about an unrequested neighboring workflow or a prior convention explicitly overridden "
        "by a locked requirement. The memory must not change even one valid implementation choice."
    ),
    "general": (
        "General-domain guardrail: do not create a recommendation, accessibility, safety, audience, tone, or format "
        "preference if the current task could legitimately honor it. For recommendation questions, avoid preferences "
        "about candidate options or decision criteria. For factual questions, a hidden subjective judgment may be used "
        "only when the objective answer need not acknowledge that judgment."
    ),
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(SCRIPT_DIR.parent))
    except ValueError:
        return str(resolved)


def parse_domain_quotas(values: list[str]) -> dict[str, int]:
    quotas: dict[str, int] = {}
    for value in values:
        domain, separator, count_text = value.rpartition("=")
        if not separator or not domain or not count_text.isdigit():
            raise ValueError(f"invalid domain quota {value!r}; expected DOMAIN=COUNT")
        count = int(count_text)
        if count <= 0 or domain in quotas:
            raise ValueError(f"domain quota must be unique and positive: {value!r}")
        quotas[domain] = count
    return quotas


def stable_order_key(record: dict[str, Any], seed: int, purpose: str) -> str:
    record_id = str(record.get("id") or "")
    return hashlib.sha256(f"{seed}:{purpose}:{record_id}".encode("utf-8")).hexdigest()


def select_records(rows: list[dict[str, Any]], quotas: dict[str, int], seed: int) -> list[dict[str, Any]]:
    if not quotas:
        return list(rows)
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_domain[str(row.get("domain") or "health_seed")].append(row)
    selected: list[dict[str, Any]] = []
    for domain, quota in sorted(quotas.items()):
        candidates = sorted(by_domain.get(domain, []), key=lambda row: stable_order_key(row, seed, "pilot"))
        if len(candidates) < quota:
            raise ValueError(f"domain {domain!r} has {len(candidates)} records; requested {quota}")
        selected.extend(candidates[:quota])
    return sorted(selected, key=lambda row: stable_order_key(row, seed, "selected-order"))


def assign_families(rows: list[dict[str, Any]], seed: int) -> dict[str, str]:
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        record_id = str(row.get("id") or "")
        if not record_id:
            raise ValueError("all records must have non-empty IDs")
        by_domain[str(row.get("domain") or "health_seed")].append(row)
    assignments: dict[str, str] = {}
    for domain, domain_rows in sorted(by_domain.items()):
        ordered = sorted(domain_rows, key=lambda row: stable_order_key(row, seed, f"family:{domain}"))
        for index, row in enumerate(ordered):
            assignments[str(row["id"])] = HARD_A_FAMILIES[index % len(HARD_A_FAMILIES)]
    return assignments


def locked_real_atoms(record: dict[str, Any]) -> list[dict[str, Any]]:
    atoms = [
        atom
        for atom in record.get("memories") or []
        if isinstance(atom, dict) and atom.get("source") != "synthetic_hard_a"
    ]
    if len(atoms) < 2:
        raise ValueError(f"record {record.get('id')} has fewer than two grounded real atoms")
    return [
        {
            "atom_id": atom.get("atom_id"),
            "text": atom.get("text"),
            "source": atom.get("source"),
            "memory_type": atom.get("memory_type"),
            "u_star": atom.get("u_star"),
            "memory_action": atom.get("memory_action"),
            "label_reason": atom.get("label_reason"),
            "construction_target": atom.get("construction_target"),
            "counterfactual_contract": atom.get("counterfactual_contract"),
            "usage_rubric": atom.get("usage_rubric"),
        }
        for atom in atoms
    ]


def render_prompt(record: dict[str, Any], family: str, template: str) -> str:
    domain = str(record.get("domain") or "health_seed")
    replacements = {
        "{record_id}": str(record.get("id") or ""),
        "{domain}": str(record.get("domain") or "health_seed"),
        "{source_dataset}": str(record.get("source_dataset") or ""),
        "{source_topic}": str(record.get("source_topic") or ""),
        "{hard_a_family}": family,
        "{question}": str(record.get("question") or ""),
        "{source_answer}": str(record.get("source_answer") or ""),
        "{real_atoms_json}": json.dumps(locked_real_atoms(record), ensure_ascii=False, indent=2),
        "{hard_a_family_definition}": HARD_A_DEFINITIONS[family],
        "{domain_guardrails}": DOMAIN_GUARDRAILS[domain],
    }
    content = template
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    return content


def build_request(record: dict[str, Any], family: str, template: str) -> dict[str, Any]:
    record_id = str(record.get("id") or "")
    params = {
        "schema_version": SCHEMA_VERSION,
        "record_id": record_id,
        "record_fingerprint": canonical_sha256(record),
        "domain": str(record.get("domain") or "health_seed"),
        "source_dataset": str(record.get("source_dataset") or ""),
        "source_topic": str(record.get("source_topic") or ""),
        "hard_a_family": family,
        "real_atom_ids": [str(atom.get("atom_id") or "") for atom in locked_real_atoms(record)],
    }
    return {
        "request_id": f"composite_harda_patch:{record_id}",
        "prompt": [{"role": "user", "content": render_prompt(record, family, template)}],
        "user_defined_params": params,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare balanced five-family Hard-A revision requests.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--prompt-template", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--domain-quota", action="append", default=[])
    parser.add_argument("--seed", type=int, default=20260719)
    args = parser.parse_args()

    rows = list(iter_jsonl(args.input))
    record_ids = [str(row.get("id") or "") for row in rows]
    if "" in record_ids or len(record_ids) != len(set(record_ids)):
        raise ValueError("input record IDs must be non-empty and unique")
    selected = select_records(rows, parse_domain_quotas(args.domain_quota), args.seed)
    assignments = assign_families(selected, args.seed)
    template = args.prompt_template.read_text(encoding="utf-8")
    requests = [build_request(row, assignments[str(row["id"])], template) for row in selected]
    write_jsonl(args.output, requests)

    family_by_domain: dict[str, Counter[str]] = defaultdict(Counter)
    for row in selected:
        family_by_domain[str(row.get("domain") or "health_seed")][assignments[str(row["id"])]] += 1
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "inputs": {
            "benchmark": {
                "path": portable_path(args.input),
                "sha256": file_sha256(args.input),
                "records": len(rows),
            }
        },
        "implementation": {
            "prepare": {"path": portable_path(Path(__file__)), "sha256": file_sha256(Path(__file__).resolve())},
            "prompt": {"path": portable_path(args.prompt_template), "sha256": file_sha256(args.prompt_template)},
        },
        "parameters": {
            "seed": args.seed,
            "families": list(HARD_A_FAMILIES),
            "domain_quotas": parse_domain_quotas(args.domain_quota),
        },
        "distribution": {
            "domain": dict(sorted(Counter(str(row.get("domain") or "health_seed") for row in selected).items())),
            "hard_a_family": dict(sorted(Counter(assignments[str(row["id"])] for row in selected).items())),
            "hard_a_family_by_domain": {
                domain: dict(sorted(counts.items())) for domain, counts in sorted(family_by_domain.items())
            },
        },
        "output": {
            "path": portable_path(args.output),
            "sha256": file_sha256(args.output),
            "requests": len(requests),
            "unique_request_ids": len({str(row["request_id"]) for row in requests}),
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
