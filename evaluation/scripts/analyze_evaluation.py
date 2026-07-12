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
    result = {"schema_version": "memcalib-evaluation-metrics-v1", "models": {}}
    for model in models:
        model_rows = [row for row in rows if row["model_key"] == model]
        atoms = _flatten(model_rows)
        panel_metrics = {}
        for panel in ("representative", "diagnostic"):
            panel_rows = [row for row in model_rows if row["panel"] == panel]
            panel_atoms = _flatten(panel_rows)
            panel_samples = {
                sample_id: sample
                for sample_id, sample in all_samples_by_id.items()
                if any(row["sample_id"] == sample_id for row in panel_rows)
            }
            panel_metrics[panel] = {
                "full_memory": _condition_metrics(panel_rows, panel_atoms, "full_memory", panel_samples),
                "no_memory": _condition_metrics(panel_rows, panel_atoms, "no_memory", panel_samples),
                "paired": _paired_metrics(panel_atoms),
            }
        result["models"][model] = {
            "full_memory": _condition_metrics(model_rows, atoms, "full_memory", all_samples_by_id),
            "no_memory": _condition_metrics(model_rows, atoms, "no_memory", all_samples_by_id),
            "paired": _paired_metrics(atoms),
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


def assess_benchmark_validity(metrics: dict[str, Any]) -> dict[str, Any]:
    models = metrics.get("models") or {}
    scores = [
        float(values["full_memory"]["memcalib_score"])
        for values in models.values()
        if values.get("full_memory", {}).get("memcalib_score") is not None
    ]
    positive_c = sum((values.get("paired", {}).get("delta_C") or 0) > 0 for values in models.values())
    agreement = metrics.get("judge_agreement", {}).get("overall", {})
    checks = {
        "five_models_complete": len(scores) == 5,
        "model_score_spread_at_least_0.03": bool(scores) and max(scores) - min(scores) >= 0.03,
        "positive_C_delta_in_at_least_four_models": positive_c >= 4,
        "judge_exact_agreement_at_least_0.75": (agreement.get("exact_agreement") or 0) >= 0.75,
        "judge_kappa_at_least_0.60": (agreement.get("kappa") or 0) >= 0.60,
    }
    failed = [key for key, passed in checks.items() if not passed]
    return {
        "status": "provisionally_supported" if not failed else "needs_review",
        "checks": checks,
        "failed_checks": failed,
        "model_score_spread": max(scores) - min(scores) if scores else None,
        "models_with_positive_C_delta": positive_c,
        "human_validation": "pending",
    }


def _format_metric(value: Any, digits: int = 3) -> str:
    return "—" if value is None else f"{float(value):.{digits}f}"


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
        full = values["full_memory"]
        paired = values["paired"]
        score = full["memcalib_score"] or 0
        bootstrap = values.get("bootstrap", {}).get("full_memory_label_success", {})
        score_cards.append(
            f'<article class="model-card"><span>{html.escape(model)}</span><strong>{score:.3f}</strong>'
            f'<small>严格样本正确率 {_format_metric(full.get("strict_sample_accuracy"))}</small></article>'
        )
        core_rows.append(
            "<tr>"
            f"<td>{html.escape(model)}</td>"
            f"<td>{score:.3f}</td>"
            f"<td>{_format_metric(full['label_success']['A'])}</td>"
            f"<td>{_format_metric(full['label_success']['B'])}</td>"
            f"<td>{_format_metric(full['label_success']['C'])}</td>"
            f"<td>{_format_metric(full.get('strict_sample_accuracy'))}</td>"
            f"<td>{_format_metric(full.get('mixed_parent_strict_accuracy'))}</td>"
            "</tr>"
        )
        effect_rows.append(
            f'<article class="effect-group"><h3>{html.escape(model)}</h3>'
            + _effect_rail("B 使用增益", paired.get("delta_B"), "blue")
            + _effect_rail("C 控制增益", paired.get("delta_C"), "teal")
            + _effect_rail("A 污染效应", paired.get("A_contamination_effect"), "red")
            + "</article>"
        )
        representative = values["panels"]["representative"]["full_memory"]
        diagnostic = values["panels"]["diagnostic"]["full_memory"]
        panel_rows.append(
            "<tr>"
            f"<td>{html.escape(model)}</td><td>{_format_metric(representative['memcalib_score'])}</td>"
            f"<td>{_format_metric(diagnostic['memcalib_score'])}</td>"
            f"<td>{_format_metric((diagnostic['memcalib_score'] or 0) - (representative['memcalib_score'] or 0))}</td>"
            f"<td>{_format_metric(representative.get('mixed_parent_strict_accuracy'))}</td>"
            f"<td>{_format_metric(diagnostic.get('mixed_parent_strict_accuracy'))}</td></tr>"
        )
        verdicts = full.get("verdict_counts") or {}
        total_verdicts = sum(verdicts.values()) or 1
        error_rows.append(
            "<tr>"
            f"<td>{html.escape(model)}</td>"
            f"<td>{verdicts.get('under_use', 0) / total_verdicts:.3f}</td>"
            f"<td>{verdicts.get('over_use', 0) / total_verdicts:.3f}</td>"
            f"<td>{verdicts.get('contradiction', 0) / total_verdicts:.3f}</td>"
            f"<td>{verdicts.get('unscorable', 0) / total_verdicts:.3f}</td>"
            f"<td>{_format_metric(full.get('mean_task_quality'))}</td>"
            f"<td>{_format_metric(full.get('safety_failure_rate'))}</td></tr>"
        )
    assessment = metrics.get("validity_assessment") or assess_benchmark_validity(metrics)
    status = assessment.get("status", "pending")
    status_label = {
        "provisionally_supported": "初步支持",
        "needs_review": "需要复核",
        "pending": "等待评分",
    }.get(status, status)
    failed_checks = assessment.get("failed_checks") or []
    agreement = metrics.get("judge_agreement") or {}
    overall_agreement = agreement.get("overall") or {}
    agreement_rows = []
    for label, values in (agreement.get("by_label") or {}).items():
        agreement_rows.append(
            f"<tr><td>{html.escape(label)}</td><td>{values.get('n', 0)}</td>"
            f"<td>{_format_metric(values.get('exact_agreement'))}</td><td>{_format_metric(values.get('kappa'))}</td></tr>"
        )
    payload = html.escape(json.dumps(metrics, ensure_ascii=False))
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MemCalib 500 验证报告</title><style>
:root{{--ink:#182230;--muted:#667085;--line:#d5dce6;--paper:#fff;--bg:#f2f4f7;--nav:#17253d;--teal:#087d71;--blue:#2667a9;--red:#b42318;--amber:#a15c00}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif;letter-spacing:0}}header{{background:var(--nav);color:#fff;padding:46px max(24px,calc((100vw - 1180px)/2)) 38px;border-bottom:5px solid var(--teal)}}header p{{color:#c9d3e1;max-width:760px;margin:8px 0 0}}header .status{{display:inline-flex;align-items:center;gap:8px;margin-top:18px;padding:6px 10px;border:1px solid #ffffff38;border-radius:4px}}header .status b{{color:#75e0d3}}
main{{max-width:1180px;margin:0 auto;padding:26px 24px 64px}}h1{{font-size:32px;margin:0}}h2{{font-size:20px;margin:38px 0 6px}}.section-note{{color:var(--muted);margin:0 0 14px}}.cards{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}}.model-card{{background:var(--paper);border:1px solid var(--line);border-radius:5px;padding:16px;min-width:0}}.model-card span,.model-card small{{display:block;color:var(--muted);overflow-wrap:anywhere}}.model-card strong{{display:block;font:700 28px/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--teal);margin:10px 0 4px}}
.panel{{background:var(--paper);border:1px solid var(--line);border-radius:5px;padding:16px;overflow:auto}}table{{width:100%;border-collapse:collapse;min-width:760px}}th,td{{padding:10px 11px;border-bottom:1px solid var(--line);text-align:right}}th:first-child,td:first-child{{text-align:left}}th{{color:var(--muted);font-size:12px}}tbody tr:last-child td{{border-bottom:0}}.effects{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}.effect-group{{background:#fff;border:1px solid var(--line);border-radius:5px;padding:15px}}.effect-group h3{{font-size:14px;margin:0 0 10px}}.effect{{display:grid;grid-template-columns:82px 1fr 52px;gap:9px;align-items:center;margin:8px 0}}.effect-label{{font-size:12px;color:var(--muted)}}.rail{{height:10px;background:#e8ecf2;position:relative;border-radius:2px}}.rail:after{{content:"";position:absolute;left:50%;top:-3px;bottom:-3px;width:1px;background:#8793a5}}.marker{{position:absolute;top:-3px;width:5px;height:16px;transform:translateX(-50%);border-radius:1px}}.teal{{color:var(--teal)}}.blue{{color:var(--blue)}}.red{{color:var(--red)}}.marker.teal{{background:var(--teal)}}.marker.blue{{background:var(--blue)}}.marker.red{{background:var(--red)}}.effect strong{{font:650 12px ui-monospace,SFMono-Regular,Menlo,monospace;text-align:right}}.checks{{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}}.check{{font-size:12px;padding:4px 7px;background:#fff;border:1px solid var(--line);border-radius:4px}}.check.fail{{border-color:#f0b8b2;color:var(--red)}}details{{margin-top:34px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#111827;color:#e5e7eb;padding:16px;border-radius:5px}}
@media(max-width:820px){{.cards{{grid-template-columns:1fr 1fr}}.effects{{grid-template-columns:1fr}}header{{padding:30px 18px}}main{{padding:18px 14px}}}}
</style></head><body><header><h1>MemCalib 500 验证报告</h1><p>五个代表性模型在 Full-memory 与 No-memory 配对条件下的记忆使用校准结果。正式结论需结合人工复核。</p><div class="status"><span>Benchmark 状态</span><b>{html.escape(status_label)}</b></div></header>
<main><div class="checks">{''.join(f'<span class="check fail">{html.escape(item)}</span>' for item in failed_checks) if failed_checks else '<span class="check">全部预设自动检查通过</span>'}<span class="check">人工一致性：待完成</span></div>
<h2>模型区分度</h2><p class="section-note">主指标使用 Full-memory 条件，A/B/C 三类等权宏平均。</p><section class="cards">{''.join(score_cards)}</section><section class="panel" style="margin-top:10px"><table><thead><tr><th>模型</th><th>总分</th><th>A 抑制</th><th>B 有限使用</th><th>C 控制</th><th>样本严格</th><th>混合父记忆严格</th></tr></thead><tbody>{''.join(core_rows)}</tbody></table></section>
<h2>配对效应</h2><p class="section-note">轨道中心为 0。B/C 向右表示记忆带来有效增益；A 污染向右表示加入记忆后错误增加。</p><section class="effects">{''.join(effect_rows)}</section>
<h2>面板比较</h2><p class="section-note">Representative 贴近正式集分布；Diagnostic 定向覆盖混合标签、稀有 Hard-A、安全敏感和高原子数样本。</p><section class="panel"><table><thead><tr><th>模型</th><th>Representative</th><th>Diagnostic</th><th>Diagnostic 差值</th><th>Rep 混合严格</th><th>Diag 混合严格</th></tr></thead><tbody>{''.join(panel_rows)}</tbody></table></section>
<h2>错误方向</h2><section class="panel"><table><thead><tr><th>模型</th><th>Under-use</th><th>Over-use</th><th>Contradiction</th><th>Unscorable</th><th>回答质量</th><th>安全失败</th></tr></thead><tbody>{''.join(error_rows)}</tbody></table></section>
<h2>Judge 一致性</h2><p class="section-note">总体 n={overall_agreement.get('n', 0)}，exact={_format_metric(overall_agreement.get('exact_agreement'))}，κ={_format_metric(overall_agreement.get('kappa'))}。</p><section class="panel"><table><thead><tr><th>标签</th><th>原子数</th><th>Exact</th><th>Cohen κ</th></tr></thead><tbody>{''.join(agreement_rows) or '<tr><td colspan="4">复核评分尚未完成</td></tr>'}</tbody></table></section>
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
    metrics["validity_assessment"] = assess_benchmark_validity(metrics)
    write_json(args.metrics, metrics)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(metrics), encoding="utf-8")
    print(json.dumps({"metrics": str(args.metrics), "report": str(args.report), "models": len(metrics["models"])}, indent=2))


if __name__ == "__main__":
    main()
