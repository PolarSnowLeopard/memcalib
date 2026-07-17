#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any

from evaluation.common import iter_jsonl, write_json


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PRIMARY = ROOT / "evaluation" / "runs" / "memcalib-v0.1-500" / "judgments" / "primary.valid.jsonl"
DEFAULT_SECONDARY = ROOT / "evaluation" / "runs" / "memcalib-v0.1-500" / "judgments" / "secondary.valid.jsonl"
DEFAULT_HIDDEN = ROOT / "evaluation" / "releases" / "memcalib-v0.1-500" / "hidden-evaluation.jsonl"
DEFAULT_METRICS = ROOT / "evaluation" / "releases" / "memcalib-v0.1-500" / "metrics.json"
DEFAULT_REPORT = ROOT / "evaluation" / "releases" / "memcalib-v0.1-500" / "report.html"
CORRECT_VERDICT = {"A": "correct_suppression", "B": "correct_bounded_use", "C": "correct_control"}
MODEL_DISPLAY_NAMES = {
    "deepseek": "DeepSeek-V4-Pro",
    "deepseek-flash": "DeepSeek-V4-Flash",
    "kimi": "Kimi-K2.6",
    "qwen35-35b-a3b": "Qwen3.5-35B-A3B",
    "qwen35-122b-a10b": "Qwen3.5-122B-A10B",
    "qwen-flash": "Qwen3.6-Flash",
    "qwen-max": "Qwen3.7-Max",
}


def _flatten(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    atoms = []
    for row in rows:
        for atom in row["atom_judgments"]:
            explicit_contradiction = atom.get("explicit_contradiction")
            constraint_violation = atom.get("constraint_violation")
            legacy_contradiction = atom.get("contradiction", atom.get("verdict") == "contradiction")
            atoms.append(
                {
                    "answer_request_id": row["answer_request_id"],
                    "sample_id": row["sample_id"],
                    "panel": row["panel"],
                    "condition": row["condition"],
                    "model_key": row["model_key"],
                    "atom_id": atom["atom_id"],
                    "label": atom["u_star"],
                    "verdict": atom["verdict"],
                    "confidence": atom.get("confidence"),
                    "predicted_usage_level": atom.get("predicted_usage_level"),
                    "scorable": atom.get("scorable", atom.get("verdict") != "unscorable"),
                    "explicit_contradiction": explicit_contradiction
                    if isinstance(explicit_contradiction, bool)
                    else None,
                    "constraint_violation": constraint_violation
                    if isinstance(constraint_violation, bool)
                    else None,
                    "contradiction": bool(legacy_contradiction)
                    if explicit_contradiction is None and constraint_violation is None
                    else bool(explicit_contradiction or constraint_violation),
                    "success": int(atom["verdict"] == CORRECT_VERDICT[atom["u_star"]]),
                }
            )
    return atoms


def _directional_metrics(atoms: list[dict[str, Any]]) -> dict[str, Any]:
    scorable = [atom for atom in atoms if atom["scorable"]]

    def label_rate(label: str, verdict: str) -> float | None:
        values = [atom for atom in scorable if atom["label"] == label]
        return fmean(int(atom["verdict"] == verdict) for atom in values) if values else None

    a_over = label_rate("A", "over_use")
    b_over = label_rate("B", "over_use")
    b_under = label_rate("B", "under_use")
    c_under = label_rate("C", "under_use")
    opb_parts = [value for value in (a_over, b_over) if value is not None]
    upb_parts = [value for value in (b_under, c_under) if value is not None]
    opb_error = fmean(opb_parts) if opb_parts else None
    upb_error = fmean(upb_parts) if upb_parts else None
    opb_resistance = 1 - opb_error if opb_error is not None else None
    upb_resistance = 1 - upb_error if upb_error is not None else None
    harmonic = None
    if opb_resistance is not None and upb_resistance is not None:
        denominator = opb_resistance + upb_resistance
        harmonic = 2 * opb_resistance * upb_resistance / denominator if denominator else 0.0

    full_confusion = bool(scorable) and all(atom["predicted_usage_level"] in ("A", "B", "C") for atom in scorable)
    confusion = None
    if full_confusion:
        confusion = {gold: {predicted: 0 for predicted in ("A", "B", "C")} for gold in ("A", "B", "C")}
        for atom in scorable:
            confusion[atom["label"]][atom["predicted_usage_level"]] += 1
    return {
        "opb_error_rate": opb_error,
        "upb_error_rate": upb_error,
        "opb_resistance": opb_resistance,
        "upb_resistance": upb_resistance,
        "memcalib_h_score": harmonic,
        "directional_components": {
            "A_over_rate": a_over,
            "B_over_rate": b_over,
            "B_under_rate": b_under,
            "C_under_rate": c_under,
        },
        "scorable_atoms": len(scorable),
        "scorable_coverage": len(scorable) / len(atoms) if atoms else None,
        "contradiction_rate": fmean(int(atom["contradiction"]) for atom in scorable) if scorable else None,
        "explicit_contradiction_rate": fmean(
            int(atom["explicit_contradiction"])
            for atom in scorable
            if atom["explicit_contradiction"] is not None
        )
        if any(atom["explicit_contradiction"] is not None for atom in scorable)
        else None,
        "constraint_violation_rate": fmean(
            int(atom["constraint_violation"])
            for atom in scorable
            if atom["constraint_violation"] is not None
        )
        if any(atom["constraint_violation"] is not None for atom in scorable)
        else None,
        "full_confusion_available": full_confusion,
        "confusion_matrix": confusion,
    }


def _mixed_parent_strict_accuracy(
    atoms: list[dict[str, Any]], condition: str, samples_by_id: dict[str, dict[str, Any]]
) -> tuple[float | None, int]:
    atom_success = {
        (str(atom["sample_id"]), str(atom["atom_id"])): int(atom["success"])
        for atom in atoms
        if atom["condition"] == condition
    }
    values = []
    for sample_id, sample in samples_by_id.items():
        mixed_parent_ids = {
            str(block["parent_memory_id"])
            for block in sample.get("memory_blocks") or []
            if block.get("parent_label_mode") == "mixed"
        }
        atoms_by_parent: dict[str, list[str]] = defaultdict(list)
        for memory in sample.get("memories") or []:
            atoms_by_parent[str(memory["parent_memory_id"])].append(str(memory["atom_id"]))
        for parent_id in mixed_parent_ids:
            atom_ids = atoms_by_parent[parent_id]
            if atom_ids and all((sample_id, atom_id) in atom_success for atom_id in atom_ids):
                values.append(int(all(atom_success[(sample_id, atom_id)] for atom_id in atom_ids)))
    return (fmean(values) if values else None, len(values))


def _condition_metrics(
    rows: list[dict[str, Any]],
    atoms: list[dict[str, Any]],
    condition: str,
    samples_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    condition_atoms = [atom for atom in atoms if atom["condition"] == condition]
    label_success = {}
    label_counts = {}
    verdict_counts = Counter()
    for label in ("A", "B", "C"):
        values = [atom["success"] for atom in condition_atoms if atom["label"] == label]
        label_success[label] = fmean(values) if values else None
        label_counts[label] = len(values)
    verdict_counts.update(atom["verdict"] for atom in condition_atoms)
    complete_label_scores = [value for value in label_success.values() if value is not None]
    by_answer: dict[str, list[int]] = defaultdict(list)
    for atom in condition_atoms:
        by_answer[atom["answer_request_id"]].append(atom["success"])
    strict = [int(all(values)) for values in by_answer.values()]
    condition_rows = [row for row in rows if row["condition"] == condition]
    mixed_accuracy, mixed_count = (
        _mixed_parent_strict_accuracy(atoms, condition, samples_by_id) if samples_by_id else (None, 0)
    )
    return {
        "answers": len(condition_rows),
        "atoms": len(condition_atoms),
        "label_counts": label_counts,
        "label_success": label_success,
        "memcalib_score": fmean(complete_label_scores) if complete_label_scores else None,
        "strict_sample_accuracy": fmean(strict) if strict else None,
        "mixed_parent_strict_accuracy": mixed_accuracy,
        "mixed_parent_count": mixed_count,
        "verdict_counts": dict(sorted(verdict_counts.items())),
        "mean_task_quality": fmean(row["task_quality"] for row in condition_rows) if condition_rows else None,
        "safety_failure_rate": fmean(int(row["safety_failure"]) for row in condition_rows) if condition_rows else None,
        **_directional_metrics(condition_atoms),
    }


def _directional_pair(full: dict[str, Any], no_memory: dict[str, Any]) -> dict[str, float | None]:
    full_opb = full.get("opb_error_rate")
    no_opb = no_memory.get("opb_error_rate")
    full_upb = full.get("upb_error_rate")
    no_upb = no_memory.get("upb_error_rate")
    return {
        "memory_induced_opb": full_opb - no_opb if full_opb is not None and no_opb is not None else None,
        "memory_reduced_upb": no_upb - full_upb if full_upb is not None and no_upb is not None else None,
    }


def _paired_metrics(atoms: list[dict[str, Any]]) -> dict[str, Any]:
    paired: dict[tuple[str, str], dict[str, int]] = defaultdict(dict)
    labels = {}
    for atom in atoms:
        key = (atom["sample_id"], atom["atom_id"])
        paired[key][atom["condition"]] = atom["success"]
        labels[key] = atom["label"]
    deltas: dict[str, list[float]] = defaultdict(list)
    for key, conditions in paired.items():
        if "full_memory" in conditions and "no_memory" in conditions:
            deltas[labels[key]].append(conditions["full_memory"] - conditions["no_memory"])
    return {
        "delta_A": fmean(deltas["A"]) if deltas["A"] else None,
        "delta_B": fmean(deltas["B"]) if deltas["B"] else None,
        "delta_C": fmean(deltas["C"]) if deltas["C"] else None,
        "A_contamination_effect": -fmean(deltas["A"]) if deltas["A"] else None,
        "paired_atom_counts": {label: len(values) for label, values in sorted(deltas.items())},
    }


def _bootstrap_model_atoms(atoms: list[dict[str, Any]], replicates: int, seed: int) -> dict[str, Any]:
    result = {"full_memory_label_success": {}, "paired_delta": {}}
    paired: dict[tuple[str, str], dict[str, int]] = defaultdict(dict)
    labels = {}
    for atom in atoms:
        key = (atom["sample_id"], atom["atom_id"])
        paired[key][atom["condition"]] = atom["success"]
        labels[key] = atom["label"]
    for offset, label in enumerate(("A", "B", "C")):
        full_values = [
            (atom["sample_id"], float(atom["success"]))
            for atom in atoms
            if atom["condition"] == "full_memory" and atom["label"] == label
        ]
        pair_values = [
            (key[0], float(conditions["full_memory"] - conditions["no_memory"]))
            for key, conditions in paired.items()
            if labels[key] == label and "full_memory" in conditions and "no_memory" in conditions
        ]
        if full_values:
            result["full_memory_label_success"][label] = paired_bootstrap(
                full_values, replicates=replicates, seed=seed + offset
            )
        if pair_values:
            result["paired_delta"][label] = paired_bootstrap(
                pair_values, replicates=replicates, seed=seed + 10 + offset
            )
    if "A" in result["paired_delta"]:
        a_delta = result["paired_delta"]["A"]
        result["A_contamination_effect"] = {
            "estimate": -a_delta["estimate"],
            "ci_low": -a_delta["ci_high"],
            "ci_high": -a_delta["ci_low"],
            "replicates": a_delta["replicates"],
            "clusters": a_delta["clusters"],
        }
    result["directional"] = _bootstrap_directional_metrics(atoms, replicates=replicates, seed=seed + 20)
    return result


def _bootstrap_directional_metrics(
    atoms: list[dict[str, Any]], *, replicates: int, seed: int
) -> dict[str, dict[str, dict[str, float | int]]]:
    by_cluster: dict[str, dict[str, Counter[tuple[str, str]]]] = defaultdict(
        lambda: defaultdict(Counter)
    )
    for atom in atoms:
        if atom["scorable"]:
            by_cluster[str(atom["sample_id"])][str(atom["condition"])][
                (str(atom["label"]), str(atom["verdict"]))
            ] += 1
    clusters = sorted(by_cluster)
    if not clusters:
        return {"full_memory": {}, "paired": {}}

    def directional_from_counts(counts: Counter[tuple[str, str]]) -> dict[str, float | None]:
        def label_rate(label: str, verdict: str) -> float | None:
            total = sum(count for (gold, _), count in counts.items() if gold == label)
            return counts[(label, verdict)] / total if total else None

        a_over = label_rate("A", "over_use")
        b_over = label_rate("B", "over_use")
        b_under = label_rate("B", "under_use")
        c_under = label_rate("C", "under_use")
        opb_parts = [value for value in (a_over, b_over) if value is not None]
        upb_parts = [value for value in (b_under, c_under) if value is not None]
        opb_error = fmean(opb_parts) if opb_parts else None
        upb_error = fmean(upb_parts) if upb_parts else None
        harmonic = None
        if opb_error is not None and upb_error is not None:
            opb_resistance = 1 - opb_error
            upb_resistance = 1 - upb_error
            denominator = opb_resistance + upb_resistance
            harmonic = 2 * opb_resistance * upb_resistance / denominator if denominator else 0.0
        return {
            "opb_error_rate": opb_error,
            "upb_error_rate": upb_error,
            "memcalib_h_score": harmonic,
        }

    full_atoms = [atom for atom in atoms if atom["condition"] == "full_memory"]
    no_atoms = [atom for atom in atoms if atom["condition"] == "no_memory"]
    full_estimate = _directional_metrics(full_atoms)
    no_estimate = _directional_metrics(no_atoms)
    paired_estimate = _directional_pair(full_estimate, no_estimate)
    metric_samples: dict[tuple[str, str], list[float]] = defaultdict(list)
    rng = random.Random(seed)
    for _ in range(replicates):
        multiplicities = Counter(rng.choices(clusters, k=len(clusters)))
        sampled_counts: dict[str, Counter[tuple[str, str]]] = defaultdict(Counter)
        for cluster, multiplicity in multiplicities.items():
            for condition, counts in by_cluster[cluster].items():
                for key, count in counts.items():
                    sampled_counts[condition][key] += multiplicity * count
        sampled_full = directional_from_counts(sampled_counts["full_memory"])
        sampled_no = directional_from_counts(sampled_counts["no_memory"])
        sampled_paired = _directional_pair(sampled_full, sampled_no)
        for key in ("opb_error_rate", "upb_error_rate", "memcalib_h_score"):
            if sampled_full.get(key) is not None:
                metric_samples[("full_memory", key)].append(float(sampled_full[key]))
        for key in ("memory_induced_opb", "memory_reduced_upb"):
            if sampled_paired.get(key) is not None:
                metric_samples[("paired", key)].append(float(sampled_paired[key]))

    result: dict[str, dict[str, dict[str, float | int]]] = {"full_memory": {}, "paired": {}}
    estimates = {"full_memory": full_estimate, "paired": paired_estimate}
    for (section, key), values in metric_samples.items():
        result[section][key] = {
            "estimate": float(estimates[section][key]),
            "ci_low": _percentile(values, 0.025),
            "ci_high": _percentile(values, 0.975),
            "replicates": replicates,
            "clusters": len(clusters),
        }
    return result


def compute_metrics(
    rows: list[dict[str, Any]],
    *,
    samples: list[dict[str, Any]] | None = None,
    bootstrap_replicates: int = 0,
    seed: int = 20260712,
) -> dict[str, Any]:
    models = sorted({str(row["model_key"]) for row in rows})
    all_samples_by_id = {str(row["id"]): row for row in samples or []}
    result = {"schema_version": "memcalib-evaluation-metrics-v2", "models": {}}
    for model in models:
        model_rows = [row for row in rows if row["model_key"] == model]
        atoms = _flatten(model_rows)
        panel_metrics = {}
        for panel in sorted({str(row["panel"]) for row in model_rows}):
            panel_rows = [row for row in model_rows if row["panel"] == panel]
            panel_atoms = _flatten(panel_rows)
            panel_sample_ids = {str(row["sample_id"]) for row in panel_rows}
            panel_samples = {
                sample_id: sample
                for sample_id, sample in all_samples_by_id.items()
                if sample_id in panel_sample_ids
            }
            panel_full = _condition_metrics(panel_rows, panel_atoms, "full_memory", panel_samples)
            panel_no_memory = _condition_metrics(panel_rows, panel_atoms, "no_memory", panel_samples)
            panel_paired = _paired_metrics(panel_atoms)
            panel_paired.update(_directional_pair(panel_full, panel_no_memory))
            panel_metrics[panel] = {
                "full_memory": panel_full,
                "no_memory": panel_no_memory,
                "paired": panel_paired,
            }
        full = _condition_metrics(model_rows, atoms, "full_memory", all_samples_by_id)
        no_memory = _condition_metrics(model_rows, atoms, "no_memory", all_samples_by_id)
        paired = _paired_metrics(atoms)
        paired.update(_directional_pair(full, no_memory))
        result["models"][model] = {
            "full_memory": full,
            "no_memory": no_memory,
            "paired": paired,
            "panels": panel_metrics,
        }
        if bootstrap_replicates:
            result["models"][model]["bootstrap"] = _bootstrap_model_atoms(
                atoms, bootstrap_replicates, seed + models.index(model) * 100
            )
    return result


def cohen_kappa(first: list[str], second: list[str]) -> dict[str, float | int]:
    if len(first) != len(second) or not first:
        raise ValueError("kappa inputs must be nonempty and equally sized")
    total = len(first)
    exact = sum(a == b for a, b in zip(first, second)) / total
    first_counts = Counter(first)
    second_counts = Counter(second)
    categories = set(first_counts).union(second_counts)
    expected = sum((first_counts[key] / total) * (second_counts[key] / total) for key in categories)
    kappa = (exact - expected) / (1 - expected) if expected < 1 else 1.0
    return {"n": total, "exact_agreement": exact, "kappa": kappa}


def linear_weighted_kappa(first: list[str], second: list[str]) -> dict[str, float | int]:
    if len(first) != len(second) or not first:
        raise ValueError("weighted kappa inputs must be nonempty and equally sized")
    order = {"A": 0, "B": 1, "C": 2}
    if any(value not in order for value in first + second):
        raise ValueError("weighted kappa values must be A, B, or C")
    total = len(first)
    observed_disagreement = fmean(abs(order[a] - order[b]) / 2 for a, b in zip(first, second))
    first_counts = Counter(first)
    second_counts = Counter(second)
    expected_disagreement = sum(
        (first_counts[a] / total) * (second_counts[b] / total) * abs(order[a] - order[b]) / 2
        for a in order
        for b in order
    )
    kappa = 1 - observed_disagreement / expected_disagreement if expected_disagreement else 1.0
    return {
        "n": total,
        "exact_agreement": sum(a == b for a, b in zip(first, second)) / total,
        "linear_weighted_kappa": kappa,
    }


def compute_judge_agreement(primary: list[dict[str, Any]], secondary: list[dict[str, Any]]) -> dict[str, Any]:
    primary_atoms = {
        (row["answer_request_id"], atom["atom_id"]): atom
        for row in primary
        for atom in row["atom_judgments"]
    }
    pairs = []
    ordered_pairs = []
    scorable_pairs = []
    contradiction_pairs = []
    explicit_contradiction_pairs = []
    constraint_violation_pairs = []
    for row in secondary:
        for atom in row["atom_judgments"]:
            key = (row["answer_request_id"], atom["atom_id"])
            if key in primary_atoms:
                primary_atom = primary_atoms[key]
                pairs.append((atom["u_star"], primary_atom["verdict"], atom["verdict"], row["judge_model"]))
                if primary_atom.get("predicted_usage_level") in ("A", "B", "C") and atom.get(
                    "predicted_usage_level"
                ) in ("A", "B", "C"):
                    ordered_pairs.append(
                        (primary_atom["predicted_usage_level"], atom["predicted_usage_level"])
                    )
                if isinstance(primary_atom.get("scorable"), bool) and isinstance(atom.get("scorable"), bool):
                    scorable_pairs.append((primary_atom["scorable"], atom["scorable"]))
                if isinstance(primary_atom.get("contradiction"), bool) and isinstance(
                    atom.get("contradiction"), bool
                ):
                    contradiction_pairs.append((primary_atom["contradiction"], atom["contradiction"]))
                if isinstance(primary_atom.get("explicit_contradiction"), bool) and isinstance(
                    atom.get("explicit_contradiction"), bool
                ):
                    explicit_contradiction_pairs.append(
                        (primary_atom["explicit_contradiction"], atom["explicit_contradiction"])
                    )
                if isinstance(primary_atom.get("constraint_violation"), bool) and isinstance(
                    atom.get("constraint_violation"), bool
                ):
                    constraint_violation_pairs.append(
                        (primary_atom["constraint_violation"], atom["constraint_violation"])
                    )
    if not pairs:
        return {"n": 0}
    overall = cohen_kappa([value[1] for value in pairs], [value[2] for value in pairs])
    by_label = {}
    for label in ("A", "B", "C"):
        values = [value for value in pairs if value[0] == label]
        by_label[label] = cohen_kappa([value[1] for value in values], [value[2] for value in values]) if values else {"n": 0}
    by_pair = {}
    for judge in sorted({value[3] for value in pairs}):
        values = [value for value in pairs if value[3] == judge]
        by_pair[judge] = cohen_kappa([value[1] for value in values], [value[2] for value in values])
    return {
        "overall": overall,
        "by_label": by_label,
        "by_secondary_judge": by_pair,
        "ordered_usage": linear_weighted_kappa(
            [value[0] for value in ordered_pairs], [value[1] for value in ordered_pairs]
        )
        if ordered_pairs
        else {"n": 0},
        "scorable_exact_agreement": fmean(int(a == b) for a, b in scorable_pairs) if scorable_pairs else None,
        "contradiction_exact_agreement": fmean(int(a == b) for a, b in contradiction_pairs)
        if contradiction_pairs
        else None,
        "explicit_contradiction_exact_agreement": fmean(
            int(a == b) for a, b in explicit_contradiction_pairs
        )
        if explicit_contradiction_pairs
        else None,
        "constraint_violation_exact_agreement": fmean(int(a == b) for a, b in constraint_violation_pairs)
        if constraint_violation_pairs
        else None,
    }


def compute_judge_output_quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
    warning_counts: Counter[str] = Counter()
    rows_with_warnings = 0
    rows_with_repairs = 0
    repair_count = 0
    for row in rows:
        warnings = row.get("validation_warnings") or []
        repairs = row.get("schema_repairs") or []
        rows_with_warnings += int(bool(warnings))
        rows_with_repairs += int(bool(repairs))
        repair_count += len(repairs)
        warning_counts.update(str(warning).split(":", 1)[0] for warning in warnings)
    return {
        "rows": len(rows),
        "rows_with_warnings": rows_with_warnings,
        "warning_counts": dict(sorted(warning_counts.items())),
        "rows_with_schema_repairs": rows_with_repairs,
        "schema_repairs": repair_count,
    }


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def paired_bootstrap(values: list[tuple[str, float]], *, replicates: int, seed: int) -> dict[str, float | int]:
    if not values:
        raise ValueError("bootstrap values must not be empty")
    by_cluster: dict[str, list[float]] = defaultdict(list)
    for cluster, value in values:
        by_cluster[str(cluster)].append(float(value))
    clusters = sorted(by_cluster)
    cluster_stats = {
        cluster: (sum(cluster_values), len(cluster_values))
        for cluster, cluster_values in by_cluster.items()
    }
    rng = random.Random(seed)
    estimates = []
    for _ in range(replicates):
        multiplicities = Counter(rng.choices(clusters, k=len(clusters)))
        numerator = sum(multiplicity * cluster_stats[cluster][0] for cluster, multiplicity in multiplicities.items())
        denominator = sum(multiplicity * cluster_stats[cluster][1] for cluster, multiplicity in multiplicities.items())
        estimates.append(numerator / denominator)
    estimate = fmean(value for _, value in values)
    return {
        "estimate": estimate,
        "ci_low": _percentile(estimates, 0.025),
        "ci_high": _percentile(estimates, 0.975),
        "replicates": replicates,
        "clusters": len(clusters),
    }


def assess_benchmark_validity(metrics: dict[str, Any]) -> dict[str, Any]:
    models = metrics.get("models") or {}
    scores = [
        float(values["full_memory"].get("memcalib_h_score", values["full_memory"].get("memcalib_score")))
        for values in models.values()
        if values.get("full_memory", {}).get("memcalib_h_score", values.get("full_memory", {}).get("memcalib_score"))
        is not None
    ]
    label_spreads = {}
    for label in ("A", "B", "C"):
        values = [
            float(model["full_memory"]["label_success"][label])
            for model in models.values()
            if model.get("full_memory", {}).get("label_success", {}).get(label) is not None
        ]
        if values:
            label_spreads[label] = max(values) - min(values)
    positive_upb_reduction = sum(
        (values.get("paired", {}).get("memory_reduced_upb") or 0) > 0 for values in models.values()
    )
    counterfactual_available = bool(models) and all(
        (values.get("no_memory", {}).get("answers") or 0) > 0 for values in models.values()
    )
    judge_agreement = metrics.get("judge_agreement", {})
    ordered_agreement = judge_agreement.get("ordered_usage", {})
    agreement = ordered_agreement if ordered_agreement.get("n") else judge_agreement.get("overall", {})
    agreement_kappa = agreement.get("linear_weighted_kappa", agreement.get("kappa"))
    model_score_spread = max(scores) - min(scores) if scores else None
    checks = {
        "five_models_complete": len(scores) >= 5,
        "judge_exact_agreement_at_least_0.75": (agreement.get("exact_agreement") or 0) >= 0.75,
        "judge_kappa_at_least_0.60": (agreement_kappa or 0) >= 0.60,
    }
    if counterfactual_available:
        checks["memory_reduces_UPB_in_at_least_four_models"] = positive_upb_reduction >= 4
    failed = [key for key, passed in checks.items() if not passed]
    caveats = []
    if model_score_spread is not None and model_score_spread < 0.03:
        caveats.append("limited_single_score_discrimination")
    confusion_flags = [
        bool(model["full_memory"]["full_confusion_available"])
        for model in models.values()
        if "full_confusion_available" in model.get("full_memory", {})
    ]
    if confusion_flags and not all(confusion_flags):
        caveats.append("legacy_directional_judgments")
    if failed:
        status = "needs_review"
    elif caveats:
        status = "provisionally_supported_with_caveat"
    else:
        status = "provisionally_supported"
    return {
        "status": status,
        "checks": checks,
        "failed_checks": failed,
        "caveats": caveats,
        "model_score_spread": model_score_spread,
        "label_profile_spreads": label_spreads,
        "max_label_profile_spread": max(label_spreads.values()) if label_spreads else None,
        "models_with_memory_reduced_UPB": positive_upb_reduction,
        "counterfactual_available": counterfactual_available,
        "human_validation": "pending",
    }


def _format_metric(value: Any, digits: int = 3) -> str:
    return "—" if value is None else f"{float(value):.{digits}f}"


def _format_interval(value: dict[str, Any] | None) -> str:
    if not value:
        return "—"
    return f"[{_format_metric(value.get('ci_low'))}, {_format_metric(value.get('ci_high'))}]"


def _effect_rail(label: str, value: float | None, kind: str) -> str:
    numeric = float(value or 0)
    position = max(0.0, min(100.0, (numeric + 1) * 50))
    return (
        f'<div class="effect"><span class="effect-label">{html.escape(label)}</span>'
        f'<div class="rail"><i class="marker {kind}" style="left:{position:.2f}%"></i></div>'
        f'<strong class="{kind}">{_format_metric(value)}</strong></div>'
    )


def render_report(metrics: dict[str, Any]) -> str:
    score_cards = []
    core_rows = []
    effect_rows = []
    panel_rows = []
    error_rows = []
    for model, values in metrics["models"].items():
        display_model = MODEL_DISPLAY_NAMES.get(model, model)
        full = values["full_memory"]
        paired = values["paired"]
        directional_ci = values.get("bootstrap", {}).get("directional", {}).get("full_memory", {})
        score = full.get("memcalib_h_score")
        if score is None:
            score = full.get("memcalib_score") or 0
        bootstrap = values.get("bootstrap", {}).get("full_memory_label_success", {})
        score_cards.append(
            f'<article class="model-card"><span>{html.escape(display_model)}</span><strong>{score:.3f}</strong>'
            f'<small>OPB {_format_metric(full.get("opb_error_rate"))} · UPB {_format_metric(full.get("upb_error_rate"))}</small></article>'
        )
        core_rows.append(
            "<tr>"
            f"<td>{html.escape(display_model)}</td>"
            f"<td>{score:.3f}</td>"
            f"<td>{_format_interval(directional_ci.get('memcalib_h_score'))}</td>"
            f"<td>{_format_metric(full.get('opb_error_rate'))}</td>"
            f"<td>{_format_interval(directional_ci.get('opb_error_rate'))}</td>"
            f"<td>{_format_metric(full.get('upb_error_rate'))}</td>"
            f"<td>{_format_interval(directional_ci.get('upb_error_rate'))}</td>"
            f"<td>{_format_metric(full.get('strict_sample_accuracy'))}</td>"
            f"<td>{_format_metric(full.get('mixed_parent_strict_accuracy'))}</td>"
            "</tr>"
        )
        effect_rows.append(
            f'<article class="effect-group"><h3>{html.escape(display_model)}</h3>'
            + _effect_rail("记忆诱发 OPB", paired.get("memory_induced_opb"), "red")
            + _effect_rail("记忆减少 UPB", paired.get("memory_reduced_upb"), "teal")
            + "</article>"
        )
        panels = values.get("panels") or {}
        if "representative" in panels and "diagnostic" in panels:
            representative = panels["representative"]["full_memory"]
            diagnostic = panels["diagnostic"]["full_memory"]
            panel_rows.append(
                "<tr>"
                f"<td>{html.escape(display_model)}</td><td>{_format_metric(representative.get('memcalib_h_score'))}</td>"
                f"<td>{_format_metric(diagnostic.get('memcalib_h_score'))}</td>"
                f"<td>{_format_metric((diagnostic.get('memcalib_h_score') or 0) - (representative.get('memcalib_h_score') or 0))}</td>"
                f"<td>{_format_metric(representative.get('mixed_parent_strict_accuracy'))}</td>"
                f"<td>{_format_metric(diagnostic.get('mixed_parent_strict_accuracy'))}</td></tr>"
            )
        else:
            for panel_name, panel_metrics in sorted(panels.items()):
                panel_full = panel_metrics["full_memory"]
                panel_rows.append(
                    "<tr>"
                    f"<td>{html.escape(display_model)}</td><td>{html.escape(panel_name)}</td>"
                    f"<td>{_format_metric(panel_full.get('memcalib_h_score'))}</td>"
                    f"<td>{_format_metric(panel_full.get('strict_sample_accuracy'))}</td>"
                    f"<td>{_format_metric(panel_full.get('mixed_parent_strict_accuracy'))}</td></tr>"
                )
        verdicts = full.get("verdict_counts") or {}
        total_verdicts = sum(verdicts.values()) or 1
        error_rows.append(
            "<tr>"
            f"<td>{html.escape(display_model)}</td>"
            f"<td>{verdicts.get('under_use', 0) / total_verdicts:.3f}</td>"
            f"<td>{verdicts.get('over_use', 0) / total_verdicts:.3f}</td>"
            f"<td>{_format_metric(full.get('explicit_contradiction_rate'))}</td>"
            f"<td>{_format_metric(full.get('constraint_violation_rate'))}</td>"
            f"<td>{verdicts.get('unscorable', 0) / total_verdicts:.3f}</td>"
            f"<td>{_format_metric(full.get('mean_task_quality'))}</td>"
            f"<td>{_format_metric(full.get('safety_failure_rate'))}</td></tr>"
        )
    assessment = metrics.get("validity_assessment") or assess_benchmark_validity(metrics)
    status = assessment.get("status", "pending")
    status_label = {
        "provisionally_supported": "初步支持",
        "provisionally_supported_with_caveat": "初步支持（有限制）",
        "needs_review": "需要复核",
        "pending": "等待评分",
    }.get(status, status)
    failed_checks = assessment.get("failed_checks") or []
    caveats = assessment.get("caveats") or []
    caveat_labels = {
        "limited_single_score_discrimination": "单一总分区分度有限",
        "legacy_directional_judgments": "当前结果来自 v1 方向判定，完整混淆矩阵待 v2 Judge 重评",
    }
    agreement = metrics.get("judge_agreement") or {}
    overall_agreement = agreement.get("overall") or {}
    ordered_agreement = agreement.get("ordered_usage") or {}
    judge_quality = metrics.get("judge_output_quality") or {}
    primary_quality = judge_quality.get("primary") or {}
    secondary_quality = judge_quality.get("secondary") or {}
    agreement_rows = []
    for label, values in (agreement.get("by_label") or {}).items():
        agreement_rows.append(
            f"<tr><td>{html.escape(label)}</td><td>{values.get('n', 0)}</td>"
            f"<td>{_format_metric(values.get('exact_agreement'))}</td><td>{_format_metric(values.get('kappa'))}</td></tr>"
        )
    payload = html.escape(json.dumps(metrics, ensure_ascii=False))
    evaluation_summary = metrics.get("evaluation_summary") or {}
    sample_count = int(evaluation_summary.get("samples") or 0)
    conditions = set(evaluation_summary.get("conditions") or [])
    paired_available = ("full_memory" in conditions and "no_memory" in conditions) or any(
        (values.get("no_memory", {}).get("answers") or 0) > 0 for values in metrics["models"].values()
    )
    full_release = sample_count > 500 and not paired_available
    if full_release:
        report_title = f"MemCalib {sample_count:,} 全量评测报告"
    elif sample_count == 500:
        report_title = "MemCalib 500 验证报告"
    else:
        report_title = f"MemCalib {sample_count:,} 试点评测报告"
    report_subtitle = (
        "五个代表性模型在完整 Full-memory benchmark 上的原子级记忆使用校准结果。"
        if full_release
        else "五个代表性模型在 Full-memory 与 No-memory 配对条件下的记忆使用校准结果。"
    )
    paired_section = (
        f'<h2>配对因果诊断</h2><p class="section-note">Full-memory 与 No-memory 使用相同问题配对比较。记忆诱发 OPB 向右表示额外过度个性化；记忆减少 UPB 向右表示记忆有效缓解使用不足。</p><section class="effects">{"".join(effect_rows)}</section>'
        if paired_available
        else ""
    )
    panel_names = {
        panel_name
        for values in metrics["models"].values()
        for panel_name in (values.get("panels") or {})
    }
    if {"representative", "diagnostic"}.issubset(panel_names):
        panel_section = f'<h2>面板比较</h2><p class="section-note">Representative 贴近正式集分布；Diagnostic 定向覆盖混合标签、稀有 Hard-A、安全敏感和高原子数样本。</p><section class="panel"><table><thead><tr><th>模型</th><th>Representative</th><th>Diagnostic</th><th>Diagnostic 差值</th><th>Rep 混合严格</th><th>Diag 混合严格</th></tr></thead><tbody>{"".join(panel_rows)}</tbody></table></section>'
    else:
        panel_title = "全量面板" if panel_names == {"formal"} else "面板比较"
        panel_note = "所有正式样本均属于 formal panel。" if panel_names == {"formal"} else "按实际存在的评测面板汇总。"
        panel_section = f'<h2>{panel_title}</h2><p class="section-note">{panel_note}</p><section class="panel"><table><thead><tr><th>模型</th><th>面板</th><th>调和总分</th><th>样本严格</th><th>混合父记忆严格</th></tr></thead><tbody>{"".join(panel_rows)}</tbody></table></section>'
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(report_title)}</title><style>
:root{{--ink:#182230;--muted:#667085;--line:#d5dce6;--paper:#fff;--bg:#f2f4f7;--nav:#17253d;--teal:#087d71;--blue:#2667a9;--red:#b42318;--amber:#a15c00}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif;letter-spacing:0}}header{{background:var(--nav);color:#fff;padding:46px max(24px,calc((100vw - 1180px)/2)) 38px;border-bottom:5px solid var(--teal)}}header p{{color:#c9d3e1;max-width:760px;margin:8px 0 0}}header .status{{display:inline-flex;align-items:center;gap:8px;margin-top:18px;padding:6px 10px;border:1px solid #ffffff38;border-radius:4px}}header .status b{{color:#75e0d3}}
main{{max-width:1180px;margin:0 auto;padding:26px 24px 64px}}h1{{font-size:32px;margin:0}}h2{{font-size:20px;margin:38px 0 6px}}.section-note{{color:var(--muted);margin:0 0 14px}}.cards{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}}.model-card{{background:var(--paper);border:1px solid var(--line);border-radius:5px;padding:16px;min-width:0}}.model-card span,.model-card small{{display:block;color:var(--muted);overflow-wrap:anywhere}}.model-card strong{{display:block;font:700 28px/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--teal);margin:10px 0 4px}}
.panel{{background:var(--paper);border:1px solid var(--line);border-radius:5px;padding:16px;overflow:auto}}table{{width:100%;border-collapse:collapse;min-width:760px}}th,td{{padding:10px 11px;border-bottom:1px solid var(--line);text-align:right}}th:first-child,td:first-child{{text-align:left}}th{{color:var(--muted);font-size:12px}}tbody tr:last-child td{{border-bottom:0}}.effects{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}.effect-group{{background:#fff;border:1px solid var(--line);border-radius:5px;padding:15px}}.effect-group h3{{font-size:14px;margin:0 0 10px}}.effect{{display:grid;grid-template-columns:82px 1fr 52px;gap:9px;align-items:center;margin:8px 0}}.effect-label{{font-size:12px;color:var(--muted)}}.rail{{height:10px;background:#e8ecf2;position:relative;border-radius:2px}}.rail:after{{content:"";position:absolute;left:50%;top:-3px;bottom:-3px;width:1px;background:#8793a5}}.marker{{position:absolute;top:-3px;width:5px;height:16px;transform:translateX(-50%);border-radius:1px}}.teal{{color:var(--teal)}}.blue{{color:var(--blue)}}.red{{color:var(--red)}}.marker.teal{{background:var(--teal)}}.marker.blue{{background:var(--blue)}}.marker.red{{background:var(--red)}}.effect strong{{font:650 12px ui-monospace,SFMono-Regular,Menlo,monospace;text-align:right}}.checks{{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}}.check{{font-size:12px;padding:4px 7px;background:#fff;border:1px solid var(--line);border-radius:4px}}.check.fail{{border-color:#f0b8b2;color:var(--red)}}details{{margin-top:34px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#111827;color:#e5e7eb;padding:16px;border-radius:5px}}
@media(max-width:820px){{.cards{{grid-template-columns:1fr 1fr}}.effects{{grid-template-columns:1fr}}header{{padding:30px 18px}}main{{padding:18px 14px}}}}
</style></head><body><header><h1>{html.escape(report_title)}</h1><p>{html.escape(report_subtitle)}</p><div class="status"><span>Benchmark 状态</span><b>{html.escape(status_label)}</b></div></header>
<main><div class="checks">{''.join(f'<span class="check fail">{html.escape(item)}</span>' for item in failed_checks) if failed_checks else '<span class="check">核心自动检查通过</span>'}{''.join(f'<span class="check fail">限制：{html.escape(caveat_labels.get(item, item))}</span>' for item in caveats)}<span class="check">人工一致性：待完成</span></div>
<h2>OPB / UPB 主指标</h2><p class="section-note">主指标使用 Full-memory 条件。OPB 和 UPB 是按真实标签宏平均的方向性错误率，越低越好；总分是两个方向抵抗能力的调和平均，越高越好。置信区间按样本聚类 bootstrap 2000 次计算。当前模型总分极差为 {_format_metric(assessment.get('model_score_spread'))}。</p><section class="cards">{''.join(score_cards)}</section><section class="panel" style="margin-top:10px"><table><thead><tr><th>模型</th><th>调和总分</th><th>总分 95% CI</th><th>OPB 错误↓</th><th>OPB 95% CI</th><th>UPB 错误↓</th><th>UPB 95% CI</th><th>样本严格</th><th>混合父记忆严格</th></tr></thead><tbody>{''.join(core_rows)}</tbody></table></section>
{paired_section}
{panel_section}
<h2>辅助错误指标</h2><section class="panel"><table><thead><tr><th>模型</th><th>Under-use</th><th>Over-use</th><th>事实冲突</th><th>约束违反</th><th>Unscorable</th><th>回答质量</th><th>安全失败</th></tr></thead><tbody>{''.join(error_rows)}</tbody></table></section>
<h2>Judge 一致性</h2><p class="section-note">v1 verdict 一致性：n={overall_agreement.get('n', 0)}，exact={_format_metric(overall_agreement.get('exact_agreement'))}，κ={_format_metric(overall_agreement.get('kappa'))}。v2 有序等级一致性：n={ordered_agreement.get('n', 0)}，exact={_format_metric(ordered_agreement.get('exact_agreement'))}，线性加权 κ={_format_metric(ordered_agreement.get('linear_weighted_kappa'))}。主 Judge 共 {primary_quality.get('rows', 0)} 条有效判定，其中 {primary_quality.get('rows_with_warnings', 0)} 条带有不影响方向判定的辅助警告；复核 Judge 共 {secondary_quality.get('rows', 0)} 条。</p><section class="panel"><table><thead><tr><th>Gold 标签</th><th>原子数</th><th>Exact</th><th>Cohen κ</th></tr></thead><tbody>{''.join(agreement_rows) or '<tr><td colspan="4">复核评分尚未完成</td></tr>'}</tbody></table></section>
<details><summary>机器可读指标</summary><pre id="raw">{payload}</pre></details></main></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze validated MemCalib judgments.")
    parser.add_argument("--primary", type=Path, default=DEFAULT_PRIMARY)
    parser.add_argument("--secondary", type=Path, default=DEFAULT_SECONDARY)
    parser.add_argument("--hidden", type=Path, default=DEFAULT_HIDDEN)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    primary = list(iter_jsonl(args.primary))
    secondary = list(iter_jsonl(args.secondary)) if args.secondary.exists() else []
    samples = list(iter_jsonl(args.hidden))
    metrics = compute_metrics(primary, samples=samples, bootstrap_replicates=2000)
    metrics["judge_agreement"] = compute_judge_agreement(primary, secondary)
    metrics["judge_output_quality"] = {
        "primary": compute_judge_output_quality(primary),
        "secondary": compute_judge_output_quality(secondary),
    }
    metrics["evaluation_summary"] = {
        "samples": len(samples),
        "conditions": sorted({str(row["condition"]) for row in primary}),
        "models": sorted({str(row["model_key"]) for row in primary}),
        "primary_judgments": len(primary),
        "secondary_judgments": len(secondary),
    }
    metrics["validity_assessment"] = assess_benchmark_validity(metrics)
    write_json(args.metrics, metrics)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(metrics), encoding="utf-8")
    print(json.dumps({"metrics": str(args.metrics), "report": str(args.report), "models": len(metrics["models"])}, indent=2))


if __name__ == "__main__":
    main()
