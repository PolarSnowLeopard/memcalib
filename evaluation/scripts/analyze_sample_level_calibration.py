#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean, median, pstdev
from typing import Any, Iterable

from evaluation.common import iter_jsonl, write_json


ROOT = Path(__file__).resolve().parents[2]
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


def summarize_scores(rows: list[dict[str, Any]], rhos: Iterable[float]) -> dict[str, Any]:
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
    rows: list[dict[str, Any]], rhos: tuple[float, ...]
) -> dict[str, Any]:
    models = sorted({str(row["model_key"]) for row in rows})
    modes = sorted({str(row["mode"]) for row in rows})
    conditions = sorted({str(row["condition"]) for row in rows})
    result: dict[str, Any] = {
        "schema_version": "memcalib-sample-level-calibration-v1",
        "definition": {
            "rank": RANK,
            "over_budget": "sum(max(rank(predicted)-rank(gold), 0)) within one answer",
            "under_budget": "sum(max(rank(gold)-rank(predicted), 0)) within one answer",
            "sample_any_opb": "1 if over_budget > 0 else 0",
            "sample_any_upb": "1 if under_budget > 0 else 0",
            "sample_exact": "1 if over_budget + under_budget == 0 else 0",
            "scs_rho": "rho ** (over_budget + under_budget)",
            "aggregation": "arithmetic mean over samples; every sample has equal model-level weight",
            "rhos": list(rhos),
            "primary_rho": 0.5,
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
                conditions_result[condition] = {
                    "overall": summarize_scores(condition_rows, rhos),
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


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---:" if i else "---" for i in range(len(headers))) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def render_readme(analysis: dict[str, Any]) -> str:
    sections = [
        "# MemCalib v2.3 sample-level calibration metrics",
        "",
        "This analysis reuses the completed primary-Judge outputs. It makes no new model or Judge calls.",
        "Each answer first receives one sample-level over-use budget, under-use budget, and bounded score:",
        "",
        "`SCS_rho(s) = rho ** (over_budget(s) + under_budget(s))`.",
        "",
        "A one-step A/B/C error adds one budget unit; an A-to-C or C-to-A error adds two. The headline",
        "sample score uses `rho=0.5`. Every sample has equal weight in the final model mean. Additional",
        "atoms do not directly reduce a perfect score, but they create additional opportunities for error.",
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
            dist = values["total_budget_distribution"]
            rows.append(
                [
                    models[model]["display_name"],
                    fmt(values["scs"]["0.5"]["mean"]),
                    fmt(values["sample_any_opb_rate"]),
                    fmt(values["sample_any_upb_rate"]),
                    fmt(values["sample_exact_accuracy"]),
                    fmt(values["mean_total_budget"]),
                    fmt(dist["0"]["share"]),
                    fmt(dist["1"]["share"]),
                    fmt(dist["2"]["share"]),
                    fmt(dist["3"]["share"]),
                    fmt(dist["4"]["share"]),
                    fmt(dist["5_plus"]["share"]),
                ]
            )
        sections.extend(
            [
                "",
                f"## {mode}: full-memory sample distribution",
                "",
                markdown_table(
                    [
                        "Model",
                        "SCS(0.5) up",
                        "Any OPB down",
                        "Any UPB down",
                        "Exact up",
                        "Mean budget down",
                        "B=0",
                        "B=1",
                        "B=2",
                        "B=3",
                        "B=4",
                        "B>=5",
                    ],
                    rows,
                ),
            ]
        )

        sensitivity_rows = []
        for model in ordered:
            values = models[model]["conditions"]["full_memory"]["overall"]
            sensitivity_rows.append(
                [
                    models[model]["display_name"],
                    fmt(values["scs"]["0.25"]["mean"]),
                    fmt(values["scs"]["0.5"]["mean"]),
                    fmt(values["scs"]["0.75"]["mean"]),
                    f"[{fmt(values['scs']['0.5']['p10'])}, {fmt(values['scs']['0.5']['p90'])}]",
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
                    fmt(by_level["level_1"]["scs"]["0.5"]["mean"]),
                    fmt(by_level["level_2"]["scs"]["0.5"]["mean"]),
                    fmt(by_level["level_3"]["scs"]["0.5"]["mean"]),
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
                    fmt(non_scs),
                    fmt(think_scs),
                    f"{think_scs - non_scs:+.3f}",
                    f"{think['sample_any_opb_rate'] - non['sample_any_opb_rate']:+.3f}",
                    f"{think['sample_any_upb_rate'] - non['sample_any_upb_rate']:+.3f}",
                    f"{think['sample_exact_accuracy'] - non['sample_exact_accuracy']:+.3f}",
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
                        "Delta Any OPB",
                        "Delta Any UPB",
                        "Delta Exact",
                    ],
                    comparison_rows,
                ),
                "",
                "Negative deltas are improvements for Any OPB/UPB; positive deltas are improvements for SCS/Exact.",
                "Codex reuses identical answers and therefore remains a repeated-Judge control rather than an answer-mode effect.",
            ]
        )
    sections.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `Any OPB` and `Any UPB` are family-wise sample event rates: one directional atom error is enough.",
            "- `Exact` is the share of answers with no scorable atom error and is the hard endpoint of this family.",
            "- `SCS(0.5)` preserves partial credit while compounding every one-step error; a two-step error has the",
            "  same penalty as two one-step errors.",
            "- Rankings can differ from atom-macro H because this metric rewards clean whole answers and penalizes",
            "  errors spread across many records. It should be reported beside directional atom metrics, not used",
            "  to erase the OPB/UPB trade-off.",
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


def render_html(analysis: dict[str, Any]) -> str:
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
                f'<div class="bar">{segments}</div><b>{overall["scs"]["0.5"]["mean"]:.3f}</b></div>'
            )
            table_rows.append(
                [
                    models[model]["display_name"],
                    fmt(overall["scs"]["0.5"]["mean"]),
                    fmt(overall["sample_any_opb_rate"]),
                    fmt(overall["sample_any_upb_rate"]),
                    fmt(overall["sample_exact_accuracy"]),
                    fmt(overall["mean_total_budget"]),
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
                ["Model", "SCS(0.5)", "Any OPB", "Any UPB", "Exact", "Mean budget"],
                table_rows,
            )
            + "</section>"
        )
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MemCalib v2.3 sample-level score distributions</title>
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
</style></head><body><header><h1>MemCalib v2.3 sample-level score distributions</h1>
<p>Existing primary-Judge outputs only. Each answer has one cumulative over/under error budget. SCS(0.5) = 0.5^(over budget + under budget), then averaged with equal sample weight.</p>
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
    analysis = compute_analysis(sample_rows, rhos)
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
    readme_path.write_text(render_readme(analysis), encoding="utf-8")
    html_path.write_text(render_html(analysis), encoding="utf-8")
    output_files = [metrics_path, scores_path, readme_path, html_path]
    manifest = {
        "schema_version": "memcalib-sample-level-calibration-manifest-v1",
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
