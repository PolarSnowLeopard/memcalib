#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

from evaluation.common import iter_jsonl, stable_hash, write_jsonl
from evaluation.scripts.prepare_judge_requests import load_answers


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "evaluation" / "configs" / "memcalib-v0.1-500.json"
DEFAULT_HIDDEN = ROOT / "evaluation" / "releases" / "memcalib-v0.1-500" / "hidden-evaluation.jsonl"
DEFAULT_ANSWERS = ROOT / "evaluation" / "runs" / "memcalib-v0.1-500" / "answers"
DEFAULT_PRIMARY = ROOT / "evaluation" / "runs" / "memcalib-v0.1-500" / "judgments" / "primary.valid.jsonl"
DEFAULT_SECONDARY = ROOT / "evaluation" / "runs" / "memcalib-v0.1-500" / "judgments" / "secondary.valid.jsonl"
DEFAULT_RANDOM_IDS = ROOT / "evaluation" / "runs" / "memcalib-v0.1-500" / "requests" / "judges" / "human-random-answer-ids.txt"
DEFAULT_JSONL = ROOT / "evaluation" / "releases" / "memcalib-v0.1-500" / "human-review-100.jsonl"
DEFAULT_HTML = ROOT / "evaluation" / "releases" / "memcalib-v0.1-500" / "human-review-100.html"


def _judgment_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["answer_request_id"]): row for row in rows}


def _diagnostic_score(answer_id: str, primary: dict[str, Any], secondary: dict[str, Any] | None) -> float:
    primary_atoms = {str(atom["atom_id"]): atom for atom in primary.get("atom_judgments") or []}
    disagreement = 0
    unscorable = 0
    confidences = []
    for atom in primary_atoms.values():
        unscorable += int(atom.get("verdict") == "unscorable")
        if isinstance(atom.get("confidence"), (int, float)):
            confidences.append(float(atom["confidence"]))
    if secondary:
        for atom in secondary.get("atom_judgments") or []:
            atom_id = str(atom["atom_id"])
            if atom_id in primary_atoms and atom.get("verdict") != primary_atoms[atom_id].get("verdict"):
                disagreement += 1
            unscorable += int(atom.get("verdict") == "unscorable")
            if isinstance(atom.get("confidence"), (int, float)):
                confidences.append(float(atom["confidence"]))
    min_confidence = min(confidences) if confidences else 0.0
    return disagreement * 10 + unscorable * 5 + (1 - min_confidence)


def select_human_review_ids(
    answers: list[dict[str, Any]],
    primary: list[dict[str, Any]],
    secondary: list[dict[str, Any]],
    *,
    random_ids: set[str],
    diagnostic_count: int,
    seed: int,
) -> dict[str, list[str]]:
    answer_ids = {str(row["request_id"]) for row in answers}
    primary_by_id = _judgment_map(primary)
    secondary_by_id = _judgment_map(secondary)
    missing_random = random_ids.difference(answer_ids)
    if missing_random:
        raise ValueError(f"human random IDs missing from answers: {len(missing_random)}")
    candidates = []
    for answer_id in answer_ids.difference(random_ids):
        if answer_id not in primary_by_id:
            continue
        score = _diagnostic_score(answer_id, primary_by_id[answer_id], secondary_by_id.get(answer_id))
        candidates.append((score, stable_hash(seed, answer_id), answer_id))
    candidates.sort(key=lambda row: (-row[0], row[1]))
    if len(candidates) < diagnostic_count:
        raise ValueError(f"insufficient diagnostic human-review candidates: {len(candidates)}")
    return {
        "random": sorted(random_ids),
        "diagnostic": [row[2] for row in candidates[:diagnostic_count]],
    }


def build_review_records(
    selected: dict[str, list[str]],
    samples: list[dict[str, Any]],
    answers: list[dict[str, Any]],
    primary: list[dict[str, Any]],
    secondary: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    samples_by_id = {str(row["id"]): row for row in samples}
    answers_by_id = {str(row["request_id"]): row for row in answers}
    primary_by_id = _judgment_map(primary)
    secondary_by_id = _judgment_map(secondary)
    records = []
    for stratum in ("random", "diagnostic"):
        for answer_id in selected[stratum]:
            answer = answers_by_id[answer_id]
            params = answer["user_defined_params"]
            sample = samples_by_id[str(params["sample_id"])]
            records.append(
                {
                    "review_stratum": stratum,
                    "answer_request_id": answer_id,
                    "sample_id": sample["id"],
                    "panel": params["panel"],
                    "model_key": params["model_key"],
                    "condition": params["condition"],
                    "question": sample["question"],
                    "memory_blocks": [
                        {"parent_memory_id": block["parent_memory_id"], "memory_text": block["memory_text"]}
                        for block in sample["memory_blocks"]
                    ],
                    "model_response": answer["response"],
                    "atomic_memories": [
                        {
                            "atom_id": atom["atom_id"],
                            "parent_memory_id": atom["parent_memory_id"],
                            "text": atom["text"],
                            "u_star": atom["u_star"],
                            "usage_rubric": atom["usage_rubric"],
                        }
                        for atom in sample["memories"]
                    ],
                    "primary_judgment": primary_by_id.get(answer_id),
                    "secondary_judgment": secondary_by_id.get(answer_id),
                }
            )
    return records


def render_review_html(records: list[dict[str, Any]]) -> str:
    payload = json.dumps(records, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MemCalib 人工复核</title><style>
:root{{--ink:#182230;--muted:#667085;--line:#d8dee8;--paper:#fff;--bg:#eef2f5;--nav:#17253d;--teal:#0b766d;--gold:#a15c00;--violet:#6941c6}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif;letter-spacing:0}}
button,select,textarea{{font:inherit}}.topbar{{position:sticky;top:0;z-index:10;height:68px;background:var(--nav);color:#fff;display:grid;grid-template-columns:160px 1fr 160px;align-items:center;padding:0 max(18px,calc((100vw - 1320px)/2));box-shadow:0 2px 12px #16233b33}}
.topbar button{{height:38px;border:1px solid #ffffff40;background:#ffffff12;color:#fff;border-radius:5px;cursor:pointer}}.counter{{text-align:center}}.counter strong{{display:block;font-size:18px}}.counter span{{color:#b8c4d6;font-size:12px}}
main{{max-width:1320px;margin:0 auto;padding:22px 18px 70px}}.meta{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}}.tag{{padding:4px 8px;border:1px solid var(--line);background:#fff;border-radius:4px;color:var(--muted)}}
.workspace{{display:grid;grid-template-columns:minmax(0,1fr) 390px;gap:16px;align-items:start}}.content,.audit{{background:var(--paper);border:1px solid var(--line);border-radius:6px}}.content{{padding:22px}}.audit{{position:sticky;top:84px;padding:18px}}
h2{{font-size:12px;text-transform:uppercase;color:var(--muted);margin:0 0 8px}}h3{{font-size:15px;margin:0 0 8px}}.section{{padding:0 0 20px;margin:0 0 20px;border-bottom:1px solid var(--line)}}.section:last-child{{border:0;margin:0;padding:0}}
.memory{{border-left:3px solid var(--teal);padding:10px 12px;margin:8px 0;background:#f4fbfa}}.response{{white-space:pre-wrap;font-size:15px}}.atom{{padding:14px 0;border-bottom:1px solid var(--line)}}.atom:last-child{{border:0}}.atom-head{{display:flex;justify-content:space-between;gap:8px}}.label{{font-weight:700;color:var(--violet)}}
.rubric{{margin-top:8px;color:#344054;font-size:13px}}.rubric div{{margin-top:4px}}.judge{{padding:10px;background:#f8fafc;border:1px solid var(--line);margin-top:8px}}.judge b{{color:var(--gold)}}
.field{{margin-bottom:14px}}.field label{{display:block;font-weight:650;margin-bottom:5px}}select,textarea{{width:100%;border:1px solid #b8c2d1;border-radius:5px;background:#fff;padding:9px}}textarea{{height:92px;resize:vertical}}.help{{font-size:12px;color:var(--muted);margin-top:4px}}.export{{width:100%;height:40px;border:0;border-radius:5px;background:var(--teal);color:#fff;font-weight:700;cursor:pointer}}
@media(max-width:900px){{.workspace{{grid-template-columns:1fr}}.audit{{position:static}}.topbar{{grid-template-columns:96px 1fr 96px}}}}
</style></head><body><nav class="topbar"><button id="prev">上一条</button><div class="counter"><strong id="count"></strong><span id="identity"></span></div><button id="next">下一条</button></nav><main><div class="meta" id="meta"></div><div class="workspace"><article class="content" id="content"></article><aside class="audit" id="audit"></aside></div></main>
<script>const records={payload};let index=0;const key='memcalib-human-review-v1';const saved=JSON.parse(localStorage.getItem(key)||'{{}}');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
function atomJudge(row,id){{return row?.atom_judgments?.find(x=>x.atom_id===id)}}
function render(){{const r=records[index];document.getElementById('count').textContent=`${{index+1}} / ${{records.length}}`;document.getElementById('identity').textContent=r.answer_request_id;document.getElementById('meta').innerHTML=[r.review_stratum,r.panel,r.model_key,r.condition].map(x=>`<span class="tag">${{esc(x)}}</span>`).join('');
let atoms=r.atomic_memories.map(a=>{{const p=atomJudge(r.primary_judgment,a.atom_id),s=atomJudge(r.secondary_judgment,a.atom_id);const rubric=Object.entries(a.usage_rubric||{{}}).map(([k,v])=>`<div><b>${{esc(k)}}</b>: ${{esc(Array.isArray(v)?v.join(' · '):v)}}</div>`).join('');return `<section class="atom"><div class="atom-head"><h3>${{esc(a.atom_id)}} · ${{esc(a.text)}}</h3><span class="label">${{esc(a.u_star)}}</span></div><div class="rubric">${{rubric}}</div><div class="judge"><b>主 Judge</b> ${{esc(p?.verdict||'缺失')}} · ${{esc(p?.reason||'')}}</div><div class="judge"><b>复核 Judge</b> ${{esc(s?.verdict||'未抽中复核')}} · ${{esc(s?.reason||'')}}</div></section>`}}).join('');
document.getElementById('content').innerHTML=`<section class="section"><h2>Current query</h2><div class="response">${{esc(r.question)}}</div></section><section class="section"><h2>Model-facing memory</h2>${{r.memory_blocks.map((m,i)=>`<div class="memory"><b>${{i+1}}</b> ${{esc(m.memory_text)}}</div>`).join('')}}</section><section class="section"><h2>Model response</h2><div class="response">${{esc(r.model_response)}}</div></section><section><h2>Hidden atomic annotation and judges</h2>${{atoms}}</section>`;
const current=saved[r.answer_request_id]||{{}};document.getElementById('audit').innerHTML=`<h2>Manual audit</h2><div class="field"><label>自动评分是否可接受</label><select id="decision"><option value="">未标注</option><option value="accept">接受</option><option value="revise">需要修订</option><option value="reject">拒绝</option><option value="unscorable">无法判断</option></select><div class="help">核对每个原子记忆的 verdict 是否符合 rubric 和回答中的可观测证据。</div></div><div class="field"><label>主要问题</label><select id="issue"><option value="">无 / 未标注</option><option value="atom_verdict">原子 verdict 错误</option><option value="rubric">rubric 不可操作</option><option value="answer_quality">基础回答质量干扰</option><option value="judge_grounding">Judge 证据不充分</option><option value="sample_invalid">样本本身有问题</option></select></div><div class="field"><label>备注</label><textarea id="note"></textarea></div><button class="export" id="export">导出当前全部标注</button>`;for(const id of ['decision','issue','note']){{const el=document.getElementById(id);el.value=current[id]||'';el.oninput=()=>{{saved[r.answer_request_id]={{decision:document.getElementById('decision').value,issue:document.getElementById('issue').value,note:document.getElementById('note').value}};localStorage.setItem(key,JSON.stringify(saved))}}}}document.getElementById('export').onclick=exportData;document.getElementById('prev').disabled=index===0;document.getElementById('next').disabled=index===records.length-1}}
function go(delta){{index=Math.max(0,Math.min(records.length-1,index+delta));render();scrollTo(0,0)}}function exportData(){{const blob=new Blob([JSON.stringify(saved,null,2)],{{type:'application/json'}});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='memcalib-human-annotations.json';a.click();URL.revokeObjectURL(a.href)}}document.getElementById('prev').onclick=()=>go(-1);document.getElementById('next').onclick=()=>go(1);addEventListener('keydown',e=>{{if(['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName))return;if(e.key==='ArrowLeft')go(-1);if(e.key==='ArrowRight')go(1)}});render();</script></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the MemCalib 100-response human review pack.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--hidden", type=Path, default=DEFAULT_HIDDEN)
    parser.add_argument("--answers", type=Path, default=DEFAULT_ANSWERS)
    parser.add_argument("--primary", type=Path, default=DEFAULT_PRIMARY)
    parser.add_argument("--secondary", type=Path, default=DEFAULT_SECONDARY)
    parser.add_argument("--random-ids", type=Path, default=DEFAULT_RANDOM_IDS)
    parser.add_argument("--jsonl", type=Path, default=DEFAULT_JSONL)
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    samples = list(iter_jsonl(args.hidden))
    answers = load_answers(args.answers, config)
    primary = list(iter_jsonl(args.primary))
    secondary = list(iter_jsonl(args.secondary))
    random_ids = {line.strip() for line in args.random_ids.read_text(encoding="utf-8").splitlines() if line.strip()}
    selected = select_human_review_ids(
        answers, primary, secondary, random_ids=random_ids, diagnostic_count=40, seed=int(config["seed"])
    )
    records = build_review_records(selected, samples, answers, primary, secondary)
    write_jsonl(args.jsonl, records)
    args.html.parent.mkdir(parents=True, exist_ok=True)
    args.html.write_text(render_review_html(records), encoding="utf-8")
    print(json.dumps({"records": len(records), "random": len(selected["random"]), "diagnostic": len(selected["diagnostic"]), "html": str(args.html)}, indent=2))


if __name__ == "__main__":
    main()
