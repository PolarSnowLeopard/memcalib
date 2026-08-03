#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import statistics
from pathlib import Path
from typing import Any


OFFICIAL_FIELDS = (
    "memcalib_score",
    "memcalib_h_score",
    "opb_error_rate",
    "upb_error_rate",
    "strict_sample_accuracy",
    "mean_task_quality",
    "safety_failure_rate",
    "contradiction_rate",
    "constraint_violation_rate",
)
SAMPLE_FIELDS = (
    "scs_0_5",
    "sample_directional_opb_0_5",
    "sample_directional_upb_0_5",
    "sample_directional_h_0_5",
    "sample_any_opb_rate",
    "sample_any_upb_rate",
    "sample_event_h",
    "sample_exact_accuracy",
)
DISPLAY_NAMES = {
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_repeat(value: str) -> tuple[str, Path, Path]:
    try:
        label, paths = value.split("=", 1)
        official, sample = paths.split(",", 1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected LABEL=OFFICIAL_METRICS,SAMPLE_LEVEL_METRICS") from exc
    if not label or not official or not sample:
        raise argparse.ArgumentTypeError("repeat label and both paths must be nonempty")
    return label, Path(official), Path(sample)


def mean_sd(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.fmean(values),
        "population_sd": statistics.pstdev(values),
        "minimum": min(values),
        "maximum": max(values),
    }


def sample_values(overall: dict[str, Any]) -> dict[str, float]:
    directional = overall["directional_risk"]["0.5"]
    event = overall["event_guardrail"]
    return {
        "scs_0_5": float(overall["scs"]["0.5"]["mean"]),
        "sample_directional_opb_0_5": float(directional["opb"]),
        "sample_directional_upb_0_5": float(directional["upb"]),
        "sample_directional_h_0_5": float(directional["harmonic"]),
        "sample_any_opb_rate": float(event["opb"]),
        "sample_any_upb_rate": float(event["upb"]),
        "sample_event_h": float(event["harmonic"]),
        "sample_exact_accuracy": float(overall["sample_exact_accuracy"]),
    }


def load_repeat(label: str, official_path: Path, sample_path: Path) -> dict[str, Any]:
    official = json.loads(official_path.read_text(encoding="utf-8"))
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    sample_models = sample["modes"]["nonthinking"]["models"]
    rows: dict[str, dict[str, dict[str, float]]] = {}
    for model, official_model in official["models"].items():
        if model not in sample_models:
            raise ValueError(f"{label}: model {model} missing from sample-level metrics")
        rows[model] = {}
        for condition in ("full_memory", "no_memory"):
            official_cell = official_model[condition]
            sample_cell = sample_models[model]["conditions"][condition]["overall"]
            values = {field: float(official_cell[field]) for field in OFFICIAL_FIELDS}
            values.update(sample_values(sample_cell))
            rows[model][condition] = values
    if set(rows) != set(sample_models):
        raise ValueError(f"{label}: official and sample-level model sets differ")
    return {
        "label": label,
        "official": {"path": str(official_path), "sha256": sha256_file(official_path)},
        "sample_level": {"path": str(sample_path), "sha256": sha256_file(sample_path)},
        "rows": rows,
    }


def aggregate(repeats: list[dict[str, Any]]) -> dict[str, Any]:
    if len(repeats) < 2:
        raise ValueError("at least two independent repeats are required")
    model_sets = [set(repeat["rows"]) for repeat in repeats]
    if any(models != model_sets[0] for models in model_sets[1:]):
        raise ValueError("repeat model sets differ")
    fields = OFFICIAL_FIELDS + SAMPLE_FIELDS
    models: dict[str, Any] = {}
    for model in sorted(model_sets[0]):
        models[model] = {}
        for condition in ("full_memory", "no_memory"):
            models[model][condition] = {
                field: mean_sd([repeat["rows"][model][condition][field] for repeat in repeats])
                for field in fields
            }
            models[model][condition]["repeat_values"] = {
                repeat["label"]: repeat["rows"][model][condition] for repeat in repeats
            }
    return {
        "schema_version": "memcalib-repeated-evaluation-aggregate-v1",
        "repeat_count": len(repeats),
        "judge_model": "deepseek-v4-pro",
        "answer_mode": "nonthinking",
        "conditions": ["full_memory", "no_memory"],
        "sources": [
            {
                "label": repeat["label"],
                "official": repeat["official"],
                "sample_level": repeat["sample_level"],
            }
            for repeat in repeats
        ],
        "models": models,
    }


def pct(value: float) -> str:
    return f"{100 * value:.2f}%"


def pm(value: dict[str, float]) -> str:
    return f"{pct(value['mean'])} +/- {100 * value['population_sd']:.2f} pp"


def write_csv(path: Path, result: dict[str, Any]) -> None:
    fields = OFFICIAL_FIELDS + SAMPLE_FIELDS
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["model", "condition", "metric", "mean", "population_sd", "minimum", "maximum"])
        for model, conditions in result["models"].items():
            for condition, metrics in conditions.items():
                for field in fields:
                    value = metrics[field]
                    writer.writerow(
                        [model, condition, field, value["mean"], value["population_sd"], value["minimum"], value["maximum"]]
                    )


def headline_rows(result: dict[str, Any]) -> list[list[str]]:
    rows = []
    for model, conditions in result["models"].items():
        cell = conditions["full_memory"]
        rows.append(
            [
                model,
                DISPLAY_NAMES.get(model, model),
                pm(cell["scs_0_5"]),
                pm(cell["sample_directional_opb_0_5"]),
                pm(cell["sample_directional_upb_0_5"]),
                pm(cell["sample_any_opb_rate"]),
                pm(cell["sample_any_upb_rate"]),
                pm(cell["sample_exact_accuracy"]),
                pm(cell["memcalib_h_score"]),
            ]
        )
    return sorted(rows, key=lambda row: row[1])


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] + ["---:"] * (len(headers) - 1)) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def write_readme(path: Path, result: dict[str, Any]) -> None:
    headers = ["模型键", "模型", "SCS", "sOPB", "sUPB", "Any OPB", "Any UPB", "Exact", "原子 H"]
    lines = [
        "# MemCalib v2.4.1：DeepSeek-V4-Pro Judge 三轮 Non-Think 评测",
        "",
        "9 个回答模型在同一组锁定的 494 条样本上独立调用 3 次，每次均包含 Full-memory 与 No-memory。所有主判分都由 DeepSeek-V4-Pro 在关闭 thinking 的条件下独立完成。下表是三轮 Full-memory 的均值；`+/-` 后为三轮总体标准差（population SD）。",
        "",
        markdown_table(headers, headline_rows(result)),
        "",
        "每轮原始值、均值、总体标准差、最小值和最大值见 `aggregate-metrics.json` 与 `aggregate-metrics.csv`；两个文件也包含 No-memory 结果。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_html(path: Path, result: dict[str, Any]) -> None:
    headers = ["模型键", "模型", "SCS", "sOPB", "sUPB", "Any OPB", "Any UPB", "Exact", "原子 H"]
    head = "".join(f"<th>{html.escape(value)}</th>" for value in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(value)}</td>" for value in row) + "</tr>"
        for row in headline_rows(result)
    )
    path.write_text(
        "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>MemCalib 三轮评测</title><style>body{font:15px/1.55 Arial,sans-serif;color:#17212b;margin:36px auto;max-width:1280px;padding:0 20px}"
        "table{width:100%;border-collapse:collapse}th,td{padding:9px;border-bottom:1px solid #d9dfe5;text-align:right;font-variant-numeric:tabular-nums}"
        "th:first-child,td:first-child{text-align:left}p{max-width:920px;color:#52606d}</style></head><body>"
        "<h1>MemCalib v2.4.1：DeepSeek-V4-Pro Judge 三轮 Non-Think 评测</h1>"
        "<p>下表为三次独立回答调用的 Full-memory 均值 +/- 总体标准差。每轮还保存配对的 No-memory 条件，以及完整回答、Judge 输出和失败审计。</p>"
        f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></body></html>",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate independent MemCalib evaluation repeats.")
    parser.add_argument("--repeat", action="append", type=parse_repeat, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    repeats = [load_repeat(*item) for item in args.repeat]
    labels = [repeat["label"] for repeat in repeats]
    if len(labels) != len(set(labels)):
        raise ValueError("repeat labels must be unique")
    result = aggregate(repeats)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = args.output_dir / "aggregate-metrics.json"
    csv_path = args.output_dir / "aggregate-metrics.csv"
    readme_path = args.output_dir / "README.md"
    html_path = args.output_dir / "three-repeat-summary.html"
    metrics_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(csv_path, result)
    write_readme(readme_path, result)
    write_html(html_path, result)
    print(json.dumps({"repeats": labels, "models": len(result["models"]), "output": str(args.output_dir)}, indent=2))


if __name__ == "__main__":
    main()
