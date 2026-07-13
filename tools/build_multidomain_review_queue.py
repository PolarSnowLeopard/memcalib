#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_DIR = ROOT / "pipeline"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


AUDIT = load_module("memcalib_canonical_audit", PIPELINE_DIR / "12_build_canonical_audit_artifacts.py")
VALIDATOR = load_module("memcalib_multidomain_validator", PIPELINE_DIR / "28_validate_multidomain_benchmark.py")

SCHEMA_VERSION = "memcalib-multidomain-human-review-queue-v1"
DEFAULT_RELEASE_DIR = ROOT / "release" / "memcalib-multidomain-pilot-v0.2"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number} is not a JSON object")
            rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(seed: int, value: str) -> str:
    return hashlib.sha256(f"{seed}\0{value}".encode("utf-8")).hexdigest()


def answer_overlap_atom_count(row: dict[str, Any]) -> int:
    visible_shingles = VALIDATOR.shingles(row.get("raw_query")) | VALIDATOR.shingles(row.get("source_context"))
    answer_only = VALIDATOR.shingles(row.get("source_answer")) - visible_shingles
    count = 0
    for memory in row.get("memories") or []:
        if memory.get("source") == "synthetic_hard_a":
            continue
        memory_shingles = VALIDATOR.shingles(memory.get("text")) | VALIDATOR.shingles(memory.get("atomic_predicate"))
        count += int(bool(answer_only & memory_shingles))
    return count


def sample_signals(row: dict[str, Any]) -> dict[str, Any]:
    blocks = list(row.get("memory_blocks") or [])
    non_atomic_count = sum(
        int(block.get("atom_count") or len(block.get("atom_ids") or [])) > 1
        for block in blocks
    )
    mixed_parent_count = sum(
        str(block.get("parent_label_mode") or "") == "mixed"
        or len(set(str(label) for label in block.get("parent_label_set") or [])) > 1
        for block in blocks
    )
    label_counts = Counter(str(memory.get("u_star") or "unknown") for memory in row.get("memories") or [])
    lineage = row.get("lineage") if isinstance(row.get("lineage"), dict) else {}
    raw_selection = lineage.get("raw_selection") if isinstance(lineage.get("raw_selection"), dict) else {}
    return {
        "generation_repair_round": int(lineage.get("generation_repair_round") or 0),
        "non_atomic_parent_count": non_atomic_count,
        "mixed_parent_count": mixed_parent_count,
        "answer_overlap_atom_count": answer_overlap_atom_count(row),
        "seed_complexity": str(raw_selection.get("seed_complexity") or "unknown"),
        "source_topic": str(row.get("source_topic") or "unknown"),
        "label_counts": {label: label_counts.get(label, 0) for label in ("A", "B", "C")},
        "label_signature": "+".join(label for label in ("A", "B", "C") if label_counts.get(label)),
    }


def mandatory_for_domain(domain: str, signals: dict[str, Any]) -> bool:
    if domain == "general":
        return bool(signals["generation_repair_round"] or signals["answer_overlap_atom_count"])
    if domain == "coding":
        return bool(signals["non_atomic_parent_count"] or signals["answer_overlap_atom_count"])
    raise ValueError(f"unsupported domain: {domain}")


def selection_reasons(signals: dict[str, Any], stratified_fill: bool) -> list[str]:
    reasons = []
    if signals["generation_repair_round"]:
        reasons.append("generation_repair")
    if signals["non_atomic_parent_count"]:
        reasons.append("non_atomic_parent")
    if signals["answer_overlap_atom_count"]:
        reasons.append("reference_answer_overlap")
    if signals["mixed_parent_count"]:
        reasons.append("mixed_parent_label")
    if stratified_fill:
        reasons.append("stratified_fill")
    return reasons


def select_review_rows(
    rows: list[dict[str, Any]],
    *,
    domain: str,
    target: int,
    seed: int,
) -> list[dict[str, Any]]:
    if target <= 0 or target > len(rows):
        raise ValueError(f"target must be between 1 and {len(rows)}")
    ids = [str(row.get("id") or "") for row in rows]
    if "" in ids or len(set(ids)) != len(ids):
        raise ValueError("sample IDs must be non-empty and unique")

    features = {str(row["id"]): sample_signals(row) for row in rows}
    row_by_id = {str(row["id"]): row for row in rows}
    mandatory_ids = {
        sample_id
        for sample_id, signals in features.items()
        if mandatory_for_domain(domain, signals)
    }
    if len(mandatory_ids) > target:
        raise ValueError(f"mandatory review rows exceed target: {len(mandatory_ids)} > {target}")

    selected_ids = set(mandatory_ids)
    topic_counts = Counter(features[sample_id]["source_topic"] for sample_id in selected_ids)
    complexity_counts = Counter(features[sample_id]["seed_complexity"] for sample_id in selected_ids)
    structure_counts = Counter(bool(features[sample_id]["non_atomic_parent_count"]) for sample_id in selected_ids)
    signature_counts = Counter(features[sample_id]["label_signature"] for sample_id in selected_ids)
    repair_counts = Counter(bool(features[sample_id]["generation_repair_round"]) for sample_id in selected_ids)

    while len(selected_ids) < target:
        candidates = [sample_id for sample_id in ids if sample_id not in selected_ids]

        def candidate_key(sample_id: str) -> tuple[int, str]:
            signals = features[sample_id]
            balance_cost = (
                topic_counts[signals["source_topic"]] * 4
                + complexity_counts[signals["seed_complexity"]] * 3
                + structure_counts[bool(signals["non_atomic_parent_count"])] * 2
                + signature_counts[signals["label_signature"]]
                + repair_counts[bool(signals["generation_repair_round"])]
            )
            return balance_cost, stable_hash(seed, f"{domain}:{sample_id}")

        chosen = min(candidates, key=candidate_key)
        selected_ids.add(chosen)
        signals = features[chosen]
        topic_counts[signals["source_topic"]] += 1
        complexity_counts[signals["seed_complexity"]] += 1
        structure_counts[bool(signals["non_atomic_parent_count"])] += 1
        signature_counts[signals["label_signature"]] += 1
        repair_counts[bool(signals["generation_repair_round"])] += 1

    def review_priority(sample_id: str) -> tuple[int, int, int, int, str]:
        signals = features[sample_id]
        return (
            -int(bool(signals["answer_overlap_atom_count"])),
            -int(bool(signals["generation_repair_round"])),
            -int(bool(signals["non_atomic_parent_count"])),
            -int(bool(signals["mixed_parent_count"])),
            stable_hash(seed, f"queue:{domain}:{sample_id}"),
        )

    ordered_ids = sorted(selected_ids, key=review_priority)
    selected = []
    for position, sample_id in enumerate(ordered_ids, start=1):
        item = copy.deepcopy(row_by_id[sample_id])
        signals = features[sample_id]
        item["audit_selection"] = {
            "schema_version": SCHEMA_VERSION,
            "domain": domain,
            "queue_position": position,
            "selection_reasons": selection_reasons(signals, sample_id not in mandatory_ids),
            "mandatory": sample_id in mandatory_ids,
            "signals": signals,
        }
        selected.append(item)
    return selected


def count_selected(selected: list[dict[str, Any]]) -> dict[str, Any]:
    reason_counts: Counter[str] = Counter()
    complexity_counts: Counter[str] = Counter()
    topic_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    mandatory = 0
    for row in selected:
        audit = row["audit_selection"]
        reason_counts.update(audit["selection_reasons"])
        complexity_counts[audit["signals"]["seed_complexity"]] += 1
        topic_counts[audit["signals"]["source_topic"]] += 1
        label_counts.update(audit["signals"]["label_counts"])
        mandatory += int(audit["mandatory"])
    return {
        "samples": len(selected),
        "mandatory_samples": mandatory,
        "selection_reason_counts": dict(sorted(reason_counts.items())),
        "seed_complexity_counts": dict(sorted(complexity_counts.items())),
        "source_topic_counts": dict(sorted(topic_counts.items())),
        "atom_label_counts": {label: label_counts.get(label, 0) for label in ("A", "B", "C")},
    }


def build_domain_queue(
    *,
    input_path: Path,
    release_dir: Path,
    domain: str,
    target: int,
    seed: int,
) -> dict[str, Any]:
    source_rows = read_jsonl(input_path)
    selected = select_review_rows(source_rows, domain=domain, target=target, seed=seed)
    stem = f"{domain}-review-queue-{target}"
    jsonl_path = release_dir / "review" / f"{stem}.jsonl"
    csv_path = release_dir / "review" / f"{stem}.csv"
    html_path = release_dir / "review" / f"{stem}.html"
    write_jsonl(jsonl_path, selected)

    audit_rows = AUDIT.build_parent_audit_rows(selected)
    summary = AUDIT.summarize_rows(audit_rows, selected)
    summary.update(
        {
            "audit_title": f"MemCalib {domain} 领域分层人工审查",
            "audit_intro": "队列优先覆盖构建修复、非原子记忆、答案重叠预警和标签混合样本，并用分层补样保持主题与难度多样性。每个 parent memory 均需完成审查结论。",
            "storage_key": f"memcalib-multidomain-pilot-v0.2:{stem}",
            "export_filename": f"{stem}-annotations.json",
        }
    )
    AUDIT.write_audit_csv(csv_path, audit_rows)
    AUDIT.write_audit_html(html_path, audit_rows, summary)

    selected_counts = count_selected(selected)
    return {
        "domain": domain,
        "target": target,
        "source": {
            "path": str(input_path.relative_to(ROOT)),
            "rows": len(source_rows),
            "sha256": file_sha256(input_path),
        },
        "selection": selected_counts,
        "selected_id_sha256": hashlib.sha256(
            "\n".join(str(row["id"]) for row in selected).encode("utf-8")
        ).hexdigest(),
        "outputs": {
            "jsonl": {"path": str(jsonl_path.relative_to(ROOT)), "sha256": file_sha256(jsonl_path)},
            "csv": {"path": str(csv_path.relative_to(ROOT)), "sha256": file_sha256(csv_path)},
            "html": {"path": str(html_path.relative_to(ROOT)), "sha256": file_sha256(html_path)},
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build deterministic human-review queues for the multi-domain pilot.")
    parser.add_argument(
        "--general-input",
        type=Path,
        default=DEFAULT_RELEASE_DIR / "data" / "general-hidden-construction-100.jsonl",
    )
    parser.add_argument(
        "--coding-input",
        type=Path,
        default=DEFAULT_RELEASE_DIR / "data" / "coding-hidden-construction-100.jsonl",
    )
    parser.add_argument("--release-dir", type=Path, default=DEFAULT_RELEASE_DIR)
    parser.add_argument("--general-target", type=int, default=35)
    parser.add_argument("--coding-target", type=int, default=50)
    parser.add_argument("--seed", type=int, default=20260713)
    args = parser.parse_args()

    domains = [
        build_domain_queue(
            input_path=args.general_input.resolve(),
            release_dir=args.release_dir.resolve(),
            domain="general",
            target=args.general_target,
            seed=args.seed,
        ),
        build_domain_queue(
            input_path=args.coding_input.resolve(),
            release_dir=args.release_dir.resolve(),
            domain="coding",
            target=args.coding_target,
            seed=args.seed,
        ),
    ]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "seed": args.seed,
        "selection_policy": {
            "general_mandatory": ["generation_repair", "reference_answer_overlap"],
            "coding_mandatory": ["non_atomic_parent", "reference_answer_overlap"],
            "fill": "deterministic greedy balancing over topic, seed complexity, parent atomicity, label signature, and repair status",
        },
        "domains": domains,
    }
    manifest_path = args.release_dir.resolve() / "metadata" / "review-queue-manifest.json"
    write_json(manifest_path, manifest)
    print(json.dumps({"manifest": str(manifest_path), "domains": domains}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
