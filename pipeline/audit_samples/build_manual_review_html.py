#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path
from typing import Any


AUDIT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = AUDIT_DIR / "manual_quality_review_samples.jsonl"
DEFAULT_OUTPUT = AUDIT_DIR / "manual_quality_review.html"


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def label_sequence(row: dict[str, Any]) -> str:
    prefs = row.get("record", {}).get("preferences", []) or []
    return "".join(str(pref.get("u_star", "")) for pref in prefs)


def count_preferences(row: dict[str, Any]) -> int:
    return len(row.get("record", {}).get("preferences", []) or [])


def enrich_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for row in rows:
        record = row.get("record", {}) or {}
        verification = record.get("verification", {}) or {}
        enriched.append(
            {
                **row,
                "review_overall": "",
                "review_issue_types": [],
                "review_notes": "",
                "summary": {
                    "record_id": record.get("id", ""),
                    "source_raw_id": record.get("source_raw_id", ""),
                    "source_dataset": record.get("source_dataset", ""),
                    "source_split": record.get("source_split", ""),
                    "source_index": record.get("source_index", ""),
                    "topic": record.get("topic", ""),
                    "question": record.get("question", ""),
                    "question_lang": question_lang(record.get("question", "")),
                    "intent_type": label_sequence(row),
                    "preference_count": count_preferences(row),
                    "reject_errors": row.get("reject_errors", []) or [],
                    "record_level_issues": verification.get("record_level_issues", []) or [],
                },
            }
        )
    return enriched


def question_lang(text: str) -> str:
    chars = [ch for ch in str(text or "") if not ch.isspace()]
    if not chars:
        return "empty"
    cjk = sum(1 for ch in chars if "\u4e00" <= ch <= "\u9fff")
    ratio = cjk / len(chars)
    if ratio >= 0.2:
        return "cjk_heavy"
    if ratio >= 0.02:
        return "mixed_cjk"
    return "mostly_non_cjk"


def unique_values(rows: list[dict[str, Any]], field: str) -> list[str]:
    values = set()
    for row in rows:
        if field == "status":
            value = row.get("record_status", "")
        elif field == "bucket":
            value = row.get("sample_bucket", "")
        else:
            value = row.get("summary", {}).get(field, "")
        if value:
            values.add(str(value))
    return sorted(values)


def options(values: list[str]) -> str:
    return "\n".join(f'<option value="{html.escape(value)}">{html.escape(value)}</option>' for value in values)


def build_html(rows: list[dict[str, Any]], input_path: Path) -> str:
    enriched = enrich_rows(rows)
    status_counts = Counter(row.get("record_status", "") for row in enriched)
    bucket_counts = Counter(row.get("sample_bucket", "") for row in enriched)
    topic_counts = Counter(row.get("summary", {}).get("topic", "") for row in enriched)
    data_json = json.dumps(enriched, ensure_ascii=False, separators=(",", ":"))
    stats_json = json.dumps(
        {
            "rows": len(enriched),
            "status_counts": dict(status_counts),
            "bucket_counts": dict(bucket_counts),
            "topic_counts": dict(topic_counts),
            "input": str(input_path),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Medical RPEval Manual Review</title>
  <style>
    :root {{
      --ink: #1f2933;
      --muted: #5b6673;
      --line: #d7dde5;
      --panel: #ffffff;
      --wash: #f6f8fb;
      --quiet: #eef2f7;
      --blue: #2463eb;
      --green: #0f8a5f;
      --yellow: #a16207;
      --red: #b42318;
      --violet: #6d28d9;
      --shadow: 0 12px 30px rgba(31, 41, 51, 0.08);
      --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      --sans: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}

    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: var(--wash);
      font-family: var(--sans);
      letter-spacing: 0;
    }}
    button, input, select, textarea {{
      font: inherit;
    }}
    button {{
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--ink);
      border-radius: 7px;
      min-height: 36px;
      padding: 0 12px;
      cursor: pointer;
    }}
    button:hover {{ border-color: #9aa8ba; }}
    button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible {{
      outline: 2px solid var(--blue);
      outline-offset: 2px;
    }}
    .app {{
      min-height: 100vh;
      display: grid;
      grid-template-columns: 320px minmax(0, 1fr);
    }}
    .sidebar {{
      position: sticky;
      top: 0;
      height: 100vh;
      overflow: auto;
      background: #ffffff;
      border-right: 1px solid var(--line);
      padding: 18px 16px;
    }}
    .brand {{
      display: flex;
      flex-direction: column;
      gap: 5px;
      margin-bottom: 18px;
    }}
    .brand h1 {{
      margin: 0;
      font-size: 18px;
      line-height: 1.2;
      font-weight: 760;
    }}
    .brand p {{
      margin: 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }}
    .progress-box {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      margin-bottom: 14px;
      background: linear-gradient(180deg, #ffffff, #fbfcfe);
    }}
    .progress-row {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
      margin-bottom: 9px;
    }}
    .progress-row strong {{ font-size: 20px; }}
    .progress-row span {{ color: var(--muted); font-size: 12px; }}
    .bar {{
      height: 8px;
      background: var(--quiet);
      border-radius: 999px;
      overflow: hidden;
    }}
    .bar-fill {{
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, var(--blue), var(--green));
    }}
    .filters {{
      display: grid;
      gap: 10px;
      margin-top: 14px;
    }}
    .field label {{
      display: block;
      font-size: 12px;
      font-weight: 700;
      color: #374151;
      margin-bottom: 5px;
    }}
    .field select, .field input {{
      width: 100%;
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #fff;
      padding: 0 10px;
    }}
    .checkbox-row {{
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
    }}
    .actions {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-top: 14px;
    }}
    .actions button.primary {{
      grid-column: span 2;
      background: var(--ink);
      color: #fff;
      border-color: var(--ink);
    }}
    .content {{
      padding: 22px;
      min-width: 0;
    }}
    .topbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 14px;
      margin-bottom: 14px;
    }}
    .topbar-title {{
      min-width: 0;
    }}
    .topbar-title h2 {{
      margin: 0;
      font-size: 20px;
      line-height: 1.25;
    }}
    .topbar-title p {{
      margin: 5px 0 0;
      color: var(--muted);
      font-size: 13px;
    }}
    .nav {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .counter {{
      color: var(--muted);
      min-width: 88px;
      text-align: center;
      font-variant-numeric: tabular-nums;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .card-head {{
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 0 8px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: var(--quiet);
      color: #344054;
      font-size: 12px;
      font-weight: 650;
    }}
    .pill.status-verified {{ background: #e7f7ef; color: var(--green); border-color: #b9e5cf; }}
    .pill.status-rejected {{ background: #fff1f0; color: var(--red); border-color: #ffd0cc; }}
    .pill.lang-mixed_cjk {{ background: #f4ecff; color: var(--violet); border-color: #dcc7ff; }}
    .question {{
      padding: 18px 18px 8px;
    }}
    .question h3 {{
      margin: 0 0 8px;
      font-size: 12px;
      text-transform: uppercase;
      color: var(--muted);
      letter-spacing: 0;
    }}
    .question-text {{
      margin: 0;
      font-size: 23px;
      line-height: 1.45;
      font-weight: 720;
      overflow-wrap: anywhere;
    }}
    .review-panel {{
      margin: 14px 18px 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcff;
      padding: 12px;
    }}
    .review-grid {{
      display: grid;
      grid-template-columns: minmax(240px, 0.8fr) minmax(260px, 1.2fr);
      gap: 12px;
    }}
    .segmented {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 6px;
    }}
    .review-choice {{
      min-width: 0;
      padding: 0 6px;
      font-size: 13px;
      font-weight: 700;
    }}
    .review-choice.active[data-review-value="pass"] {{ color: #fff; background: var(--green); border-color: var(--green); }}
    .review-choice.active[data-review-value="minor_fix"] {{ color: #fff; background: var(--blue); border-color: var(--blue); }}
    .review-choice.active[data-review-value="major_fix"] {{ color: #fff; background: var(--yellow); border-color: var(--yellow); }}
    .review-choice.active[data-review-value="drop"] {{ color: #fff; background: var(--red); border-color: var(--red); }}
    .issue-select {{
      width: 100%;
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 5px 8px;
      background: #fff;
    }}
    .notes {{
      grid-column: span 2;
    }}
    .notes textarea {{
      width: 100%;
      min-height: 74px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 9px 10px;
      line-height: 1.45;
    }}
    .section {{
      padding: 18px;
      border-top: 1px solid var(--line);
    }}
    .compact-section {{
      padding-top: 12px;
      padding-bottom: 12px;
    }}
    .section h3 {{
      margin: 0 0 10px;
      font-size: 14px;
      line-height: 1.2;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }}
    .muted {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 500;
    }}
    details {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      overflow: hidden;
    }}
    summary {{
      cursor: pointer;
      padding: 12px;
      font-size: 14px;
      font-weight: 760;
      color: #263343;
      list-style-position: inside;
    }}
    summary:hover {{
      background: #f8fafc;
    }}
    .meta-grid {{
      display: grid;
      grid-template-columns: minmax(160px, 240px) minmax(0, 1fr);
      border-top: 1px solid var(--line);
    }}
    .meta-key, .meta-value {{
      padding: 9px 12px;
      border-bottom: 1px solid var(--line);
      font-size: 13px;
      line-height: 1.45;
    }}
    .meta-key {{
      font-family: var(--mono);
      color: #475467;
      background: #f8fafc;
      border-right: 1px solid var(--line);
    }}
    .meta-value {{
      overflow-wrap: anywhere;
      color: #1f2933;
    }}
    .prefs {{
      display: grid;
      gap: 10px;
    }}
    .pref {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 11px 12px;
      background: #fff;
    }}
    .pref-top {{
      display: flex;
      gap: 8px;
      align-items: center;
      margin-bottom: 8px;
      flex-wrap: wrap;
    }}
    .label {{
      width: 26px;
      height: 26px;
      border-radius: 50%;
      color: white;
      display: inline-grid;
      place-items: center;
      font-weight: 800;
      font-size: 13px;
    }}
    .label-A {{ background: #64748b; }}
    .label-B {{ background: var(--blue); }}
    .label-C {{ background: var(--red); }}
    .pref-text {{
      margin: 0 0 8px;
      font-size: 15px;
      line-height: 1.55;
      overflow-wrap: anywhere;
    }}
    .reason {{
      margin: 0;
      color: #475467;
      font-size: 13px;
      line-height: 1.55;
      overflow-wrap: anywhere;
    }}
    .two-col {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
    }}
    .text-box {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 12px;
      max-height: 360px;
      overflow: auto;
      line-height: 1.6;
      font-size: 14px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }}
    .json-box {{
      margin: 0;
      border-top: 1px solid var(--line);
      background: #0f172a;
      color: #e5e7eb;
      padding: 12px;
      max-height: 420px;
      overflow: auto;
      font-family: var(--mono);
      font-size: 12px;
      line-height: 1.55;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }}
    .issue-box {{
      border-left: 4px solid var(--red);
      background: #fff7f6;
      color: #7a271a;
      padding: 12px;
      border-radius: 7px;
      white-space: pre-wrap;
      line-height: 1.55;
      font-size: 13px;
      overflow-wrap: anywhere;
    }}
    .empty {{
      border: 1px dashed var(--line);
      border-radius: 8px;
      padding: 28px;
      background: #fff;
      color: var(--muted);
      text-align: center;
    }}
    .kbd {{
      font-family: var(--mono);
      font-size: 11px;
      background: #eef2f7;
      border: 1px solid #d7dde5;
      border-bottom-color: #b8c2ce;
      border-radius: 5px;
      padding: 1px 5px;
    }}
    @media (max-width: 980px) {{
      .app {{ grid-template-columns: 1fr; }}
      .sidebar {{
        position: static;
        height: auto;
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }}
      .review-grid, .two-col {{ grid-template-columns: 1fr; }}
      .meta-grid {{ grid-template-columns: 1fr; }}
      .meta-key {{ border-right: 0; }}
      .notes {{ grid-column: auto; }}
      .question-text {{ font-size: 19px; }}
      .content {{ padding: 14px; }}
    }}
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="brand">
        <h1>Medical RPEval Review</h1>
        <p>逐条审查 question、preferences、原始问答和 verifier 问题。标注会自动保存在本浏览器。</p>
      </div>

      <div class="progress-box">
        <div class="progress-row">
          <strong id="progressText">0 / {len(enriched)}</strong>
          <span id="filteredText">{len(enriched)} shown</span>
        </div>
        <div class="bar"><div class="bar-fill" id="progressFill"></div></div>
      </div>

      <div class="filters">
        <div class="field">
          <label for="searchInput">搜索</label>
          <input id="searchInput" type="search" placeholder="question / preference / issue">
        </div>
        <div class="field">
          <label for="statusFilter">状态</label>
          <select id="statusFilter">
            <option value="">All statuses</option>
            {options(unique_values(enriched, "status"))}
          </select>
        </div>
        <div class="field">
          <label for="bucketFilter">抽样 bucket</label>
          <select id="bucketFilter">
            <option value="">All buckets</option>
            {options(unique_values(enriched, "bucket"))}
          </select>
        </div>
        <div class="field">
          <label for="topicFilter">Topic</label>
          <select id="topicFilter">
            <option value="">All topics</option>
            {options(unique_values(enriched, "topic"))}
          </select>
        </div>
        <div class="field">
          <label for="langFilter">语言</label>
          <select id="langFilter">
            <option value="">All languages</option>
            {options(unique_values(enriched, "question_lang"))}
          </select>
        </div>
        <div class="field">
          <label for="sourceFilter">来源</label>
          <select id="sourceFilter">
            <option value="">All sources</option>
            {options(unique_values(enriched, "source_dataset"))}
          </select>
        </div>
        <label class="checkbox-row">
          <input id="unreviewedOnly" type="checkbox">
          只看未审查
        </label>
      </div>

      <div class="actions">
        <button type="button" id="resetFilters">Reset</button>
        <button type="button" id="clearCurrent">Clear row</button>
        <button type="button" id="exportJson" class="primary">Export JSON</button>
        <button type="button" id="exportCsv">Export CSV</button>
      </div>
    </aside>

    <main class="content">
      <div class="topbar">
        <div class="topbar-title">
          <h2 id="sampleTitle">Sample</h2>
          <p>快捷键：<span class="kbd">J</span>/<span class="kbd">K</span> 切换，<span class="kbd">1</span>-<span class="kbd">4</span> 标注，输入备注时快捷键不会触发。</p>
        </div>
        <div class="nav">
          <button type="button" id="prevBtn">Prev</button>
          <span class="counter" id="positionText">0 / 0</span>
          <button type="button" id="nextBtn">Next</button>
        </div>
      </div>
      <div id="recordMount"></div>
    </main>
  </div>

  <script>
    window.REVIEW_SAMPLES = {data_json};
    window.REVIEW_STATS = {stats_json};
  </script>
  <script>
    const STORAGE_KEY = "med-rpeval-review-v1";
    const ISSUE_TYPES = [
      "question_not_decontextualized",
      "question_preference_leakage",
      "source_task_drift",
      "wrong_u_star",
      "unnatural_preference",
      "medical_inaccuracy",
      "unsafe_personalization",
      "language_inconsistent",
      "duplicate_or_near_duplicate",
      "too_much_synthetic_context",
      "other"
    ];
    const samples = window.REVIEW_SAMPLES;
    let annotations = loadAnnotations();
    let filtered = samples.slice();
    let currentIndex = 0;

    const els = {{
      mount: document.getElementById("recordMount"),
      search: document.getElementById("searchInput"),
      status: document.getElementById("statusFilter"),
      bucket: document.getElementById("bucketFilter"),
      topic: document.getElementById("topicFilter"),
      lang: document.getElementById("langFilter"),
      source: document.getElementById("sourceFilter"),
      unreviewed: document.getElementById("unreviewedOnly"),
      reset: document.getElementById("resetFilters"),
      clear: document.getElementById("clearCurrent"),
      exportJson: document.getElementById("exportJson"),
      exportCsv: document.getElementById("exportCsv"),
      prev: document.getElementById("prevBtn"),
      next: document.getElementById("nextBtn"),
      title: document.getElementById("sampleTitle"),
      pos: document.getElementById("positionText"),
      progressText: document.getElementById("progressText"),
      progressFill: document.getElementById("progressFill"),
      filteredText: document.getElementById("filteredText")
    }};

    function loadAnnotations() {{
      try {{
        return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{{}}");
      }} catch (_err) {{
        return {{}};
      }}
    }}

    function saveAnnotations() {{
      localStorage.setItem(STORAGE_KEY, JSON.stringify(annotations));
      updateProgress();
    }}

    function annotationFor(row) {{
      if (!annotations[row.review_id]) {{
        annotations[row.review_id] = {{
          review_id: row.review_id,
          record_status: row.record_status,
          sample_bucket: row.sample_bucket,
          record_id: row.summary.record_id,
          review_overall: "",
          review_issue_types: [],
          review_notes: "",
          updated_at: ""
        }};
      }}
      return annotations[row.review_id];
    }}

    function reviewedCount() {{
      return samples.filter(row => (annotations[row.review_id] || {{}}).review_overall).length;
    }}

    function updateProgress() {{
      const done = reviewedCount();
      const pct = samples.length ? Math.round(done / samples.length * 100) : 0;
      els.progressText.textContent = `${{done}} / ${{samples.length}}`;
      els.progressFill.style.width = `${{pct}}%`;
      els.filteredText.textContent = `${{filtered.length}} shown`;
    }}

    function haystack(row) {{
      return JSON.stringify([
        row.review_id,
        row.sample_bucket,
        row.review_focus,
        row.record_status,
        row.summary,
        row.record && row.record.preferences,
        row.record && row.record.raw_question,
        row.record && row.record.doctor_answer,
        row.reject_errors
      ]).toLowerCase();
    }}

    function applyFilters() {{
      const q = els.search.value.trim().toLowerCase();
      filtered = samples.filter(row => {{
        const ann = annotations[row.review_id] || {{}};
        if (els.status.value && row.record_status !== els.status.value) return false;
        if (els.bucket.value && row.sample_bucket !== els.bucket.value) return false;
        if (els.topic.value && row.summary.topic !== els.topic.value) return false;
        if (els.lang.value && row.summary.question_lang !== els.lang.value) return false;
        if (els.source.value && row.summary.source_dataset !== els.source.value) return false;
        if (els.unreviewed.checked && ann.review_overall) return false;
        if (q && !haystack(row).includes(q)) return false;
        return true;
      }});
      currentIndex = Math.min(currentIndex, Math.max(filtered.length - 1, 0));
      render();
    }}

    function escapeHtml(value) {{
      return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    }}

    function pills(row) {{
      const parts = [
        `<span class="pill status-${{escapeHtml(row.record_status)}}">${{escapeHtml(row.record_status)}}</span>`,
        `<span class="pill">${{escapeHtml(row.review_id)}}</span>`,
        `<span class="pill">${{escapeHtml(row.summary.topic || "no_topic")}}</span>`,
        `<span class="pill lang-${{escapeHtml(row.summary.question_lang)}}">${{escapeHtml(row.summary.question_lang)}}</span>`,
        `<span class="pill">${{escapeHtml(row.summary.intent_type || "no_labels")}}</span>`,
        `<span class="pill">${{escapeHtml(row.summary.source_dataset || "unknown_source")}}</span>`,
        `<span class="pill">${{escapeHtml(row.sample_bucket)}}</span>`
      ];
      return parts.join("");
    }}

    function prefHtml(pref, index) {{
      const label = escapeHtml(pref.u_star || "?");
      const issue = pref.verify_issue ? `<p class="reason"><strong>Issue:</strong> ${{escapeHtml(pref.verify_issue)}}</p>` : "";
      const verify = pref.verify_reason ? `<p class="reason"><strong>Verifier:</strong> ${{escapeHtml(pref.verify_reason)}}</p>` : "";
      return `<article class="pref">
        <div class="pref-top">
          <span class="label label-${{label}}">${{label}}</span>
          <span class="pill">#${{index + 1}}</span>
          <span class="pill">${{escapeHtml(pref.source || "no_source")}}</span>
          <span class="pill">${{escapeHtml(pref.boundary_case || "none")}}</span>
        </div>
        <p class="pref-text">${{escapeHtml(pref.preference || "")}}</p>
        <p class="reason"><strong>Reason:</strong> ${{escapeHtml(pref.reason || "")}}</p>
        ${{verify}}
        ${{issue}}
      </article>`;
    }}

    function issueOptions(selected) {{
      const selectedSet = new Set(selected || []);
      return ISSUE_TYPES.map(issue =>
        `<option value="${{issue}}" ${{selectedSet.has(issue) ? "selected" : ""}}>${{issue}}</option>`
      ).join("");
    }}

    function renderReviewPanel(row, ann) {{
      const choices = [
        ["pass", "Pass"],
        ["minor_fix", "Minor"],
        ["major_fix", "Major"],
        ["drop", "Drop"]
      ].map(([value, label]) =>
        `<button type="button" class="review-choice ${{ann.review_overall === value ? "active" : ""}}" data-review-value="${{value}}">${{label}}</button>`
      ).join("");
      return `<section class="review-panel">
        <div class="review-grid">
          <div>
            <label class="muted">Overall</label>
            <div class="segmented" id="reviewChoices">${{choices}}</div>
          </div>
          <div>
            <label class="muted" for="issueSelect">Issue types</label>
            <select id="issueSelect" class="issue-select" multiple size="4">${{issueOptions(ann.review_issue_types)}}</select>
          </div>
          <div class="notes">
            <label class="muted" for="notesInput">Notes</label>
            <textarea id="notesInput" placeholder="记录人工判断、需要修复的位置或原因">${{escapeHtml(ann.review_notes || "")}}</textarea>
          </div>
        </div>
      </section>`;
    }}

    function issuesHtml(row) {{
      const chunks = [];
      if ((row.reject_errors || []).length) chunks.push(`Reject errors:\\n${{row.reject_errors.join("\\n")}}`);
      if ((row.summary.record_level_issues || []).length) chunks.push(`Record issues:\\n${{row.summary.record_level_issues.join("\\n")}}`);
      const items = ((row.record.verification || {{}}).items || [])
        .filter(item => item.issue || item.pass !== true)
        .map(item => `#${{item.index}} pass=${{item.pass}} issue=${{item.issue || ""}} audit=${{item.audit_reason || ""}}`);
      if (items.length) chunks.push(`Item issues:\\n${{items.join("\\n")}}`);
      if (!chunks.length) return "";
      return `<section class="section"><h3>Verifier / Reject Issues</h3><div class="issue-box">${{escapeHtml(chunks.join("\\n\\n"))}}</div></section>`;
    }}

    function metadataHtml(row) {{
      const record = row.record || {{}};
      const fields = [
        ["review_id", row.review_id],
        ["sample_bucket", row.sample_bucket],
        ["review_focus", row.review_focus],
        ["record_status", row.record_status],
        ["record.id", record.id],
        ["source_raw_id", record.source_raw_id],
        ["source_dataset", record.source_dataset],
        ["source_split", record.source_split],
        ["source_index", record.source_index],
        ["topic", record.topic],
        ["question_lang", row.summary.question_lang],
        ["intent_type", row.summary.intent_type],
        ["preference_count", row.summary.preference_count]
      ];
      const rows = fields.map(([key, value]) => `
        <div class="meta-key">${{escapeHtml(key)}}</div>
        <div class="meta-value">${{escapeHtml(value ?? "")}}</div>
      `).join("");
      return `<section class="section compact-section">
        <details>
          <summary>Metadata</summary>
          <div class="meta-grid">${{rows}}</div>
        </details>
      </section>`;
    }}

    function fullVerifierAuditHtml(row) {{
      const record = row.record || {{}};
      const verification = record.verification || {{}};
      const payload = {{
        reject_errors: row.reject_errors || [],
        record_level_issues: verification.record_level_issues || [],
        items: verification.items || []
      }};
      return `<section class="section compact-section">
        <details>
          <summary>Full verifier audit</summary>
          <pre class="json-box">${{escapeHtml(JSON.stringify(payload, null, 2))}}</pre>
        </details>
      </section>`;
    }}

    function render() {{
      updateProgress();
      if (!filtered.length) {{
        els.title.textContent = "No matching samples";
        els.pos.textContent = "0 / 0";
        els.mount.innerHTML = `<div class="empty">没有符合当前筛选条件的样本。</div>`;
        return;
      }}

      const row = filtered[currentIndex];
      const record = row.record || {{}};
      const ann = annotationFor(row);
      els.title.textContent = `${{row.review_id}} · ${{row.review_focus}}`;
      els.pos.textContent = `${{currentIndex + 1}} / ${{filtered.length}}`;

      const prefs = (record.preferences || []).map(prefHtml).join("") || `<div class="empty">No preferences</div>`;
      els.mount.innerHTML = `<article class="card">
        <header class="card-head">${{pills(row)}}</header>
        <section class="question">
          <h3>Generated question / 构造后问题</h3>
          <p class="question-text">${{escapeHtml(record.question || "")}}</p>
        </section>
        ${{renderReviewPanel(row, ann)}}
        ${{metadataHtml(row)}}
        ${{fullVerifierAuditHtml(row)}}
        <section class="section">
          <h3>Preferences <span class="muted">${{record.preferences ? record.preferences.length : 0}} items</span></h3>
          <div class="prefs">${{prefs}}</div>
        </section>
        ${{issuesHtml(row)}}
        <section class="section">
          <h3>Raw Source</h3>
          <div class="two-col">
            <div>
              <h3>Original raw question / 原始问题</h3>
              <div class="text-box">${{escapeHtml(record.raw_question || "")}}</div>
            </div>
            <div>
              <h3>Original doctor answer / 原始医生回答</h3>
              <div class="text-box">${{escapeHtml(record.doctor_answer || "")}}</div>
            </div>
          </div>
        </section>
        <section class="section">
          <h3>Generation notes</h3>
          <div class="text-box">${{escapeHtml(record.generation_notes || "")}}</div>
        </section>
      </article>`;

      document.querySelectorAll(".review-choice").forEach(button => {{
        button.addEventListener("click", () => setReview(row, button.dataset.reviewValue));
      }});
      document.getElementById("issueSelect").addEventListener("change", event => {{
        ann.review_issue_types = Array.from(event.target.selectedOptions).map(option => option.value);
        ann.updated_at = new Date().toISOString();
        saveAnnotations();
      }});
      document.getElementById("notesInput").addEventListener("input", event => {{
        ann.review_notes = event.target.value;
        ann.updated_at = new Date().toISOString();
        saveAnnotations();
      }});
    }}

    function setReview(row, value) {{
      const ann = annotationFor(row);
      ann.review_overall = ann.review_overall === value ? "" : value;
      ann.updated_at = new Date().toISOString();
      saveAnnotations();
      render();
    }}

    function move(delta) {{
      if (!filtered.length) return;
      currentIndex = Math.max(0, Math.min(filtered.length - 1, currentIndex + delta));
      render();
      window.scrollTo({{ top: 0, behavior: "smooth" }});
    }}

    function resetFilters() {{
      els.search.value = "";
      els.status.value = "";
      els.bucket.value = "";
      els.topic.value = "";
      els.lang.value = "";
      els.source.value = "";
      els.unreviewed.checked = false;
      currentIndex = 0;
      applyFilters();
    }}

    function clearCurrent() {{
      if (!filtered.length) return;
      const row = filtered[currentIndex];
      delete annotations[row.review_id];
      saveAnnotations();
      render();
    }}

    function reviewRows() {{
      return samples.map(row => ({{
        review_id: row.review_id,
        sample_bucket: row.sample_bucket,
        review_focus: row.review_focus,
        record_status: row.record_status,
        record_id: row.summary.record_id,
        source_raw_id: row.summary.source_raw_id,
        source_dataset: row.summary.source_dataset,
        source_split: row.summary.source_split,
        source_index: row.summary.source_index,
        topic: row.summary.topic,
        question_lang: row.summary.question_lang,
        question: row.summary.question,
        intent_type: row.summary.intent_type,
        preference_count: row.summary.preference_count,
        review_overall: (annotations[row.review_id] || {{}}).review_overall || "",
        review_issue_types: ((annotations[row.review_id] || {{}}).review_issue_types || []).join(";"),
        review_notes: (annotations[row.review_id] || {{}}).review_notes || "",
        updated_at: (annotations[row.review_id] || {{}}).updated_at || ""
      }}));
    }}

    function download(filename, content, type) {{
      const blob = new Blob([content], {{ type }});
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    }}

    function exportJson() {{
      const payload = {{
        exported_at: new Date().toISOString(),
        source_stats: window.REVIEW_STATS,
        annotations,
        rows: reviewRows()
      }};
      download("manual_quality_review_results.json", JSON.stringify(payload, null, 2), "application/json;charset=utf-8");
    }}

    function csvEscape(value) {{
      const text = String(value ?? "");
      return `"${{text.replace(/"/g, '""')}}"`;
    }}

    function exportCsv() {{
      const rows = reviewRows();
      const headers = Object.keys(rows[0] || {{ review_id: "" }});
      const body = [headers.join(",")]
        .concat(rows.map(row => headers.map(header => csvEscape(row[header])).join(",")))
        .join("\\n");
      download("manual_quality_review_results.csv", body, "text/csv;charset=utf-8");
    }}

    [els.search, els.status, els.bucket, els.topic, els.lang, els.source, els.unreviewed].forEach(el => {{
      el.addEventListener("input", applyFilters);
      el.addEventListener("change", applyFilters);
    }});
    els.reset.addEventListener("click", resetFilters);
    els.clear.addEventListener("click", clearCurrent);
    els.exportJson.addEventListener("click", exportJson);
    els.exportCsv.addEventListener("click", exportCsv);
    els.prev.addEventListener("click", () => move(-1));
    els.next.addEventListener("click", () => move(1));
    document.addEventListener("keydown", event => {{
      const target = event.target;
      const typing = target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
      if (typing) return;
      if (event.key === "j" || event.key === "ArrowRight") move(1);
      if (event.key === "k" || event.key === "ArrowLeft") move(-1);
      if (["1", "2", "3", "4"].includes(event.key) && filtered.length) {{
        const values = ["pass", "minor_fix", "major_fix", "drop"];
        setReview(filtered[currentIndex], values[Number(event.key) - 1]);
      }}
    }});

    applyFilters();
  </script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a standalone manual review HTML page.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    rows = iter_jsonl(args.input)
    html_text = build_html(rows, args.input)
    args.output.write_text(html_text, encoding="utf-8")
    print(json.dumps({"output": str(args.output), "rows": len(rows)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
