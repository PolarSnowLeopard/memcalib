#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean, median, pstdev
from typing import Any, Iterable

from evaluation.common import iter_jsonl, write_json


ROOT = Path(__file__).resolve().parents[2]
RANK = {"A": 0, "B": 1, "C": 2}
MODEL_DISPLAY_NAMES = {
    "claude-opus-5": "Claude Opus 5",
    "claude-sonnet-4-6": "Claude Sonnet 4.6",
    "codex-gpt56-sol": "Codex GPT-5.6 Sol",
    "deepseek": "DeepSeek-V4-Pro",
    "deepseek-flash": "DeepSeek-V4-Flash",
    "deepseek-flash-0731": "DeepSeek-V4-Flash-0731",
    "glm52": "GLM-5.2",
    "gemini35-flash": "Gemini 3.5 Flash",
    "gpt56-sol": "GPT-5.6-SOL",
    "grok-4": "Grok 4",
    "kimi": "Kimi-K2.6",
    "kimi-k26": "Kimi-K2.6",
    "qwen-flash": "Qwen3.6-Flash",
    "qwen-max": "Qwen3.7-Max",
    "qwen38-max": "Qwen3.8-Max",
    "qwen3-8b": "Qwen3-8B",
    "qwen35-35b-a3b": "Qwen3.5-35B-A3B",
    "qwen35-a3b-base-vllm": "Qwen3.5-35B-A3B Base",
    "qwen35-a3b-sft-vllm": "Qwen3.5-35B-A3B SFT",
}


def percentile(values: list[float], quantile: float) -> float:
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


def rho_key(rho: float) -> str:
    return str(rho).replace(".", "_")


def harmonic_resistance(opb: float, upb: float) -> float:
    over_resistance = 1 - opb
    under_resistance = 1 - upb
    denominator = over_resistance + under_resistance
    return (
        2 * over_resistance * under_resistance / denominator
        if denominator
        else 0.0
    )


def score_judgment_row(
    row: dict[str, Any],
    *,
    mode: str,
    metadata: dict[str, dict[str, Any]],
    rhos: Iterable[float],
) -> dict[str, Any]:
    sample_id = str(row["sample_id"])
    if sample_id not in metadata:
        raise ValueError(f"missing sample metadata: {sample_id}")
    atom_count = 0
    over_budget = 0
    under_budget = 0
    severe_two_step = False
    for atom in row["atom_judgments"]:
        if not atom.get("scorable", True):
            continue
        gold = atom.get("u_star")
        predicted = atom.get("predicted_usage_level")
        if gold not in RANK or predicted not in RANK:
            raise ValueError(
                f"{row['answer_request_id']}: invalid scorable usage pair {gold!r}, {predicted!r}"
            )
        delta = RANK[str(predicted)] - RANK[str(gold)]
        over_budget += max(delta, 0)
        under_budget += max(-delta, 0)
        severe_two_step = severe_two_step or abs(delta) == 2
        atom_count += 1
    if not atom_count:
        raise ValueError(f"{row['answer_request_id']}: no scorable atoms")
    total_budget = over_budget + under_budget
    result = {
        "mode": mode,
        "model_key": str(row["model_key"]),
        "condition": str(row["condition"]),
        "answer_request_id": str(row["answer_request_id"]),
        "sample_id": sample_id,
        "domain": metadata[sample_id]["domain"],
        "difficulty": metadata[sample_id]["difficulty"],
        "atom_count": atom_count,
        "over_budget": over_budget,
        "under_budget": under_budget,
        "total_budget": total_budget,
        "sample_any_opb": int(over_budget > 0),
        "sample_any_upb": int(under_budget > 0),
        "sample_any_error": int(total_budget > 0),
        "sample_exact": int(total_budget == 0),
        "severe_two_step": int(severe_two_step),
    }
    for rho in rhos:
        result[f"scs_rho_{rho_key(rho)}"] = rho**total_budget
    return result


def budget_distribution(values: list[int]) -> dict[str, dict[str, float | int]]:
    counts = Counter("5_plus" if value >= 5 else str(value) for value in values)
    total = len(values)
    return {
        key: {"count": counts[key], "share": counts[key] / total}
        for key in ("0", "1", "2", "3", "4", "5_plus")
    }


def headline_metrics(rows: list[dict[str, Any]], rho: float) -> dict[str, float]:
    if not rows:
        raise ValueError("cannot summarize empty sample-score rows")
    rho_suffix = rho_key(rho)
    scs = fmean(float(row[f"scs_rho_{rho_suffix}"]) for row in rows)
    directional_opb = fmean(
        1 - rho ** int(row["over_budget"]) for row in rows
    )
    directional_upb = fmean(
        1 - rho ** int(row["under_budget"]) for row in rows
    )
    any_opb = fmean(int(row["sample_any_opb"]) for row in rows)
    any_upb = fmean(int(row["sample_any_upb"]) for row in rows)
    return {
        "scs": scs,
        "directional_opb": directional_opb,
        "directional_upb": directional_upb,
        "directional_h": harmonic_resistance(directional_opb, directional_upb),
        "any_opb": any_opb,
        "any_upb": any_upb,
        "any_h": harmonic_resistance(any_opb, any_upb),
        "exact": fmean(int(row["sample_exact"]) for row in rows),
    }


def bootstrap_headline_metrics(
    rows: list[dict[str, Any]],
    *,
    rho: float,
    replicates: int,
    seed: int,
) -> dict[str, dict[str, float | int]]:
    estimates = headline_metrics(rows, rho)
    if replicates <= 0:
        return {
            key: {
                "estimate": value,
                "ci_low": value,
                "ci_high": value,
                "replicates": 0,
                "clusters": len(rows),
            }
            for key, value in estimates.items()
        }
    rng = random.Random(seed)
    metric_samples: dict[str, list[float]] = {
        key: [] for key in estimates
    }
    row_count = len(rows)
    for _ in range(replicates):
        sampled = [rows[rng.randrange(row_count)] for _ in range(row_count)]
        values = headline_metrics(sampled, rho)
        for key, value in values.items():
            metric_samples[key].append(value)
    return {
        key: {
            "estimate": estimate,
            "ci_low": percentile(metric_samples[key], 0.025),
            "ci_high": percentile(metric_samples[key], 0.975),
            "replicates": replicates,
            "clusters": row_count,
        }
        for key, estimate in estimates.items()
    }


def summarize_scores(
    rows: list[dict[str, Any]],
    rhos: Iterable[float],
    *,
    bootstrap_replicates: int = 0,
    bootstrap_seed: int = 0,
) -> dict[str, Any]:
    if not rows:
        raise ValueError("cannot summarize empty sample-score rows")
    result: dict[str, Any] = {
        "samples": len(rows),
        "atoms": sum(int(row["atom_count"]) for row in rows),
        "mean_atoms_per_sample": fmean(int(row["atom_count"]) for row in rows),
        "sample_any_opb_rate": fmean(int(row["sample_any_opb"]) for row in rows),
        "sample_any_upb_rate": fmean(int(row["sample_any_upb"]) for row in rows),
        "sample_any_error_rate": fmean(int(row["sample_any_error"]) for row in rows),
        "sample_exact_accuracy": fmean(int(row["sample_exact"]) for row in rows),
        "severe_two_step_sample_rate": fmean(int(row["severe_two_step"]) for row in rows),
        "mean_over_budget": fmean(int(row["over_budget"]) for row in rows),
        "mean_under_budget": fmean(int(row["under_budget"]) for row in rows),
        "mean_total_budget": fmean(int(row["total_budget"]) for row in rows),
        "total_budget_distribution": budget_distribution(
            [int(row["total_budget"]) for row in rows]
        ),
        "scs": {},
        "directional_risk": {},
    }
    for rho in rhos:
        key = f"scs_rho_{rho_key(rho)}"
        values = [float(row[key]) for row in rows]
        result["scs"][str(rho)] = {
            "mean": fmean(values),
            "population_sd": pstdev(values),
            "minimum": min(values),
            "p10": percentile(values, 0.10),
            "p25": percentile(values, 0.25),
            "median": median(values),
            "p75": percentile(values, 0.75),
            "p90": percentile(values, 0.90),
            "maximum": max(values),
        }
        opb = fmean(
            1 - rho ** int(row["over_budget"]) for row in rows
        )
        upb = fmean(
            1 - rho ** int(row["under_budget"]) for row in rows
        )
        result["directional_risk"][str(rho)] = {
            "opb": opb,
            "upb": upb,
            "harmonic": harmonic_resistance(opb, upb),
        }
    event_opb = float(result["sample_any_opb_rate"])
    event_upb = float(result["sample_any_upb_rate"])
    result["event_guardrail"] = {
        "opb": event_opb,
        "upb": event_upb,
        "harmonic": harmonic_resistance(event_opb, event_upb),
    }
    if bootstrap_replicates:
        result["headline_bootstrap_95_ci"] = bootstrap_headline_metrics(
            rows,
            rho=0.5,
            replicates=bootstrap_replicates,
            seed=bootstrap_seed,
        )
    return result


def summarize_breakdown(
    rows: list[dict[str, Any]], field: str, rhos: Iterable[float]
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[field])].append(row)
    return {
        key: summarize_scores(values, rhos)
        for key, values in sorted(grouped.items())
    }


def validate_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    answer_ids: set[tuple[str, str]] = set()
    for row in rows:
        answer_id = (str(row["mode"]), str(row["answer_request_id"]))
        if answer_id in answer_ids:
            raise ValueError(f"duplicate mode/answer_request_id: {answer_id}")
        answer_ids.add(answer_id)
        buckets[(str(row["mode"]), str(row["model_key"]), str(row["condition"]))].add(
            str(row["sample_id"])
        )
    sample_sets = list(buckets.values())
    if not sample_sets or any(values != sample_sets[0] for values in sample_sets[1:]):
        raise ValueError("mode/model/condition buckets do not use identical sample IDs")
    return {
        "sample_score_rows": len(rows),
        "unique_answer_request_ids": len(answer_ids),
        "buckets": len(buckets),
        "samples_per_bucket": len(sample_sets[0]),
        "common_sample_ids": len(sample_sets[0]),
    }


def compute_analysis(
    rows: list[dict[str, Any]],
    rhos: tuple[float, ...],
    *,
    bootstrap_replicates: int = 0,
) -> dict[str, Any]:
    models = sorted({str(row["model_key"]) for row in rows})
    modes = sorted({str(row["mode"]) for row in rows})
    conditions = sorted({str(row["condition"]) for row in rows})
    result: dict[str, Any] = {
        "schema_version": "memcalib-sample-level-calibration-v2",
        "definition": {
            "rank": RANK,
            "over_budget": "sum(max(rank(predicted)-rank(gold), 0)) within one answer",
            "under_budget": "sum(max(rank(gold)-rank(predicted), 0)) within one answer",
            "sample_any_opb": "1 if over_budget > 0 else 0",
            "sample_any_upb": "1 if under_budget > 0 else 0",
            "sample_exact": "1 if over_budget + under_budget == 0 else 0",
            "scs_rho": "rho ** (over_budget + under_budget)",
            "sample_directional_opb_risk": "1 - rho ** over_budget",
            "sample_directional_upb_risk": "1 - rho ** under_budget",
            "directional_aggregation": "arithmetic mean of sample directional risks",
            "event_guardrail": "arithmetic mean of 1[directional budget > 0]",
            "directional_harmonic": "harmonic mean of (1 - OPB) and (1 - UPB)",
            "aggregation": "arithmetic mean over samples; every sample has equal model-level weight",
            "rhos": list(rhos),
            "primary_rho": 0.5,
            "bootstrap_replicates": bootstrap_replicates,
        },
        "input_integrity": validate_coverage(rows),
        "modes": {},
    }
    for mode in modes:
        result["modes"][mode] = {"models": {}}
        for model in models:
            model_rows = [
                row for row in rows if row["mode"] == mode and row["model_key"] == model
            ]
            conditions_result = {}
            for condition in conditions:
                condition_rows = [
                    row for row in model_rows if row["condition"] == condition
                ]
                seed_material = f"{mode}\0{model}\0{condition}".encode("utf-8")
                bootstrap_seed = int.from_bytes(
                    hashlib.sha256(seed_material).digest()[:8], "big"
                )
                conditions_result[condition] = {
                    "overall": summarize_scores(
                        condition_rows,
                        rhos,
                        bootstrap_replicates=bootstrap_replicates,
                        bootstrap_seed=bootstrap_seed,
                    ),
                    "by_domain": summarize_breakdown(condition_rows, "domain", rhos),
                    "by_difficulty": summarize_breakdown(
                        condition_rows, "difficulty", rhos
                    ),
                }
            result["modes"][mode]["models"][model] = {
                "display_name": MODEL_DISPLAY_NAMES.get(model, model),
                "conditions": conditions_result,
            }
    return result


def fmt(value: float) -> str:
    return f"{value:.3f}"


def fmt_pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def fmt_pp(value: float) -> str:
    return f"{100 * value:+.1f} pp"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---:" if i else "---" for i in range(len(headers))) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def render_readme(analysis: dict[str, Any], *, study_title: str) -> str:
    sections = [
        f"# {study_title}",
        "",
        "This analysis reuses the completed primary-Judge outputs. It makes no new model or Judge calls.",
        "The public evaluation uses three complementary layers at the answer-sample level:",
        "",
        "1. **Overall primary:** `SCS_0.5(s) = 0.5 ** (over_budget(s) + under_budget(s))`.",
        "2. **Directional primary:** `sOPB_0.5(s) = 1 - 0.5 ** over_budget(s)` and",
        "   `sUPB_0.5(s) = 1 - 0.5 ** under_budget(s)`.",
        "3. **Event guardrails:** `Any-OPB = 1[over_budget(s) > 0]` and",
        "   `Any-UPB = 1[under_budget(s) > 0]`.",
        "",
        "A one-step A/B/C error adds one budget unit; an A-to-C or C-to-A error adds two. All model-level",
        "values are arithmetic means over samples, so each answer has equal weight. Directional primary",
        "metrics preserve the number and severity of errors without growing unbounded; event guardrails",
        "only answer whether a direction occurred at least once and therefore must not be used alone.",
    ]
    mode_order = [mode for mode in ("thinking", "nonthinking") if mode in analysis["modes"]]
    mode_order.extend(mode for mode in sorted(analysis["modes"]) if mode not in mode_order)
    for mode in mode_order:
        models = analysis["modes"][mode]["models"]
        ordered = sorted(
            models,
            key=lambda key: models[key]["conditions"]["full_memory"]["overall"]["scs"]["0.5"]["mean"],
            reverse=True,
        )
        rows = []
        for model in ordered:
            values = models[model]["conditions"]["full_memory"]["overall"]
            directional = values["directional_risk"]["0.5"]
            event = values["event_guardrail"]
            rows.append(
                [
                    models[model]["display_name"],
                    fmt_pct(values["scs"]["0.5"]["mean"]),
                    fmt_pct(directional["opb"]),
                    fmt_pct(directional["upb"]),
                    fmt_pct(directional["harmonic"]),
                    fmt_pct(event["opb"]),
                    fmt_pct(event["upb"]),
                    fmt_pct(event["harmonic"]),
                    fmt_pct(values["sample_exact_accuracy"]),
                ]
            )
        sections.extend(
            [
                "",
                f"## {mode}: three-layer full-memory results",
                "",
                markdown_table(
                    [
                        "Model",
                        "SCS(0.5) up",
                        "sOPB(0.5) down",
                        "sUPB(0.5) down",
                        "Directional H up",
                        "Any OPB down",
                        "Any UPB down",
                        "Event H up",
                        "Exact up",
                    ],
                    rows,
                ),
            ]
        )

        bootstrap_rows = []
        budget_rows = []
        for model in ordered:
            values = models[model]["conditions"]["full_memory"]["overall"]
            intervals = values["headline_bootstrap_95_ci"]
            dist = values["total_budget_distribution"]
            bootstrap_rows.append(
                [
                    models[model]["display_name"],
                    f"[{fmt_pct(intervals['scs']['ci_low'])}, {fmt_pct(intervals['scs']['ci_high'])}]",
                    f"[{fmt_pct(intervals['directional_opb']['ci_low'])}, {fmt_pct(intervals['directional_opb']['ci_high'])}]",
                    f"[{fmt_pct(intervals['directional_upb']['ci_low'])}, {fmt_pct(intervals['directional_upb']['ci_high'])}]",
                    f"[{fmt_pct(intervals['any_opb']['ci_low'])}, {fmt_pct(intervals['any_opb']['ci_high'])}]",
                    f"[{fmt_pct(intervals['any_upb']['ci_low'])}, {fmt_pct(intervals['any_upb']['ci_high'])}]",
                ]
            )
            budget_rows.append(
                [
                    models[model]["display_name"],
                    fmt(values["mean_total_budget"]),
                    fmt_pct(dist["0"]["share"]),
                    fmt_pct(dist["1"]["share"]),
                    fmt_pct(dist["2"]["share"]),
                    fmt_pct(dist["3"]["share"]),
                    fmt_pct(dist["4"]["share"]),
                    fmt_pct(dist["5_plus"]["share"]),
                ]
            )
        sections.extend(
            [
                "",
                f"### {mode}: sample-bootstrap 95% intervals",
                "",
                markdown_table(
                    [
                        "Model",
                        "SCS",
                        "sOPB",
                        "sUPB",
                        "Any OPB",
                        "Any UPB",
                    ],
                    bootstrap_rows,
                ),
                "",
                f"### {mode}: total error-budget distribution",
                "",
                markdown_table(
                    ["Model", "Mean", "B=0", "B=1", "B=2", "B=3", "B=4", "B>=5"],
                    budget_rows,
                ),
            ]
        )

        sensitivity_rows = []
        for model in ordered:
            values = models[model]["conditions"]["full_memory"]["overall"]
            sensitivity_rows.append(
                [
                    models[model]["display_name"],
                    fmt_pct(values["scs"]["0.25"]["mean"]),
                    fmt_pct(values["scs"]["0.5"]["mean"]),
                    fmt_pct(values["scs"]["0.75"]["mean"]),
                    f"[{fmt_pct(values['scs']['0.5']['p10'])}, {fmt_pct(values['scs']['0.5']['p90'])}]",
                ]
            )
        sections.extend(
            [
                "",
                f"### {mode}: rho sensitivity and within-model spread",
                "",
                markdown_table(
                    ["Model", "SCS(0.25)", "SCS(0.5)", "SCS(0.75)", "SCS(0.5) P10-P90"],
                    sensitivity_rows,
                ),
            ]
        )

        difficulty_rows = []
        for model in ordered:
            by_level = models[model]["conditions"]["full_memory"]["by_difficulty"]
            difficulty_rows.append(
                [
                    models[model]["display_name"],
                    fmt_pct(by_level["level_1"]["scs"]["0.5"]["mean"]),
                    fmt_pct(by_level["level_2"]["scs"]["0.5"]["mean"]),
                    fmt_pct(by_level["level_3"]["scs"]["0.5"]["mean"]),
                ]
            )
        sections.extend(
            [
                "",
                f"### {mode}: SCS(0.5) by memory-load level",
                "",
                markdown_table(["Model", "Level 1", "Level 2", "Level 3"], difficulty_rows),
            ]
        )
    if {"thinking", "nonthinking"}.issubset(analysis["modes"]):
        thinking = analysis["modes"]["thinking"]["models"]
        nonthinking = analysis["modes"]["nonthinking"]["models"]
        ordered = sorted(
            thinking,
            key=lambda key: thinking[key]["conditions"]["full_memory"]["overall"]["scs"]["0.5"]["mean"],
            reverse=True,
        )
        comparison_rows = []
        for model in ordered:
            think = thinking[model]["conditions"]["full_memory"]["overall"]
            non = nonthinking[model]["conditions"]["full_memory"]["overall"]
            think_scs = think["scs"]["0.5"]["mean"]
            non_scs = non["scs"]["0.5"]["mean"]
            comparison_rows.append(
                [
                    thinking[model]["display_name"],
                    fmt_pct(non_scs),
                    fmt_pct(think_scs),
                    fmt_pp(think_scs - non_scs),
                    fmt_pp(
                        think["directional_risk"]["0.5"]["opb"]
                        - non["directional_risk"]["0.5"]["opb"]
                    ),
                    fmt_pp(
                        think["directional_risk"]["0.5"]["upb"]
                        - non["directional_risk"]["0.5"]["upb"]
                    ),
                    fmt_pp(
                        think["event_guardrail"]["opb"]
                        - non["event_guardrail"]["opb"]
                    ),
                    fmt_pp(
                        think["event_guardrail"]["upb"]
                        - non["event_guardrail"]["upb"]
                    ),
                    fmt_pp(
                        think["sample_exact_accuracy"]
                        - non["sample_exact_accuracy"]
                    ),
                ]
            )
        sections.extend(
            [
                "",
                "## Thinking minus non-thinking on identical samples",
                "",
                markdown_table(
                    [
                        "Model",
                        "SCS non-think",
                        "SCS think",
                        "Delta SCS",
                        "Delta sOPB",
                        "Delta sUPB",
                        "Delta Any OPB",
                        "Delta Any UPB",
                        "Delta Exact",
                    ],
                    comparison_rows,
                ),
                "",
                "Negative deltas are improvements for sOPB/sUPB and Any OPB/UPB; positive deltas are",
                "improvements for SCS/Exact.",
                "Codex reuses identical answers and therefore remains a repeated-Judge control rather than an answer-mode effect.",
            ]
        )
    sections.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `SCS(0.5)` is the overall primary metric. It compounds over-use and under-use budgets within each",
            "  answer, then gives each answer one equal model-level vote.",
            "- `sOPB(0.5)` and `sUPB(0.5)` are the directional primary metrics. They distinguish one directional",
            "  error from repeated or severe errors but asymptotically cap each sample at 1.",
            "- `Any OPB` and `Any UPB` are event-rate guardrails. They reveal how widely errors are distributed",
            "  across samples, but deliberately collapse one and many errors to the same event.",
            "- `Directional H` and `Event H` summarize their paired resistance terms, but neither should replace",
            "  the two directional columns in reporting.",
            "- `Exact` is the share of answers with no scorable atom error and is the hardest event endpoint.",
            "- `rho` is a policy parameter. It is fixed before interpretation, and the sensitivity table remains",
            "  part of the release rather than selecting the value that creates the preferred ranking.",
            "",
            "## Files",
            "",
            "- `sample-level-metrics.json`: aggregate metrics and domain/difficulty breakdowns.",
            "- `sample-level-scores.csv`: one row per mode/model/condition/sample.",
            "- `sample-level-score-distributions.html`: visual error-budget distributions.",
            "- `analysis-manifest.json`: source and output hashes.",
            "",
        ]
    )
    return "\n".join(sections)


def html_table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{html.escape(value)}</th>" for value in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(value)}</td>" for value in row) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render_html(analysis: dict[str, Any], *, study_title: str) -> str:
    colors = {
        "0": "#1b7f5a",
        "1": "#70a36b",
        "2": "#d2aa48",
        "3": "#df7b3f",
        "4": "#c74b4b",
        "5_plus": "#792f45",
    }
    content = []
    mode_order = [mode for mode in ("thinking", "nonthinking") if mode in analysis["modes"]]
    mode_order.extend(mode for mode in sorted(analysis["modes"]) if mode not in mode_order)
    for mode in mode_order:
        models = analysis["modes"][mode]["models"]
        ordered = sorted(
            models,
            key=lambda key: models[key]["conditions"]["full_memory"]["overall"]["scs"]["0.5"]["mean"],
            reverse=True,
        )
        bars = []
        table_rows = []
        for model in ordered:
            overall = models[model]["conditions"]["full_memory"]["overall"]
            dist = overall["total_budget_distribution"]
            segments = "".join(
                f'<span style="width:{100 * dist[key]["share"]:.4f}%;background:{colors[key]}" '
                f'title="budget {key}: {100 * dist[key]["share"]:.1f}%"></span>'
                for key in ("0", "1", "2", "3", "4", "5_plus")
            )
            bars.append(
                f'<div class="bar-row"><strong>{html.escape(models[model]["display_name"])}</strong>'
                f'<div class="bar">{segments}</div><b>{fmt_pct(overall["scs"]["0.5"]["mean"])}</b></div>'
            )
            table_rows.append(
                [
                    models[model]["display_name"],
                    fmt_pct(overall["scs"]["0.5"]["mean"]),
                    fmt_pct(overall["directional_risk"]["0.5"]["opb"]),
                    fmt_pct(overall["directional_risk"]["0.5"]["upb"]),
                    fmt_pct(overall["directional_risk"]["0.5"]["harmonic"]),
                    fmt_pct(overall["event_guardrail"]["opb"]),
                    fmt_pct(overall["event_guardrail"]["upb"]),
                    fmt_pct(overall["event_guardrail"]["harmonic"]),
                    fmt_pct(overall["sample_exact_accuracy"]),
                ]
            )
        content.append(
            f"<section><h2>{html.escape(mode)} full-memory</h2>"
            '<p class="note">Stacked bars show total error-budget bins: '
            '<i style="background:#1b7f5a"></i>0, <i style="background:#70a36b"></i>1, '
            '<i style="background:#d2aa48"></i>2, <i style="background:#df7b3f"></i>3, '
            '<i style="background:#c74b4b"></i>4, <i style="background:#792f45"></i>5+. '
            "The number at right is mean SCS(0.5).</p>"
            + "".join(bars)
            + html_table(
                [
                    "Model",
                    "SCS(0.5)",
                    "sOPB(0.5)",
                    "sUPB(0.5)",
                    "Directional H",
                    "Any OPB",
                    "Any UPB",
                    "Event H",
                    "Exact",
                ],
                table_rows,
            )
            + "</section>"
        )
    escaped_title = html.escape(study_title)
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>""" + escaped_title + """</title>
<style>
:root{--ink:#15202b;--muted:#5c6875;--line:#d8dee5;--paper:#f5f7f8;--panel:#fff}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 Arial,sans-serif}
header,main{max-width:1160px;margin:auto;padding:24px}header{padding-top:38px;padding-bottom:10px}
h1{font-size:31px;margin:0 0 8px}h2{font-size:22px;margin:0 0 8px;letter-spacing:0}
p{color:var(--muted);max-width:900px}section{background:var(--panel);border:1px solid var(--line);border-radius:7px;padding:24px;margin:18px 0}
.note i{display:inline-block;width:13px;height:13px;vertical-align:-2px;margin-left:5px;border-radius:2px}
.bar-row{display:grid;grid-template-columns:190px minmax(260px,1fr) 58px;gap:12px;align-items:center;margin:11px 0}
.bar-row strong{font-size:13px}.bar-row b{text-align:right;font-variant-numeric:tabular-nums}.bar{height:22px;display:flex;overflow:hidden;border-radius:3px;background:#edf0f2}.bar span{height:100%;display:block}
table{width:100%;border-collapse:collapse;margin-top:24px;font-size:13px}th,td{padding:9px 10px;border-bottom:1px solid var(--line);text-align:right;font-variant-numeric:tabular-nums}th:first-child,td:first-child{text-align:left}
@media(max-width:700px){.bar-row{grid-template-columns:125px minmax(120px,1fr) 46px}header,main{padding:16px}section{padding:16px;overflow-x:auto}}
</style></head><body><header><h1>""" + escaped_title + """</h1>
<p>Existing primary-Judge outputs only. Overall SCS, exponential directional OPB/UPB, and Any-event guardrails are all averaged with equal sample weight.</p>
</header><main>""" + "".join(content) + "</main></body></html>"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_labeled_path(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("expected LABEL=PATH")
    label, raw_path = value.split("=", 1)
    if not label or not raw_path:
        raise argparse.ArgumentTypeError("expected nonempty LABEL=PATH")
    return label, Path(raw_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute sample-level MemCalib calibration distributions.")
    parser.add_argument("--judgments", action="append", type=parse_labeled_path, required=True)
    parser.add_argument("--hidden", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--rhos", nargs="+", type=float, default=[0.25, 0.5, 0.75])
    parser.add_argument("--bootstrap-replicates", type=int, default=2000)
    parser.add_argument(
        "--study-title",
        default="MemCalib v2.3 three-layer sample-level metrics",
    )
    args = parser.parse_args()
    rhos = tuple(sorted(set(args.rhos)))
    if not rhos or any(not 0 < rho < 1 for rho in rhos) or 0.5 not in rhos:
        raise ValueError("rhos must be in (0, 1) and include 0.5")

    hidden_rows = list(iter_jsonl(args.hidden))
    metadata = {
        str(row["id"]): {
            "domain": str(row["domain"]),
            "difficulty": str(row["composite_block_revision"]["difficulty_level"]),
        }
        for row in hidden_rows
    }
    if len(metadata) != len(hidden_rows):
        raise ValueError("hidden sample IDs must be unique")

    sample_rows = []
    source_manifest = {}
    for mode, path in args.judgments:
        judgments = list(iter_jsonl(path))
        source_manifest[mode] = {
            "path": str(path),
            "sha256": sha256_file(path),
            "rows": len(judgments),
        }
        sample_rows.extend(
            score_judgment_row(row, mode=mode, metadata=metadata, rhos=rhos)
            for row in judgments
        )
    analysis = compute_analysis(
        sample_rows,
        rhos,
        bootstrap_replicates=args.bootstrap_replicates,
    )
    analysis["sources"] = {
        "hidden": {
            "path": str(args.hidden),
            "sha256": sha256_file(args.hidden),
            "rows": len(hidden_rows),
        },
        "judgments": source_manifest,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = args.output_dir / "sample-level-metrics.json"
    scores_path = args.output_dir / "sample-level-scores.csv"
    readme_path = args.output_dir / "README.md"
    html_path = args.output_dir / "sample-level-score-distributions.html"
    manifest_path = args.output_dir / "analysis-manifest.json"
    write_json(metrics_path, analysis)
    fieldnames = list(sample_rows[0])
    with scores_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(sample_rows)
    readme_path.write_text(
        render_readme(analysis, study_title=args.study_title),
        encoding="utf-8",
    )
    html_path.write_text(
        render_html(analysis, study_title=args.study_title),
        encoding="utf-8",
    )
    output_files = [metrics_path, scores_path, readme_path, html_path]
    manifest = {
        "schema_version": "memcalib-sample-level-calibration-manifest-v2",
        "sources": analysis["sources"],
        "outputs": {
            path.name: {"sha256": sha256_file(path), "bytes": path.stat().st_size}
            for path in output_files
        },
    }
    write_json(manifest_path, manifest)
    print(json.dumps(analysis["input_integrity"], indent=2))
    print(f"wrote {args.output_dir}")


if __name__ == "__main__":
    main()
