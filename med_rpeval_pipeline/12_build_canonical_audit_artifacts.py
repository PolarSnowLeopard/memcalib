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
    "atom_details_json",
    "rubric_details_json",
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

REVIEW_FIELD_DEFS = [
    {
        "field": "review_status",
        "label": "审查结论",
        "help": "判断这条 parent memory 是否可以进入后续 benchmark。若任一核心字段不可辩护，应标为需修改或剔除。",
        "options": [
            ("", "未标注"),
            ("pass", "通过"),
            ("revise", "需修改"),
            ("exclude", "剔除"),
            ("unsure", "不确定"),
        ],
    },
    {
        "field": "memory_text_quality",
        "label": "记忆条目质量",
        "help": "判定 stored memory 是否像真实记忆系统总结出的条目：应保留原始记忆含义，避免第一人称原话、过度扩展、事实错误或无依据重写。",
        "options": [
            ("", "未标注"),
            ("good", "合格"),
            ("too_raw", "太像原话"),
            ("too_broad", "过度概括"),
            ("unsupported", "加入无依据内容"),
            ("fact_error", "事实错误"),
            ("unclear", "表达不清"),
        ],
    },
    {
        "field": "atomization_quality",
        "label": "原子拆分质量",
        "help": "检查原子拆分是否保持单一事实且边界自然；同一事件的必要限定条件不应被硬拆成互不完整的片段。",
        "options": [
            ("", "未标注"),
            ("good", "合格"),
            ("over_split", "拆得过细"),
            ("under_split", "应继续拆分"),
            ("missing_atom", "遗漏原子信息"),
            ("overlap", "与其他记忆重叠"),
            ("unclear_boundary", "边界不清"),
        ],
    },
    {
        "field": "abc_label_quality",
        "label": "A/B/C 标签质量",
        "help": "检查每个 atom 的 A/B/C 标签是否符合当前问题：A 不应使用，B 支持性使用，C 必须控制回答结论或方案。",
        "options": [
            ("", "未标注"),
            ("good", "合格"),
            ("a_should_be_b", "A 应改 B"),
            ("a_should_be_c", "A 应改 C"),
            ("b_should_be_a", "B 应改 A"),
            ("b_should_be_c", "B 应改 C"),
            ("c_should_be_a", "C 应改 A"),
            ("c_should_be_b", "C 应改 B"),
            ("mixed_unclear", "混合标签边界不清"),
        ],
    },
    {
        "field": "hard_a_quality",
        "label": "Hard-A 质量",
        "help": "只在涉及 A 类时判断：Hard-A 应表面相关但不能用于当前回答，使用它会造成错误约束、危险顺从或无依据延展。",
        "options": [
            ("", "未标注"),
            ("not_applicable", "不适用"),
            ("good", "合格"),
            ("too_easy", "太容易忽略"),
            ("actually_useful", "其实应使用"),
            ("not_risky", "风险不足"),
            ("family_unclear", "类别不清"),
        ],
    },
    {
        "field": "rubric_quality",
        "label": "Judge rubric 质量",
        "help": "判断 correct / under-use / over-use 是否能直接指导 judge；边界应可观察、可复核，不能只写抽象原则。",
        "options": [
            ("", "未标注"),
            ("good", "合格"),
            ("correct_unclear", "correct 模糊"),
            ("under_unclear", "under-use 模糊"),
            ("over_unclear", "over-use 模糊"),
            ("not_observable", "不可观察"),
            ("missing_failure", "缺少失败边界"),
        ],
    },
]

ATOM_DETAIL_FIELDS = [
    "atom_id",
    "u_star",
    "text",
    "evidence",
    "atomic_predicate",
    "derivation",
    "source",
    "memory_type",
    "subtype",
    "hard_a_family",
    "label_reason",
    "verifier_reason",
    "overlap_group",
    "overlap_note",
    "construction_target",
]

RUBRIC_FIELD_ORDER = [
    "memory_usage_weight",
    "expected_answer_behavior",
    "validity_scope",
    "correct_use",
    "under_use",
    "over_use",
    "forbidden_memory_role",
    "failure_direction",
    "controlling_factor",
    "missing_memory_failure",
    "allowed_memory_use",
    "maximum_footprint",
    "contamination_signals",
    "observable_checks",
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


def compact_value(value: Any) -> Any:
    if isinstance(value, str):
        return norm_text(value)
    if isinstance(value, list):
        return [compact_value(item) for item in value if item not in (None, "")]
    if isinstance(value, dict):
        return {
            str(key): compact_value(item)
            for key, item in value.items()
            if item not in (None, "", [], {})
        }
    return value


def build_atom_details(memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    details = []
    for memory in memories:
        item = {
            field: compact_value(memory.get(field))
            for field in ATOM_DETAIL_FIELDS
            if memory.get(field) not in (None, "", [], {})
        }
        details.append(item)
    return details


def build_rubric_details(memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    details = []
    for memory in memories:
        rubric = memory.get("usage_rubric") if isinstance(memory.get("usage_rubric"), dict) else {}
        details.append(
            {
                "atom_id": memory.get("atom_id", ""),
                "u_star": memory.get("u_star", ""),
                "text": compact_value(memory.get("text", "")),
                "rubric": compact_value(rubric),
            }
        )
    return details


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
                "atom_details_json": json.dumps(build_atom_details(memories), ensure_ascii=False),
                "rubric_details_json": json.dumps(build_rubric_details(memories), ensure_ascii=False),
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
        writer = csv.DictWriter(f, fieldnames=AUDIT_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(csv_row(row) for row in rows)


def cell(text: Any) -> str:
    return html.escape(str(text or "")).replace("\n", "<br>")


def attr(text: Any) -> str:
    return html.escape(str(text or ""), quote=True)


def group_rows_by_sample(rows: list[dict[str, str]]) -> list[tuple[str, list[dict[str, str]]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    order = []
    for row in rows:
        sample_id = row["sample_id"]
        if sample_id not in grouped:
            grouped[sample_id] = []
            order.append(sample_id)
        grouped[sample_id].append(row)
    return [(sample_id, grouped[sample_id]) for sample_id in order]


def html_id_part(text: Any) -> str:
    value = str(text or "")
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in value)
    return cleaned.strip("-") or "x"


def parse_json_list(value: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def render_value(value: Any) -> str:
    if isinstance(value, list):
        if not value:
            return '<span class="empty-value">无</span>'
        items = "".join(f"<li>{render_value(item)}</li>" for item in value)
        return f'<ul class="value-list">{items}</ul>'
    if isinstance(value, dict):
        if not value:
            return '<span class="empty-value">无</span>'
        rows = "".join(
            f"<dt>{cell(key)}</dt><dd>{render_value(item)}</dd>"
            for key, item in value.items()
        )
        return f'<dl class="nested-detail-list">{rows}</dl>'
    if value in (None, ""):
        return '<span class="empty-value">无</span>'
    return cell(value)


def render_detail_list(items: list[tuple[str, Any]]) -> str:
    rows = "".join(
        f"<dt>{cell(label)}</dt><dd>{render_value(value)}</dd>"
        for label, value in items
        if value not in (None, "", [], {})
    )
    return f'<dl class="detail-list">{rows}</dl>' if rows else '<p class="empty-value">无可展示字段</p>'


def render_atom_cards(row: dict[str, str]) -> str:
    atoms = parse_json_list(row.get("atom_details_json", "[]"))
    if not atoms:
        return f'<div class="atom-card"><p>{cell(row.get("atom_summary", ""))}</p></div>'
    cards = []
    for atom in atoms:
        atom_id = atom.get("atom_id", "")
        label = atom.get("u_star", "")
        title = atom.get("text", "")
        detail_items = [
            (field, atom.get(field))
            for field in ATOM_DETAIL_FIELDS
            if field not in {"atom_id", "u_star", "text"}
        ]
        cards.append(
            f"""
            <article class="atom-card">
              <header class="atom-card-head">
                <span class="atom-id">{cell(atom_id)}</span>
                <span class="u-chip u-{attr(label).lower()}">{cell(label)}</span>
              </header>
              <p class="atom-text">{cell(title)}</p>
              {render_detail_list(detail_items)}
            </article>
            """
        )
    return "".join(cards)


def ordered_rubric_items(rubric: dict[str, Any]) -> list[tuple[str, Any]]:
    ordered = [(key, rubric.get(key)) for key in RUBRIC_FIELD_ORDER if key in rubric]
    ordered_keys = {key for key, _ in ordered}
    ordered.extend((key, rubric.get(key)) for key in sorted(rubric) if key not in ordered_keys)
    return ordered


def render_rubric_cards(row: dict[str, str]) -> str:
    rubric_details = parse_json_list(row.get("rubric_details_json", "[]"))
    if not rubric_details:
        return f'<div class="rubric-card"><p>{cell(row.get("rubric_summary", ""))}</p></div>'
    cards = []
    for detail in rubric_details:
        atom_id = detail.get("atom_id", "")
        label = detail.get("u_star", "")
        text = detail.get("text", "")
        rubric = detail.get("rubric") if isinstance(detail.get("rubric"), dict) else {}
        cards.append(
            f"""
            <article class="rubric-card">
              <header class="rubric-card-head">
                <div>
                  <span class="atom-id">{cell(atom_id)}</span>
                  <span class="u-chip u-{attr(label).lower()}">{cell(label)}</span>
                </div>
                <p>{cell(text)}</p>
              </header>
              {render_detail_list(ordered_rubric_items(rubric))}
            </article>
            """
        )
    return "".join(cards)


def render_review_controls(row: dict[str, str]) -> str:
    parent_id = row["parent_memory_id"]
    control_suffix = f"{html_id_part(row['sample_id'])}-{html_id_part(parent_id)}"
    controls = []
    for field_def in REVIEW_FIELD_DEFS:
        field = field_def["field"]
        control_id = f"{field}-{control_suffix}"
        help_id = f"{control_id}-help"
        options = "".join(
            f'<option value="{attr(value)}">{cell(label)}</option>'
            for value, label in field_def["options"]
        )
        controls.append(
            f"""
            <label class="review-field" for="{attr(control_id)}">
              <span class="field-label">{cell(field_def['label'])}</span>
              <select name="{attr(field)}" id="{attr(control_id)}" data-parent-id="{attr(parent_id)}" aria-describedby="{attr(help_id)}">
                {options}
              </select>
              <small id="{attr(help_id)}" class="field-help">{cell(field_def['help'])}</small>
            </label>
            """
        )
    notes_id = f"reviewer_notes-{control_suffix}"
    controls.append(
        f"""
        <label class="review-field notes" for="{attr(notes_id)}">
          <span class="field-label">备注</span>
          <textarea id="{attr(notes_id)}" name="reviewer_notes" data-parent-id="{attr(parent_id)}" aria-describedby="{attr(notes_id)}-help"></textarea>
          <small id="{attr(notes_id)}-help" class="field-help">只记录无法用选择框表达的问题，例如建议合并哪些 atom、哪条 rubric 需要重写、是否应整条剔除。</small>
        </label>
        """
    )
    return "".join(controls)


def render_memory_card(row: dict[str, str]) -> str:
    mode_class = "mixed" if row["parent_label_mode"] == "mixed" else "homogeneous"
    return f"""
          <article class="audit-row {mode_class}" data-mode="{mode_class}" data-label-set="{attr(row['parent_label_set'])}">
            <header class="memory-card-head">
              <div class="label-block">
                <span class="mode">{cell(row['parent_label_mode'])}</span>
                <span class="label-set">{cell(row['parent_label_set'])}</span>
              </div>
              <div class="memory-title-block">
                <p class="eyebrow">Model-facing memory</p>
                <h3>{cell(row['memory_text'])}</h3>
                <p class="memory-id-line">parent memory id: {cell(row['parent_memory_id'])}</p>
              </div>
              <div class="memory-facts">
                <span><strong>{cell(row['atom_count'])}</strong><small>atoms</small></span>
                <span><strong>{cell(row['parent_source'])}</strong><small>source</small></span>
                <span><strong>{cell(row['hard_a_family_set'] or 'none')}</strong><small>hard A</small></span>
              </div>
            </header>
            <div class="memory-card-layout">
              <div class="memory-workbench">
                <section class="read-section">
                  <p class="eyebrow">audit evidence</p>
                  <p class="raw-evidence">{cell(row['raw_evidence'])}</p>
                </section>
                <section class="read-section">
                  <div class="section-heading">
                    <p class="eyebrow">hidden atom annotation</p>
                    <h4>Atomic annotations</h4>
                  </div>
                  <div class="atom-grid">{render_atom_cards(row)}</div>
                </section>
                <section class="read-section">
                  <div class="section-heading">
                    <p class="eyebrow">judge input</p>
                    <h4>Usage rubric</h4>
                  </div>
                  <div class="rubric-list">{render_rubric_cards(row)}</div>
                </section>
              </div>
              <aside class="review-panel">
                <p class="eyebrow">manual audit</p>
                <div class="review-grid">
                  {render_review_controls(row)}
                </div>
              </aside>
            </div>
          </article>
    """


def write_audit_html(path: Path, rows: list[dict[str, str]], summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    grouped_samples = group_rows_by_sample(rows)
    display_summary = {
        "total_samples": summary.get("total_samples", 0),
        "total_parent_rows": summary.get("total_parent_rows", len(rows)),
        "mixed_parent_rows": summary.get("mixed_parent_rows", sum(1 for row in rows if row["parent_label_mode"] == "mixed")),
        "homogeneous_parent_rows": summary.get("homogeneous_parent_rows", sum(1 for row in rows if row["parent_label_mode"] == "homogeneous")),
    }
    sample_pages = []
    for index, (sample_id, sample_rows) in enumerate(grouped_samples):
        first = sample_rows[0]
        mixed_count = sum(1 for row in sample_rows if row["parent_label_mode"] == "mixed")
        label_sets = label_set([label for row in sample_rows for label in row["parent_label_set"].split("+") if label])
        active_class = " active" if index == 0 else ""
        cards = "".join(render_memory_card(row) for row in sample_rows)
        sample_pages.append(
            f"""
      <section class="sample-page{active_class}" data-sample-index="{index}" data-sample-id="{attr(sample_id)}">
        <section class="sample-brief">
          <div>
            <p class="eyebrow">sample</p>
            <h2>{cell(sample_id)}</h2>
            <p class="meta-line">{cell(first['source_topic'])} · {cell(first['source_dataset'])} · source_id={cell(first['source_id'])}</p>
          </div>
          <p class="question">{cell(first['question'])}</p>
          <div class="sample-stats">
            <span><strong>{len(sample_rows)}</strong><small>parent memories</small></span>
            <span><strong>{mixed_count}</strong><small>mixed rows</small></span>
            <span><strong>{cell(label_sets or 'none')}</strong><small>label set</small></span>
          </div>
        </section>
        <section class="memory-list">
          {cards}
        </section>
      </section>
            """
        )

    content = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CRK-2 Canonical Memory 人工审查</title>
  <style>
    :root {{
      --paper: #ffffff;
      --bg: #f2f5f7;
      --ink: #172033;
      --muted: #667085;
      --line: #d3dce8;
      --panel: #f8fafc;
      --mixed: #995f12;
      --homogeneous: #0f6b63;
      --review: #4f5b93;
      --nav: #223047;
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
      padding: 24px min(5vw, 58px) 18px;
      background: var(--paper);
      border-bottom: 1px solid var(--line);
    }}
    h1 {{ margin: 0; font-size: 28px; line-height: 1.15; letter-spacing: 0; }}
    header p {{ margin: 9px 0 0; color: #3d4858; max-width: 1060px; font-size: 15px; }}
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
    .sample-nav {{
      position: sticky;
      top: 0;
      z-index: 10;
      display: grid;
      grid-template-columns: minmax(120px, auto) 1fr minmax(120px, auto);
      align-items: center;
      gap: 12px;
      padding: 11px min(5vw, 58px);
      background: rgba(242, 245, 247, 0.96);
      border-top: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
      backdrop-filter: blur(12px);
    }}
    .nav-button {{
      min-height: 34px;
      border: 1px solid #b9c4d3;
      border-radius: 7px;
      background: var(--nav);
      color: #fff;
      padding: 0 13px;
      font: inherit;
      font-size: 13px;
      font-weight: 780;
      cursor: pointer;
    }}
    .nav-button:disabled {{
      background: #d9e0ea;
      border-color: #d9e0ea;
      color: #6b7788;
      cursor: default;
    }}
    .sample-position {{
      min-width: 0;
      text-align: center;
      color: #344054;
      font-size: 13px;
      font-weight: 760;
    }}
    #sample-counter {{ display: block; color: var(--ink); font-size: 15px; }}
    #sample-title {{ display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--muted); }}
    main {{
      padding: 14px min(5vw, 58px) 56px;
    }}
    p {{ margin: 0; }}
    .sample-page {{ display: none; }}
    .sample-page.active {{ display: block; }}
    .sample-brief {{
      display: grid;
      grid-template-columns: minmax(180px, 0.58fr) minmax(300px, 1.25fr) minmax(250px, 0.72fr);
      gap: 18px;
      align-items: start;
      padding: 18px;
      margin-bottom: 14px;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 10px 24px rgba(24, 33, 47, 0.05);
    }}
    .sample-brief h2 {{
      margin: 0;
      font-size: 17px;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }}
    .meta-line {{ margin-top: 5px; color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }}
    .question {{
      color: #2f3a4c;
      font-size: 16px;
      line-height: 1.58;
      font-weight: 680;
      overflow-wrap: anywhere;
    }}
    .sample-stats, .mini-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }}
    .sample-stats span, .mini-grid span {{
      min-width: 0;
      padding: 9px;
      border: 1px solid #dfe5ee;
      border-radius: 7px;
      background: #fff;
    }}
    .sample-stats strong, .mini-grid strong {{
      display: block;
      color: #1f2937;
      font-size: 14px;
      line-height: 1.2;
      overflow-wrap: anywhere;
    }}
    .sample-stats small, .mini-grid small {{ display: block; margin-top: 3px; color: var(--muted); font-size: 11px; }}
    .memory-list {{
      display: grid;
      gap: 18px;
    }}
    .audit-row {{
      overflow: hidden;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 10px 24px rgba(24, 33, 47, 0.06);
    }}
    .memory-card-head {{
      display: grid;
      grid-template-columns: 118px minmax(360px, 1fr) minmax(280px, 0.42fr);
      gap: 16px;
      align-items: stretch;
      padding: 16px;
      border-bottom: 1px solid var(--line);
      background: #fbfcfe;
    }}
    .label-block {{
      display: grid;
      align-content: center;
      justify-items: center;
      gap: 7px;
      min-height: 112px;
      border-radius: 7px;
      color: #fff;
    }}
    .audit-row.mixed .label-block {{ background: var(--mixed); }}
    .audit-row.homogeneous .label-block {{ background: var(--homogeneous); }}
    .mode {{ font-size: 11px; text-transform: uppercase; font-weight: 860; opacity: 0.9; }}
    .label-set {{ font-size: 32px; line-height: 1; font-weight: 920; overflow-wrap: anywhere; }}
    .memory-title-block h3 {{
      margin: 5px 0 0;
      color: #172033;
      font-size: 22px;
      line-height: 1.38;
      font-weight: 800;
      letter-spacing: 0;
      overflow-wrap: anywhere;
    }}
    .memory-id-line {{
      margin-top: 9px;
      color: #667085;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      font-weight: 760;
      overflow-wrap: anywhere;
    }}
    .memory-facts {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      align-self: center;
    }}
    .memory-facts span {{
      min-width: 0;
      padding: 10px;
      border: 1px solid #dfe5ee;
      border-radius: 7px;
      background: #fff;
    }}
    .memory-facts strong {{
      display: block;
      color: #1f2937;
      font-size: 14px;
      line-height: 1.2;
      overflow-wrap: anywhere;
    }}
    .memory-facts small {{ display: block; margin-top: 4px; color: var(--muted); font-size: 11px; }}
    .memory-card-layout {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 390px;
      align-items: start;
    }}
    .memory-workbench {{
      display: grid;
      gap: 12px;
      padding: 16px;
      background: #fff;
    }}
    .read-section {{
      border: 1px solid #dfe5ee;
      border-radius: 8px;
      background: #fbfcfe;
      padding: 14px;
    }}
    .section-heading {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }}
    .section-heading h4 {{
      margin: 0;
      color: #1f2937;
      font-size: 16px;
      line-height: 1.2;
      font-weight: 820;
    }}
    .review-panel {{
      position: sticky;
      top: 66px;
      max-height: calc(100vh - 78px);
      overflow: auto;
      padding: 16px;
      border-left: 1px solid var(--line);
      background: #f7f7fd;
    }}
    .eyebrow {{
      margin: 0 0 7px;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.2;
      font-weight: 820;
      text-transform: uppercase;
    }}
    .raw-evidence {{
      color: #3f4b5d;
      font-size: 14px;
      line-height: 1.65;
      padding: 12px 13px;
      border-left: 3px solid #9aa8bb;
      background: #fff;
      overflow-wrap: anywhere;
    }}
    .atom-grid, .rubric-list {{ display: grid; gap: 10px; }}
    .atom-card, .rubric-card {{
      border: 1px solid #d8e0eb;
      border-radius: 8px;
      background: #fff;
      padding: 12px;
    }}
    .atom-card-head, .rubric-card-head {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 8px;
    }}
    .rubric-card-head {{
      align-items: flex-start;
      border-bottom: 1px solid #edf1f6;
      padding-bottom: 8px;
    }}
    .rubric-card-head p {{
      flex: 1;
      color: #344054;
      font-size: 13px;
      line-height: 1.45;
      overflow-wrap: anywhere;
    }}
    .atom-id {{
      color: #526174;
      font-size: 12px;
      font-weight: 820;
      white-space: nowrap;
    }}
    .u-chip {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 28px;
      min-height: 24px;
      border-radius: 999px;
      color: #fff;
      font-size: 12px;
      font-weight: 860;
      line-height: 1;
    }}
    .u-a {{ background: #697386; }}
    .u-b {{ background: #4f5b93; }}
    .u-c {{ background: #0f6b63; }}
    .atom-text {{
      margin-bottom: 9px;
      color: #172033;
      font-size: 15px;
      line-height: 1.5;
      font-weight: 740;
      overflow-wrap: anywhere;
    }}
    .detail-list, .nested-detail-list {{
      display: grid;
      grid-template-columns: minmax(150px, 0.32fr) minmax(0, 1fr);
      gap: 7px 12px;
      margin: 0;
    }}
    .detail-list dt, .nested-detail-list dt {{
      color: #667085;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      font-weight: 760;
      overflow-wrap: anywhere;
    }}
    .detail-list dd, .nested-detail-list dd {{
      margin: 0;
      color: #273244;
      font-size: 13px;
      line-height: 1.5;
      overflow-wrap: anywhere;
    }}
    .value-list {{
      margin: 0;
      padding-left: 18px;
    }}
    .value-list li + li {{ margin-top: 4px; }}
    .empty-value {{ color: #8a95a6; font-style: italic; }}
    .review-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      min-width: 0;
    }}
    .review-field {{ min-width: 0; color: var(--muted); font-size: 12px; font-weight: 740; }}
    .field-label {{ display: block; color: #303a4b; overflow-wrap: anywhere; }}
    .field-help {{
      display: block;
      margin-top: 5px;
      color: #667085;
      font-size: 11px;
      line-height: 1.38;
      font-weight: 520;
    }}
    select, textarea {{
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
    select {{ min-height: 32px; }}
    select:focus-visible, textarea:focus-visible, .nav-button:focus-visible {{
      outline: 3px solid rgba(91, 95, 151, 0.24);
      outline-offset: 2px;
    }}
    .notes {{ grid-column: 1 / -1; }}
    textarea {{ min-height: 74px; resize: vertical; }}
    @media (max-width: 1280px) {{
      .sample-brief {{ grid-template-columns: 1fr; }}
      .memory-card-head {{ grid-template-columns: 96px 1fr; }}
      .memory-facts {{ grid-column: 2; }}
      .memory-card-layout {{ grid-template-columns: 1fr; }}
      .review-panel {{
        border-top: 1px solid var(--line);
        border-left: 0;
        max-height: none;
        position: static;
      }}
    }}
    @media (max-width: 760px) {{
      header, .metrics, .sample-nav, main {{ padding-left: 14px; padding-right: 14px; }}
      .metrics {{ grid-template-columns: 1fr 1fr; }}
      .sample-nav {{ grid-template-columns: 1fr; }}
      .sample-position {{ order: -1; }}
      .memory-card-head {{ grid-template-columns: 1fr; }}
      .label-block {{ min-height: auto; grid-template-columns: auto auto; justify-content: start; padding: 12px; }}
      .memory-facts {{ grid-column: 1; }}
      .memory-facts, .sample-stats {{ grid-template-columns: 1fr; }}
      .detail-list, .nested-detail-list {{ grid-template-columns: 1fr; }}
      .review-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>CRK-2 Canonical Memory 人工审查</h1>
    <p>每页对应一个样本，样本内展示所有 model-facing parent memory block。审查重点是记忆条目、原子拆分、A/B/C 标签和 judge rubric 是否可辩护。</p>
  </header>
  <section class="metrics">
    <div class="metric"><strong>{html.escape(str(display_summary.get('total_samples', 0)))}</strong><span>samples</span></div>
    <div class="metric"><strong>{html.escape(str(display_summary.get('total_parent_rows', len(rows))))}</strong><span>parent rows</span></div>
    <div class="metric"><strong>{html.escape(str(display_summary.get('mixed_parent_rows', 0)))}</strong><span>mixed-label rows</span></div>
    <div class="metric"><strong>{html.escape(str(display_summary.get('homogeneous_parent_rows', 0)))}</strong><span>homogeneous rows</span></div>
  </section>
  <nav class="sample-nav" aria-label="Sample navigation">
    <button class="nav-button" id="prev-sample" type="button">上一条</button>
    <div class="sample-position" aria-live="polite">
      <span id="sample-counter">1 / {len(grouped_samples)}</span>
      <span id="sample-title">{cell(grouped_samples[0][0] if grouped_samples else '')}</span>
    </div>
    <button class="nav-button" id="next-sample" type="button">下一条</button>
  </nav>
  <main>
    {''.join(sample_pages)}
  </main>
  <script>
    const pages = Array.from(document.querySelectorAll(".sample-page"));
    const counter = document.getElementById("sample-counter");
    const title = document.getElementById("sample-title");
    const prevButton = document.getElementById("prev-sample");
    const nextButton = document.getElementById("next-sample");
    let currentIndex = 0;

    function showSample(index) {{
      if (!pages.length) return;
      currentIndex = Math.max(0, Math.min(index, pages.length - 1));
      pages.forEach((page, pageIndex) => {{
        page.classList.toggle("active", pageIndex === currentIndex);
      }});
      counter.textContent = `${{currentIndex + 1}} / ${{pages.length}}`;
      title.textContent = pages[currentIndex].dataset.sampleId || "";
      prevButton.disabled = currentIndex === 0;
      nextButton.disabled = currentIndex === pages.length - 1;
      window.scrollTo({{ top: 0, behavior: "instant" }});
    }}

    prevButton.addEventListener("click", () => showSample(currentIndex - 1));
    nextButton.addEventListener("click", () => showSample(currentIndex + 1));
    document.addEventListener("keydown", (event) => {{
      const target = event.target;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      const key = event.key.toLowerCase();
      if (event.key === "ArrowRight" || key === "j") {{
        event.preventDefault();
        showSample(currentIndex + 1);
      }}
      if (event.key === "ArrowLeft" || key === "k") {{
        event.preventDefault();
        showSample(currentIndex - 1);
      }}
    }});
    showSample(0);
  </script>
</body>
</html>
"""
    path.write_text("\n".join(line.rstrip() for line in content.splitlines()) + "\n", encoding="utf-8")


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
