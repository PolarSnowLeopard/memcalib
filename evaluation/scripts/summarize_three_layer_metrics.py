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


def fmt_pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def fmt_pp(value: float) -> str:
    return f"{100 * value:+.1f} pp"


def fmt_pct_ci(values: dict[str, float | int]) -> str:
    return (
        f"[{fmt_pct(float(values['ci_low']))}, "
        f"{fmt_pct(float(values['ci_high']))}]"
    )


def fmt_pp_ci(values: dict[str, float | int]) -> str:
    return (
        f"[{fmt_pp(float(values['ci_low']))}, "
        f"{fmt_pp(float(values['ci_high']))}]"
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
    overall_rows = []
    directional_rows = []
    event_rows = []
    overall_ci_rows = []
    directional_ci_rows = []
    event_ci_rows = []
    for model in ordered:
        values = overall_values(analysis, mode, model, condition)
        display_name = MODEL_DISPLAY_NAMES.get(model, model)
        overall_rows.append(
            [display_name, fmt_pct(values["scs"]), fmt_pct(values["exact"])]
        )
        directional_rows.append(
            [
                display_name,
                fmt_pct(values["directional_opb"]),
                fmt_pct(values["directional_upb"]),
                fmt_pct(values["directional_h"]),
            ]
        )
        event_rows.append(
            [
                display_name,
                fmt_pct(values["any_opb"]),
                fmt_pct(values["any_upb"]),
                fmt_pct(values["any_h"]),
            ]
        )
        if include_intervals:
            intervals = overall_intervals(analysis, mode, model, condition)
            overall_ci_rows.append(
                [
                    display_name,
                    fmt_pct_ci(intervals["scs"]),
                    fmt_pct_ci(intervals["exact"]),
                ]
            )
            directional_ci_rows.append(
                [
                    display_name,
                    fmt_pct_ci(intervals["directional_opb"]),
                    fmt_pct_ci(intervals["directional_upb"]),
                    fmt_pct_ci(intervals["directional_h"]),
                ]
            )
            event_ci_rows.append(
                [
                    display_name,
                    fmt_pct_ci(intervals["any_opb"]),
                    fmt_pct_ci(intervals["any_upb"]),
                    fmt_pct_ci(intervals["any_h"]),
                ]
            )
    sections = [
        "**第一层：总体主指标**",
        "",
        markdown_table(["模型", "SCS ↑", "严格准确率 ↑"], overall_rows),
        "",
        "**第二层：方向主指标**",
        "",
        markdown_table(
            ["模型", "sOPB ↓", "sUPB ↓", "Directional H ↑"],
            directional_rows,
        ),
        "",
        "**第三层：事件率护栏**",
        "",
        markdown_table(
            ["模型", "Any-OPB ↓", "Any-UPB ↓", "Event H ↑"],
            event_rows,
        ),
    ]
    if include_intervals:
        sections.extend(
            [
                "",
                "<details>",
                "<summary>查看 2,000 次样本 bootstrap 的 95% 置信区间</summary>",
                "",
                "**总体指标区间**",
                "",
                markdown_table(["模型", "SCS", "严格准确率"], overall_ci_rows),
                "",
                "**方向指标区间**",
                "",
                markdown_table(
                    ["模型", "sOPB", "sUPB", "Directional H"],
                    directional_ci_rows,
                ),
                "",
                "**事件护栏区间**",
                "",
                markdown_table(
                    ["模型", "Any-OPB", "Any-UPB", "Event H"],
                    event_ci_rows,
                ),
                "",
                "</details>",
            ]
        )
    return "\n".join(sections)


def paired_table(
    deltas: dict[str, dict[str, Any]], *, include_control: bool = True
) -> str:
    ordered = sorted(
        deltas,
        key=lambda model: deltas[model]["metrics"]["scs"]["estimate"],
        reverse=True,
    )
    rows = []
    ci_rows = []
    for model in ordered:
        if not include_control and model == "codex-gpt56-sol":
            continue
        metrics = deltas[model]["metrics"]
        rows.append(
            [
                MODEL_DISPLAY_NAMES.get(model, model),
                fmt_pp(float(metrics["scs"]["estimate"])),
                fmt_pp(float(metrics["directional_opb"]["estimate"])),
                fmt_pp(float(metrics["directional_upb"]["estimate"])),
                fmt_pp(float(metrics["any_opb"]["estimate"])),
                fmt_pp(float(metrics["any_upb"]["estimate"])),
            ]
        )
        ci_rows.append(
            [
                MODEL_DISPLAY_NAMES.get(model, model),
                fmt_pp_ci(metrics["scs"]),
                fmt_pp_ci(metrics["directional_opb"]),
                fmt_pp_ci(metrics["directional_upb"]),
                fmt_pp_ci(metrics["any_opb"]),
                fmt_pp_ci(metrics["any_upb"]),
            ]
        )
    headers = [
        "模型",
        "Delta SCS",
        "Delta sOPB",
        "Delta sUPB",
        "Delta Any-OPB",
        "Delta Any-UPB",
    ]
    return "\n".join(
        [
            markdown_table(headers, rows),
            "",
            "<details>",
            "<summary>查看配对差值的 95% bootstrap 置信区间</summary>",
            "",
            markdown_table(headers, ci_rows),
            "",
            "</details>",
        ]
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


def math_block(expression: str) -> str:
    return f"$$\n{expression}\n$$"


def methodology_markdown() -> list[str]:
    transition_rows = [
        ["A → A", "正确", "0", "0"],
        ["A → B", "过用", "1", "0"],
        ["A → C", "过用", "2", "0"],
        ["B → A", "少用", "0", "1"],
        ["B → B", "正确", "0", "0"],
        ["B → C", "过用", "1", "0"],
        ["C → A", "少用", "0", "2"],
        ["C → B", "少用", "0", "1"],
        ["C → C", "正确", "0", "0"],
    ]
    risk_rows = [
        ["0", "0.0%", "100.0%"],
        ["1", "50.0%", "50.0%"],
        ["2", "75.0%", "25.0%"],
        ["3", "87.5%", "12.5%"],
        ["4", "93.8%", "6.3%"],
    ]
    example_rows = [
        ["1", "A", "B", "1", "0"],
        ["2", "B", "C", "1", "0"],
        ["3", "C", "A", "0", "2"],
        ["4", "B", "B", "0", "0"],
    ]
    return [
        "## 详细计算过程",
        "",
        "### 1. 评分输入与等级映射",
        "",
        "对样本 $s$ 中每个可评分原子 $i$，记规范使用等级为 $u^*_{s,i}$，主 Judge",
        "判定的实际使用等级为 $\\hat{u}_{s,i}$。不可评分原子不进入任何分母或预算。",
        "A 的内部构造子类型仅用于数据开发，不进入公开指标。统一等级映射为：",
        "",
        math_block(r"r(A)=0,\qquad r(B)=1,\qquad r(C)=2"),
        "",
        "### 2. 原子级有序方向误差",
        "",
        math_block(
            r"""\begin{aligned}
o_{s,i} &= \max\!\left(r(\hat{u}_{s,i})-r(u^*_{s,i}),\,0\right),\\
u_{s,i} &= \max\!\left(r(u^*_{s,i})-r(\hat{u}_{s,i}),\,0\right).
\end{aligned}"""
        ),
        "",
        "其中 $o_{s,i}$ 是过用预算，$u_{s,i}$ 是少用预算。相邻等级错误计 1，A/C 跨两级",
        "错误计 2；同一个原子不可能同时贡献过用和少用。",
        "",
        markdown_table(
            ["Gold → Predicted", "方向", "过用预算", "少用预算"],
            transition_rows,
        ),
        "",
        "### 3. 样本级方向预算",
        "",
        "将一条回答涉及的所有记忆块和所有可评分原子放回同一个样本内累加：",
        "",
        math_block(
            r"""\begin{aligned}
O_s &= \sum_{i\in s} o_{s,i},\\
U_s &= \sum_{i\in s} u_{s,i},\\
T_s &= O_s+U_s.
\end{aligned}"""
        ),
        "",
        "$O_s$、$U_s$ 和 $T_s$ 分别是样本过用、少用和总有序错误预算。记忆块数",
        "和原子数不会直接成为模型级权重，但更多原子会提供更多犯错机会。",
        "",
        "### 4. 总体主指标 SCS(0.5)",
        "",
        "单样本总体校准分：",
        "",
        math_block(
            r"""\begin{aligned}
\mathrm{SCS}_s(\rho) &= \rho^{O_s+U_s},\\
\mathrm{SCS}(\rho) &= \frac{1}{N}\sum_{s=1}^{N}\mathrm{SCS}_s(\rho),
\qquad \rho=0.5.
\end{aligned}"""
        ),
        "",
        "因此总预算 0/1/2/3/4 对应样本分数 100%/50%/25%/12.5%/6.25%。",
        "SCS 越高越好；它同时惩罚两个方向，但不能替代方向分解。",
        "",
        "### 5. 方向主指标 sOPB/sUPB(0.5)",
        "",
        math_block(
            r"""\begin{aligned}
\mathrm{sOPB}_s(\rho) &= 1-\rho^{O_s},&
\mathrm{sUPB}_s(\rho) &= 1-\rho^{U_s},\\
\mathrm{sOPB}(\rho) &= \frac{1}{N}\sum_{s=1}^{N}\mathrm{sOPB}_s(\rho),&
\mathrm{sUPB}(\rho) &= \frac{1}{N}\sum_{s=1}^{N}\mathrm{sUPB}_s(\rho).
\end{aligned}"""
        ),
        "",
        "两者越低越好。它们区分一次、重复和跨两级错误，同时把每条样本的单方向",
        "风险限制在 $[0,1)$，避免高原子数样本无限主导结果。$\\rho=0.5$ 时：",
        "",
        markdown_table(["方向预算", "风险", "抵抗能力"], risk_rows),
        "",
        "### 6. Directional H",
        "",
        "先定义方向抵抗能力 $R_O=1-\\mathrm{sOPB}$、$R_U=1-\\mathrm{sUPB}$，再取调和平均：",
        "",
        math_block(
            r"""\begin{aligned}
H_{\mathrm{directional}}
&= \frac{2R_OR_U}{R_O+R_U}\\
&= \frac{2(1-\mathrm{sOPB})(1-\mathrm{sUPB})}
{2-\mathrm{sOPB}-\mathrm{sUPB}}.
\end{aligned}"""
        ),
        "",
        "越高越好。它只用于",
        "紧凑比较；正式报告必须同时给出 sOPB 和 sUPB，避免掩盖方向取舍。",
        "",
        "### 7. 事件率护栏与严格准确率",
        "",
        math_block(
            r"""\begin{aligned}
\mathrm{AnyOPB} &= \frac{1}{N}\sum_{s=1}^{N}\mathbf{1}[O_s>0],\\
\mathrm{AnyUPB} &= \frac{1}{N}\sum_{s=1}^{N}\mathbf{1}[U_s>0],\\
\mathrm{Exact} &= \frac{1}{N}\sum_{s=1}^{N}\mathbf{1}[O_s+U_s=0].
\end{aligned}"""
        ),
        "",
        "Any 指标越低越好，Exact 越高越好。Any 只回答某方向是否至少发生一次，",
        "会把一次轻微错误和多次严重错误都记成 1，因此只作为事件覆盖面护栏。",
        "Event H 对 $(1-\\mathrm{AnyOPB})$ 和 $(1-\\mathrm{AnyUPB})$ 使用与 Directional H 相同的",
        "调和平均公式，也不能替代两个方向列。",
        "",
        "### 8. 聚合、配对差值和置信区间",
        "",
        "所有模型级指标都先在样本内汇总，再对 $N$ 条样本取算术平均；一条样本无论",
        "包含多少块和原子，在模型级都只有一个等权观测。95% 区间使用 2,000 次",
        "样本聚类 bootstrap：每次有放回抽取 $N$ 个 sample ID，保留被抽中样本的",
        "全部原子，再重算指标，最终取 2.5% 和 97.5% 分位数。",
        "",
        "Think/Non-Think 与 Base/SFT 差值使用配对 bootstrap。每次只抽取一次 sample ID",
        "序列，并将同一序列同时应用到比较两侧；报告差值定义为 $\\mathrm{after}-\\mathrm{before}$。",
        "因此 SCS/Exact 的正差值表示改善，sOPB/sUPB 和 Any 的负差值表示改善。",
        "",
        "### 9. 手算示例",
        "",
        "假设一条样本的四个可评分原子如下：",
        "",
        markdown_table(["原子", "Gold", "Predicted", "过用", "少用"], example_rows),
        "",
        "该样本有 $O_s=2$、$U_s=2$、$T_s=4$，因此：",
        "",
        math_block(
            r"""\begin{aligned}
\mathrm{SCS}_s &= 0.5^4 = 6.25\%,\\
\mathrm{sOPB}_s &= 1-0.5^2 = 75.0\%,\\
\mathrm{sUPB}_s &= 1-0.5^2 = 75.0\%,\\
\mathrm{AnyOPB}_s &= 1,\quad
\mathrm{AnyUPB}_s = 1,\quad
\mathrm{Exact}_s = 0.
\end{aligned}"""
        ),
        "",
    ]


def methodology_html() -> str:
    transition_rows = [
        ["A to A", "correct", "0", "0"],
        ["A to B", "over-use", "1", "0"],
        ["A to C", "over-use", "2", "0"],
        ["B to A", "under-use", "0", "1"],
        ["B to B", "correct", "0", "0"],
        ["B to C", "over-use", "1", "0"],
        ["C to A", "under-use", "0", "2"],
        ["C to B", "under-use", "0", "1"],
        ["C to C", "correct", "0", "0"],
    ]
    risk_rows = [
        ["0", "0.0%", "100.0%"],
        ["1", "50.0%", "50.0%"],
        ["2", "75.0%", "25.0%"],
        ["3", "87.5%", "12.5%"],
        ["4", "93.8%", "6.3%"],
    ]
    example_rows = [
        ["1", "A", "B", "1", "0"],
        ["2", "B", "C", "1", "0"],
        ["3", "C", "A", "0", "2"],
        ["4", "B", "B", "0", "0"],
    ]
    return (
        "<section><h2>Detailed calculation</h2>"
        '<div class="method-step"><h3>1. Ordered atom errors</h3>'
        "<p>For each scorable atom, map <code>r(A)=0</code>, <code>r(B)=1</code>, "
        "<code>r(C)=2</code>. Internal A construction subtypes are not exposed to the metric.</p>"
        '<code class="formula-block">o(s,i) = max(r(predicted) - r(gold), 0)<br>'
        "u(s,i) = max(r(gold) - r(predicted), 0)</code>"
        + html_table(
            ["Gold to predicted", "Direction", "Over budget", "Under budget"],
            transition_rows,
        )
        + '</div><div class="method-step"><h3>2. Sample budgets</h3>'
        "<p>Sum all scorable atoms across every memory block within one answer sample.</p>"
        '<code class="formula-block">O(s) = sum_i o(s,i)<br>U(s) = sum_i u(s,i)<br>'
        "T(s) = O(s) + U(s)</code>"
        "<p>Block and atom counts do not directly become model-level weights; they increase the "
        "number of opportunities for error.</p></div>"
        '<div class="method-step"><h3>3. Overall primary metric</h3>'
        '<code class="formula-block">SCS(s; rho) = rho^(O(s)+U(s))<br>'
        "SCS(rho) = mean_s SCS(s; rho)<br>Primary rho = 0.5</code>"
        "<p>Total budgets 0, 1, 2, 3, and 4 receive scores 100%, 50%, 25%, "
        "12.5%, and 6.25%. Higher is better.</p></div>"
        '<div class="method-step"><h3>4. Directional primary metrics</h3>'
        '<code class="formula-block">sOPB(s; rho) = 1 - rho^O(s)<br>'
        "sUPB(s; rho) = 1 - rho^U(s)<br>"
        "sOPB(rho) = mean_s sOPB(s; rho)<br>sUPB(rho) = mean_s sUPB(s; rho)</code>"
        "<p>Lower is better. Repeated and two-level errors receive more weight, while each sample "
        "remains bounded below 1.</p>"
        + html_table(["Budget", "Risk at rho=0.5", "Resistance"], risk_rows)
        + '</div><div class="method-step"><h3>5. Directional H</h3>'
        '<code class="formula-block">R(O) = 1-sOPB; R(U) = 1-sUPB<br>'
        "Directional H = 2*R(O)*R(U)/(R(O)+R(U))</code>"
        "<p>Higher is better. This compact summary never replaces the two directional columns.</p>"
        '</div><div class="method-step"><h3>6. Event guardrails and exact accuracy</h3>'
        '<code class="formula-block">Any-OPB = mean_s 1[O(s)&gt;0]<br>'
        "Any-UPB = mean_s 1[U(s)&gt;0]<br>Exact = mean_s 1[O(s)+U(s)=0]</code>"
        "<p>Any rates measure error coverage, collapsing one and many errors to the same event. "
        "Event H is the harmonic mean of their two resistance terms.</p></div>"
        '<div class="method-step"><h3>7. Aggregation and uncertainty</h3>'
        "<p>Every answer sample has one equal model-level vote. The 95% intervals use 2,000 "
        "sample-cluster bootstrap replicates and the 2.5th/97.5th percentiles. Paired comparisons "
        "resample the same sample IDs on both sides and report <code>after - before</code>.</p></div>"
        '<div class="method-step"><h3>8. Worked example</h3>'
        + html_table(["Atom", "Gold", "Predicted", "Over", "Under"], example_rows)
        + "<p>Here <code>O(s)=2</code>, <code>U(s)=2</code>, so "
        "<code>SCS(s)=6.25%</code>, <code>sOPB(s)=75.0%</code>, "
        "<code>sUPB(s)=75.0%</code>, both Any events equal 1, and Exact equals 0.</p>"
        "</div></section>"
    )


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
        "- **总体主指标 SCS(0.5)：** 汇总整条回答的双向有序错误，越高越好。",
        "- **方向主指标 sOPB/sUPB(0.5)：** 分别衡量样本级过用和少用强度，",
        "  越低越好。它们区分一次与多次/严重错误，但每条",
        "  样本的单方向风险上限为 1。",
        "- **事件率护栏 Any-OPB/Any-UPB：** 衡量发生至少一次方向错误的样本比例，",
        "  越低越好。它们只描述错误覆盖面，不能单独作为主指标。",
        "- $O_s$、$U_s$ 是样本内所有可评分原子的有序过用/少用预算；相邻等级错误",
        "  计 1，A/C 跨两级错误计 2。所有模型级值对样本等权。",
        "- 方括号为按样本聚类的 2,000 次 bootstrap 95% 区间。",
        "",
    ]
    sections.extend(methodology_markdown())
    sections.extend(
        [
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
    )
    for metric, label in (
        ("scs", "SCS"),
        ("directional_opb", "sOPB"),
        ("directional_upb", "sUPB"),
        ("any_opb", "Any-OPB"),
        ("any_upb", "Any-UPB"),
    ):
        values = trend["metrics"][metric]
        sections.append(
            f"- {label}: 平均变化 {fmt_pp(values['mean_delta'])}，中位变化 "
            f"{fmt_pp(values['median_delta'])}，改善 {values['improved_models']}/8。"
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
    overall_rows = []
    directional_rows = []
    event_rows = []
    for model in ordered:
        values = overall_values(analysis, mode, model, condition)
        display_name = MODEL_DISPLAY_NAMES.get(model, model)
        overall_rows.append(
            [
                display_name,
                fmt_pct(values["scs"]),
                fmt_pct(values["exact"]),
            ]
        )
        directional_rows.append(
            [
                display_name,
                fmt_pct(values["directional_opb"]),
                fmt_pct(values["directional_upb"]),
                fmt_pct(values["directional_h"]),
            ]
        )
        event_rows.append(
            [
                display_name,
                fmt_pct(values["any_opb"]),
                fmt_pct(values["any_upb"]),
                fmt_pct(values["any_h"]),
            ]
        )
    return (
        '<div class="layer-group"><h3>Layer 1: Overall</h3>'
        + html_table(["Model", "SCS", "Exact"], overall_rows)
        + '<h3>Layer 2: Directional</h3>'
        + html_table(
            ["Model", "sOPB", "sUPB", "Directional H"],
            directional_rows,
        )
        + '<h3>Layer 3: Event guardrails</h3>'
        + html_table(["Model", "Any-OPB", "Any-UPB", "Event H"], event_rows)
        + "</div>"
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
    sections.insert(0, methodology_html())
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
.method-step{padding:18px 0;border-top:1px solid var(--line)}.method-step:first-of-type{border-top:0;padding-top:4px}
h3{font-size:16px;margin:0 0 8px;letter-spacing:0}.layer-group h3{margin-top:22px}.formula-block{display:block;background:#f2f5f4;padding:12px;overflow-x:auto;white-space:nowrap}
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
            "rank": {"A": 0, "B": 1, "C": 2},
            "atom_over_budget": "max(rank(predicted) - rank(gold), 0)",
            "atom_under_budget": "max(rank(gold) - rank(predicted), 0)",
            "sample_over_budget": "sum_i atom_over_budget",
            "sample_under_budget": "sum_i atom_under_budget",
            "directional_h": "harmonic mean of (1-sOPB) and (1-sUPB)",
            "event_h": "harmonic mean of (1-Any-OPB) and (1-Any-UPB)",
            "exact": "mean_s 1[over_budget_s + under_budget_s == 0]",
            "aggregation_unit": "answer sample; equal model-level weight per sample",
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
