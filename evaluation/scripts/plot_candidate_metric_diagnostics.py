#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any

from evaluation.common import iter_jsonl, write_json


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = (
    ROOT
    / "evaluation"
    / "analyses"
    / "memcalib-v21-multidomain-500-candidate-metrics"
)
DEFAULT_PRIMARY = (
    ROOT
    / "evaluation"
    / "runs"
    / "memcalib-v21-multidomain-500-eight-models"
    / "judgments"
    / "primary.valid.jsonl"
)
DEFAULT_METRICS = ANALYSIS_DIR / "candidate-metrics.json"
DEFAULT_OUTPUT = ANALYSIS_DIR / "candidate-metric-diagnostics.html"
DEFAULT_MANIFEST = ANALYSIS_DIR / "candidate-metric-diagnostics.manifest.json"
RANK = {"A": 0, "B": 1, "C": 2}
SHORT_NAMES = {
    "claude-opus-5": "Claude Opus 5",
    "claude-sonnet-4-6": "Claude Sonnet 4.6",
    "codex-gpt56-sol": "Codex",
    "deepseek": "DS-Pro",
    "deepseek-flash": "DS-Flash",
    "deepseek-flash-0731": "DS-Flash-0731",
    "glm52": "GLM-5.2",
    "gemini35-flash": "Gemini 3.5 Flash",
    "gpt56-sol": "GPT-5.6-SOL",
    "grok-4": "Grok 4",
    "kimi": "Kimi",
    "kimi-k26": "Kimi-K2.6",
    "qwen-flash": "Qwen-Flash",
    "qwen-max": "Qwen-Max",
    "qwen38-max": "Qwen3.8-Max",
    "qwen3-8b": "Qwen-8B",
    "qwen35-35b-a3b": "Qwen-35B",
    "qwen35-a3b-base-vllm": "Qwen-35B Base",
    "qwen35-a3b-sft-vllm": "Qwen-35B SFT",
}
METRIC_COLUMNS = (
    ("h", "H", True),
    ("mincalib", "MinCalib", True),
    ("mcc", "MCC", True),
    ("linear_kappa", "Linear κ", True),
    ("quadratic_kappa", "Quadratic κ", True),
    ("cvar90", "CVaR90", False),
    ("pmu1", "PMU(1)", True),
    ("strict_sample", "Strict", True),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


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


def _tail_mean(values: list[float], alpha: float) -> float:
    if not values:
        raise ValueError("tail mean requires nonempty values")
    count = max(1, math.ceil((1 - alpha) * len(values)))
    return fmean(sorted(values, reverse=True)[:count])


def build_tail_profiles(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_model_sample: dict[str, dict[str, list[int]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in rows:
        if row.get("condition") != "full_memory":
            continue
        model = str(row["model_key"])
        sample_id = str(row["sample_id"])
        for atom in row["atom_judgments"]:
            predicted = atom.get("predicted_usage_level")
            gold = atom.get("u_star")
            if atom.get("scorable", True) and predicted in RANK and gold in RANK:
                by_model_sample[model][sample_id].append(
                    abs(RANK[predicted] - RANK[gold])
                )

    profiles: dict[str, dict[str, Any]] = {}
    sample_sets = []
    for model, samples in sorted(by_model_sample.items()):
        sample_sets.append(set(samples))
        stats = []
        for sample_id, distances in samples.items():
            if not distances:
                raise ValueError(f"sample {sample_id} has no scorable atoms")
            stats.append(
                {
                    "sample_id": sample_id,
                    "loss": fmean(distance / 2 for distance in distances),
                    "severe": any(distance == 2 for distance in distances),
                    "severe_atom_rate": fmean(
                        int(distance == 2) for distance in distances
                    ),
                    "atom_count": len(distances),
                }
            )
        stats.sort(key=lambda item: (item["loss"], item["sample_id"]))
        losses = [float(item["loss"]) for item in stats]
        tail_count = max(1, math.ceil(0.10 * len(stats)))
        tail = stats[-tail_count:]
        profiles[model] = {
            "samples": len(stats),
            "tail_samples": tail_count,
            "mean": fmean(losses),
            "p80": _percentile(losses, 0.80),
            "p90": _percentile(losses, 0.90),
            "p95": _percentile(losses, 0.95),
            "cvar90": _tail_mean(losses, 0.90),
            "cvar95": _tail_mean(losses, 0.95),
            "maximum": max(losses),
            "tail_severe_sample_rate": fmean(int(item["severe"]) for item in tail),
            "tail_severe_atom_rate": fmean(
                float(item["severe_atom_rate"]) for item in tail
            ),
            "tail_mean_atom_count": fmean(int(item["atom_count"]) for item in tail),
            "quantile_curve": [
                {
                    "percentile": round(index * 100 / (len(stats) - 1), 4),
                    "loss": round(float(item["loss"]), 6),
                }
                for index, item in enumerate(stats)
                if index * 100 / (len(stats) - 1) >= 70
            ],
        }

    if not sample_sets or any(values != sample_sets[0] for values in sample_sets[1:]):
        raise ValueError("models do not use identical full-memory sample IDs")
    return profiles


def _metric_values(model: dict[str, Any]) -> dict[str, float | None]:
    pmu = model["paired_utility"]["pmu_lambda_1_0"]
    return {
        "h": float(model["composites"]["harmonic_h"]),
        "mincalib": float(model["composites"]["mincalib"]),
        "mcc": float(model["classification"]["multiclass_mcc"]),
        "linear_kappa": float(model["classification"]["linear_weighted_kappa"]),
        "quadratic_kappa": float(
            model["classification"]["quadratic_weighted_kappa"]
        ),
        "cvar90": float(model["sample_risk"]["linear_loss"]["cvar90"]),
        "pmu1": float(pmu) if pmu is not None else None,
        "strict_sample": float(model["sample_risk"]["strict_sample_accuracy"]),
    }


def build_visualization_data(
    metrics: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    metric_models = metrics["models"]
    pareto_models = set(metrics.get("pareto", {}).get("pareto_front", []))
    if set(metric_models) != set(profiles):
        raise ValueError("metric and tail-profile model sets differ")

    values = {
        model_key: _metric_values(model)
        for model_key, model in metric_models.items()
    }
    ranks: dict[str, dict[str, int]] = {
        model_key: {} for model_key in metric_models
    }
    metric_columns = [
        column
        for column in METRIC_COLUMNS
        if any(values[model_key][column[0]] is not None for model_key in metric_models)
    ]
    for metric_key, _, higher_is_better in metric_columns:
        ordered = sorted(
            metric_models,
            key=lambda model_key: (
                -float(values[model_key][metric_key])
                if higher_is_better
                else float(values[model_key][metric_key]),
                model_key,
            ),
        )
        for index, model_key in enumerate(ordered, start=1):
            ranks[model_key][metric_key] = index

    models = []
    for model_key, model in metric_models.items():
        standard = model["standard"]["full_memory"]
        models.append(
            {
                "key": model_key,
                "name": str(model["display_name"]),
                "short_name": SHORT_NAMES.get(model_key, model_key),
                "pareto": model_key in pareto_models,
                "opb": float(standard["opb_error_rate"]),
                "upb": float(standard["upb_error_rate"]),
                "metrics": values[model_key],
                "ranks": ranks[model_key],
                "risk": profiles[model_key],
            }
        )
    models.sort(key=lambda item: (item["ranks"]["h"], item["name"]))
    return {
        "schema_version": "memcalib-candidate-metric-visualization-v1",
        "models": models,
        "metric_columns": [
            {
                "key": key,
                "label": label,
                "higher_is_better": higher_is_better,
            }
            for key, label, higher_is_better in metric_columns
        ],
        "tail_definition": {
            "condition": "full_memory",
            "sample_loss": "mean absolute A/B/C ordinal distance divided by two",
            "alpha": 0.90,
            "tail_samples_per_model": next(iter(profiles.values()))["tail_samples"],
        },
    }


def render_fragment(data: dict[str, Any]) -> str:
    encoded = html.escape(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        quote=False,
    )
    return f"""<div id="memcalib-metric-diagnostics" class="memcalib-diagnostics">
  <section class="diagnostic-section" aria-labelledby="tail-profile-label">
    <div class="section-label" id="tail-profile-label">Full-memory sample-loss quantiles, shared 0–1 scale</div>
    <div class="tail-grid" id="memcalib-tail-grid"></div>
  </section>
  <section class="diagnostic-section" aria-labelledby="pareto-label">
    <div class="section-label" id="pareto-label">OPB–UPB error plane; lower-left is better</div>
    <svg id="memcalib-pareto" class="pareto-chart" viewBox="0 0 960 470" role="img" aria-label="OPB versus UPB Pareto plot"></svg>
  </section>
  <section class="diagnostic-section" aria-labelledby="rank-label">
    <div class="section-label" id="rank-label">Metric-sensitive ranks</div>
    <div class="rank-table-wrap">
      <table class="rank-table" id="memcalib-rank-table"></table>
    </div>
  </section>
</div>
<script type="application/json" id="memcalib-metric-diagnostics-data">{encoded}</script>
<style>
#memcalib-metric-diagnostics {{
  --mc-foreground: var(--foreground, CanvasText);
  --mc-background: var(--background, Canvas);
  --mc-border: var(
    --border,
    color-mix(in srgb, CanvasText 16%, transparent)
  );
  --mc-muted: var(--muted-foreground, GrayText);
  --mc-series-1: var(--viz-series-1, LinkText);
  --mc-series-2: var(--viz-series-2, AccentColor);
  color: var(--mc-foreground);
  background: transparent;
  width: 100%;
  letter-spacing: 0;
}}
#memcalib-metric-diagnostics .diagnostic-section {{
  padding: 14px 0 18px;
  border-top: 1px solid var(--mc-border);
}}
#memcalib-metric-diagnostics .diagnostic-section:first-child {{
  border-top: 0;
  padding-top: 0;
}}
#memcalib-metric-diagnostics .section-label {{
  color: var(--mc-foreground);
  font-weight: 500;
  margin: 0 0 10px;
}}
#memcalib-metric-diagnostics .tail-grid {{
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 18px;
}}
#memcalib-metric-diagnostics .tail-facet {{
  margin: 0;
  min-width: 0;
}}
#memcalib-metric-diagnostics .facet-caption {{
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: baseline;
  margin-bottom: 2px;
}}
#memcalib-metric-diagnostics .facet-name {{
  color: var(--mc-foreground);
  font-weight: 500;
}}
#memcalib-metric-diagnostics .facet-value,
#memcalib-metric-diagnostics .axis-label,
#memcalib-metric-diagnostics .point-label {{
  color: var(--mc-muted);
}}
#memcalib-metric-diagnostics svg {{
  display: block;
  width: 100%;
  height: auto;
  overflow: visible;
}}
#memcalib-metric-diagnostics .grid-line {{
  stroke: var(--mc-border);
  stroke-width: 1;
}}
#memcalib-metric-diagnostics .axis-line {{
  stroke: var(--mc-muted);
  stroke-width: 1;
}}
#memcalib-metric-diagnostics .tail-line {{
  fill: none;
  stroke: var(--mc-series-1);
  stroke-width: 2;
}}
#memcalib-metric-diagnostics .tail-zone {{
  fill: color-mix(in srgb, var(--mc-series-2) 12%, transparent);
}}
#memcalib-metric-diagnostics .cvar-line {{
  stroke: var(--mc-series-2);
  stroke-width: 1.5;
  stroke-dasharray: 5 4;
}}
#memcalib-metric-diagnostics .pareto-point {{
  fill: var(--mc-series-1);
  stroke: var(--mc-background);
  stroke-width: 2;
}}
#memcalib-metric-diagnostics .dominated-point {{
  fill: var(--mc-muted);
  stroke: var(--mc-background);
  stroke-width: 2;
}}
#memcalib-metric-diagnostics .label-connector {{
  stroke: var(--mc-muted);
  stroke-width: 1;
}}
#memcalib-metric-diagnostics text {{
  fill: var(--mc-foreground);
  font-family: inherit;
  font-size: var(--font-size-base, 14px);
  font-weight: 400;
  letter-spacing: 0;
}}
#memcalib-metric-diagnostics text.tick,
#memcalib-metric-diagnostics text.point-note {{
  fill: var(--mc-muted);
}}
#memcalib-metric-diagnostics .rank-table-wrap {{
  overflow-x: auto;
}}
#memcalib-metric-diagnostics .rank-table {{
  width: 100%;
  border-collapse: collapse;
  min-width: 680px;
}}
#memcalib-metric-diagnostics .rank-table th,
#memcalib-metric-diagnostics .rank-table td {{
  padding: 6px 4px;
  border-bottom: 1px solid var(--mc-border);
  text-align: center;
  white-space: nowrap;
}}
#memcalib-metric-diagnostics .rank-table th:first-child,
#memcalib-metric-diagnostics .rank-table td:first-child {{
  text-align: left;
}}
#memcalib-metric-diagnostics .rank-table th {{
  color: var(--mc-muted);
  font-weight: 500;
}}
#memcalib-metric-diagnostics .rank-cell {{
  background: color-mix(
    in srgb,
    var(--mc-series-1) var(--rank-strength),
    transparent
  );
}}
#memcalib-metric-diagnostics .rank-number {{
  font-weight: 500;
}}
#memcalib-metric-diagnostics .rank-value {{
  color: var(--mc-muted);
  display: block;
}}
@media (max-width: 620px) {{
  #memcalib-metric-diagnostics .tail-grid {{
    grid-template-columns: minmax(0, 1fr);
  }}
}}
</style>
<script>
(() => {{
  const root = document.getElementById("memcalib-metric-diagnostics");
  const dataNode = document.getElementById("memcalib-metric-diagnostics-data");
  if (!root || !dataNode) return;
  const data = JSON.parse(dataNode.textContent);
  const NS = "http://www.w3.org/2000/svg";

  function svgNode(tag, attrs = {{}}, text = "") {{
    const node = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
    if (text) node.textContent = text;
    return node;
  }}

  function scale(value, inMin, inMax, outMin, outMax) {{
    return outMin + ((value - inMin) / (inMax - inMin)) * (outMax - outMin);
  }}

  function drawTailFacets() {{
    const grid = root.querySelector("#memcalib-tail-grid");
    data.models.forEach((model) => {{
      const figure = document.createElement("figure");
      figure.className = "tail-facet";
      figure.setAttribute(
        "aria-label",
        `${{model.name}} loss quantiles; CVaR90 ${{model.risk.cvar90.toFixed(3)}}`
      );
      const caption = document.createElement("figcaption");
      caption.className = "facet-caption";
      const name = document.createElement("span");
      name.className = "facet-name";
      name.textContent = model.name;
      const value = document.createElement("span");
      value.className = "facet-value";
      value.textContent = `CVaR90 ${{model.risk.cvar90.toFixed(3)}}`;
      caption.append(name, value);
      figure.appendChild(caption);

      const svg = svgNode("svg", {{
        viewBox: "0 0 430 170",
        role: "img",
        "aria-label": `${{model.name}} upper-tail empirical quantile curve`,
      }});
      const left = 34, right = 414, top = 10, bottom = 142;
      const x = (p) => scale(p, 70, 100, left, right);
      const y = (loss) => scale(loss, 0, 1, bottom, top);
      svg.appendChild(svgNode("rect", {{
        x: x(90),
        y: top,
        width: right - x(90),
        height: bottom - top,
        class: "tail-zone",
      }}));
      [0, 0.5, 1].forEach((tick) => {{
        svg.appendChild(svgNode("line", {{
          x1: left, y1: y(tick), x2: right, y2: y(tick), class: "grid-line",
        }}));
        svg.appendChild(svgNode("text", {{
          x: left - 7, y: y(tick) + 4, "text-anchor": "end", class: "tick",
        }}, tick.toFixed(1)));
      }});
      [70, 80, 90, 100].forEach((tick) => {{
        svg.appendChild(svgNode("text", {{
          x: x(tick), y: bottom + 19, "text-anchor": "middle", class: "tick",
        }}, `${{tick}}`));
      }});
      svg.appendChild(svgNode("line", {{
        x1: left, y1: bottom, x2: right, y2: bottom, class: "axis-line",
      }}));
      svg.appendChild(svgNode("line", {{
        x1: left, y1: top, x2: left, y2: bottom, class: "axis-line",
      }}));
      const path = model.risk.quantile_curve
        .map((point, index) =>
          `${{index === 0 ? "M" : "L"}}${{x(point.percentile).toFixed(2)}},${{y(point.loss).toFixed(2)}}`
        )
        .join(" ");
      svg.appendChild(svgNode("path", {{d: path, class: "tail-line"}}));
      svg.appendChild(svgNode("line", {{
        x1: x(90),
        y1: y(model.risk.cvar90),
        x2: right,
        y2: y(model.risk.cvar90),
        class: "cvar-line",
      }}));
      figure.appendChild(svg);
      grid.appendChild(figure);
    }});
  }}

  function drawPareto() {{
    const svg = root.querySelector("#memcalib-pareto");
    const left = 72, right = 920, top = 30, bottom = 408;
    const xMin = 0.15, xMax = 0.45, yMin = 0.15, yMax = 0.48;
    const x = (value) => scale(value, xMin, xMax, left, right);
    const y = (value) => scale(value, yMin, yMax, bottom, top);
    [0.2, 0.3, 0.4].forEach((tick) => {{
      svg.appendChild(svgNode("line", {{
        x1: x(tick), y1: top, x2: x(tick), y2: bottom, class: "grid-line",
      }}));
      svg.appendChild(svgNode("text", {{
        x: x(tick), y: bottom + 24, "text-anchor": "middle", class: "tick",
      }}, tick.toFixed(1)));
    }});
    [0.2, 0.3, 0.4].forEach((tick) => {{
      svg.appendChild(svgNode("line", {{
        x1: left, y1: y(tick), x2: right, y2: y(tick), class: "grid-line",
      }}));
      svg.appendChild(svgNode("text", {{
        x: left - 12, y: y(tick) + 5, "text-anchor": "end", class: "tick",
      }}, tick.toFixed(1)));
    }});
    svg.appendChild(svgNode("line", {{
      x1: left, y1: bottom, x2: right, y2: bottom, class: "axis-line",
    }}));
    svg.appendChild(svgNode("line", {{
      x1: left, y1: top, x2: left, y2: bottom, class: "axis-line",
    }}));
    svg.appendChild(svgNode("text", {{
      x: (left + right) / 2, y: 458, "text-anchor": "middle", class: "tick",
    }}, "OPB"));
    svg.appendChild(svgNode("text", {{
      x: 19, y: (top + bottom) / 2, transform: `rotate(-90 19 ${{(top + bottom) / 2}})`,
      "text-anchor": "middle", class: "tick",
    }}, "UPB"));
    svg.appendChild(svgNode("text", {{
      x: left + 5, y: bottom - 8, class: "point-note",
    }}, "ideal"));

    const offsets = {{
      "codex-gpt56-sol": [10, -13],
      "kimi": [10, -12],
      "deepseek": [-80, 33],
      "deepseek-flash": [40, -43],
      "qwen-flash": [40, -13],
      "qwen-max": [-80, -35],
      "qwen3-8b": [10, -12],
      "qwen35-35b-a3b": [25, 25],
    }};
    data.models.forEach((model) => {{
      const pointClass = model.pareto ? "pareto-point" : "dominated-point";
      svg.appendChild(svgNode("circle", {{
        cx: x(model.opb), cy: y(model.upb), r: model.pareto ? 8 : 6,
        class: pointClass,
      }}));
      const [dx, dy] = offsets[model.key] || [8, -8];
      if (Math.abs(dx) > 20 || Math.abs(dy) > 20) {{
        svg.appendChild(svgNode("line", {{
          x1: x(model.opb),
          y1: y(model.upb),
          x2: x(model.opb) + dx,
          y2: y(model.upb) + dy - 4,
          class: "label-connector",
        }}));
      }}
      svg.appendChild(svgNode("text", {{
        x: x(model.opb) + dx,
        y: y(model.upb) + dy,
        "text-anchor": dx < 0 ? "end" : "start",
        class: "point-note",
      }}, model.short_name));
    }});
  }}

  function drawRankTable() {{
    const table = root.querySelector("#memcalib-rank-table");
    const head = document.createElement("thead");
    const headerRow = document.createElement("tr");
    const modelHeader = document.createElement("th");
    modelHeader.scope = "col";
    modelHeader.textContent = "Model";
    headerRow.appendChild(modelHeader);
    data.metric_columns.forEach((metric) => {{
      const th = document.createElement("th");
      th.scope = "col";
      th.textContent = `${{metric.label}}${{metric.higher_is_better ? "↑" : "↓"}}`;
      headerRow.appendChild(th);
    }});
    head.appendChild(headerRow);
    table.appendChild(head);

    const body = document.createElement("tbody");
    data.models.forEach((model) => {{
      const row = document.createElement("tr");
      const name = document.createElement("th");
      name.scope = "row";
      name.textContent = model.short_name;
      name.setAttribute("aria-label", model.name);
      row.appendChild(name);
      data.metric_columns.forEach((metric) => {{
        const rank = model.ranks[metric.key];
        const value = model.metrics[metric.key];
        const cell = document.createElement("td");
        cell.className = "rank-cell";
        cell.style.setProperty("--rank-strength", `${{38 - rank * 4}}%`);
        cell.setAttribute(
          "aria-label",
          `${{model.name}} ${{metric.label}} rank ${{rank}}, value ${{value.toFixed(3)}}`
        );
        const rankSpan = document.createElement("span");
        rankSpan.className = "rank-number";
        rankSpan.textContent = `#${{rank}}`;
        const valueSpan = document.createElement("span");
        valueSpan.className = "rank-value";
        valueSpan.textContent = value.toFixed(3);
        cell.append(rankSpan, valueSpan);
        row.appendChild(cell);
      }});
      body.appendChild(row);
    }});
    table.appendChild(body);
  }}

  drawTailFacets();
  drawPareto();
  drawRankTable();
}})();
</script>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", type=Path, default=DEFAULT_PRIMARY)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    rows = list(iter_jsonl(args.primary))
    metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    profiles = build_tail_profiles(rows)
    data = build_visualization_data(metrics, profiles)
    fragment = render_fragment(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(fragment, encoding="utf-8")

    manifest = {
        "schema_version": "memcalib-candidate-metric-visualization-manifest-v1",
        "inputs": {
            "primary": {
                "path": _portable_path(args.primary),
                "sha256": _sha256(args.primary),
            },
            "metrics": {
                "path": _portable_path(args.metrics),
                "sha256": _sha256(args.metrics),
            },
        },
        "script": {
            "path": _portable_path(Path(__file__).resolve()),
            "sha256": _sha256(Path(__file__).resolve()),
        },
        "output": {
            "path": _portable_path(args.output),
            "sha256": _sha256(args.output),
            "bytes": args.output.stat().st_size,
        },
        "integrity": {
            "models": len(data["models"]),
            "samples_per_model": sorted(
                {model["risk"]["samples"] for model in data["models"]}
            ),
            "tail_samples_per_model": sorted(
                {model["risk"]["tail_samples"] for model in data["models"]}
            ),
        },
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.manifest, manifest)
    print(
        json.dumps(
            {
                "models": len(data["models"]),
                "samples_per_model": manifest["integrity"]["samples_per_model"],
                "tail_samples_per_model": manifest["integrity"][
                    "tail_samples_per_model"
                ],
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
