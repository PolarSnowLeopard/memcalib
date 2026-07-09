#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from utils import iter_jsonl, norm_text


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = SCRIPT_DIR / "data" / "crk2_canonical_memory_benchmark_100.jsonl"
DEFAULT_CSV = SCRIPT_DIR / "data" / "crk2_canonical_memory_audit_100.csv"
DEFAULT_HTML = SCRIPT_DIR / "data" / "crk2_canonical_memory_audit_100.html"

AUDIT_COLUMNS = [
    "sample_id",
    "source_id",
    "source_topic",
    "source_dataset",
    "question",
    "parent_memory_id",
    "parent_source",
    "parent_block_label",
    "parent_label_set",
    "parent_label_mode",
    "atom_count",
    "memory_text",
    "raw_evidence",
    "atom_summary",
    "rubric_summary",
    "hard_a_family_set",
    "review_status",
    "memory_text_quality",
    "atomization_quality",
    "abc_label_quality",
    "hard_a_quality",
    "rubric_quality",
    "reviewer_notes",
]

REVIEW_FIELDS = [
    "review_status",
    "memory_text_quality",
    "atomization_quality",
    "abc_label_quality",
    "hard_a_quality",
    "rubric_quality",
    "reviewer_notes",
]


def label_set(labels: list[str]) -> str:
    ordered = [label for label in ("A", "B", "C") if label in labels]
    return "+".join(ordered)


def build_atom_summary(memories: list[dict[str, Any]]) -> str:
    parts = []
    for memory in memories:
        parts.append(
            f"{memory.get('atom_id', '')}:{memory.get('u_star', '')}:{norm_text(str(memory.get('text', '')))}"
        )
    return "\n".join(parts)


def build_rubric_summary(memories: list[dict[str, Any]]) -> str:
    parts = []
    for memory in memories:
        rubric = memory.get("usage_rubric") if isinstance(memory.get("usage_rubric"), dict) else {}
        parts.append(
            " | ".join(
                [
                    f"{memory.get('atom_id', '')}:{memory.get('u_star', '')}",
                    f"weight={rubric.get('memory_usage_weight', '')}",
                    f"correct={norm_text(str(rubric.get('correct_use', '')))}",
                    f"under={norm_text(str(rubric.get('under_use', '')))}",
                    f"over={norm_text(str(rubric.get('over_use', '')))}",
                ]
            )
        )
    return "\n".join(parts)


def build_parent_audit_rows(samples: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = []
    for sample in samples:
        memories_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for memory in sample.get("memories", []):
            memories_by_parent[str(memory.get("parent_memory_id", ""))].append(memory)

        for block in sample.get("memory_blocks", []):
            parent_id = str(block.get("parent_memory_id", ""))
            memories = memories_by_parent.get(parent_id, [])
            labels = [str(memory.get("u_star", "")) for memory in memories]
            parent_label_set = label_set(labels)
            families = sorted(
                {
                    str(memory.get("hard_a_family"))
                    for memory in memories
                    if memory.get("hard_a_family")
                }
            )
            row = {
                "sample_id": str(sample.get("id", "")),
                "source_id": str(sample.get("source_id", "")),
                "source_topic": str(sample.get("source_topic", "")),
                "source_dataset": str(sample.get("source_dataset", "")),
                "question": norm_text(str(sample.get("question", ""))),
                "parent_memory_id": parent_id,
                "parent_source": str(block.get("source", "")),
                "parent_block_label": str(block.get("u_star", "")),
                "parent_label_set": parent_label_set,
                "parent_label_mode": "mixed" if "+" in parent_label_set else "homogeneous",
                "atom_count": str(len(memories)),
                "memory_text": norm_text(str(block.get("memory_text") or block.get("text", ""))),
                "raw_evidence": norm_text(str(block.get("raw_evidence", ""))),
                "atom_summary": build_atom_summary(memories),
                "rubric_summary": build_rubric_summary(memories),
                "hard_a_family_set": "+".join(families),
            }
            for field in REVIEW_FIELDS:
                row[field] = ""
            rows.append(row)
    return rows


def summarize_rows(rows: list[dict[str, str]], samples: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    mixed = sum(1 for row in rows if row["parent_label_mode"] == "mixed")
    return {
        "total_samples": len(samples or []),
        "total_parent_rows": len(rows),
        "mixed_parent_rows": mixed,
        "homogeneous_parent_rows": len(rows) - mixed,
    }


def write_audit_csv(path: Path, rows: list[dict[str, str]]) -> None:
    def csv_row(row: dict[str, str]) -> dict[str, str]:
        return {
            key: str(value).replace("\r\n", "\n").replace("\r", "\n").replace("\n", " | ")
            for key, value in row.items()
        }

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=AUDIT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(csv_row(row) for row in rows)


def cell(text: Any) -> str:
    return html.escape(str(text or "")).replace("\n", "<br>")


def write_audit_html(path: Path, rows: list[dict[str, str]], summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    display_summary = {
        "total_samples": summary.get("total_samples", 0),
        "total_parent_rows": summary.get("total_parent_rows", len(rows)),
        "mixed_parent_rows": summary.get("mixed_parent_rows", sum(1 for row in rows if row["parent_label_mode"] == "mixed")),
        "homogeneous_parent_rows": summary.get("homogeneous_parent_rows", sum(1 for row in rows if row["parent_label_mode"] == "homogeneous")),
    }
    cards = []
    for row in rows:
        mode_class = "mixed" if row["parent_label_mode"] == "mixed" else "homogeneous"
        review_fields = "".join(
            f"""
            <label>
              <span>{html.escape(field)}</span>
              <input aria-label="{html.escape(field)}">
            </label>
            """
            for field in REVIEW_FIELDS[:-1]
        )
        cards.append(
            f"""
            <article class="audit-row {mode_class}" data-mode="{mode_class}" data-label-set="{html.escape(row['parent_label_set'])}">
              <div class="label-rail">
                <span class="mode">{cell(row['parent_label_mode'])}</span>
                <span class="label-set">{cell(row['parent_label_set'])}</span>
                <span class="parent-id">{cell(row['parent_memory_id'])}</span>
              </div>
              <div class="sample-panel">
                <p class="eyebrow">sample</p>
                <h2>{cell(row['sample_id'])}</h2>
                <p class="meta-line">{cell(row['source_topic'])} · {cell(row['source_dataset'])}</p>
                <p class="question">{cell(row['question'])}</p>
                <div class="mini-grid">
                  <span><strong>{cell(row['atom_count'])}</strong><small>atoms</small></span>
                  <span><strong>{cell(row['parent_source'])}</strong><small>source</small></span>
                  <span><strong>{cell(row['hard_a_family_set'] or 'none')}</strong><small>hard A</small></span>
                </div>
              </div>
              <div class="memory-panel">
                <p class="eyebrow">model-facing memory</p>
                <p class="stored-memory">{cell(row['memory_text'])}</p>
                <p class="eyebrow evidence-title">audit evidence</p>
                <p class="raw-evidence">{cell(row['raw_evidence'])}</p>
              </div>
              <div class="annotation-panel">
                <p class="eyebrow">hidden atom annotation</p>
                <div class="atom-summary">{cell(row['atom_summary'])}</div>
                <details>
                  <summary>Rubric summary</summary>
                  <div class="rubric-summary">{cell(row['rubric_summary'])}</div>
                </details>
              </div>
              <aside class="review-panel">
                <p class="eyebrow">manual audit</p>
                <div class="review-grid">
                  {review_fields}
                  <label class="notes">
                    <span>{html.escape(REVIEW_FIELDS[-1])}</span>
                    <textarea aria-label="{html.escape(REVIEW_FIELDS[-1])}"></textarea>
                  </label>
                </div>
              </aside>
            </article>
            """
        )

    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CRK-2 Canonical Memory 人工审查</title>
  <style>
    :root {{
      --paper: #ffffff;
      --bg: #f4f6f8;
      --ink: #18212f;
      --muted: #667085;
      --line: #d5dde7;
      --panel: #f9fbfd;
      --mixed: #a15c07;
      --mixed-soft: #fff4df;
      --homogeneous: #0f766e;
      --homogeneous-soft: #e6f4f1;
      --review: #5b5f97;
      --danger: #b42318;
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
    header {{
      padding: 26px min(5vw, 58px) 18px;
      background: var(--paper);
      border-bottom: 1px solid var(--line);
    }}
    h1 {{ margin: 0; font-size: 30px; line-height: 1.15; letter-spacing: 0; }}
    header p {{ margin: 9px 0 0; color: #3d4858; max-width: 980px; font-size: 15px; }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(4, minmax(160px, 1fr));
      gap: 10px;
      padding: 14px min(5vw, 58px) 10px;
    }}
    .metric {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px 13px;
    }}
    .metric strong {{ display: block; font-size: 22px; }}
    .metric span {{ color: var(--muted); font-size: 13px; }}
    .toolbar {{
      position: sticky;
      top: 0;
      z-index: 8;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      padding: 10px min(5vw, 58px);
      background: rgba(244, 246, 248, 0.94);
      border-top: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
      backdrop-filter: blur(12px);
    }}
    .filter-button {{
      min-height: 32px;
      border: 1px solid #bec8d6;
      border-radius: 999px;
      background: var(--paper);
      color: #344054;
      padding: 0 12px;
      font: inherit;
      font-size: 13px;
      font-weight: 760;
      cursor: pointer;
    }}
    .filter-button.active {{
      background: #18212f;
      border-color: #18212f;
      color: #fff;
    }}
    .toolbar-note {{ margin-left: auto; color: var(--muted); font-size: 13px; }}
    main {{
      display: grid;
      gap: 14px;
      padding: 14px min(5vw, 58px) 56px;
    }}
    p {{ margin: 0; }}
    .audit-row {{
      display: grid;
      grid-template-columns: 94px minmax(190px, 0.72fr) minmax(300px, 1.1fr) minmax(260px, 0.95fr) minmax(240px, 0.82fr);
      gap: 0;
      overflow: hidden;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 10px 24px rgba(24, 33, 47, 0.06);
    }}
    .audit-row.hidden {{ display: none; }}
    .label-rail {{
      display: grid;
      grid-template-rows: auto auto 1fr;
      gap: 8px;
      align-content: start;
      padding: 14px 12px;
      color: #fff;
    }}
    .audit-row.mixed .label-rail {{ background: var(--mixed); }}
    .audit-row.homogeneous .label-rail {{ background: var(--homogeneous); }}
    .mode {{ font-size: 11px; text-transform: uppercase; font-weight: 860; opacity: 0.88; }}
    .label-set {{ font-size: 25px; line-height: 1; font-weight: 920; overflow-wrap: anywhere; }}
    .parent-id {{ align-self: end; font-size: 13px; font-weight: 820; opacity: 0.9; }}
    .sample-panel, .memory-panel, .annotation-panel, .review-panel {{
      padding: 14px 15px;
      border-left: 1px solid var(--line);
      min-width: 0;
    }}
    .sample-panel {{ background: #fbfcfe; }}
    .memory-panel {{ background: var(--paper); }}
    .annotation-panel {{ background: var(--panel); }}
    .review-panel {{ background: #fbfaff; }}
    .eyebrow {{
      margin: 0 0 7px;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.2;
      font-weight: 820;
      text-transform: uppercase;
    }}
    .sample-panel h2 {{
      margin: 0;
      font-size: 14px;
      line-height: 1.28;
      overflow-wrap: anywhere;
    }}
    .meta-line {{ margin-top: 5px; color: var(--muted); font-size: 12px; }}
    .question {{
      margin-top: 12px;
      color: #2f3a4c;
      font-size: 13px;
      font-weight: 650;
      overflow-wrap: anywhere;
    }}
    .mini-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 7px;
      margin-top: 13px;
    }}
    .mini-grid span {{
      min-width: 0;
      padding: 8px;
      border: 1px solid #e0e6ef;
      border-radius: 8px;
      background: #fff;
    }}
    .mini-grid strong {{
      display: block;
      color: #1f2937;
      font-size: 13px;
      line-height: 1.2;
      overflow-wrap: anywhere;
    }}
    .mini-grid small {{ display: block; margin-top: 3px; color: var(--muted); font-size: 11px; }}
    .stored-memory {{
      color: #172033;
      font-size: 16px;
      line-height: 1.55;
      font-weight: 720;
      overflow-wrap: anywhere;
    }}
    .evidence-title {{ margin-top: 16px; }}
    .raw-evidence {{
      color: #556274;
      font-size: 13px;
      line-height: 1.5;
      padding: 10px 11px;
      border-left: 3px solid #9aa8bb;
      background: #f5f7fa;
      overflow-wrap: anywhere;
    }}
    .atom-summary, .rubric-summary {{
      color: #344054;
      font-size: 13px;
      line-height: 1.55;
      overflow-wrap: anywhere;
    }}
    details {{
      margin-top: 13px;
      border-top: 1px solid #dfe5ee;
      padding-top: 10px;
    }}
    summary {{
      color: #344054;
      font-size: 13px;
      font-weight: 820;
      cursor: pointer;
    }}
    .rubric-summary {{ margin-top: 8px; color: #4e5b6e; }}
    .review-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      min-width: 0;
    }}
    label {{ min-width: 0; color: var(--muted); font-size: 12px; font-weight: 740; }}
    label span {{ display: block; overflow-wrap: anywhere; }}
    input, textarea {{
      width: 100%;
      border: 1px solid #c8d1df;
      border-radius: 7px;
      min-height: 31px;
      background: #fff;
      color: var(--ink);
      font: inherit;
      font-size: 13px;
      padding: 5px 7px;
      margin-top: 3px;
    }}
    input:focus-visible, textarea:focus-visible, .filter-button:focus-visible {{
      outline: 3px solid rgba(91, 95, 151, 0.24);
      outline-offset: 2px;
    }}
    .notes {{ grid-column: 1 / -1; }}
    textarea {{ min-height: 74px; resize: vertical; }}
    @media (max-width: 1280px) {{
      .audit-row {{
        grid-template-columns: 84px 1fr 1.25fr;
      }}
      .annotation-panel, .review-panel {{
        grid-column: 2 / -1;
        border-top: 1px solid var(--line);
      }}
    }}
    @media (max-width: 760px) {{
      header, .metrics, .toolbar, main {{ padding-left: 14px; padding-right: 14px; }}
      .metrics {{ grid-template-columns: 1fr 1fr; }}
      .toolbar-note {{ flex-basis: 100%; margin-left: 0; }}
      .audit-row {{ grid-template-columns: 1fr; }}
      .label-rail {{
        grid-template-columns: auto auto 1fr;
        grid-template-rows: auto;
      align-items: center;
      }}
      .parent-id {{ justify-self: end; align-self: center; }}
      .sample-panel, .memory-panel, .annotation-panel, .review-panel {{
        grid-column: 1;
        border-left: 0;
        border-top: 1px solid var(--line);
      }}
      .review-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>CRK-2 Canonical Memory 人工审查</h1>
    <p>每行对应一条 model-facing parent memory block。审查重点是 stored memory 是否像真实记忆系统总结、atom 拆分是否合理、A/B/C 标签和 rubric 是否可辩护。</p>
  </header>
  <section class="metrics">
    <div class="metric"><strong>{html.escape(str(display_summary.get('total_samples', 0)))}</strong><span>samples</span></div>
    <div class="metric"><strong>{html.escape(str(display_summary.get('total_parent_rows', len(rows))))}</strong><span>parent rows</span></div>
    <div class="metric"><strong>{html.escape(str(display_summary.get('mixed_parent_rows', 0)))}</strong><span>mixed-label rows</span></div>
    <div class="metric"><strong>{html.escape(str(display_summary.get('homogeneous_parent_rows', 0)))}</strong><span>homogeneous rows</span></div>
  </section>
  <nav class="toolbar" aria-label="Audit filters">
    <button class="filter-button active" type="button" data-filter="all">All rows</button>
    <button class="filter-button" type="button" data-filter="mixed">Mixed only</button>
    <button class="filter-button" type="button" data-filter="homogeneous">Homogeneous</button>
    <span class="toolbar-note">Use the review panel on each card; CSV keeps the same fields for batch editing.</span>
  </nav>
  <main>
    {''.join(cards)}
  </main>
  <script>
    const buttons = Array.from(document.querySelectorAll(".filter-button"));
    const rows = Array.from(document.querySelectorAll(".audit-row"));
    function applyFilter(filter) {{
      rows.forEach((row) => {{
        const show = filter === "all" || row.dataset.mode === filter;
        row.classList.toggle("hidden", !show);
      }});
      buttons.forEach((button) => button.classList.toggle("active", button.dataset.filter === filter));
    }}
    buttons.forEach((button) => {{
      button.addEventListener("click", () => applyFilter(button.dataset.filter));
    }});
  </script>
</body>
</html>
""",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build parent-level human audit CSV/HTML for canonical CRK-2 benchmark data.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    args = parser.parse_args()

    samples = list(iter_jsonl(args.input))
    rows = build_parent_audit_rows(samples)
    summary = summarize_rows(rows, samples)
    write_audit_csv(args.csv, rows)
    write_audit_html(args.html, rows, summary)
    print(json.dumps({"input": str(args.input), "csv": str(args.csv), "html": str(args.html), **summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
