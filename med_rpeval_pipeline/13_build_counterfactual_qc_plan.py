#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path
from typing import Any

from utils import iter_jsonl, norm_text, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = SCRIPT_DIR / "data" / "crk2_canonical_memory_benchmark_100.jsonl"
DEFAULT_OUTPUT = SCRIPT_DIR / "data" / "crk2_canonical_counterfactual_qc_plan_100.jsonl"
DEFAULT_HTML = SCRIPT_DIR / "data" / "crk2_canonical_counterfactual_qc_plan_100.html"


def block_text_by_id(sample: dict[str, Any]) -> dict[str, str]:
    return {
        str(block.get("parent_memory_id", "")): norm_text(str(block.get("memory_text") or block.get("text", "")))
        for block in sample.get("memory_blocks", [])
    }


def contamination_signals(rubric: dict[str, Any]) -> str:
    signals = rubric.get("contamination_signals")
    if isinstance(signals, list):
        return "；".join(str(signal) for signal in signals)
    return ""


def row_for_memory(sample: dict[str, Any], memory: dict[str, Any], parent_text: str) -> dict[str, str]:
    label = str(memory.get("u_star", ""))
    rubric = memory.get("usage_rubric") if isinstance(memory.get("usage_rubric"), dict) else {}
    if label == "C":
        counterfactual_type = "remove_or_mask_C"
        operation = "从 model-facing parent memory 中移除或遮蔽该 C atom 的语义，其他记忆尽量保持不变。"
        expected_change = "回答主干应发生可观察变化；若主干不变，说明该 C 记忆可能并非真正 answer-controlling。"
        failure_signal = norm_text(str(rubric.get("missing_memory_failure") or rubric.get("under_use", "")))
        priority = "high"
    elif label == "B":
        counterfactual_type = "remove_or_mask_B"
        operation = "从 model-facing parent memory 中移除或遮蔽该 B atom 的语义，保留核心 C 信息。"
        expected_change = "回答主干应基本稳定，但局部解释、语气、执行细节或次要优先级应下降。"
        failure_signal = norm_text(str(rubric.get("under_use") or rubric.get("maximum_footprint", "")))
        priority = "medium"
    else:
        counterfactual_type = "A_overuse_probe"
        operation = "保留该 A atom，并检查模型回答是否错误提及、暗示或受其影响。"
        expected_change = "理想回答不应出现该 A 记忆的 footprint；若使用该记忆，应判为 over-use。"
        failure_signal = norm_text(str(rubric.get("over_use", "")))
        extra = contamination_signals(rubric)
        if extra:
            failure_signal = f"{failure_signal}；{extra}" if failure_signal else extra
        priority = "high" if memory.get("source") == "synthetic_hard_a" else "medium"

    return {
        "sample_id": str(sample.get("id", "")),
        "source_topic": str(sample.get("source_topic", "")),
        "question": norm_text(str(sample.get("question", ""))),
        "parent_memory_id": str(memory.get("parent_memory_id", "")),
        "parent_memory_text": parent_text,
        "atom_id": str(memory.get("atom_id", "")),
        "atom_label": label,
        "atom_text": norm_text(str(memory.get("text", ""))),
        "counterfactual_type": counterfactual_type,
        "model_memory_operation": operation,
        "expected_change": expected_change,
        "failure_signal": failure_signal,
        "rubric_reference": json.dumps(rubric, ensure_ascii=False, sort_keys=True),
        "priority": priority,
    }


def build_counterfactual_rows(samples: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = []
    for sample in samples:
        parents = block_text_by_id(sample)
        for memory in sample.get("memories", []):
            parent_text = parents.get(str(memory.get("parent_memory_id", "")), "")
            rows.append(row_for_memory(sample, memory, parent_text))
    return rows


def summarize_rows(rows: list[dict[str, str]], samples: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    type_counts = Counter(row["counterfactual_type"] for row in rows)
    priority_counts = Counter(row["priority"] for row in rows)
    return {
        "total_samples": len(samples or []),
        "total_checks": len(rows),
        "counterfactual_type_counts": dict(type_counts),
        "priority_counts": dict(priority_counts),
    }


def cell(text: Any) -> str:
    return html.escape(str(text or "")).replace("\n", "<br>")


def write_counterfactual_html(path: Path, rows: list[dict[str, str]], summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table_rows = []
    for row in rows:
        table_rows.append(
            f"""
            <tr>
              <td>{cell(row['sample_id'])}<br><small>{cell(row['source_topic'])}</small></td>
              <td><span class="badge">{cell(row['counterfactual_type'])}</span><br><small>{cell(row['priority'])}</small></td>
              <td>{cell(row['parent_memory_text'])}<p class="atom">{cell(row['atom_id'])} · {cell(row['atom_label'])}: {cell(row['atom_text'])}</p></td>
              <td>{cell(row['model_memory_operation'])}</td>
              <td>{cell(row['expected_change'])}</td>
              <td>{cell(row['failure_signal'])}</td>
            </tr>
            """
        )

    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Counterfactual QC Plan</title>
  <style>
    :root {{
      --bg: #f7f9fc;
      --paper: #ffffff;
      --ink: #172033;
      --muted: #647084;
      --line: #d8e0ea;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.55;
      letter-spacing: 0;
    }}
    header {{ padding: 28px min(5vw, 56px) 18px; background: var(--paper); border-bottom: 1px solid var(--line); }}
    h1 {{ margin: 0; font-size: 30px; }}
    header p {{ margin: 9px 0 0; color: #3d4858; max-width: 980px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, minmax(160px, 1fr)); gap: 10px; padding: 14px min(5vw, 56px); }}
    .metric {{ background: var(--paper); border: 1px solid var(--line); border-radius: 8px; padding: 12px; }}
    .metric strong {{ display: block; font-size: 22px; }}
    .metric span {{ color: var(--muted); font-size: 13px; }}
    main {{ padding: 0 min(5vw, 56px) 48px; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--paper); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }}
    th, td {{ border-top: 1px solid var(--line); padding: 10px; vertical-align: top; text-align: left; font-size: 13px; }}
    th {{ background: #eef3f8; color: #344054; position: sticky; top: 0; z-index: 1; }}
    small {{ color: var(--muted); }}
    .badge {{ display: inline-flex; align-items: center; min-height: 23px; padding: 0 8px; border-radius: 999px; background: #172033; color: #fff; font-weight: 820; }}
    .atom {{ margin: 7px 0 0; color: #475569; font-weight: 720; }}
    @media (max-width: 900px) {{
      .metrics {{ grid-template-columns: 1fr 1fr; }}
      table {{ display: block; overflow-x: auto; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Counterfactual QC Plan</h1>
    <p>This is a hidden atom-level QC plan: the model still sees parent memories, while each check describes how to ablate or probe one annotated atom for validation.</p>
  </header>
  <section class="metrics">
    <div class="metric"><strong>{html.escape(str(summary.get('total_samples', 0)))}</strong><span>samples</span></div>
    <div class="metric"><strong>{html.escape(str(summary.get('total_checks', len(rows))))}</strong><span>atom-level checks</span></div>
    <div class="metric"><strong>{html.escape(str(summary.get('counterfactual_type_counts', {}).get('remove_or_mask_C', 0)))}</strong><span>C removals</span></div>
    <div class="metric"><strong>{html.escape(str(summary.get('counterfactual_type_counts', {}).get('A_overuse_probe', 0)))}</strong><span>A over-use probes</span></div>
  </section>
  <main>
    <table>
      <thead>
        <tr><th>sample</th><th>check</th><th>memory / atom</th><th>operation</th><th>expected change</th><th>failure signal</th></tr>
      </thead>
      <tbody>{''.join(table_rows)}</tbody>
    </table>
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build hidden atom-level counterfactual QC plan for canonical CRK-2 samples.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    args = parser.parse_args()

    samples = list(iter_jsonl(args.input))
    rows = build_counterfactual_rows(samples)
    summary = summarize_rows(rows, samples)
    write_jsonl(args.output, rows)
    write_counterfactual_html(args.html, rows, summary)
    print(json.dumps({"input": str(args.input), "output": str(args.output), "html": str(args.html), **summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
