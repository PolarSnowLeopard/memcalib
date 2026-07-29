#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import random
from pathlib import Path
from statistics import fmean, median
from typing import Any

from evaluation.common import write_json
from evaluation.scripts.analyze_sample_level_calibration import (
    headline_metrics,
    percentile,
)


ROOT = Path(__file__).resolve().parents[2]
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
METRIC_ORDER = (
    "scs",
    "directional_opb",
    "directional_upb",
    "directional_h",
    "any_opb",
    "any_upb",
    "any_h",
    "exact",
)
LOWER_IS_BETTER = {
    "directional_opb",
    "directional_upb",
    "any_opb",
    "any_upb",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_scores(path: Path) -> list[dict[str, Any]]:
    integer_fields = {
        "atom_count",
        "over_budget",
        "under_budget",
        "total_budget",
        "sample_any_opb",
        "sample_any_upb",
        "sample_any_error",
        "sample_exact",
        "severe_two_step",
    }
    float_prefixes = ("scs_rho_", "sample_opb_risk_", "sample_upb_risk_")
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for source in csv.DictReader(handle):
            row: dict[str, Any] = dict(source)
            for key in integer_fields:
                row[key] = int(source[key])
            for key, value in source.items():
                if key.startswith(float_prefixes):
                    row[key] = float(value)
            rows.append(row)
    return rows


def overall_values(
    analysis: dict[str, Any], mode: str, model: str, condition: str
) -> dict[str, float]:
    overall = analysis["modes"][mode]["models"][model]["conditions"][condition][
        "overall"
    ]
    directional = overall["directional_risk"]["0.5"]
    event = overall["event_guardrail"]
    return {
        "scs": overall["scs"]["0.5"]["mean"],
        "directional_opb": directional["opb"],
        "directional_upb": directional["upb"],
        "directional_h": directional["harmonic"],
        "any_opb": event["opb"],
        "any_upb": event["upb"],
        "any_h": event["harmonic"],
        "exact": overall["sample_exact_accuracy"],
    }


def overall_intervals(
    analysis: dict[str, Any], mode: str, model: str, condition: str
) -> dict[str, dict[str, float | int]]:
    return analysis["modes"][mode]["models"][model]["conditions"][condition][
        "overall"
    ]["headline_bootstrap_95_ci"]


def index_rows(
    rows: list[dict[str, Any]],
) -> dict[tuple[str, str, str], dict[str, dict[str, Any]]]:
    indexed: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = {}
    for row in rows:
        key = (str(row["mode"]), str(row["model_key"]), str(row["condition"]))
        sample_id = str(row["sample_id"])
        bucket = indexed.setdefault(key, {})
        if sample_id in bucket:
            raise ValueError(f"duplicate sample in score bucket: {key} {sample_id}")
        bucket[sample_id] = row
    return indexed


def paired_delta_bootstrap(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
    *,
    replicates: int,
    seed: int,
) -> dict[str, Any]:
    sample_ids = sorted(set(before) & set(after))
    if set(before) != set(after):
        raise ValueError("paired score buckets must have identical sample IDs")
    before_rows = [before[sample_id] for sample_id in sample_ids]
    after_rows = [after[sample_id] for sample_id in sample_ids]
    before_estimate = headline_metrics(before_rows, 0.5)
    after_estimate = headline_metrics(after_rows, 0.5)
    estimates = {
        key: after_estimate[key] - before_estimate[key] for key in METRIC_ORDER
    }
    samples = {key: [] for key in METRIC_ORDER}
    rng = random.Random(seed)
    for _ in range(replicates):
        positions = [rng.randrange(len(sample_ids)) for _ in sample_ids]
        left = headline_metrics([before_rows[position] for position in positions], 0.5)
        right = headline_metrics([after_rows[position] for position in positions], 0.5)
        for key in METRIC_ORDER:
            samples[key].append(right[key] - left[key])
    return {
        "samples": len(sample_ids),
        "replicates": replicates,
        "metrics": {
            key: {
                "estimate": estimates[key],
                "ci_low": percentile(samples[key], 0.025),
                "ci_high": percentile(samples[key], 0.975),
            }
            for key in METRIC_ORDER
        },
    }


def fmt(value: float) -> str:
    return f"{value:.3f}"


def fmt_delta(value: float) -> str:
    return f"{value:+.3f}"


def fmt_ci(values: dict[str, float | int]) -> str:
    return (
        f"{fmt(float(values['estimate']))} "
        f"[{fmt(float(values['ci_low']))}, {fmt(float(values['ci_high']))}]"
    )


def fmt_delta_ci(values: dict[str, float | int]) -> str:
    return (
        f"{fmt_delta(float(values['estimate']))} "
        f"[{fmt_delta(float(values['ci_low']))}, "
        f"{fmt_delta(float(values['ci_high']))}]"
    )


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" if index == 0 else "---:" for index in range(len(headers))) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def metric_table(
    analysis: dict[str, Any],
    *,
    mode: str,
    condition: str,
    include_intervals: bool,
) -> str:
    models = analysis["modes"][mode]["models"]
    ordered = sorted(
        models,
        key=lambda model: overall_values(analysis, mode, model, condition)["scs"],
        reverse=True,
    )
    rows = []
    for model in ordered:
        values = overall_values(analysis, mode, model, condition)
        if include_intervals:
            intervals = overall_intervals(analysis, mode, model, condition)
            rows.append(
                [
                    MODEL_DISPLAY_NAMES.get(model, model),
                    fmt_ci(intervals["scs"]),
                    fmt_ci(intervals["directional_opb"]),
                    fmt_ci(intervals["directional_upb"]),
                    fmt(values["directional_h"]),
                    fmt_ci(intervals["any_opb"]),
                    fmt_ci(intervals["any_upb"]),
                    fmt(values["any_h"]),
                    fmt(values["exact"]),
                ]
            )
        else:
            rows.append(
                [
                    MODEL_DISPLAY_NAMES.get(model, model),
                    *(fmt(values[key]) for key in METRIC_ORDER),
                ]
            )
    return markdown_table(
        [
            "Model",
            "SCS up",
            "sOPB down",
            "sUPB down",
            "Directional H up",
            "Any-OPB down",
            "Any-UPB down",
            "Event H up",
            "Exact up",
        ],
        rows,
    )


def paired_table(
    deltas: dict[str, dict[str, Any]], *, include_control: bool = True
) -> str:
    ordered = sorted(
        deltas,
        key=lambda model: deltas[model]["metrics"]["scs"]["estimate"],
        reverse=True,
    )
    rows = []
    for model in ordered:
        if not include_control and model == "codex-gpt56-sol":
            continue
        metrics = deltas[model]["metrics"]
        rows.append(
            [
                MODEL_DISPLAY_NAMES.get(model, model),
                fmt_delta_ci(metrics["scs"]),
                fmt_delta_ci(metrics["directional_opb"]),
                fmt_delta_ci(metrics["directional_upb"]),
                fmt_delta_ci(metrics["any_opb"]),
                fmt_delta_ci(metrics["any_upb"]),
            ]
        )
    return markdown_table(
        [
            "Model",
            "Delta SCS",
            "Delta sOPB",
            "Delta sUPB",
            "Delta Any-OPB",
            "Delta Any-UPB",
        ],
        rows,
    )


def direction_improved(metric: str, value: float) -> bool:
    return value < 0 if metric in LOWER_IS_BETTER else value > 0


def summarize_mode_deltas(deltas: dict[str, dict[str, Any]]) -> dict[str, Any]:
    model_keys = [key for key in deltas if key != "codex-gpt56-sol"]
    summary: dict[str, Any] = {"models": len(model_keys), "metrics": {}}
    for metric in ("scs", "directional_opb", "directional_upb", "any_opb", "any_upb"):
        values = [deltas[key]["metrics"][metric]["estimate"] for key in model_keys]
        summary["metrics"][metric] = {
            "mean_delta": fmean(values),
            "median_delta": median(values),
            "improved_models": sum(direction_improved(metric, value) for value in values),
            "worsened_models": sum(direction_improved(metric, -value) for value in values),
            "unchanged_models": sum(value == 0 for value in values),
        }
    return summary


def render_readme(
    result: dict[str, Any],
    main: dict[str, Any],
    sft: dict[str, Any],
) -> str:
    deltas = result["paired_deltas"]["thinking_minus_nonthinking"]
    sft_delta = result["paired_deltas"]["sft_minus_base"]
    trend = result["trend_summary"]["thinking_minus_nonthinking_eight_bailian_models"]
    sections = [
        "# MemCalib v2.3 three-layer evaluation summary",
        "",
        "本报告只复用已经完成的主 Judge 输出，不重新调用回答模型或 Judge。所有主表均以",
        "一条回答样本为聚合单位；内部构建用的 A 子类型不进入公开指标。",
        "",
        "## 统一口径",
        "",
        "- **总体主指标 SCS(0.5)：** `mean_s 0.5^(O_s + U_s)`，越高越好。",
        "- **方向主指标 sOPB/sUPB(0.5)：** `mean_s (1-0.5^O_s)` 与",
        "  `mean_s (1-0.5^U_s)`，越低越好。它们区分一次与多次/严重错误，但每条",
        "  样本的单方向风险上限为 1。",
        "- **事件率护栏 Any-OPB/Any-UPB：** `mean_s 1[O_s>0]` 与",
        "  `mean_s 1[U_s>0]`，越低越好。它们只描述错误覆盖面，不能单独作为主指标。",
        "- `O_s`、`U_s` 是样本内所有可评分原子的有序过用/少用预算；相邻等级错误",
        "  计 1，A/C 跨两级错误计 2。所有模型级值对样本等权。",
        "- 方括号为按样本聚类的 2,000 次 bootstrap 95% 区间。",
        "",
        "## Think：Full-memory",
        "",
        metric_table(main, mode="thinking", condition="full_memory", include_intervals=True),
        "",
        "## Non-Think：Full-memory",
        "",
        metric_table(main, mode="nonthinking", condition="full_memory", include_intervals=True),
        "",
        "## Think 相对 Non-Think 的同样本变化",
        "",
        paired_table(deltas),
        "",
        "负的 sOPB/sUPB 和 Any-OPB/Any-UPB 差值表示改善；正的 SCS 差值表示改善。",
        "Codex 两侧复用相同回答，因此只用于估计重复 Judge 波动，不代表思考模式效果。",
        "",
        "八个百炼模型的聚合趋势：",
        "",
    ]
    for metric, label in (
        ("scs", "SCS"),
        ("directional_opb", "sOPB"),
        ("directional_upb", "sUPB"),
        ("any_opb", "Any-OPB"),
        ("any_upb", "Any-UPB"),
    ):
        values = trend["metrics"][metric]
        sections.append(
            f"- {label}: 平均变化 {fmt_delta(values['mean_delta'])}，中位变化 "
            f"{fmt_delta(values['median_delta'])}，改善 {values['improved_models']}/8。"
        )
    sections.extend(
        [
            "",
            "## Base/SFT：496 条严格配对 Full-memory",
            "",
            metric_table(sft, mode="sft-pilot", condition="full_memory", include_intervals=True),
            "",
            "### SFT 相对 Base 的同样本变化",
            "",
            paired_table({"qwen35-a3b-sft-vllm": sft_delta}),
            "",
            "SFT 对总体错误和过用方向的改善明显，但少用方向恶化；这一结论在方向主指标",
            "和事件率护栏上保持一致。",
            "",
            "## No-memory 反事实附表",
            "",
            "No-memory 不进入 Full-memory 主排行榜。它用于确认：不提供记忆时过用风险应降低，",
            "而依赖相关记忆才能恢复的信息会表现为高少用风险。",
            "",
            "### Think：No-memory",
            "",
            metric_table(main, mode="thinking", condition="no_memory", include_intervals=False),
            "",
            "### Non-Think：No-memory",
            "",
            metric_table(main, mode="nonthinking", condition="no_memory", include_intervals=False),
            "",
            "## 总体观察",
            "",
            "- 三层口径没有把方向折叠进单一总分：SCS 回答“整条回答总体是否可靠”，",
            "  sOPB/sUPB 回答“错误方向与累积强度”，Any 护栏回答“错误是否广泛散布”。",
            "- Any 指标的模型间跨度通常大于指数方向风险，但更容易随原子数增加而饱和；",
            "  因此它适合做护栏，不适合取代 sOPB/sUPB。",
            "- Directional H 和 Event H 只用于紧凑比较。论文主表仍应同时公开两个方向列，",
            "  避免调和平均掩盖过用和少用之间的取舍。",
            "- Think 与 Non-Think 的变化不是单向一致的；模型可能降低少用同时增加过用，",
            "  所以不能只根据 SCS 或某一个方向指标宣称整体改善。",
            "",
            "## 产物",
            "",
            "- `three-layer-metrics.json`：全部点估计、区间、同样本差值和趋势统计。",
            "- `three-layer-metrics.html`：适合直接审阅的可视化总表。",
            "- `analysis-manifest.json`：输入与输出 SHA-256。",
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
    return f"<div class=\"table-wrap\"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def html_metric_table(
    analysis: dict[str, Any], *, mode: str, condition: str
) -> str:
    models = analysis["modes"][mode]["models"]
    ordered = sorted(
        models,
        key=lambda model: overall_values(analysis, mode, model, condition)["scs"],
        reverse=True,
    )
    rows = []
    for model in ordered:
        values = overall_values(analysis, mode, model, condition)
        rows.append(
            [
                MODEL_DISPLAY_NAMES.get(model, model),
                fmt(values["scs"]),
                fmt(values["directional_opb"]),
                fmt(values["directional_upb"]),
                fmt(values["directional_h"]),
                fmt(values["any_opb"]),
                fmt(values["any_upb"]),
                fmt(values["any_h"]),
            ]
        )
    return html_table(
        [
            "Model",
            "SCS",
            "sOPB",
            "sUPB",
            "Dir. H",
            "Any-OPB",
            "Any-UPB",
            "Event H",
        ],
        rows,
    )


def render_html(
    result: dict[str, Any],
    main: dict[str, Any],
    sft: dict[str, Any],
) -> str:
    sections = []
    for title, analysis, mode in (
        ("Think / Full-memory", main, "thinking"),
        ("Non-Think / Full-memory", main, "nonthinking"),
        ("Base and SFT / Full-memory", sft, "sft-pilot"),
    ):
        sections.append(
            f"<section><h2>{html.escape(title)}</h2>"
            f"{html_metric_table(analysis, mode=mode, condition='full_memory')}</section>"
        )
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MemCalib v2.3 three-layer evaluation</title>
<style>
:root{--ink:#15212a;--muted:#596771;--line:#d7dde1;--paper:#f4f6f5;--panel:#fff;--accent:#176b5b}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 Arial,sans-serif}
header,main{max-width:1180px;margin:auto;padding:24px}header{padding-top:42px;padding-bottom:10px}
h1{font-size:32px;margin:0 0 10px;letter-spacing:0}h2{font-size:21px;margin:0 0 14px;letter-spacing:0}
p{max-width:940px;color:var(--muted)}.formula{border-left:4px solid var(--accent);padding:10px 14px;background:#eef5f2;color:var(--ink)}
section{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:22px;margin:18px 0}
.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:10px;border-bottom:1px solid var(--line);text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
th:first-child,td:first-child{text-align:left}th{color:#40505b;background:#f8f9f8}
@media(max-width:700px){header,main{padding:15px}section{padding:14px}h1{font-size:25px}}
</style></head><body><header><h1>MemCalib v2.3 three-layer evaluation</h1>
<p>Existing Judge outputs only. Every aggregate gives each answer sample equal weight.</p>
<p class="formula"><b>Overall:</b> SCS(0.5). <b>Directional:</b> sOPB/sUPB(0.5).
<b>Guardrails:</b> Any-OPB/Any-UPB.</p></header><main>""" + "".join(sections) + """
</main></body></html>"""


def compact_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {"modes": {}}
    for mode, mode_values in analysis["modes"].items():
        compact["modes"][mode] = {"models": {}}
        for model, model_values in mode_values["models"].items():
            conditions = {}
            for condition in model_values["conditions"]:
                conditions[condition] = {
                    "metrics": overall_values(analysis, mode, model, condition),
                    "bootstrap_95_ci": overall_intervals(
                        analysis, mode, model, condition
                    ),
                }
            compact["modes"][mode]["models"][model] = {
                "display_name": MODEL_DISPLAY_NAMES.get(model, model),
                "conditions": conditions,
            }
    return compact


def build_result(
    main_analysis: dict[str, Any],
    main_scores: list[dict[str, Any]],
    sft_analysis: dict[str, Any],
    sft_scores: list[dict[str, Any]],
    *,
    replicates: int,
) -> dict[str, Any]:
    main_index = index_rows(main_scores)
    sft_index = index_rows(sft_scores)
    model_keys = sorted(main_analysis["modes"]["thinking"]["models"])
    mode_deltas = {}
    for model in model_keys:
        seed = int.from_bytes(
            hashlib.sha256(f"think-delta\0{model}".encode()).digest()[:8], "big"
        )
        mode_deltas[model] = paired_delta_bootstrap(
            main_index[("nonthinking", model, "full_memory")],
            main_index[("thinking", model, "full_memory")],
            replicates=replicates,
            seed=seed,
        )
    sft_delta = paired_delta_bootstrap(
        sft_index[("sft-pilot", "qwen35-a3b-base-vllm", "full_memory")],
        sft_index[("sft-pilot", "qwen35-a3b-sft-vllm", "full_memory")],
        replicates=replicates,
        seed=20260729,
    )
    return {
        "schema_version": "memcalib-v23-three-layer-summary-v1",
        "definition": {
            "primary_rho": 0.5,
            "overall_primary": "mean_s 0.5 ** (over_budget_s + under_budget_s)",
            "directional_primary_opb": "mean_s (1 - 0.5 ** over_budget_s)",
            "directional_primary_upb": "mean_s (1 - 0.5 ** under_budget_s)",
            "event_guardrail_opb": "mean_s 1[over_budget_s > 0]",
            "event_guardrail_upb": "mean_s 1[under_budget_s > 0]",
            "bootstrap": f"{replicates} sample-cluster replicates; percentile 95% interval",
        },
        "results": {
            "nine_model": compact_analysis(main_analysis),
            "base_sft": compact_analysis(sft_analysis),
        },
        "paired_deltas": {
            "thinking_minus_nonthinking": mode_deltas,
            "sft_minus_base": sft_delta,
        },
        "trend_summary": {
            "thinking_minus_nonthinking_eight_bailian_models": summarize_mode_deltas(
                mode_deltas
            )
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize MemCalib v2.3 three-layer sample-level metrics."
    )
    parser.add_argument(
        "--nine-model-dir",
        type=Path,
        default=ROOT
        / "evaluation/analyses/memcalib-v23-sample-level-calibration",
    )
    parser.add_argument(
        "--base-sft-dir",
        type=Path,
        default=ROOT
        / "evaluation/analyses/memcalib-v23-sft-base-full-only-paired-sample-level",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "evaluation/analyses/memcalib-v23-three-layer-metrics",
    )
    parser.add_argument("--bootstrap-replicates", type=int, default=2000)
    args = parser.parse_args()

    source_paths = {
        "nine_model_metrics": args.nine_model_dir / "sample-level-metrics.json",
        "nine_model_scores": args.nine_model_dir / "sample-level-scores.csv",
        "base_sft_metrics": args.base_sft_dir / "sample-level-metrics.json",
        "base_sft_scores": args.base_sft_dir / "sample-level-scores.csv",
    }
    main_analysis = read_json(source_paths["nine_model_metrics"])
    main_scores = read_scores(source_paths["nine_model_scores"])
    sft_analysis = read_json(source_paths["base_sft_metrics"])
    sft_scores = read_scores(source_paths["base_sft_scores"])
    result = build_result(
        main_analysis,
        main_scores,
        sft_analysis,
        sft_scores,
        replicates=args.bootstrap_replicates,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = args.output_dir / "three-layer-metrics.json"
    readme_path = args.output_dir / "README.md"
    html_path = args.output_dir / "three-layer-metrics.html"
    manifest_path = args.output_dir / "analysis-manifest.json"
    write_json(metrics_path, result)
    readme_path.write_text(
        render_readme(result, main_analysis, sft_analysis),
        encoding="utf-8",
    )
    html_path.write_text(
        render_html(result, main_analysis, sft_analysis),
        encoding="utf-8",
    )
    outputs = (metrics_path, readme_path, html_path)
    manifest = {
        "schema_version": "memcalib-v23-three-layer-summary-manifest-v1",
        "sources": {
            key: {
                "path": str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for key, path in source_paths.items()
        },
        "outputs": {
            path.name: {
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for path in outputs
        },
    }
    write_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "nine_model_score_rows": len(main_scores),
                "base_sft_score_rows": len(sft_scores),
                "paired_models": len(
                    result["paired_deltas"]["thinking_minus_nonthinking"]
                ),
                "output_dir": str(args.output_dir),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
