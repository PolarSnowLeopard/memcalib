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
DEFAULT_METRICS = ROOT / "evaluation" / "releases" / "memcalib-v0.1-500" / "metrics.json"
DEFAULT_REPORT = ROOT / "evaluation" / "releases" / "memcalib-v0.1-500" / "report.html"
CORRECT_VERDICT = {"A": "correct_suppression", "B": "correct_bounded_use", "C": "correct_control"}


def _flatten(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    atoms = []
    for row in rows:
        for atom in row["atom_judgments"]:
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
                    "confidence": atom["confidence"],
                    "success": int(atom["verdict"] == CORRECT_VERDICT[atom["u_star"]]),
                }
            )
    return atoms


def _condition_metrics(rows: list[dict[str, Any]], atoms: list[dict[str, Any]], condition: str) -> dict[str, Any]:
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
    return {
        "answers": len(condition_rows),
        "atoms": len(condition_atoms),
        "label_counts": label_counts,
        "label_success": label_success,
        "memcalib_score": fmean(complete_label_scores) if complete_label_scores else None,
        "strict_sample_accuracy": fmean(strict) if strict else None,
        "verdict_counts": dict(sorted(verdict_counts.items())),
        "mean_task_quality": fmean(row["task_quality"] for row in condition_rows) if condition_rows else None,
        "safety_failure_rate": fmean(int(row["safety_failure"]) for row in condition_rows) if condition_rows else None,
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


def compute_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    models = sorted({str(row["model_key"]) for row in rows})
    result = {"schema_version": "memcalib-evaluation-metrics-v1", "models": {}}
    for model in models:
        model_rows = [row for row in rows if row["model_key"] == model]
        atoms = _flatten(model_rows)
        panel_metrics = {}
        for panel in ("representative", "diagnostic"):
            panel_rows = [row for row in model_rows if row["panel"] == panel]
            panel_atoms = _flatten(panel_rows)
            panel_metrics[panel] = {
                "full_memory": _condition_metrics(panel_rows, panel_atoms, "full_memory"),
                "no_memory": _condition_metrics(panel_rows, panel_atoms, "no_memory"),
                "paired": _paired_metrics(panel_atoms),
            }
        result["models"][model] = {
            "full_memory": _condition_metrics(model_rows, atoms, "full_memory"),
            "no_memory": _condition_metrics(model_rows, atoms, "no_memory"),
            "paired": _paired_metrics(atoms),
            "panels": panel_metrics,
        }
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


def compute_judge_agreement(primary: list[dict[str, Any]], secondary: list[dict[str, Any]]) -> dict[str, Any]:
    primary_atoms = {
        (row["answer_request_id"], atom["atom_id"]): atom
        for row in primary
        for atom in row["atom_judgments"]
    }
    pairs = []
    for row in secondary:
        for atom in row["atom_judgments"]:
            key = (row["answer_request_id"], atom["atom_id"])
            if key in primary_atoms:
                pairs.append((atom["u_star"], primary_atoms[key]["verdict"], atom["verdict"], row["judge_model"]))
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
    return {"overall": overall, "by_label": by_label, "by_secondary_judge": by_pair}


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
    rng = random.Random(seed)
    estimates = []
    for _ in range(replicates):
        sampled = [rng.choice(clusters) for _ in clusters]
        flattened = [value for cluster in sampled for value in by_cluster[cluster]]
        estimates.append(fmean(flattened))
    estimate = fmean(value for _, value in values)
    return {
        "estimate": estimate,
        "ci_low": _percentile(estimates, 0.025),
        "ci_high": _percentile(estimates, 0.975),
        "replicates": replicates,
        "clusters": len(clusters),
    }


def render_report(metrics: dict[str, Any]) -> str:
    cards = []
    rows = []
    for model, values in metrics["models"].items():
        full = values["full_memory"]
        paired = values["paired"]
        score = full["memcalib_score"] or 0
        cards.append(f'<article class="model-card"><span>{html.escape(model)}</span><strong>{score:.3f}</strong><small>MemCalib Score</small></article>')
        rows.append(
            "<tr>"
            f"<td>{html.escape(model)}</td>"
            f"<td>{score:.3f}</td>"
            f"<td>{full['label_success']['A']:.3f}</td>"
            f"<td>{full['label_success']['B']:.3f}</td>"
            f"<td>{full['label_success']['C']:.3f}</td>"
            f"<td>{paired['delta_C']:.3f}</td>"
            f"<td>{paired['A_contamination_effect']:.3f}</td>"
            "</tr>"
        )
    payload = html.escape(json.dumps(metrics, ensure_ascii=False))
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MemCalib 500 验证报告</title><style>
:root{{--ink:#172033;--muted:#667085;--line:#dfe4ec;--paper:#fff;--bg:#f4f6f8;--teal:#0f766e;--red:#b42318}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;letter-spacing:0}}
header{{background:#152238;color:#fff;padding:44px max(24px,calc((100vw - 1180px)/2)) 38px}}header p{{color:#cbd5e1;max-width:760px;margin:8px 0 0}}
main{{max-width:1180px;margin:0 auto;padding:28px 24px 60px}}h1{{font-size:32px;margin:0}}h2{{font-size:20px;margin:34px 0 12px}}
.cards{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}}.model-card{{background:var(--paper);border:1px solid var(--line);border-radius:6px;padding:18px;min-width:0}}
.model-card span,.model-card small{{display:block;color:var(--muted);overflow-wrap:anywhere}}.model-card strong{{display:block;font-size:28px;color:var(--teal);margin:10px 0 2px}}
.panel{{background:var(--paper);border:1px solid var(--line);border-radius:6px;padding:18px;overflow:auto}}table{{width:100%;border-collapse:collapse;min-width:760px}}th,td{{padding:11px 12px;border-bottom:1px solid var(--line);text-align:right}}th:first-child,td:first-child{{text-align:left}}th{{color:var(--muted);font-size:12px;text-transform:uppercase}}
details{{margin-top:30px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#111827;color:#e5e7eb;padding:16px;border-radius:6px}}
@media(max-width:800px){{.cards{{grid-template-columns:1fr 1fr}}header{{padding:30px 20px}}main{{padding:20px 14px}}}}
</style></head><body><header><h1>MemCalib 500 验证报告</h1><p>五个代表性模型在 Full-memory 与 No-memory 配对条件下的记忆使用校准结果。</p></header>
<main><section class="cards">{''.join(cards)}</section><h2>核心结果</h2><section class="panel"><table><thead><tr><th>模型</th><th>总分</th><th>A 抑制</th><th>B 有限使用</th><th>C 控制</th><th>C 配对增益</th><th>A 污染效应</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section>
<details><summary>机器可读指标</summary><pre id="raw">{payload}</pre></details></main></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze validated MemCalib judgments.")
    parser.add_argument("--primary", type=Path, default=DEFAULT_PRIMARY)
    parser.add_argument("--secondary", type=Path, default=DEFAULT_SECONDARY)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    primary = list(iter_jsonl(args.primary))
    secondary = list(iter_jsonl(args.secondary)) if args.secondary.exists() else []
    metrics = compute_metrics(primary)
    metrics["judge_agreement"] = compute_judge_agreement(primary, secondary)
    write_json(args.metrics, metrics)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(metrics), encoding="utf-8")
    print(json.dumps({"metrics": str(args.metrics), "report": str(args.report), "models": len(metrics["models"])}, indent=2))


if __name__ == "__main__":
    main()
