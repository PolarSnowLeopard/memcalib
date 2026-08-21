#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any

from evaluation.common import sha256_file, write_json


SKIP_KEYS = {"bootstrap_ci95", "display_name"}
HEADLINE_PATHS = (
    "standard.full_memory.memcalib_h_score",
    "composites.mincalib",
    "classification.multiclass_mcc",
    "classification.linear_weighted_kappa",
    "classification.quadratic_weighted_kappa",
    "sample_risk.linear_loss.cvar90",
    "sample_risk.strict_sample_accuracy",
)


def parse_repeat(value: str) -> tuple[str, Path]:
    try:
        label, path = value.split("=", 1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected LABEL=CANDIDATE_METRICS") from exc
    if not label or not path:
        raise argparse.ArgumentTypeError("repeat label and path must be nonempty")
    return label, Path(path)


def flatten_numeric(value: Any, *, prefix: str = "") -> dict[str, float]:
    flattened: dict[str, float] = {}
    if isinstance(value, bool) or value is None:
        return flattened
    if isinstance(value, (int, float)):
        number = float(value)
        if math.isfinite(number):
            flattened[prefix] = number
        return flattened
    if not isinstance(value, dict):
        return flattened
    for key, nested in value.items():
        if str(key) in SKIP_KEYS:
            continue
        path = f"{prefix}.{key}" if prefix else str(key)
        flattened.update(flatten_numeric(nested, prefix=path))
    return flattened


def mean_sd(values: list[float]) -> dict[str, Any]:
    return {
        "mean": statistics.fmean(values),
        "population_sd": statistics.pstdev(values),
        "minimum": min(values),
        "maximum": max(values),
    }


def aggregate(repeats: list[tuple[str, Path]]) -> dict[str, Any]:
    if len(repeats) < 2:
        raise ValueError("at least two repeats are required")
    loaded = []
    for label, path in repeats:
        payload = json.loads(path.read_text(encoding="utf-8"))
        loaded.append(
            {
                "label": label,
                "path": str(path),
                "sha256": sha256_file(path),
                "models": {
                    model: flatten_numeric(values)
                    for model, values in payload["models"].items()
                },
                "display_names": {
                    model: str(values.get("display_name") or model)
                    for model, values in payload["models"].items()
                },
            }
        )
    model_sets = [set(repeat["models"]) for repeat in loaded]
    if any(models != model_sets[0] for models in model_sets[1:]):
        raise ValueError("repeat model sets differ")

    models: dict[str, Any] = {}
    for model in sorted(model_sets[0]):
        path_sets = [set(repeat["models"][model]) for repeat in loaded]
        if any(paths != path_sets[0] for paths in path_sets[1:]):
            raise ValueError(f"repeat candidate metric paths differ for {model}")
        models[model] = {
            "display_name": loaded[0]["display_names"][model],
            "metrics": {},
        }
        for path in sorted(path_sets[0]):
            values = [repeat["models"][model][path] for repeat in loaded]
            summary = mean_sd(values)
            summary["repeat_values"] = {
                repeat["label"]: repeat["models"][model][path]
                for repeat in loaded
            }
            models[model]["metrics"][path] = summary
    return {
        "schema_version": "memcalib-repeated-candidate-metrics-aggregate-v1",
        "repeat_count": len(loaded),
        "sources": [
            {key: repeat[key] for key in ("label", "path", "sha256")}
            for repeat in loaded
        ],
        "models": models,
    }


def write_csv_output(path: Path, result: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(
            ["model", "display_name", "metric", "mean", "population_sd", "minimum", "maximum"]
        )
        for model, model_values in result["models"].items():
            for metric, summary in model_values["metrics"].items():
                writer.writerow(
                    [
                        model,
                        model_values["display_name"],
                        metric,
                        summary["mean"],
                        summary["population_sd"],
                        summary["minimum"],
                        summary["maximum"],
                    ]
                )


def write_readme(path: Path, result: dict[str, Any]) -> None:
    headers = ["模型", "H", "MinCalib", "MCC", "Linear kappa", "Quadratic kappa", "CVaR90", "Strict"]
    lines = [
        f"# MemCalib v2.4.1 {result['repeat_count']} 轮候选指标聚合",
        "",
        f"下表为 {result['repeat_count']} 次独立回答调用的均值与总体标准差。完整的逐轮值及所有可计算标量指标见 `candidate-aggregate.json` 和 `candidate-aggregate.csv`。",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] + ["---:"] * (len(headers) - 1)) + " |",
    ]
    for model_values in result["models"].values():
        cells = [model_values["display_name"]]
        for metric in HEADLINE_PATHS:
            summary = model_values["metrics"].get(metric)
            cells.append(
                "NA"
                if summary is None
                else f"{summary['mean']:.3f} +/- {summary['population_sd']:.3f}"
            )
        lines.append("| " + " | ".join(cells) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Aggregate all scalar candidate metrics across independent repeats."
    )
    parser.add_argument("--repeat", action="append", type=parse_repeat, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    labels = [label for label, _ in args.repeat]
    if len(labels) != len(set(labels)):
        raise ValueError("repeat labels must be unique")
    result = aggregate(args.repeat)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "candidate-aggregate.json", result)
    write_csv_output(args.output_dir / "candidate-aggregate.csv", result)
    write_readme(args.output_dir / "candidate-aggregate-README.md", result)
    print(json.dumps({"repeats": labels, "models": len(result["models"])}, indent=2))


if __name__ == "__main__":
    main()
