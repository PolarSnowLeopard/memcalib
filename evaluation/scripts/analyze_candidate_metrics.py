#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import fmean, median
from typing import Any

import numpy as np

from evaluation.common import iter_jsonl, write_json


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PRIMARY = (
    ROOT
    / "evaluation"
    / "runs"
    / "memcalib-v21-multidomain-500-eight-models"
    / "judgments"
    / "primary.valid.jsonl"
)
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "evaluation"
    / "analyses"
    / "memcalib-v21-multidomain-500-candidate-metrics"
)
DEFAULT_OFFICIAL_METRICS = (
    ROOT
    / "evaluation"
    / "releases"
    / "memcalib-v21-multidomain-500-eight-models"
    / "metrics.json"
)
DEFAULT_STUDY_TITLE = "MemCalib v2.1 candidate metric study"
DEFAULT_STUDY_DESCRIPTION = (
    "This diagnostic uses the same locked 500 records and all 8,000 primary-Judge "
    "rows from the eight-model full/no-memory comparison. It does not change the "
    "official metric definition."
)
LABELS = ("A", "B", "C")
RANK = {"A": 0, "B": 1, "C": 2}
MODEL_DISPLAY_NAMES = {
    "codex-gpt56-sol": "Codex GPT-5.6 Sol",
    "deepseek": "DeepSeek-V4-Pro",
    "deepseek-flash": "DeepSeek-V4-Flash",
    "glm52": "GLM-5.2",
    "kimi": "Kimi-K2.6",
    "qwen-flash": "Qwen3.6-Flash",
    "qwen-max": "Qwen3.7-Max",
    "qwen3-8b": "Qwen3-8B",
    "qwen35-35b-a3b": "Qwen3.5-35B-A3B",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_input(rows: list[dict[str, Any]]) -> dict[str, Any]:
    models = sorted({str(row["model_key"]) for row in rows})
    conditions = sorted({str(row["condition"]) for row in rows})
    answer_ids = [str(row["answer_request_id"]) for row in rows]
    if len(answer_ids) != len(set(answer_ids)):
        raise ValueError("answer_request_id values must be unique")
    bucket_samples: dict[tuple[str, str], set[str]] = defaultdict(set)
    signatures: dict[str, set[tuple[str, str]]] = {}
    for row in rows:
        model = str(row["model_key"])
        condition = str(row["condition"])
        sample_id = str(row["sample_id"])
        bucket_samples[(model, condition)].add(sample_id)
        signature = {
            (str(atom["atom_id"]), str(atom["u_star"]))
            for atom in row["atom_judgments"]
            if atom.get("scorable", True)
        }
        if sample_id in signatures and signatures[sample_id] != signature:
            raise ValueError(f"atom signature mismatch for sample {sample_id}")
        signatures[sample_id] = signature
    sample_sets = list(bucket_samples.values())
    if not sample_sets or any(values != sample_sets[0] for values in sample_sets[1:]):
        raise ValueError("model-condition buckets do not use identical sample IDs")
    expected_buckets = {(model, condition) for model in models for condition in conditions}
    if set(bucket_samples) != expected_buckets:
        raise ValueError("model-condition bucket coverage is incomplete")
    return {
        "rows": len(rows),
        "unique_answer_request_ids": len(set(answer_ids)),
        "models": models,
        "conditions": conditions,
        "model_condition_buckets": len(bucket_samples),
        "samples_per_bucket": len(sample_sets[0]),
        "common_sample_ids": len(sample_sets[0]),
        "atom_signatures_consistent": True,
    }


def _safe_div(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        raise ValueError("percentile requires nonempty values")
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _flatten(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    atoms: list[dict[str, Any]] = []
    for row in rows:
        for atom in row["atom_judgments"]:
            predicted = atom.get("predicted_usage_level")
            gold = atom.get("u_star")
            if atom.get("scorable", True) and predicted in RANK and gold in RANK:
                atoms.append(
                    {
                        "model_key": str(row["model_key"]),
                        "condition": str(row["condition"]),
                        "sample_id": str(row["sample_id"]),
                        "atom_id": str(atom["atom_id"]),
                        "gold": str(gold),
                        "predicted": str(predicted),
                    }
                )
    return atoms


def _confusion(atoms: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    matrix = {gold: {predicted: 0 for predicted in LABELS} for gold in LABELS}
    for atom in atoms:
        matrix[atom["gold"]][atom["predicted"]] += 1
    return matrix


def _matrix_to_confusion(matrix: np.ndarray) -> dict[str, dict[str, int]]:
    return {
        gold: {
            predicted: int(matrix[gold_index, predicted_index])
            for predicted_index, predicted in enumerate(LABELS)
        }
        for gold_index, gold in enumerate(LABELS)
    }


def _directional_from_confusion(
    confusion: dict[str, dict[str, int]],
) -> dict[str, float]:
    a_total = sum(confusion["A"].values())
    b_total = sum(confusion["B"].values())
    c_total = sum(confusion["C"].values())
    a_over = (confusion["A"]["B"] + confusion["A"]["C"]) / a_total
    b_over = confusion["B"]["C"] / b_total
    b_under = confusion["B"]["A"] / b_total
    c_under = (confusion["C"]["A"] + confusion["C"]["B"]) / c_total
    opb = (a_over + b_over) / 2
    upb = (b_under + c_under) / 2
    over_resistance = 1 - opb
    under_resistance = 1 - upb
    return {
        "opb_error_rate": opb,
        "upb_error_rate": upb,
        "memcalib_h_score": (
            2
            * over_resistance
            * under_resistance
            / (over_resistance + under_resistance)
        ),
    }


def _weighted_kappa(matrix: list[list[int]], power: int) -> float | None:
    total = sum(sum(row) for row in matrix)
    if not total:
        return None
    row_totals = [sum(row) for row in matrix]
    column_totals = [sum(matrix[i][j] for i in range(3)) for j in range(3)]
    observed = 0.0
    expected = 0.0
    for i in range(3):
        for j in range(3):
            loss = (abs(i - j) / 2) ** power
            observed += loss * matrix[i][j] / total
            expected += loss * row_totals[i] * column_totals[j] / (total * total)
    return 1 - observed / expected if expected else 1.0


def _pearson_from_counts(matrix: list[list[int]]) -> float | None:
    total = sum(sum(row) for row in matrix)
    if not total:
        return None
    mean_gold = sum(i * sum(matrix[i]) for i in range(3)) / total
    mean_predicted = (
        sum(j * sum(matrix[i][j] for i in range(3)) for j in range(3)) / total
    )
    covariance = sum(
        matrix[i][j] * (i - mean_gold) * (j - mean_predicted)
        for i in range(3)
        for j in range(3)
    )
    gold_variance = sum(
        matrix[i][j] * (i - mean_gold) ** 2
        for i in range(3)
        for j in range(3)
    )
    predicted_variance = sum(
        matrix[i][j] * (j - mean_predicted) ** 2
        for i in range(3)
        for j in range(3)
    )
    denominator = math.sqrt(gold_variance * predicted_variance)
    return covariance / denominator if denominator else None


def classification_metrics(
    confusion: dict[str, dict[str, int]],
) -> dict[str, Any]:
    matrix = [[confusion[gold][predicted] for predicted in LABELS] for gold in LABELS]
    total = sum(sum(row) for row in matrix)
    row_totals = [sum(row) for row in matrix]
    column_totals = [sum(matrix[i][j] for i in range(3)) for j in range(3)]
    diagonal = sum(matrix[i][i] for i in range(3))
    per_label: dict[str, dict[str, float | int | None]] = {}
    recalls: list[float] = []
    precisions: list[float] = []
    f1_values: list[float] = []
    for i, label in enumerate(LABELS):
        recall = _safe_div(matrix[i][i], row_totals[i])
        precision = _safe_div(matrix[i][i], column_totals[i])
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision is not None and recall is not None and precision + recall
            else 0.0
        )
        per_label[label] = {
            "support": row_totals[i],
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
        if recall is not None:
            recalls.append(recall)
        if precision is not None:
            precisions.append(precision)
        f1_values.append(f1)

    expected_accuracy = (
        sum(row_totals[i] * column_totals[i] for i in range(3)) / (total * total)
        if total
        else None
    )
    accuracy = _safe_div(diagonal, total)
    unweighted_kappa = (
        (accuracy - expected_accuracy) / (1 - expected_accuracy)
        if accuracy is not None and expected_accuracy is not None and expected_accuracy < 1
        else None
    )

    mcc_numerator = diagonal * total - sum(
        row_totals[i] * column_totals[i] for i in range(3)
    )
    mcc_denominator = math.sqrt(
        (total * total - sum(value * value for value in row_totals))
        * (total * total - sum(value * value for value in column_totals))
    )
    mcc = mcc_numerator / mcc_denominator if mcc_denominator else None

    mutual_information = 0.0
    for i in range(3):
        for j in range(3):
            count = matrix[i][j]
            if count and row_totals[i] and column_totals[j]:
                probability = count / total
                mutual_information += probability * math.log(
                    count * total / (row_totals[i] * column_totals[j])
                )
    gold_entropy = -sum(
        (count / total) * math.log(count / total) for count in row_totals if count
    )
    predicted_entropy = -sum(
        (count / total) * math.log(count / total) for count in column_totals if count
    )
    nmi_denominator = math.sqrt(gold_entropy * predicted_entropy)
    normalized_mutual_information = (
        mutual_information / nmi_denominator if nmi_denominator else None
    )

    chi_square = 0.0
    for i in range(3):
        for j in range(3):
            expected = row_totals[i] * column_totals[j] / total if total else 0.0
            if expected:
                chi_square += (matrix[i][j] - expected) ** 2 / expected
    cramers_v = math.sqrt(chi_square / (total * 2)) if total else None

    return {
        "atom_count": total,
        "atom_exact_accuracy": accuracy,
        "balanced_accuracy": fmean(recalls) if recalls else None,
        "macro_precision": fmean(precisions) if precisions else None,
        "macro_recall": fmean(recalls) if recalls else None,
        "macro_f1": fmean(f1_values) if f1_values else None,
        "weighted_f1": (
            sum(f1_values[i] * row_totals[i] for i in range(3)) / total
            if total
            else None
        ),
        "multiclass_mcc": mcc,
        "cohen_kappa": unweighted_kappa,
        "linear_weighted_kappa": _weighted_kappa(matrix, 1),
        "quadratic_weighted_kappa": _weighted_kappa(matrix, 2),
        "normalized_mutual_information": normalized_mutual_information,
        "cramers_v": cramers_v,
        "ordinal_rank_correlation": _pearson_from_counts(matrix),
        "per_label": per_label,
    }


def ordinal_metrics(
    confusion: dict[str, dict[str, int]],
) -> dict[str, float | int | None]:
    matrix = [[confusion[gold][predicted] for predicted in LABELS] for gold in LABELS]
    total = sum(sum(row) for row in matrix)
    absolute_error = sum(
        matrix[i][j] * abs(i - j) for i in range(3) for j in range(3)
    )
    squared_error = sum(
        matrix[i][j] * (i - j) ** 2 for i in range(3) for j in range(3)
    )
    severe = matrix[0][2] + matrix[2][0]
    over_linear = sum(
        matrix[i][j] * max(j - i, 0) for i in range(3) for j in range(3)
    )
    under_linear = sum(
        matrix[i][j] * max(i - j, 0) for i in range(3) for j in range(3)
    )
    over_quadratic = sum(
        matrix[i][j] * max(j - i, 0) ** 2 for i in range(3) for j in range(3)
    )
    under_quadratic = sum(
        matrix[i][j] * max(i - j, 0) ** 2 for i in range(3) for j in range(3)
    )
    row_totals = [sum(row) for row in matrix]
    over_linear_max = 2 * row_totals[0] + row_totals[1]
    under_linear_max = row_totals[1] + 2 * row_totals[2]
    over_quadratic_max = 4 * row_totals[0] + row_totals[1]
    under_quadratic_max = row_totals[1] + 4 * row_totals[2]
    symmetric_linear_max = sum(
        row_totals[i] * max(i, 2 - i) for i in range(3)
    )
    symmetric_quadratic_max = sum(
        row_totals[i] * max(i, 2 - i) ** 2 for i in range(3)
    )

    macro_linear_scores = []
    macro_quadratic_scores = []
    for i in range(3):
        if row_totals[i]:
            max_distance = max(i, 2 - i)
            linear_loss = sum(
                matrix[i][j] * abs(i - j) for j in range(3)
            ) / (row_totals[i] * max_distance)
            quadratic_loss = sum(
                matrix[i][j] * (i - j) ** 2 for j in range(3)
            ) / (row_totals[i] * max_distance**2)
            macro_linear_scores.append(1 - linear_loss)
            macro_quadratic_scores.append(1 - quadratic_loss)

    return {
        "ordinal_mae": _safe_div(absolute_error, total),
        "ordinal_rmse": math.sqrt(squared_error / total) if total else None,
        "normalized_global_linear_score": (
            1 - absolute_error / symmetric_linear_max
            if symmetric_linear_max
            else None
        ),
        "normalized_global_quadratic_score": (
            1 - squared_error / symmetric_quadratic_max
            if symmetric_quadratic_max
            else None
        ),
        "macro_normalized_linear_score": (
            fmean(macro_linear_scores) if macro_linear_scores else None
        ),
        "macro_normalized_quadratic_score": (
            fmean(macro_quadratic_scores) if macro_quadratic_scores else None
        ),
        "severe_two_step_atom_error_rate": _safe_div(severe, total),
        "overuse_linear_cost_rate": _safe_div(over_linear, over_linear_max),
        "underuse_linear_cost_rate": _safe_div(under_linear, under_linear_max),
        "overuse_quadratic_cost_rate": _safe_div(
            over_quadratic, over_quadratic_max
        ),
        "underuse_quadratic_cost_rate": _safe_div(
            under_quadratic, under_quadratic_max
        ),
    }


def composite_metrics(opb: float, upb: float) -> dict[str, float]:
    over_resistance = 1 - opb
    under_resistance = 1 - upb

    def power_mean(power: float) -> float:
        return (
            (over_resistance**power + under_resistance**power) / 2
        ) ** (1 / power)

    return {
        "harmonic_h": 2
        * over_resistance
        * under_resistance
        / (over_resistance + under_resistance),
        "arithmetic_resistance": (over_resistance + under_resistance) / 2,
        "geometric_resistance": math.sqrt(over_resistance * under_resistance),
        "product_resistance": over_resistance * under_resistance,
        "softmin_p_minus_2": power_mean(-2),
        "softmin_p_minus_4": power_mean(-4),
        "softmin_p_minus_8": power_mean(-8),
        "mincalib": min(over_resistance, under_resistance),
        "ideal_l2_score": 1 - math.sqrt((opb * opb + upb * upb) / 2),
    }


def _tail_mean(values: list[float], alpha: float) -> float:
    count = max(1, math.ceil((1 - alpha) * len(values)))
    return fmean(sorted(values, reverse=True)[:count])


def sample_risk_metrics(
    atoms: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, float]]:
    by_sample: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for atom in atoms:
        by_sample[atom["sample_id"]].append(atom)
    linear_losses: dict[str, float] = {}
    quadratic_losses: dict[str, float] = {}
    exact_losses: dict[str, float] = {}
    severe_flags: list[int] = []
    strict_flags: list[int] = []
    by_atom_count: dict[int, list[float]] = defaultdict(list)
    for sample_id, values in by_sample.items():
        distances = [
            abs(RANK[atom["predicted"]] - RANK[atom["gold"]]) for atom in values
        ]
        linear = fmean(distance / 2 for distance in distances)
        quadratic = fmean((distance / 2) ** 2 for distance in distances)
        exact_loss = fmean(int(distance > 0) for distance in distances)
        linear_losses[sample_id] = linear
        quadratic_losses[sample_id] = quadratic
        exact_losses[sample_id] = exact_loss
        severe_flags.append(int(any(distance == 2 for distance in distances)))
        strict_flags.append(int(all(distance == 0 for distance in distances)))
        by_atom_count[len(distances)].append(linear)

    linear_values = list(linear_losses.values())
    quadratic_values = list(quadratic_losses.values())
    exact_values = list(exact_losses.values())
    return (
        {
            "samples": len(by_sample),
            "strict_sample_accuracy": fmean(strict_flags),
            "any_atom_error_rate": 1 - fmean(strict_flags),
            "severe_two_step_sample_rate": fmean(severe_flags),
            "linear_loss": {
                "mean": fmean(linear_values),
                "median": median(linear_values),
                "p90": _percentile(linear_values, 0.90),
                "p95": _percentile(linear_values, 0.95),
                "cvar90": _tail_mean(linear_values, 0.90),
                "cvar95": _tail_mean(linear_values, 0.95),
                "maximum": max(linear_values),
            },
            "quadratic_loss": {
                "mean": fmean(quadratic_values),
                "median": median(quadratic_values),
                "p90": _percentile(quadratic_values, 0.90),
                "p95": _percentile(quadratic_values, 0.95),
                "cvar90": _tail_mean(quadratic_values, 0.90),
                "cvar95": _tail_mean(quadratic_values, 0.95),
                "maximum": max(quadratic_values),
            },
            "exact_atom_loss": {
                "mean": fmean(exact_values),
                "cvar90": _tail_mean(exact_values, 0.90),
                "cvar95": _tail_mean(exact_values, 0.95),
            },
            "linear_loss_by_atom_count": {
                str(count): {
                    "samples": len(values),
                    "mean": fmean(values),
                }
                for count, values in sorted(by_atom_count.items())
            },
        },
        linear_losses,
    )


def bootstrap_candidate_intervals(
    atoms: list[dict[str, Any]],
    *,
    replicates: int,
    seed: int,
) -> dict[str, dict[str, float | int]]:
    by_sample_condition: dict[
        str, dict[str, list[dict[str, Any]]]
    ] = defaultdict(lambda: defaultdict(list))
    for atom in atoms:
        by_sample_condition[atom["sample_id"]][atom["condition"]].append(atom)
    sample_ids = sorted(by_sample_condition)
    full_confusions = np.zeros((len(sample_ids), 3, 3), dtype=np.int64)
    no_confusions = np.zeros_like(full_confusions)
    linear_losses = np.zeros(len(sample_ids), dtype=float)
    strict = np.zeros(len(sample_ids), dtype=float)
    severe = np.zeros(len(sample_ids), dtype=float)
    for sample_index, sample_id in enumerate(sample_ids):
        for condition, target in (
            ("full_memory", full_confusions),
            ("no_memory", no_confusions),
        ):
            for atom in by_sample_condition[sample_id][condition]:
                target[
                    sample_index,
                    RANK[atom["gold"]],
                    RANK[atom["predicted"]],
                ] += 1
        distances = [
            abs(RANK[atom["predicted"]] - RANK[atom["gold"]])
            for atom in by_sample_condition[sample_id]["full_memory"]
        ]
        linear_losses[sample_index] = fmean(distance / 2 for distance in distances)
        strict[sample_index] = float(all(distance == 0 for distance in distances))
        severe[sample_index] = float(any(distance == 2 for distance in distances))

    samples: dict[str, list[float]] = defaultdict(list)
    rng = np.random.default_rng(seed)
    for _ in range(replicates):
        indices = rng.integers(0, len(sample_ids), size=len(sample_ids))
        full_confusion = _matrix_to_confusion(full_confusions[indices].sum(axis=0))
        no_confusion = _matrix_to_confusion(no_confusions[indices].sum(axis=0))
        full_directional = _directional_from_confusion(full_confusion)
        no_directional = _directional_from_confusion(no_confusion)
        composites = composite_metrics(
            full_directional["opb_error_rate"],
            full_directional["upb_error_rate"],
        )
        classification = classification_metrics(full_confusion)
        ordinal = ordinal_metrics(full_confusion)
        induced_opb = (
            full_directional["opb_error_rate"]
            - no_directional["opb_error_rate"]
        )
        reduced_upb = (
            no_directional["upb_error_rate"]
            - full_directional["upb_error_rate"]
        )
        sampled_losses = [float(value) for value in linear_losses[indices]]
        values = {
            "opb_error_rate": full_directional["opb_error_rate"],
            "upb_error_rate": full_directional["upb_error_rate"],
            "H": composites["harmonic_h"],
            "MinCalib": composites["mincalib"],
            "multiclass_mcc": classification["multiclass_mcc"],
            "linear_weighted_kappa": classification["linear_weighted_kappa"],
            "quadratic_weighted_kappa": classification[
                "quadratic_weighted_kappa"
            ],
            "strict_sample_accuracy": float(strict[indices].mean()),
            "severe_two_step_sample_rate": float(severe[indices].mean()),
            "severe_two_step_atom_error_rate": ordinal[
                "severe_two_step_atom_error_rate"
            ],
            "cvar90_linear_loss": _tail_mean(sampled_losses, 0.90),
            "pmu_lambda_1_0": reduced_upb - induced_opb,
        }
        for key, value in values.items():
            if value is not None:
                samples[key].append(float(value))
    return {
        key: {
            "ci_low": _percentile(values, 0.025),
            "ci_high": _percentile(values, 0.975),
            "replicates": replicates,
            "clusters": len(sample_ids),
        }
        for key, values in samples.items()
    }


def paired_utility(
    full: dict[str, Any], no_memory: dict[str, Any]
) -> dict[str, float]:
    induced_opb = full["opb_error_rate"] - no_memory["opb_error_rate"]
    reduced_upb = no_memory["upb_error_rate"] - full["upb_error_rate"]
    relative_upb_reduction = (
        reduced_upb / no_memory["upb_error_rate"]
        if no_memory["upb_error_rate"]
        else 0.0
    )
    result = {
        "memory_induced_opb": induced_opb,
        "memory_reduced_upb": reduced_upb,
        "relative_upb_reduction": relative_upb_reduction,
        "full_minus_no_memory_h": (
            full["memcalib_h_score"] - no_memory["memcalib_h_score"]
        ),
    }
    for value in (0.5, 1.0, 2.0):
        suffix = str(value).replace(".", "_")
        result[f"pmu_lambda_{suffix}"] = reduced_upb - value * induced_opb
        result[f"relative_pmu_lambda_{suffix}"] = (
            relative_upb_reduction - value * induced_opb
        )
    return result


def _two_sided_sign_test(wins: int, losses: int) -> float:
    trials = wins + losses
    if not trials:
        return 1.0
    tail = min(wins, losses)
    probability = sum(math.comb(trials, value) for value in range(tail + 1)) / (
        2**trials
    )
    return min(1.0, 2 * probability)


def pairwise_comparisons(
    losses_by_model: dict[str, dict[str, float]],
    *,
    bootstrap_replicates: int,
    seed: int,
) -> list[dict[str, Any]]:
    models = sorted(losses_by_model)
    comparisons = []
    for pair_index, left in enumerate(models):
        for right in models[pair_index + 1 :]:
            sample_ids = sorted(
                set(losses_by_model[left]).intersection(losses_by_model[right])
            )
            differences = [
                losses_by_model[left][sample_id]
                - losses_by_model[right][sample_id]
                for sample_id in sample_ids
            ]
            wins = sum(value < -1e-12 for value in differences)
            losses = sum(value > 1e-12 for value in differences)
            ties = len(differences) - wins - losses
            bootstrap_values: list[float] = []
            rng = random.Random(seed + pair_index * 100 + models.index(right))
            for _ in range(bootstrap_replicates):
                bootstrap_values.append(
                    fmean(rng.choices(differences, k=len(differences)))
                )
            comparisons.append(
                {
                    "left": left,
                    "right": right,
                    "samples": len(sample_ids),
                    "left_wins": wins,
                    "ties": ties,
                    "right_wins": losses,
                    "left_win_share": (wins + 0.5 * ties) / len(sample_ids),
                    "mean_loss_difference_left_minus_right": fmean(differences),
                    "mean_loss_difference_ci95": [
                        _percentile(bootstrap_values, 0.025),
                        _percentile(bootstrap_values, 0.975),
                    ],
                    "two_sided_sign_test_p": _two_sided_sign_test(wins, losses),
                }
            )
    return comparisons


def fit_bradley_terry(
    comparisons: list[dict[str, Any]],
) -> dict[str, dict[str, float]]:
    models = sorted(
        {row["left"] for row in comparisons}.union(
            row["right"] for row in comparisons
        )
    )
    index = {model: position for position, model in enumerate(models)}
    wins = np.zeros((len(models), len(models)), dtype=float)
    totals = np.zeros_like(wins)
    for row in comparisons:
        left = index[row["left"]]
        right = index[row["right"]]
        left_wins = row["left_wins"] + 0.5 * row["ties"]
        right_wins = row["right_wins"] + 0.5 * row["ties"]
        wins[left, right] = left_wins
        wins[right, left] = right_wins
        totals[left, right] = totals[right, left] = row["samples"]

    strengths = np.ones(len(models), dtype=float)
    total_wins = wins.sum(axis=1)
    for _ in range(10000):
        updated = np.zeros_like(strengths)
        for i in range(len(models)):
            denominator = sum(
                totals[i, j] / (strengths[i] + strengths[j])
                for j in range(len(models))
                if i != j and totals[i, j]
            )
            updated[i] = total_wins[i] / denominator if denominator else 1.0
        updated /= math.exp(float(np.log(updated).mean()))
        if float(np.max(np.abs(np.log(updated) - np.log(strengths)))) < 1e-12:
            strengths = updated
            break
        strengths = updated
    abilities = np.log(strengths)
    abilities -= abilities.mean()
    return {
        model: {
            "ability": float(abilities[index[model]]),
            "strength": float(math.exp(abilities[index[model]])),
        }
        for model in models
    }


def fit_rasch(
    atoms: list[dict[str, Any]],
    models: list[str],
    *,
    direction: str,
) -> dict[str, Any]:
    if direction not in {"over", "under"}:
        raise ValueError("direction must be over or under")
    eligible_gold = {"A", "B"} if direction == "over" else {"B", "C"}
    item_outcomes: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for atom in atoms:
        if atom["gold"] not in eligible_gold:
            continue
        gold_rank = RANK[atom["gold"]]
        predicted_rank = RANK[atom["predicted"]]
        success = (
            predicted_rank <= gold_rank
            if direction == "over"
            else predicted_rank >= gold_rank
        )
        item_outcomes[(atom["sample_id"], atom["atom_id"])][atom["model_key"]] = float(
            success
        )
    complete_items = sorted(
        item for item, outcomes in item_outcomes.items() if set(outcomes) == set(models)
    )
    responses = np.array(
        [[item_outcomes[item][model] for item in complete_items] for model in models],
        dtype=float,
    )
    theta = np.zeros(len(models), dtype=float)
    difficulty = np.zeros(len(complete_items), dtype=float)
    ridge = 1e-3
    converged = False
    iterations = 0
    for iterations in range(1, 501):
        previous_theta = theta.copy()
        previous_difficulty = difficulty.copy()
        for model_index in range(len(models)):
            eta = np.clip(theta[model_index] - difficulty, -20, 20)
            probability = 1 / (1 + np.exp(-eta))
            gradient = float((responses[model_index] - probability).sum()) - ridge * theta[
                model_index
            ]
            hessian = -float((probability * (1 - probability)).sum()) - ridge
            theta[model_index] -= gradient / hessian
        for item_index in range(len(complete_items)):
            eta = np.clip(theta - difficulty[item_index], -20, 20)
            probability = 1 / (1 + np.exp(-eta))
            gradient = float((probability - responses[:, item_index]).sum()) - ridge * difficulty[
                item_index
            ]
            hessian = -float((probability * (1 - probability)).sum()) - ridge
            difficulty[item_index] -= gradient / hessian
        shift = float(difficulty.mean())
        difficulty -= shift
        theta -= shift
        difficulty = np.clip(difficulty, -8, 8)
        theta = np.clip(theta, -8, 8)
        change = max(
            float(np.max(np.abs(theta - previous_theta))),
            float(np.max(np.abs(difficulty - previous_difficulty))),
        )
        if change < 1e-8:
            converged = True
            break
    theta -= theta.mean()
    standard_errors = []
    for model_index in range(len(models)):
        eta = np.clip(theta[model_index] - difficulty, -20, 20)
        probability = 1 / (1 + np.exp(-eta))
        information = float((probability * (1 - probability)).sum()) + ridge
        standard_errors.append(1 / math.sqrt(information))
    return {
        "direction": direction,
        "items": len(complete_items),
        "models": len(models),
        "converged": converged,
        "iterations": iterations,
        "estimator": "joint_maximum_likelihood_rasch_1pl",
        "model_abilities": {
            model: {
                "theta": float(theta[index]),
                "approximate_standard_error": standard_errors[index],
            }
            for index, model in enumerate(models)
        },
        "limitations": (
            "Approximate model standard errors condition on estimated item "
            "difficulties and do not include full joint uncertainty."
        ),
    }


def pareto_summary(
    model_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    models = sorted(model_metrics)
    dominates: dict[str, list[str]] = {model: [] for model in models}
    dominated_by: dict[str, list[str]] = {model: [] for model in models}
    for left in models:
        left_opb = model_metrics[left]["standard"]["full_memory"]["opb_error_rate"]
        left_upb = model_metrics[left]["standard"]["full_memory"]["upb_error_rate"]
        for right in models:
            if left == right:
                continue
            right_opb = model_metrics[right]["standard"]["full_memory"]["opb_error_rate"]
            right_upb = model_metrics[right]["standard"]["full_memory"]["upb_error_rate"]
            if (
                left_opb <= right_opb
                and left_upb <= right_upb
                and (left_opb < right_opb or left_upb < right_upb)
            ):
                dominates[left].append(right)
                dominated_by[right].append(left)
    return {
        "pareto_front": [model for model in models if not dominated_by[model]],
        "dominates": dominates,
        "dominated_by": dominated_by,
    }


def _metric_spreads(model_metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    paths = {
        "H": ("composites", "harmonic_h"),
        "MinCalib": ("composites", "mincalib"),
        "product_resistance": ("composites", "product_resistance"),
        "MCC": ("classification", "multiclass_mcc"),
        "linear_kappa": ("classification", "linear_weighted_kappa"),
        "quadratic_kappa": ("classification", "quadratic_weighted_kappa"),
        "balanced_accuracy": ("classification", "balanced_accuracy"),
        "macro_F1": ("classification", "macro_f1"),
        "strict_sample_accuracy": ("sample_risk", "strict_sample_accuracy"),
        "CVaR90_linear_loss": ("sample_risk", "linear_loss", "cvar90"),
        "PMU_lambda_1": ("paired_utility", "pmu_lambda_1_0"),
    }
    result = {}
    for name, path in paths.items():
        values = []
        for metrics in model_metrics.values():
            value: Any = metrics
            for key in path:
                value = value[key]
            values.append(float(value))
        result[name] = {
            "minimum": min(values),
            "maximum": max(values),
            "range": max(values) - min(values),
            "population_sd": float(np.std(values)),
        }
    return result


def compute_candidate_metrics(
    rows: list[dict[str, Any]],
    *,
    bootstrap_replicates: int = 2000,
    seed: int = 20260720,
) -> dict[str, Any]:
    from evaluation.scripts.analyze_evaluation import compute_metrics

    input_integrity = validate_input(rows)
    standard = compute_metrics(rows)
    atoms = _flatten(rows)
    models = sorted(standard["models"])
    model_metrics: dict[str, dict[str, Any]] = {}
    losses_by_model: dict[str, dict[str, float]] = {}
    for model in models:
        model_atoms = [atom for atom in atoms if atom["model_key"] == model]
        full_atoms = [
            atom for atom in model_atoms if atom["condition"] == "full_memory"
        ]
        full_confusion = _confusion(full_atoms)
        classification = classification_metrics(full_confusion)
        ordinal = ordinal_metrics(full_confusion)
        full_standard = standard["models"][model]["full_memory"]
        no_standard = standard["models"][model]["no_memory"]
        sample_risk, losses = sample_risk_metrics(full_atoms)
        losses_by_model[model] = losses
        model_metrics[model] = {
            "display_name": MODEL_DISPLAY_NAMES.get(model, model),
            "standard": {
                "full_memory": {
                    key: full_standard[key]
                    for key in (
                        "opb_error_rate",
                        "upb_error_rate",
                        "memcalib_h_score",
                        "micro_opb_error_rate",
                        "micro_upb_error_rate",
                        "micro_memcalib_h_score",
                        "label_success",
                        "strict_sample_accuracy",
                    )
                },
                "no_memory": {
                    key: no_standard[key]
                    for key in (
                        "opb_error_rate",
                        "upb_error_rate",
                        "memcalib_h_score",
                        "micro_opb_error_rate",
                        "micro_upb_error_rate",
                        "micro_memcalib_h_score",
                    )
                },
            },
            "classification": classification,
            "ordinal": ordinal,
            "composites": composite_metrics(
                full_standard["opb_error_rate"], full_standard["upb_error_rate"]
            ),
            "sample_risk": sample_risk,
            "paired_utility": paired_utility(full_standard, no_standard),
            "bootstrap_ci95": bootstrap_candidate_intervals(
                model_atoms,
                replicates=bootstrap_replicates,
                seed=seed + models.index(model) * 1000,
            ),
        }

    comparisons = pairwise_comparisons(
        losses_by_model,
        bootstrap_replicates=bootstrap_replicates,
        seed=seed,
    )
    bradley_terry = fit_bradley_terry(comparisons)
    over_irt = fit_rasch(
        [atom for atom in atoms if atom["condition"] == "full_memory"],
        models,
        direction="over",
    )
    under_irt = fit_rasch(
        [atom for atom in atoms if atom["condition"] == "full_memory"],
        models,
        direction="under",
    )
    for model in models:
        over_theta = over_irt["model_abilities"][model]["theta"]
        under_theta = under_irt["model_abilities"][model]["theta"]
        model_metrics[model]["rasch_2d"] = {
            "over_theta": over_theta,
            "under_theta": under_theta,
            "mean_theta": (over_theta + under_theta) / 2,
            "min_theta": min(over_theta, under_theta),
        }
        model_metrics[model]["bradley_terry"] = bradley_terry[model]

    return {
        "schema_version": "memcalib-candidate-metrics-study-v1",
        "source": {
            "rows": len(rows),
            "models": len(models),
            "samples_per_model_per_condition": 500,
            "bootstrap_replicates": bootstrap_replicates,
            "seed": seed,
            "basis": "ordered-usage-v2.1 primary Judge outputs",
        },
        "input_integrity": input_integrity,
        "models": model_metrics,
        "metric_spreads": _metric_spreads(model_metrics),
        "pairwise": {
            "basis": (
                "full-memory per-sample mean absolute ordinal distance, "
                "normalized by the two-level maximum"
            ),
            "comparisons": comparisons,
            "bradley_terry": bradley_terry,
        },
        "rasch_2d": {
            "overuse_resistance": over_irt,
            "underuse_resistance": under_irt,
        },
        "pareto": pareto_summary(model_metrics),
        "noncomputable_without_new_protocol": {
            "proper_probability_scores": (
                "Brier score, log loss, and ordinal CRPS require a calibrated "
                "probability distribution over A/B/C; the current Judge emits "
                "a hard level plus an ordinal confidence field."
            ),
            "human_validity": (
                "No metric transformation substitutes for blinded human expert "
                "validation of the Judge labels."
            ),
        },
    }


def _fmt(value: float | None, digits: int = 3) -> str:
    return "NA" if value is None else f"{value:.{digits}f}"


def _write_csv(result: dict[str, Any], path: Path) -> None:
    columns = [
        "model_key",
        "display_name",
        "opb",
        "upb",
        "H",
        "mincalib",
        "softmin_p_minus_4",
        "product_resistance",
        "balanced_accuracy",
        "macro_f1",
        "multiclass_mcc",
        "linear_weighted_kappa",
        "quadratic_weighted_kappa",
        "ordinal_mae",
        "severe_two_step_atom_error_rate",
        "strict_sample_accuracy",
        "severe_two_step_sample_rate",
        "linear_loss_cvar90",
        "linear_loss_cvar95",
        "pmu_lambda_0_5",
        "pmu_lambda_1_0",
        "pmu_lambda_2_0",
        "relative_pmu_lambda_1_0",
        "rasch_over_theta",
        "rasch_under_theta",
        "rasch_min_theta",
        "bradley_terry_ability",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for model, values in result["models"].items():
            full = values["standard"]["full_memory"]
            writer.writerow(
                {
                    "model_key": model,
                    "display_name": values["display_name"],
                    "opb": full["opb_error_rate"],
                    "upb": full["upb_error_rate"],
                    "H": values["composites"]["harmonic_h"],
                    "mincalib": values["composites"]["mincalib"],
                    "softmin_p_minus_4": values["composites"]["softmin_p_minus_4"],
                    "product_resistance": values["composites"]["product_resistance"],
                    "balanced_accuracy": values["classification"]["balanced_accuracy"],
                    "macro_f1": values["classification"]["macro_f1"],
                    "multiclass_mcc": values["classification"]["multiclass_mcc"],
                    "linear_weighted_kappa": values["classification"][
                        "linear_weighted_kappa"
                    ],
                    "quadratic_weighted_kappa": values["classification"][
                        "quadratic_weighted_kappa"
                    ],
                    "ordinal_mae": values["ordinal"]["ordinal_mae"],
                    "severe_two_step_atom_error_rate": values["ordinal"][
                        "severe_two_step_atom_error_rate"
                    ],
                    "strict_sample_accuracy": values["sample_risk"][
                        "strict_sample_accuracy"
                    ],
                    "severe_two_step_sample_rate": values["sample_risk"][
                        "severe_two_step_sample_rate"
                    ],
                    "linear_loss_cvar90": values["sample_risk"]["linear_loss"][
                        "cvar90"
                    ],
                    "linear_loss_cvar95": values["sample_risk"]["linear_loss"][
                        "cvar95"
                    ],
                    "pmu_lambda_0_5": values["paired_utility"]["pmu_lambda_0_5"],
                    "pmu_lambda_1_0": values["paired_utility"]["pmu_lambda_1_0"],
                    "pmu_lambda_2_0": values["paired_utility"]["pmu_lambda_2_0"],
                    "relative_pmu_lambda_1_0": values["paired_utility"][
                        "relative_pmu_lambda_1_0"
                    ],
                    "rasch_over_theta": values["rasch_2d"]["over_theta"],
                    "rasch_under_theta": values["rasch_2d"]["under_theta"],
                    "rasch_min_theta": values["rasch_2d"]["min_theta"],
                    "bradley_terry_ability": values["bradley_terry"]["ability"],
                }
            )


def _markdown_table(
    headers: list[str], rows: list[list[str]], align_right_from: int = 1
) -> str:
    separator = [
        "---" if index < align_right_from else "---:"
        for index in range(len(headers))
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def _write_markdown(result: dict[str, Any], path: Path) -> None:
    models = result["models"]
    order = sorted(
        models,
        key=lambda model: models[model]["composites"]["harmonic_h"],
        reverse=True,
    )
    overview_rows = []
    for model in order:
        values = models[model]
        full = values["standard"]["full_memory"]
        overview_rows.append(
            [
                values["display_name"],
                _fmt(full["opb_error_rate"]),
                _fmt(full["upb_error_rate"]),
                _fmt(values["composites"]["harmonic_h"]),
                _fmt(values["composites"]["mincalib"]),
                _fmt(values["classification"]["multiclass_mcc"]),
                _fmt(values["classification"]["linear_weighted_kappa"]),
                _fmt(values["sample_risk"]["linear_loss"]["cvar90"]),
                _fmt(values["paired_utility"]["pmu_lambda_1_0"]),
            ]
        )
    classification_rows = []
    for model in order:
        values = models[model]
        classification_rows.append(
            [
                values["display_name"],
                _fmt(values["classification"]["atom_exact_accuracy"]),
                _fmt(values["classification"]["balanced_accuracy"]),
                _fmt(values["classification"]["macro_f1"]),
                _fmt(values["classification"]["multiclass_mcc"]),
                _fmt(values["classification"]["cohen_kappa"]),
                _fmt(values["classification"]["linear_weighted_kappa"]),
                _fmt(values["classification"]["quadratic_weighted_kappa"]),
                _fmt(values["classification"]["normalized_mutual_information"]),
                _fmt(values["classification"]["cramers_v"]),
                _fmt(values["classification"]["ordinal_rank_correlation"]),
            ]
        )
    ordinal_rows = []
    for model in order:
        values = models[model]
        ordinal_rows.append(
            [
                values["display_name"],
                _fmt(values["ordinal"]["ordinal_mae"]),
                _fmt(values["ordinal"]["ordinal_rmse"]),
                _fmt(values["ordinal"]["macro_normalized_linear_score"]),
                _fmt(values["ordinal"]["macro_normalized_quadratic_score"]),
                _fmt(values["ordinal"]["severe_two_step_atom_error_rate"]),
                _fmt(values["ordinal"]["overuse_quadratic_cost_rate"]),
                _fmt(values["ordinal"]["underuse_quadratic_cost_rate"]),
            ]
        )
    composite_rows = []
    for model in order:
        values = models[model]["composites"]
        composite_rows.append(
            [
                models[model]["display_name"],
                _fmt(values["harmonic_h"]),
                _fmt(values["arithmetic_resistance"]),
                _fmt(values["geometric_resistance"]),
                _fmt(values["product_resistance"]),
                _fmt(values["softmin_p_minus_2"]),
                _fmt(values["softmin_p_minus_4"]),
                _fmt(values["softmin_p_minus_8"]),
                _fmt(values["mincalib"]),
                _fmt(values["ideal_l2_score"]),
            ]
        )
    risk_rows = []
    for model in order:
        values = models[model]["sample_risk"]
        risk_rows.append(
            [
                models[model]["display_name"],
                _fmt(values["strict_sample_accuracy"]),
                _fmt(values["severe_two_step_sample_rate"]),
                _fmt(values["linear_loss"]["mean"]),
                _fmt(values["linear_loss"]["p90"]),
                _fmt(values["linear_loss"]["cvar90"]),
                _fmt(values["linear_loss"]["cvar95"]),
                _fmt(values["quadratic_loss"]["cvar90"]),
            ]
        )
    paired_rows = []
    for model in order:
        values = models[model]["paired_utility"]
        paired_rows.append(
            [
                models[model]["display_name"],
                _fmt(values["memory_induced_opb"]),
                _fmt(values["memory_reduced_upb"]),
                _fmt(values["pmu_lambda_0_5"]),
                _fmt(values["pmu_lambda_1_0"]),
                _fmt(values["pmu_lambda_2_0"]),
                _fmt(values["relative_pmu_lambda_1_0"]),
            ]
        )
    latent_rows = []
    for model in sorted(
        models,
        key=lambda item: models[item]["bradley_terry"]["ability"],
        reverse=True,
    ):
        values = models[model]
        latent_rows.append(
            [
                values["display_name"],
                _fmt(values["rasch_2d"]["over_theta"]),
                _fmt(values["rasch_2d"]["under_theta"]),
                _fmt(values["rasch_2d"]["mean_theta"]),
                _fmt(values["rasch_2d"]["min_theta"]),
                _fmt(values["bradley_terry"]["ability"]),
            ]
        )

    uncertainty_rows = []
    for model in order:
        intervals = models[model]["bootstrap_ci95"]

        def interval(key: str) -> str:
            values = intervals[key]
            return f"[{_fmt(values['ci_low'])}, {_fmt(values['ci_high'])}]"

        uncertainty_rows.append(
            [
                models[model]["display_name"],
                interval("H"),
                interval("MinCalib"),
                interval("multiclass_mcc"),
                interval("linear_weighted_kappa"),
                interval("strict_sample_accuracy"),
                interval("cvar90_linear_loss"),
                interval("pmu_lambda_1_0"),
            ]
        )

    win_share: dict[tuple[str, str], float] = {}
    for row in result["pairwise"]["comparisons"]:
        win_share[(row["left"], row["right"])] = row["left_win_share"]
        win_share[(row["right"], row["left"])] = 1 - row["left_win_share"]
    matrix_rows = []
    for left in order:
        matrix_rows.append(
            [models[left]["display_name"]]
            + [
                "—" if left == right else _fmt(win_share[(left, right)])
                for right in order
            ]
        )

    spread_rows = [
        [
            name,
            _fmt(values["minimum"]),
            _fmt(values["maximum"]),
            _fmt(values["range"]),
            _fmt(values["population_sd"]),
        ]
        for name, values in sorted(
            result["metric_spreads"].items(),
            key=lambda item: item[1]["range"],
            reverse=True,
        )
    ]
    pareto_names = [
        models[model]["display_name"] for model in result["pareto"]["pareto_front"]
    ]
    h_order = sorted(
        models,
        key=lambda model: models[model]["composites"]["harmonic_h"],
        reverse=True,
    )
    mean_loss_order = sorted(
        models,
        key=lambda model: models[model]["sample_risk"]["linear_loss"]["mean"],
    )
    cvar_order = sorted(
        models,
        key=lambda model: models[model]["sample_risk"]["linear_loss"]["cvar90"],
    )
    h_rank = {model: index for index, model in enumerate(h_order, start=1)}
    mean_loss_rank = {
        model: index for index, model in enumerate(mean_loss_order, start=1)
    }
    cvar_rank = {model: index for index, model in enumerate(cvar_order, start=1)}
    tail_rank_rows = [
        [
            models[model]["display_name"],
            str(h_rank[model]),
            str(mean_loss_rank[model]),
            str(cvar_rank[model]),
            _fmt(models[model]["sample_risk"]["linear_loss"]["cvar90"]),
        ]
        for model in order
    ]
    lines = [
        f"# {result.get('study', {}).get('title', DEFAULT_STUDY_TITLE)}",
        "",
        result.get("study", {}).get("description", DEFAULT_STUDY_DESCRIPTION),
        "",
        "## Headline comparison",
        "",
        _markdown_table(
            ["Model", "OPB↓", "UPB↓", "H↑", "MinCalib↑", "MCC↑", "Linear κ↑", "CVaR90↓", "PMU(1)↑"],
            overview_rows,
        ),
        "",
        "Numeric ranges across differently scaled metrics are not directly comparable. "
        "Use paired confidence intervals and ranking robustness, not range alone.",
        "",
        "## Classification and chance-corrected metrics",
        "",
        _markdown_table(
            [
                "Model",
                "Exact↑",
                "Balanced acc.↑",
                "Macro F1↑",
                "MCC↑",
                "κ↑",
                "Linear κ↑",
                "Quadratic κ↑",
                "NMI↑",
                "Cramér V↑",
                "Ordinal r↑",
            ],
            classification_rows,
        ),
        "",
        "## Ordinal severity metrics",
        "",
        _markdown_table(
            ["Model", "MAE↓", "RMSE↓", "Macro L1↑", "Macro L2↑", "A↔C atom rate↓", "Over quadratic cost↓", "Under quadratic cost↓"],
            ordinal_rows,
        ),
        "",
        "## Composite-score sensitivity",
        "",
        _markdown_table(
            ["Model", "H", "Arithmetic", "Geometric", "Product", "Softmin −2", "Softmin −4", "Softmin −8", "MinCalib", "Ideal L2"],
            composite_rows,
        ),
        "",
        "## Sample-level tail risk",
        "",
        _markdown_table(
            ["Model", "Strict sample↑", "Any A↔C sample↓", "Mean L1 loss↓", "P90↓", "CVaR90↓", "CVaR95↓", "Quadratic CVaR90↓"],
            risk_rows,
        ),
        "",
        "CVaR90 is the mean loss among the worst 10% of samples; CVaR95 uses the "
        "worst 5%. Sample loss is normalized absolute ordinal distance.",
        "",
        "### Why CVaR90 can reorder models",
        "",
        _markdown_table(
            ["Model", "H rank", "Mean L1 rank", "CVaR90 rank", "CVaR90↓"],
            tail_rank_rows,
        ),
        "",
        "For a full-memory sample `s` with `n_s` scorable atoms, "
        "`L_s = mean_i(|u_hat_si - u*_si| / 2)`. CVaR90 is the arithmetic "
        "mean of the largest 50 values of `L_s` among the locked 500 samples. "
        "It therefore changes both the aggregation unit (sample rather than "
        "gold-label macro average) and the evaluated population (only the "
        "worst decile).",
        "",
        "A model can make moderately sized errors across many samples and have "
        "worse H or mean loss but a less extreme worst decile. Conversely, "
        "errors concentrated within a smaller set of samples increase CVaR90. "
        "The ordering difference is expected and is not an arithmetic "
        "inconsistency.",
        "",
        "[Open the tail, Pareto, and metric-rank diagnostics]"
        "(candidate-metric-diagnostics.html).",
        "",
        "## Paired memory utility",
        "",
        _markdown_table(
            ["Model", "Induced OPB↓", "Reduced UPB↑", "PMU(0.5)↑", "PMU(1)↑", "PMU(2)↑", "Relative PMU(1)↑"],
            paired_rows,
        ),
        "",
        "`PMU(λ) = reduced_UPB - λ × induced_OPB`. Its ranking is a policy choice, "
        "so the weight sensitivity must remain visible.",
        "",
        "## Latent and pairwise models",
        "",
        _markdown_table(
            ["Model", "Rasch over θ↑", "Rasch under θ↑", "Mean θ↑", "Min θ↑", "Bradley–Terry ability↑"],
            latent_rows,
        ),
        "",
        "The two Rasch dimensions adjust separately for atom difficulty. The current "
        "1PL fit is exploratory: standard errors condition on estimated item "
        "difficulties and are not a full Bayesian uncertainty estimate.",
        "",
        "## Pairwise win-share matrix",
        "",
        "Rows are the candidate model; each cell is its win share against the column "
        "model using full-memory normalized sample-level ordinal loss. Ties count 0.5.",
        "",
        _markdown_table(
            ["Model"] + [models[model]["display_name"] for model in order],
            matrix_rows,
        ),
        "",
        "## Pareto analysis",
        "",
        "Non-dominated OPB–UPB models: " + ", ".join(pareto_names) + ".",
        "",
        "## Observed metric spread",
        "",
        _markdown_table(
            ["Metric", "Minimum", "Maximum", "Range", "Population SD"],
            spread_rows,
        ),
        "",
        "## Sample-cluster bootstrap uncertainty",
        "",
        _markdown_table(
            [
                "Model",
                "H 95% CI",
                "MinCalib 95% CI",
                "MCC 95% CI",
                "Linear κ 95% CI",
                "Strict sample 95% CI",
                "CVaR90 95% CI",
                "PMU(1) 95% CI",
            ],
            uncertainty_rows,
            align_right_from=1,
        ),
        "",
        "All intervals resample the same 500 sample IDs as clusters and preserve "
        "their full/no-memory atom groups.",
        "",
        "## Interpretation boundary",
        "",
        "- MCC, Kappa, NMI, and ordinal correlation discard the over-use versus "
        "under-use direction even when they improve numerical separation.",
        "- Product and power-mean scores partly enlarge the numeric range through "
        "rescaling; this does not create new statistical evidence.",
        "- PMU depends on the full/no-memory causal contrast and on λ.",
        "- CVaR exposes tail failures but should not replace average performance.",
        "- Brier score, log loss, and ordinal CRPS are not validly computable without "
        "a probability distribution over A/B/C.",
        "- Pairwise bootstrap intervals and blinded human validation remain necessary "
        "before making significance or external leaderboard claims.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", type=Path, default=DEFAULT_PRIMARY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--official-metrics", type=Path, default=DEFAULT_OFFICIAL_METRICS)
    parser.add_argument("--bootstrap-replicates", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260720)
    parser.add_argument("--study-title", default=DEFAULT_STUDY_TITLE)
    parser.add_argument("--study-description", default=DEFAULT_STUDY_DESCRIPTION)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = list(iter_jsonl(args.primary))
    result = compute_candidate_metrics(
        rows,
        bootstrap_replicates=args.bootstrap_replicates,
        seed=args.seed,
    )
    result["study"] = {
        "title": args.study_title,
        "description": args.study_description,
    }
    result["source"]["primary_judgments"] = (
        str(args.primary.resolve().relative_to(ROOT))
        if args.primary.resolve().is_relative_to(ROOT)
        else str(args.primary.resolve())
    )
    result["source"]["primary_sha256"] = _sha256(args.primary)
    official_metrics = args.official_metrics.resolve()
    if official_metrics.is_file():
        result["source"]["official_metrics"] = (
            str(official_metrics.relative_to(ROOT))
            if official_metrics.is_relative_to(ROOT)
            else str(official_metrics)
        )
        result["source"]["official_metrics_sha256"] = _sha256(official_metrics)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "candidate-metrics.json", result)
    _write_csv(result, args.output_dir / "candidate-metrics.csv")
    _write_markdown(result, args.output_dir / "README.md")
    artifact_paths = [
        args.output_dir / "README.md",
        args.output_dir / "candidate-metrics.csv",
        args.output_dir / "candidate-metrics.json",
    ]
    write_json(
        args.output_dir / "analysis-manifest.json",
        {
            "schema_version": "memcalib-candidate-metrics-analysis-manifest-v1",
            "source": result["source"],
            "input_integrity": result["input_integrity"],
            "script": {
                "path": str(Path(__file__).resolve().relative_to(ROOT)),
                "sha256": _sha256(Path(__file__)),
            },
            "artifacts": {
                path.name: {
                    "bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
                for path in artifact_paths
            },
        },
    )
    print(
        json.dumps(
            {
                "rows": len(rows),
                "models": len(result["models"]),
                "pairwise_comparisons": len(result["pairwise"]["comparisons"]),
                "pareto_front": result["pareto"]["pareto_front"],
                "overuse_rasch_converged": result["rasch_2d"][
                    "overuse_resistance"
                ]["converged"],
                "underuse_rasch_converged": result["rasch_2d"][
                    "underuse_resistance"
                ]["converged"],
                "output_dir": str(args.output_dir),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
