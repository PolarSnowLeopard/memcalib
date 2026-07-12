#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

from utils import iter_jsonl, load_json


DIMENSION_NAMES = (
    "question_completeness",
    "answer_relevance",
    "answer_substantiveness",
    "memory_extractability",
    "text_integrity",
    "safety_plausibility",
)
DIMENSION_COPY = {
    "question_completeness": ("Question completeness", "问题是否完整、明确并可解释"),
    "answer_relevance": ("Answer relevance", "回答是否直接对应核心问题"),
    "answer_substantiveness": ("Answer substantiveness", "回答是否包含实质解释或行动建议"),
    "memory_extractability": ("Memory extractability", "问题中是否存在无需推断的用户事实"),
    "text_integrity": ("Text integrity", "问答是否完整且属于同一记录"),
    "safety_plausibility": ("Safety plausibility", "是否存在明确危险或明显不可信内容"),
}


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _dimension_html(name: str, item: dict[str, Any], record_id: str) -> str:
    label = str(item.get("label") or "missing")
    title, explanation = DIMENSION_COPY[name]
    options = ["未标注", "同意模型判断", "应为 pass", "应为 uncertain", "应为 reject"]
    option_html = "".join(f'<option value="{esc(option)}">{esc(option)}</option>' for option in options)
    return f"""
    <section class="dimension {esc(label)}">
      <div class="dimension-head">
        <div><h3>{esc(title)}</h3><p>{esc(explanation)}</p></div>
        <span class="verdict">{esc(label)}</span>
      </div>
      <blockquote><span>Exact evidence</span>{esc(item.get('evidence'))}</blockquote>
      <p class="reason">{esc(item.get('reason'))}</p>
      <label class="manual-field">人工复核
        <select data-record="{esc(record_id)}" data-field="dimension.{esc(name)}">{option_html}</select>
      </label>
    </section>"""


def _sample_page(record: dict[str, Any], index: int) -> str:
    semantic = record.get("semantic_qc") or {}
    judgment = semantic.get("judgment") or {}
    dimensions = judgment.get("dimensions") or {}
    state = str(semantic.get("state") or "invalid")
    record_id = str(record.get("id") or f"row-{index + 1}")
    active = " active" if index == 0 else ""
    dimension_html = "".join(_dimension_html(name, dimensions.get(name) or {}, record_id) for name in DIMENSION_NAMES)
    reject_reasons = judgment.get("reject_reasons") or []
    reason_text = ", ".join(str(reason) for reason in reject_reasons) if reject_reasons else "None"
    return f"""
    <article class="sample-page{active}" data-index="{index}" data-record-id="{esc(record_id)}">
      <header class="record-header state-{esc(state)}">
        <div>
          <span class="record-kicker">SOURCE SEMANTIC QC · {esc(record_id)}</span>
          <h1>{esc(record.get('source_dataset'))}</h1>
          <p>{esc(record.get('topic'))} · {esc((record.get('raw_selection') or {}).get('seed_complexity'))} · quality {esc((record.get('raw_selection') or {}).get('quality_score'))}</p>
        </div>
        <div class="state-mark"><span>QC STATE</span><strong>{esc(state)}</strong><small>{esc(judgment.get('confidence'))} confidence</small></div>
      </header>
      <main class="audit-grid">
        <section class="source-pane">
          <div class="source-section">
            <div class="source-label"><strong>Source question</strong><span>判断完整性与可提取记忆的唯一依据</span></div>
            <div class="source-copy question">{esc(record.get('raw_question'))}</div>
          </div>
          <div class="source-section">
            <div class="source-label"><strong>Source answer</strong><span>判断相关性、实质性与安全性的唯一依据</span></div>
            <div class="source-copy answer">{esc(record.get('doctor_answer'))}</div>
          </div>
          <section class="overall">
            <div><span>Overall verdict</span><strong>{esc(judgment.get('overall_verdict'))}</strong></div>
            <div><span>Reject reasons</span><strong>{esc(reason_text)}</strong></div>
            <p>{esc(judgment.get('summary'))}</p>
          </section>
          <section class="manual-overall">
            <h2>Manual audit</h2>
            <p>人工结论用于校准 rubric，不会直接覆盖模型输出。</p>
            <div class="manual-grid">
              <label>人工总体状态
                <select data-record="{esc(record_id)}" data-field="overall">
                  <option value="未标注">未标注</option><option value="strict_pass">strict_pass</option>
                  <option value="review">review</option><option value="reject">reject</option>
                </select>
              </label>
              <label>备注
                <textarea data-record="{esc(record_id)}" data-field="notes" placeholder="只记录模型判断不充分或错误之处"></textarea>
              </label>
            </div>
          </section>
        </section>
        <aside class="rubric-pane">
          <div class="rubric-title"><h2>Six grounded dimensions</h2><p>证据必须逐字来自左侧对应原文。</p></div>
          {dimension_html}
        </aside>
      </main>
    </article>"""


def build_html(records: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    pages = "".join(_sample_page(record, index) for index, record in enumerate(records))
    total = len(records)
    summary_copy = " · ".join(
        f"{name} {summary.get(name, 0)}" for name in ("strict_pass", "review", "reject", "invalid")
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CRK-2 Source Semantic QC Audit</title>
  <style>
    :root {{ --ink:#182235; --muted:#657188; --line:#d5dde8; --paper:#fff; --canvas:#e9eef2; --navy:#1c2a43; --teal:#08766d; --amber:#a46100; --red:#a83b3b; --soft:#f5f7f9; }}
    * {{ box-sizing:border-box; }}
    html,body {{ margin:0; min-height:100%; background:var(--canvas); color:var(--ink); font-family:Inter,"PingFang SC","Microsoft YaHei",Arial,sans-serif; letter-spacing:0; }}
    body {{ padding-top:72px; }}
    .topbar {{ position:fixed; z-index:20; inset:0 0 auto; height:72px; display:grid; grid-template-columns:170px 1fr 170px; align-items:center; gap:18px; padding:0 24px; background:rgba(251,252,253,.98); border-bottom:1px solid var(--line); box-shadow:0 4px 18px rgba(28,42,67,.08); }}
    button {{ height:38px; border:1px solid #bbc6d4; background:#fff; color:var(--navy); font-weight:750; cursor:pointer; }}
    button.primary {{ background:var(--navy); border-color:var(--navy); color:#fff; }} button:disabled {{ opacity:.35; cursor:default; }}
    .topmeta {{ text-align:center; min-width:0; }} .topmeta strong {{ display:block; font-size:17px; }} .topmeta span {{ display:block; margin-top:3px; color:var(--muted); font-size:11px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
    .sample-page {{ display:none; width:min(1700px,calc(100% - 24px)); min-height:calc(100vh - 88px); margin:12px auto; background:var(--paper); border:1px solid var(--line); box-shadow:0 16px 42px rgba(28,42,67,.08); }}
    .sample-page.active {{ display:block; }}
    .record-header {{ display:flex; justify-content:space-between; align-items:flex-end; gap:28px; padding:24px 30px; border-bottom:1px solid var(--line); border-left:8px solid var(--muted); }}
    .record-header.state-strict_pass {{ border-left-color:var(--teal); }} .record-header.state-review {{ border-left-color:var(--amber); }} .record-header.state-reject,.record-header.state-invalid {{ border-left-color:var(--red); }}
    .record-kicker {{ color:var(--muted); font-size:10px; font-weight:800; }} h1 {{ margin:7px 0 5px; font-size:23px; }} .record-header p {{ margin:0; color:var(--muted); font-size:12px; }}
    .state-mark {{ min-width:180px; padding-left:20px; border-left:1px solid var(--line); }} .state-mark span,.state-mark small {{ display:block; color:var(--muted); font-size:10px; }} .state-mark strong {{ display:block; margin:4px 0; font-size:22px; color:var(--navy); }}
    .audit-grid {{ display:grid; grid-template-columns:minmax(0,1.1fr) minmax(520px,.9fr); }} .source-pane,.rubric-pane {{ padding:26px 30px 34px; }} .rubric-pane {{ background:#f7f9fb; border-left:1px solid var(--line); }}
    .source-section + .source-section {{ margin-top:24px; }} .source-label {{ display:flex; justify-content:space-between; gap:20px; margin-bottom:9px; }} .source-label strong {{ font-size:14px; }} .source-label span {{ color:var(--muted); font-size:11px; text-align:right; }}
    .source-copy {{ padding:20px 22px; border:1px solid var(--line); border-left:4px solid #2b659e; background:var(--soft); font-family:Georgia,"Times New Roman",serif; font-size:15px; line-height:1.75; white-space:pre-wrap; }} .source-copy.answer {{ border-left-color:#7f8da3; background:#fff; }}
    .overall {{ margin-top:24px; padding:16px 18px; border-top:3px solid var(--navy); background:var(--soft); }} .overall > div {{ display:grid; grid-template-columns:130px 1fr; gap:12px; padding:5px 0; }} .overall span {{ color:var(--muted); font-size:11px; font-weight:700; }} .overall strong {{ font-size:12px; overflow-wrap:anywhere; }} .overall p {{ margin:10px 0 0; font-size:13px; line-height:1.55; }}
    .manual-overall {{ margin-top:24px; padding-top:18px; border-top:1px solid var(--line); }} .manual-overall h2,.rubric-title h2 {{ margin:0 0 4px; font-size:16px; }} .manual-overall p,.rubric-title p {{ margin:0; color:var(--muted); font-size:11px; }} .manual-grid {{ display:grid; grid-template-columns:220px 1fr; gap:14px; margin-top:14px; }}
    label {{ display:grid; gap:5px; color:var(--muted); font-size:10px; font-weight:700; }} select,textarea {{ width:100%; border:1px solid #bdc7d5; background:#fff; color:var(--ink); font:inherit; font-size:12px; }} select {{ height:34px; padding:0 8px; }} textarea {{ min-height:68px; padding:9px; resize:vertical; }}
    .rubric-title {{ padding-bottom:14px; border-bottom:2px solid var(--navy); }} .dimension {{ padding:15px 0; border-bottom:1px solid var(--line); }} .dimension-head {{ display:flex; justify-content:space-between; gap:16px; align-items:flex-start; }} .dimension h3 {{ margin:0 0 3px; font-size:13px; }} .dimension-head p {{ margin:0; color:var(--muted); font-size:10px; }}
    .verdict {{ min-width:70px; padding:4px 7px; border:1px solid currentColor; text-align:center; color:var(--muted); font-size:10px; font-weight:850; text-transform:uppercase; }} .dimension.pass .verdict {{ color:var(--teal); }} .dimension.uncertain .verdict {{ color:var(--amber); }} .dimension.reject .verdict {{ color:var(--red); }}
    blockquote {{ margin:10px 0 8px; padding:9px 11px; border-left:3px solid #8da0b7; background:#fff; font-family:Georgia,"Times New Roman",serif; font-size:12px; line-height:1.5; }} blockquote span {{ display:block; margin-bottom:3px; color:var(--muted); font-family:Inter,Arial,sans-serif; font-size:9px; font-weight:800; text-transform:uppercase; }} .reason {{ margin:0 0 9px; font-size:11px; line-height:1.5; }} .manual-field {{ grid-template-columns:82px 1fr; align-items:center; }}
    .export {{ position:fixed; z-index:21; right:18px; bottom:14px; width:112px; box-shadow:0 5px 16px rgba(28,42,67,.18); }}
    @media(max-width:1000px) {{ .audit-grid {{ grid-template-columns:1fr; }} .rubric-pane {{ border-left:0; border-top:1px solid var(--line); }} }}
    @media(max-width:640px) {{ body {{ padding-top:64px; }} .topbar {{ height:64px; grid-template-columns:88px 1fr 88px; padding:0 8px; gap:8px; }} .topbar button {{ font-size:11px; }} .sample-page {{ width:calc(100% - 12px); margin:6px auto; }} .record-header {{ display:block; padding:20px 16px; }} .state-mark {{ margin-top:14px; padding:10px 0 0; border-left:0; border-top:1px solid var(--line); }} .source-pane,.rubric-pane {{ padding:20px 16px 28px; }} .source-label {{ display:block; }} .source-label span {{ display:block; margin-top:3px; text-align:left; }} .manual-grid {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <nav class="topbar"><button id="prev">← 上一条</button><div class="topmeta"><strong><span id="current">1</span> / {total}</strong><span>{esc(summary_copy)} · ← → 切换</span></div><button id="next" class="primary">下一条 →</button></nav>
  {pages}
  <button id="export" class="primary export">导出人工标注</button>
  <script>
    const pages=[...document.querySelectorAll('.sample-page')], current=document.getElementById('current'), prev=document.getElementById('prev'), next=document.getElementById('next');
    const storageKey='crk2-source-semantic-qc-manual-v1'; let index=0; let annotations=JSON.parse(localStorage.getItem(storageKey)||'{{}}');
    function saveField(element){{ const id=element.dataset.record, field=element.dataset.field; annotations[id] ||= {{}}; annotations[id][field]=element.value; localStorage.setItem(storageKey,JSON.stringify(annotations)); }}
    document.querySelectorAll('[data-record][data-field]').forEach(el=>{{ const saved=annotations[el.dataset.record]?.[el.dataset.field]; if(saved!==undefined) el.value=saved; el.addEventListener('change',()=>saveField(el)); el.addEventListener('input',()=>saveField(el)); }});
    function show(nextIndex){{ if(!pages.length)return; index=Math.max(0,Math.min(pages.length-1,nextIndex)); pages.forEach((p,i)=>p.classList.toggle('active',i===index)); current.textContent=String(index+1); prev.disabled=index===0; next.disabled=index===pages.length-1; window.scrollTo({{top:0,behavior:'instant'}}); }}
    prev.addEventListener('click',()=>show(index-1)); next.addEventListener('click',()=>show(index+1)); document.addEventListener('keydown',event=>{{ if(event.key === 'ArrowRight')show(index+1); if(event.key === 'ArrowLeft')show(index-1); }});
    document.getElementById('export').addEventListener('click',()=>{{ const blob=new Blob([JSON.stringify(annotations,null,2)],{{type:'application/json'}}), url=URL.createObjectURL(blob), a=document.createElement('a'); a.href=url; a.download='crk2_source_semantic_qc_manual.json'; a.click(); URL.revokeObjectURL(url); }}); show(0);
  </script>
</body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a one-sample source semantic QC audit page.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = list(iter_jsonl(args.input))
    summary = load_json(args.summary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_html(records, summary), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "samples": len(records)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
