#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

from utils import iter_jsonl, norm_text, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = SCRIPT_DIR / "data" / "crk2_canonical_memory_benchmark_100.jsonl"
DEFAULT_OUTPUT = SCRIPT_DIR / "data" / "crk2_canonical_judge_calibration_pack_20.jsonl"
DEFAULT_HTML = SCRIPT_DIR / "data" / "crk2_canonical_judge_calibration_pack_20.html"


def sample_features(sample: dict[str, Any]) -> set[str]:
    features = {f"topic:{sample.get('source_topic', '')}"}
    has_mixed = False
    for block in sample.get("memory_blocks", []):
        mode = str(block.get("parent_label_mode", "unknown"))
        if mode == "mixed":
            has_mixed = True
        features.add(f"parent_mode:{mode}")
        label_set = block.get("parent_label_set")
        if isinstance(label_set, list):
            features.add("parent_label_set:" + "+".join(label_set))
    for memory in sample.get("memories", []):
        family = memory.get("hard_a_family")
        if family:
            features.add(f"hard_a_family:{family}")
        label = memory.get("u_star")
        if label:
            features.add(f"atom_label:{label}")
    features.add("has_mixed_parent:true" if has_mixed else "has_mixed_parent:false")
    return features


def has_mixed_parent(sample: dict[str, Any]) -> bool:
    return any(block.get("parent_label_mode") == "mixed" for block in sample.get("memory_blocks", []))


def select_calibration_samples(samples: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    remaining = list(samples)
    selected: list[dict[str, Any]] = []
    covered: set[str] = set()
    while remaining and len(selected) < limit:
        scored = []
        for index, sample in enumerate(remaining):
            features = sample_features(sample)
            score = len(features - covered)
            scored.append(
                (
                    score,
                    1 if has_mixed_parent(sample) else 0,
                    len([memory for memory in sample.get("memories", []) if memory.get("source") == "synthetic_hard_a"]),
                    -index,
                    sample,
                )
            )
        scored.sort(reverse=True, key=lambda item: item[:4])
        chosen = scored[0][4]
        selected.append(chosen)
        covered.update(sample_features(chosen))
        remaining.remove(chosen)
    return selected


def model_input_text(sample: dict[str, Any]) -> str:
    memory_lines = []
    for index, block in enumerate(sample.get("memory_blocks", []), start=1):
        memory_lines.append(f"{index}. {norm_text(str(block.get('memory_text') or block.get('text', '')))}")
    return "Question:\n" + norm_text(str(sample.get("question", ""))) + "\n\nMemories:\n" + "\n".join(memory_lines)


def hidden_annotation(sample: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "atom_id": memory.get("atom_id", ""),
            "parent_memory_id": memory.get("parent_memory_id", ""),
            "u_star": memory.get("u_star", ""),
            "text": memory.get("text", ""),
            "hard_a_family": memory.get("hard_a_family"),
        }
        for memory in sample.get("memories", [])
    ]


def judge_rubric_bundle(sample: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "atom_id": memory.get("atom_id", ""),
            "u_star": memory.get("u_star", ""),
            "usage_rubric": memory.get("usage_rubric", {}),
            "construction_target": memory.get("construction_target", {}),
        }
        for memory in sample.get("memories", [])
    ]


def build_calibration_rows(samples: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = []
    for sample in samples:
        rows.append(
            {
                "sample_id": str(sample.get("id", "")),
                "source_topic": str(sample.get("source_topic", "")),
                "source_dataset": str(sample.get("source_dataset", "")),
                "has_mixed_parent": str(has_mixed_parent(sample)),
                "selection_features": json.dumps(sorted(sample_features(sample)), ensure_ascii=False),
                "model_input": model_input_text(sample),
                "hidden_annotation": json.dumps(hidden_annotation(sample), ensure_ascii=False),
                "judge_rubric_bundle": json.dumps(judge_rubric_bundle(sample), ensure_ascii=False),
            }
        )
    return rows


def write_calibration_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    write_jsonl(path, rows)


def cell(text: Any) -> str:
    return html.escape(str(text or "")).replace("\n", "<br>")


def write_calibration_html(path: Path, rows: list[dict[str, str]], summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table_rows = []
    for row in rows:
        table_rows.append(
            f"""
            <tr>
              <td>{cell(row['sample_id'])}<br><small>{cell(row['source_topic'])}</small><br><small>mixed={cell(row['has_mixed_parent'])}</small></td>
              <td>{cell(row['model_input'])}</td>
              <td>{cell(row['hidden_annotation'])}</td>
              <td>{cell(row['judge_rubric_bundle'])}</td>
            </tr>
            """
        )
    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Judge Calibration Pack</title>
  <style>
    :root {{ --bg: #f7f9fc; --paper: #fff; --ink: #172033; --muted: #647084; --line: #d8e0ea; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--ink); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; line-height: 1.55; letter-spacing: 0; }}
    header {{ padding: 28px min(5vw, 56px) 18px; background: var(--paper); border-bottom: 1px solid var(--line); }}
    h1 {{ margin: 0; font-size: 30px; }}
    header p {{ margin: 9px 0 0; color: #3d4858; max-width: 980px; }}
    main {{ padding: 16px min(5vw, 56px) 48px; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--paper); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }}
    th, td {{ border-top: 1px solid var(--line); padding: 10px; vertical-align: top; text-align: left; font-size: 13px; }}
    th {{ background: #eef3f8; color: #344054; position: sticky; top: 0; z-index: 1; }}
    small {{ color: var(--muted); }}
    @media (max-width: 900px) {{ table {{ display: block; overflow-x: auto; }} }}
  </style>
</head>
<body>
  <header>
    <h1>Judge Calibration Pack</h1>
    <p>Each row contains the model-facing input for answer generation and the hidden annotation/rubric bundle for judge calibration.</p>
  </header>
  <main>
    <p><strong>{html.escape(str(summary.get('total_samples', len(rows))))}</strong> samples selected for calibration.</p>
    <table>
      <thead><tr><th>sample</th><th>model-facing input</th><th>hidden annotation</th><th>judge rubric bundle</th></tr></thead>
      <tbody>{''.join(table_rows)}</tbody>
    </table>
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a small representative pack for answer-model and judge calibration.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    samples = list(iter_jsonl(args.input))
    selected = select_calibration_samples(samples, args.limit)
    rows = build_calibration_rows(selected)
    write_calibration_jsonl(args.output, rows)
    write_calibration_html(args.html, rows, {"total_samples": len(rows)})
    print(json.dumps({"input": str(args.input), "output": str(args.output), "html": str(args.html), "selected": len(rows)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
