#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

from utils import iter_jsonl, load_json


SCRIPT_DIR = Path(__file__).resolve().parent

COMPONENT_LABELS = {
    "question_informativeness": "Question informativeness / 问题信息量",
    "answer_substance": "Answer substance / 回答实质性",
    "memory_suitability": "Memory suitability / 记忆可构造性",
    "cleanliness_coherence": "Cleanliness & coherence / 文本清洁与连贯性",
}

SIGNAL_LABELS = {
    "personal_entity": "Personal entity / 人物主体",
    "temporal_history": "Temporal history / 时间与既往史",
    "condition_history": "Condition history / 疾病史",
    "treatment": "Treatment / 治疗与用药",
    "measurement": "Measurement / 检查与数值",
    "event_exposure": "Event or exposure / 事件与暴露",
    "preference_constraint": "Preference or constraint / 偏好与约束",
    "symptom_course": "Symptom course / 症状演变",
}


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _component_rows(components: dict[str, Any]) -> str:
    maximums = {
        "question_informativeness": 25,
        "answer_substance": 25,
        "memory_suitability": 40,
        "cleanliness_coherence": 10,
    }
    rows = []
    for key in COMPONENT_LABELS:
        value = int(components.get(key, 0))
        maximum = maximums[key]
        width = round(100 * value / maximum) if maximum else 0
        rows.append(
            f"""
            <div class="component-row">
              <div class="component-label"><span>{esc(COMPONENT_LABELS[key])}</span><strong>{value}/{maximum}</strong></div>
              <div class="meter"><span style="width:{width}%"></span></div>
            </div>"""
        )
    return "".join(rows)


def _signal_pills(signals: list[str]) -> str:
    if not signals:
        return '<span class="empty">No signal matched</span>'
    return "".join(f'<span class="signal">{esc(SIGNAL_LABELS.get(signal, signal))}</span>' for signal in signals)


def _feature_table(features: dict[str, Any]) -> str:
    labels = {
        "question_chars": "Question characters",
        "answer_chars": "Answer characters",
        "question_tokens": "Question tokens",
        "answer_tokens": "Answer tokens",
        "answer_content_tokens": "Non-boilerplate answer tokens",
        "question_sentences": "Question sentences",
        "answer_sentences": "Answer sentences",
        "relation_count": "Explicit relations",
        "question_intent": "Explicit question or request intent",
        "question_english_letter_ratio": "Question English-letter ratio",
        "answer_english_letter_ratio": "Answer English-letter ratio",
        "answer_boilerplate_ratio": "Answer boilerplate ratio",
        "text_noise": "Text-noise flag",
    }
    return "".join(
        f"<tr><th>{esc(labels.get(key, key))}</th><td>{esc(features.get(key, ''))}</td></tr>" for key in labels
    )


def _sample_page(row: dict[str, Any], index: int) -> str:
    selection = row.get("raw_selection") or {}
    components = selection.get("quality_components") or {}
    features = selection.get("features") or {}
    stratum = selection.get("selection_stratum") or {}
    active = " active" if index == 0 else ""
    status = str(selection.get("selection_status") or "unknown")
    status_class = "pass" if status == "selected" else "warn"
    reasons = selection.get("hard_rejection_reasons") or []
    reasons_html = (
        "".join(f"<li>{esc(reason)}</li>" for reason in reasons)
        if reasons
        else "<li>None. All deterministic hard filters passed.</li>"
    )
    return f"""
    <article class="sample-page{active}" data-index="{index}">
      <header class="sample-header">
        <div>
          <div class="eyebrow">RAW SEED · {esc(row.get('id'))}</div>
          <h1>{esc(row.get('source_dataset'))}</h1>
          <p>{esc(row.get('source_split'))} · source_index={esc(row.get('source_index'))} · topic={esc(row.get('topic'))}</p>
        </div>
        <div class="score-block">
          <span>QUALITY SCORE</span>
          <strong>{esc(selection.get('quality_score'))}</strong>
          <small>/ 100</small>
        </div>
      </header>

      <main class="workspace">
        <section class="source-column">
          <div class="section-heading">
            <span>01</span>
            <div><h2>Model-facing source question</h2><p>送入 CRK-2 构造模型的原始问题；这里尚未生成记忆或 A/B/C 标签。</p></div>
          </div>
          <div class="source-text question">{esc(row.get('raw_question'))}</div>

          <div class="section-heading answer-heading">
            <span>02</span>
            <div><h2>Reference source answer</h2><p>仅用于判断原始问答是否有实质内容，并为后续构造提供医学语境。</p></div>
          </div>
          <div class="source-text answer">{esc(row.get('doctor_answer'))}</div>
        </section>

        <aside class="quality-column">
          <section class="decision-band">
            <div><span>SELECTION STATUS</span><strong class="{status_class}">{esc(status)}</strong></div>
            <div><span>SEED COMPLEXITY</span><strong>{esc(selection.get('seed_complexity'))}</strong></div>
            <div><span>SELECTION RANK</span><strong>{esc(selection.get('selection_rank', '—'))}</strong></div>
          </section>

          <section class="quality-section">
            <div class="section-heading compact">
              <span>03</span>
              <div><h2>Quality components</h2><p>四项可解释分数之和；它是原始种子筛选分，不是 benchmark 难度或模型得分。</p></div>
            </div>
            {_component_rows(components)}
          </section>

          <section class="quality-section">
            <div class="section-heading compact">
              <span>04</span>
              <div><h2>Memory-signal families</h2><p>问题中可转写为长期记忆的线索类型。至少命中一类才进入质量评分候选。</p></div>
            </div>
            <div class="signals">{_signal_pills(selection.get('memory_signal_families') or [])}</div>
          </section>

          <details class="quality-section" open>
            <summary>Selection stratum / 分层位置</summary>
            <dl class="stratum">
              <div><dt>source</dt><dd>{esc(stratum.get('source_dataset', row.get('source_dataset')))}</dd></div>
              <div><dt>topic</dt><dd>{esc(stratum.get('topic', row.get('topic')))}</dd></div>
              <div><dt>complexity</dt><dd>{esc(stratum.get('seed_complexity', selection.get('seed_complexity')))}</dd></div>
              <div><dt>fill phase</dt><dd>{esc(stratum.get('fill_phase', '—'))}</dd></div>
            </dl>
          </details>

          <details class="quality-section">
            <summary>Hard-filter decision / 硬过滤结论</summary>
            <p class="detail-note">hard_filter_pass={esc(selection.get('hard_filter_pass'))}; score_pass={esc(selection.get('score_pass'))}; dedup_status={esc(selection.get('dedup_status'))}</p>
            <ul class="reasons">{reasons_html}</ul>
          </details>

          <details class="quality-section">
            <summary>Observable features / 可观测特征</summary>
            <table>{_feature_table(features)}</table>
          </details>
        </aside>
      </main>
    </article>"""


def build_html(records: list[dict[str, Any]], manifest: dict[str, Any]) -> str:
    pages = "".join(_sample_page(row, index) for index, row in enumerate(records))
    total = len(records)
    schema = manifest.get("schema_version", "")
    parameters = manifest.get("parameters") or {}
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CRK-2 Raw Seed Selection Audit</title>
  <style>
    :root {{
      --ink:#172033; --muted:#647087; --line:#d7dee9; --paper:#ffffff; --soft:#f4f7fa;
      --navy:#1c2b46; --teal:#0e756b; --amber:#a65f00; --blue:#2463a9;
    }}
    * {{ box-sizing:border-box; }}
    html, body {{ margin:0; min-height:100%; background:#eaf0f3; color:var(--ink); font-family:Inter, "PingFang SC", "Microsoft YaHei", Arial, sans-serif; letter-spacing:0; }}
    body {{ padding:70px 0 0; }}
    .topbar {{ position:fixed; z-index:20; inset:0 0 auto; height:70px; display:grid; grid-template-columns:180px 1fr 180px; align-items:center; padding:0 28px; background:rgba(250,252,253,.97); border-bottom:1px solid var(--line); box-shadow:0 4px 18px rgba(28,43,70,.08); }}
    .topbar button {{ height:38px; border:1px solid #bdc7d5; background:#fff; color:var(--navy); font-size:14px; font-weight:700; cursor:pointer; }}
    .topbar button:hover:not(:disabled) {{ border-color:var(--navy); }}
    .topbar button:disabled {{ opacity:.35; cursor:default; }}
    .topbar .next {{ background:var(--navy); border-color:var(--navy); color:white; }}
    .position {{ text-align:center; }}
    .position strong {{ display:block; font-size:18px; }}
    .position span {{ font-size:11px; color:var(--muted); text-transform:uppercase; }}
    .sample-page {{ display:none; width:min(1680px, calc(100% - 32px)); min-height:calc(100vh - 92px); margin:16px auto; background:var(--paper); border:1px solid var(--line); box-shadow:0 14px 40px rgba(28,43,70,.08); }}
    .sample-page.active {{ display:block; }}
    .sample-header {{ display:flex; align-items:flex-end; justify-content:space-between; gap:30px; padding:28px 34px; border-bottom:1px solid var(--line); }}
    .eyebrow {{ margin-bottom:7px; font-size:11px; font-weight:800; color:var(--teal); }}
    h1 {{ margin:0 0 6px; font-size:24px; line-height:1.2; }}
    .sample-header p {{ margin:0; color:var(--muted); font-size:13px; }}
    .score-block {{ min-width:155px; display:grid; grid-template-columns:1fr auto; align-items:end; column-gap:6px; padding-left:24px; border-left:4px solid var(--teal); }}
    .score-block span {{ grid-column:1 / -1; font-size:11px; font-weight:800; color:var(--muted); }}
    .score-block strong {{ font-size:42px; line-height:1; color:var(--teal); }}
    .score-block small {{ padding-bottom:5px; color:var(--muted); }}
    .workspace {{ display:grid; grid-template-columns:minmax(0, 1.15fr) minmax(460px, .85fr); }}
    .source-column, .quality-column {{ padding:30px 34px 38px; }}
    .quality-column {{ background:#f7f9fb; border-left:1px solid var(--line); }}
    .section-heading {{ display:flex; gap:14px; align-items:flex-start; margin-bottom:12px; }}
    .section-heading > span {{ display:grid; place-items:center; width:34px; height:34px; flex:0 0 34px; border:1px solid var(--line); color:var(--teal); font-size:12px; font-weight:800; }}
    .section-heading h2 {{ margin:0 0 3px; font-size:16px; }}
    .section-heading p {{ margin:0; color:var(--muted); font-size:12px; line-height:1.55; }}
    .section-heading.compact {{ margin-bottom:16px; }}
    .source-text {{ padding:22px 24px; border-left:4px solid var(--blue); background:var(--soft); font-family:Georgia, "Times New Roman", serif; font-size:16px; line-height:1.75; white-space:pre-wrap; }}
    .source-text.answer {{ border-left-color:#8995a8; background:#fff; border-top:1px solid var(--line); border-right:1px solid var(--line); border-bottom:1px solid var(--line); }}
    .answer-heading {{ margin-top:30px; }}
    .decision-band {{ display:grid; grid-template-columns:repeat(3,1fr); border:1px solid var(--line); background:#fff; }}
    .decision-band > div {{ min-width:0; padding:14px 16px; border-right:1px solid var(--line); }}
    .decision-band > div:last-child {{ border-right:0; }}
    .decision-band span {{ display:block; margin-bottom:5px; color:var(--muted); font-size:10px; font-weight:800; }}
    .decision-band strong {{ font-size:14px; overflow-wrap:anywhere; }}
    .decision-band .pass {{ color:var(--teal); }}
    .decision-band .warn {{ color:var(--amber); }}
    .quality-section {{ margin-top:18px; padding:18px; background:#fff; border:1px solid var(--line); }}
    .component-row + .component-row {{ margin-top:13px; }}
    .component-label {{ display:flex; justify-content:space-between; gap:12px; margin-bottom:6px; font-size:12px; }}
    .component-label strong {{ color:var(--navy); }}
    .meter {{ height:7px; background:#e7ebf0; overflow:hidden; }}
    .meter span {{ display:block; height:100%; background:var(--teal); }}
    .signals {{ display:flex; flex-wrap:wrap; gap:7px; }}
    .signal {{ display:inline-flex; padding:6px 9px; border:1px solid #b8d7d3; background:#edf7f5; color:#075e56; font-size:11px; font-weight:700; }}
    .empty {{ color:var(--muted); font-size:12px; }}
    details summary {{ cursor:pointer; font-size:13px; font-weight:800; color:var(--navy); }}
    .stratum {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin:14px 0 0; }}
    .stratum div {{ min-width:0; padding-top:8px; border-top:1px solid var(--line); }}
    dt {{ color:var(--muted); font-size:10px; font-weight:800; text-transform:uppercase; }}
    dd {{ margin:4px 0 0; font-size:12px; font-weight:700; overflow-wrap:anywhere; }}
    .detail-note, .reasons {{ color:var(--muted); font-size:12px; line-height:1.6; }}
    .reasons {{ padding-left:18px; margin-bottom:0; }}
    table {{ width:100%; margin-top:12px; border-collapse:collapse; font-size:11px; }}
    th, td {{ padding:7px 6px; border-top:1px solid var(--line); text-align:left; }}
    th {{ color:var(--muted); font-weight:600; }}
    td {{ text-align:right; font-weight:700; }}
    .meta {{ position:fixed; z-index:19; right:20px; bottom:14px; padding:7px 10px; background:rgba(28,43,70,.92); color:#fff; font-size:10px; }}
    @media (max-width:980px) {{
      body {{ padding-top:64px; }} .topbar {{ height:64px; grid-template-columns:110px 1fr 110px; padding:0 12px; }}
      .sample-page {{ width:calc(100% - 16px); margin:8px auto; }} .sample-header {{ align-items:flex-start; padding:22px 20px; }}
      .workspace {{ grid-template-columns:1fr; }} .quality-column {{ border-left:0; border-top:1px solid var(--line); }}
      .source-column, .quality-column {{ padding:22px 20px 28px; }}
    }}
    @media (max-width:620px) {{
      .topbar {{ grid-template-columns:88px 1fr 88px; }} .topbar button {{ font-size:12px; }}
      .sample-header {{ display:block; }} .score-block {{ margin-top:18px; padding:12px 0 0; border-left:0; border-top:4px solid var(--teal); }}
      .decision-band {{ grid-template-columns:1fr; }} .decision-band > div {{ border-right:0; border-bottom:1px solid var(--line); }}
      .stratum {{ grid-template-columns:1fr; }} .source-text {{ padding:18px; font-size:15px; }}
    }}
  </style>
</head>
<body>
  <nav class="topbar">
    <button id="prev" type="button">← 上一条</button>
    <div class="position"><strong><span id="current">1</span> / {total}</strong><span>← → 切换样本</span></div>
    <button id="next" class="next" type="button">下一条 →</button>
  </nav>
  {pages}
  <div class="meta">{esc(schema)} · seed={esc(parameters.get('seed', ''))} · threshold={esc(parameters.get('min_quality_score', ''))}</div>
  <script>
    const pages = [...document.querySelectorAll('.sample-page')];
    const current = document.getElementById('current');
    const prev = document.getElementById('prev');
    const next = document.getElementById('next');
    let index = 0;
    function show(nextIndex) {{
      if (!pages.length) return;
      index = Math.max(0, Math.min(pages.length - 1, nextIndex));
      pages.forEach((page, pageIndex) => page.classList.toggle('active', pageIndex === index));
      current.textContent = String(index + 1);
      prev.disabled = index === 0;
      next.disabled = index === pages.length - 1;
      window.scrollTo({{ top: 0, behavior: 'instant' }});
    }}
    prev.addEventListener('click', () => show(index - 1));
    next.addEventListener('click', () => show(index + 1));
    document.addEventListener('keydown', (event) => {{
      if (event.key === 'ArrowRight') show(index + 1);
      if (event.key === 'ArrowLeft') show(index - 1);
    }});
    show(0);
  </script>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a one-sample-per-page CRK-2 raw seed audit HTML.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    records = list(iter_jsonl(args.input))
    manifest = load_json(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_html(records, manifest), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "samples": len(records)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
