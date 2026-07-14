#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from utils import iter_jsonl, load_json, write_json


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_BENCHMARK = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_100.resolved.jsonl"
DEFAULT_STRICT = SCRIPT_DIR / "data" / "crk2_v2_independent_qc_100.resolved.strict_pass.jsonl"
DEFAULT_REJECT = SCRIPT_DIR / "data" / "crk2_v2_independent_qc_100.resolved.reject.jsonl"
DEFAULT_OUTPUT = REPO_ROOT / "evaluation" / "releases" / "memcalib-v0.2-construction-pilot-100" / "review.html"
DEFAULT_SUMMARY = REPO_ROOT / "evaluation" / "releases" / "memcalib-v0.2-construction-pilot-100" / "result-summary.json"
DEFAULT_PRIMARY_SUMMARY = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_100.summary.json"
DEFAULT_REPAIR_SUMMARY = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_repair1.summary.json"
DEFAULT_QC_SUMMARY = SCRIPT_DIR / "data" / "crk2_v2_independent_qc_100.resolved.summary.json"
DEFAULT_BENCHMARK_PACKAGE = DEFAULT_OUTPUT.parent / "benchmark-resolved.jsonl.gz"
DEFAULT_STRICT_PACKAGE = DEFAULT_OUTPUT.parent / "strict-pass.jsonl.gz"
DEFAULT_REJECT_PACKAGE = DEFAULT_OUTPUT.parent / "qc-reject.jsonl.gz"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


def write_deterministic_gzip(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as source_handle, destination.open("wb") as output_handle:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output_handle, compresslevel=9, mtime=0) as gzip_handle:
            shutil.copyfileobj(source_handle, gzip_handle)


def ordered_review_records(benchmark_path: Path, strict_path: Path, reject_path: Path) -> list[dict[str, Any]]:
    order = [str(record.get("id") or "") for record in iter_jsonl(benchmark_path)]
    indexed: dict[str, dict[str, Any]] = {}
    for decision, path in (("strict_pass", strict_path), ("reject", reject_path)):
        for record in iter_jsonl(path):
            record_id = str(record.get("id") or "")
            if not record_id or record_id in indexed:
                raise ValueError(f"bad or duplicate review record id: {record_id}")
            item = dict(record)
            item["review_decision"] = decision
            indexed[record_id] = item
    if set(order) != set(indexed):
        raise ValueError("review records do not exactly cover the resolved benchmark")
    position = {record_id: index for index, record_id in enumerate(order)}
    return sorted(indexed.values(), key=lambda row: (row["review_decision"] != "reject", position[row["id"]]))


def build_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    labels: Counter[str] = Counter()
    actions: Counter[str] = Counter()
    failure_dimensions: Counter[str] = Counter()
    atoms = 0
    parents = 0
    for record in records:
        memories = record.get("memories") if isinstance(record.get("memories"), list) else []
        atoms += len(memories)
        parents += len(record.get("memory_blocks") if isinstance(record.get("memory_blocks"), list) else [])
        labels.update(str(memory.get("u_star") or "") for memory in memories)
        actions.update(str(memory.get("memory_action") or "") for memory in memories)
        if record.get("review_decision") == "reject":
            for check in (record.get("independent_qc") or {}).get("atom_checks", []):
                if check.get("query_relation") != "absent":
                    failure_dimensions["query_isolation"] += 1
                if check.get("atomicity") != "pass":
                    failure_dimensions["atomicity"] += 1
                if check.get("label_action_validity") == "fail":
                    failure_dimensions["label_action"] += 1
                if check.get("counterfactual_observability") != "pass":
                    failure_dimensions["counterfactual"] += 1
                if check.get("rubric_judgeability") == "fail":
                    failure_dimensions["rubric"] += 1
    return {
        "schema_version": "crk2-v2-pilot-review-summary-v1",
        "records": len(records),
        "decisions": dict(sorted(Counter(str(row.get("review_decision") or "") for row in records).items())),
        "source_dataset": dict(sorted(Counter(str(row.get("source_dataset") or "") for row in records).items())),
        "parent_memories": parents,
        "atomic_memories": atoms,
        "label_counts": dict(sorted(labels.items())),
        "memory_action_counts": dict(sorted(actions.items())),
        "reject_failure_dimensions": dict(sorted(failure_dimensions.items())),
    }


def render_html(records: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    payload = json.dumps(records, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    summary_payload = json.dumps(summary, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MemCalib v2 · 100 条构建审查</title>
  <style>
    :root{--ink:#182033;--muted:#657189;--line:#d9e1e8;--paper:#fff;--canvas:#edf2f3;--teal:#087f73;--teal2:#dff2ee;--blue:#315f91;--blue2:#eaf1f8;--amber:#9c570d;--amber2:#fff3df;--red:#a72c36;--red2:#fbeaec;--violet:#6b4e86;--violet2:#f0eaf5}*{box-sizing:border-box}body{margin:0;background:var(--canvas);color:var(--ink);font-family:"Noto Sans SC","PingFang SC","Microsoft YaHei",system-ui,sans-serif;line-height:1.6;letter-spacing:0}.topbar{position:sticky;top:0;z-index:20;background:rgba(255,255,255,.97);border-bottom:1px solid var(--line)}.topbar-inner{width:min(1500px,calc(100% - 24px));margin:auto;display:grid;grid-template-columns:180px minmax(260px,1fr) 360px;align-items:center;gap:16px;min-height:72px}.nav-button{height:38px;border:1px solid var(--line);background:#fff;color:var(--ink);font-weight:700;cursor:pointer}.nav-button:disabled{opacity:.35;cursor:not-allowed}.nav-button:hover:not(:disabled),.nav-button:focus-visible{border-color:var(--teal);color:var(--teal);outline:none}.nav-pair{display:grid;grid-template-columns:1fr 1fr;gap:8px}.identity{text-align:center;min-width:0}.position{font:800 15px/1.2 ui-monospace,SFMono-Regular,Menlo,monospace}.record-id{margin-top:5px;color:var(--muted);font:600 11px/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.toolbar{display:grid;grid-template-columns:120px 74px 1fr;gap:8px}.toolbar select,.toolbar input{height:38px;border:1px solid var(--line);background:#fff;padding:0 10px;color:var(--ink)}.toolbar input{min-width:0}.page{width:min(1500px,calc(100% - 24px));margin:18px auto 50px}.metrics{display:grid;grid-template-columns:repeat(6,1fr);background:#fff;border:1px solid var(--line);margin-bottom:16px}.metric{padding:13px 16px;border-right:1px solid var(--line)}.metric:last-child{border-right:0}.metric strong{display:block;font:800 19px/1.1 ui-monospace,SFMono-Regular,Menlo,monospace}.metric span{display:block;color:var(--muted);font-size:11px;margin-top:5px}.sample{display:grid;grid-template-columns:minmax(0,1fr) 330px;background:#fff;border:1px solid var(--line)}.main{min-width:0}.audit{border-left:1px solid var(--line);background:#f8f7fb;padding:18px;align-self:start;position:sticky;top:90px}.sample-head{padding:22px 24px;border-bottom:1px solid var(--line);display:grid;grid-template-columns:1fr auto;gap:18px}.eyebrow{color:var(--muted);font:700 11px/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase}.sample-head h1{font-size:22px;line-height:1.35;margin:7px 0 0}.badges{display:flex;gap:7px;align-items:flex-start;flex-wrap:wrap;justify-content:flex-end}.badge{display:inline-flex;align-items:center;min-height:28px;padding:0 9px;border:1px solid currentColor;font:750 11px/1 ui-monospace,SFMono-Regular,Menlo,monospace}.strict{color:var(--teal);background:var(--teal2)}.reject{color:var(--red);background:var(--red2)}.source{color:var(--blue);background:var(--blue2)}.band{padding:22px 24px;border-bottom:1px solid var(--line)}.band:last-child{border-bottom:0}.section-title{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin-bottom:12px}.section-title h2{font-size:16px;margin:0}.section-title span{color:var(--muted);font-size:11px}.source-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.text-block{white-space:pre-wrap;overflow-wrap:anywhere}.text-block.muted{color:var(--muted)}details{border-top:1px solid var(--line);padding-top:12px;margin-top:12px}summary{cursor:pointer;font-weight:700;color:var(--blue)}.parent{border-top:3px solid var(--teal);padding-top:16px;margin-top:24px}.parent:first-of-type{margin-top:0}.parent-head{display:grid;grid-template-columns:1fr auto;gap:14px}.parent-title{font-size:18px;font-weight:750}.parent-evidence{margin-top:10px;padding:12px 14px;border-left:3px solid #aeb9c8;background:#f6f8fa;color:#4e5b70}.atoms{display:grid;gap:12px;margin-top:14px}.atom{border:1px solid var(--line);padding:16px}.atom-head{display:flex;align-items:center;gap:8px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding-bottom:11px;margin-bottom:12px}.atom-id{margin-right:auto;font:700 12px/1 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted)}.label-a{color:#596579;background:#f2f4f6}.label-b{color:var(--blue);background:var(--blue2)}.label-c{color:var(--teal);background:var(--teal2)}.action-ignore{color:#596579;background:#f2f4f6}.action-apply{color:var(--violet);background:var(--violet2)}.action-correct{color:var(--amber);background:var(--amber2)}.predicate{font-weight:750;font-size:16px;margin-bottom:10px}.kv{display:grid;grid-template-columns:145px 1fr;gap:6px 12px;font-size:13px}.kv dt{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted)}.kv dd{margin:0;overflow-wrap:anywhere}.contract{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line);border:1px solid var(--line);margin-top:14px}.contract>div{background:#f8fafb;padding:12px}.contract strong{display:block;font-size:11px;color:var(--muted);margin-bottom:5px}.delta{grid-column:1/-1}.rubric{margin-top:14px;border-left:3px solid var(--blue);padding-left:14px}.rubric h3{font-size:13px;margin:0 0 8px}.qc{border-top:3px solid var(--amber);padding-top:16px}.qc-atom{padding:12px 0;border-bottom:1px solid var(--line)}.qc-atom:last-child{border-bottom:0}.qc-status{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}.mini{font:700 10px/1 ui-monospace,monospace;border:1px solid var(--line);padding:5px 7px;background:#fff}.mini.fail{color:var(--red);border-color:#e0aeb3;background:var(--red2)}.audit h2{font-size:15px;margin:0 0 14px}.field{margin-bottom:14px}.field label{display:block;font-size:12px;font-weight:750;margin-bottom:5px}.field select,.field textarea{width:100%;border:1px solid #cbd5df;background:#fff;color:var(--ink);padding:8px}.field select{height:38px}.field textarea{min-height:110px;resize:vertical}.help{color:var(--muted);font-size:11px;line-height:1.45;margin-top:5px}.audit-actions{display:grid;grid-template-columns:1fr 1fr;gap:8px}.command{height:38px;border:1px solid var(--ink);background:var(--ink);color:#fff;font-weight:700;cursor:pointer}.command.secondary{background:#fff;color:var(--ink)}.empty{padding:60px;text-align:center;color:var(--muted)}@media(max-width:1050px){.topbar-inner{grid-template-columns:140px 1fr 280px}.sample{grid-template-columns:1fr}.audit{position:static;border-left:0;border-top:1px solid var(--line)}.metrics{grid-template-columns:repeat(3,1fr)}.metric:nth-child(3){border-right:0}.metric:nth-child(-n+3){border-bottom:1px solid var(--line)}}@media(max-width:720px){.topbar-inner{grid-template-columns:1fr;gap:7px;padding:8px 0}.identity{grid-row:1}.nav-pair{grid-row:2}.toolbar{grid-row:3}.page{margin-top:10px}.metrics{grid-template-columns:repeat(2,1fr)}.metric:nth-child(2n){border-right:0}.metric:nth-child(3){border-right:1px solid var(--line)}.source-grid,.contract{grid-template-columns:1fr}.delta{grid-column:auto}.sample-head{grid-template-columns:1fr}.badges{justify-content:flex-start}.band,.sample-head{padding:18px}.kv{grid-template-columns:1fr}.kv dt{margin-top:5px}}
  </style>
</head>
<body>
  <header class="topbar"><div class="topbar-inner">
    <div class="nav-pair"><button class="nav-button" id="prev" title="上一条">← 上一条</button><button class="nav-button" id="next" title="下一条">下一条 →</button></div>
    <div class="identity"><div class="position" id="position"></div><div class="record-id" id="recordId"></div></div>
    <div class="toolbar"><select id="filter" title="筛选"><option value="all">全部样本</option><option value="reject">QC reject</option><option value="strict_pass">Strict pass</option></select><input id="jump" type="number" min="1" title="跳转序号"><button class="nav-button" id="go">跳转</button></div>
  </div></header>
  <main class="page"><div class="metrics" id="metrics"></div><div id="root"></div></main>
  <script>
  const records=__RECORDS__;const summary=__SUMMARY__;const auditKey="memcalib-v2-pilot-audit";let audits=JSON.parse(localStorage.getItem(auditKey)||"{}");let filtered=[...records];let cursor=0;
  const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const arr=v=>Array.isArray(v)?v:[];const obj=v=>(v&&typeof v==="object"&&!Array.isArray(v))?v:{};
  function badge(text,cls=""){return `<span class="badge ${cls}">${esc(text)}</span>`}
  function renderMetrics(){const d=summary.decisions||{};document.getElementById("metrics").innerHTML=[[summary.records,"samples"],[d.strict_pass||0,"strict pass"],[d.reject||0,"QC reject"],[summary.parent_memories,"parent memories"],[summary.atomic_memories,"atomic memories"],[Object.keys(summary.reject_failure_dimensions||{}).length,"failure dimensions"]].map(x=>`<div class="metric"><strong>${esc(x[0])}</strong><span>${esc(x[1])}</span></div>`).join("")}
  function kvRows(data,keys){return `<dl class="kv">${keys.map(k=>`<dt>${esc(k)}</dt><dd>${Array.isArray(data[k])?data[k].map(esc).join(" · "):esc(data[k])}</dd>`).join("")}</dl>`}
  function rubricView(r){r=obj(r);return `<div class="rubric"><h3>Judge rubric · 完整判分规则</h3>${kvRows(r,["expected_answer_behavior","memory_usage_weight","validity_scope","correct_use","under_use","over_use","forbidden_memory_role","failure_direction","observable_checks"])}</div>`}
  function atomView(m,qcMap){const id=m.atom_id||m.memory_id;const c=obj(m.counterfactual_contract),t=obj(m.construction_target),q=qcMap[id];return `<article class="atom"><div class="atom-head"><span class="atom-id">${esc(id)}</span>${badge(m.u_star,"label-"+String(m.u_star||"").toLowerCase())}${badge(m.memory_action,"action-"+m.memory_action)}${badge(m.query_relation||"",m.query_relation==="absent"?"strict":"reject")}</div><div class="predicate">${esc(m.text||m.atomic_predicate)}</div>${kvRows(m,["evidence","atomic_predicate","source","derivation","memory_type","subtype","hard_a_family","label_reason"])}<details><summary>Construction target · 构建目标</summary>${kvRows(t,["task_goal","memory_role","usage_boundary","failure_direction"])}</details><div class="contract"><div><strong>WITHOUT MEMORY</strong>${esc(c.without_memory_behavior)}</div><div><strong>WITH MEMORY</strong>${esc(c.with_memory_behavior)}</div><div class="delta"><strong>OBSERVABLE DELTA</strong>${esc(c.observable_delta)}<br><b>Minimal evidence:</b> ${arr(c.minimal_evidence).map(esc).join(" · ")||"none"}</div></div>${rubricView(m.usage_rubric)}${q?qcAtomView(q):""}</article>`}
  function qcAtomView(q){const fields=[["query",q.query_relation,q.query_relation!=="absent"],["atomic",q.atomicity,q.atomicity!=="pass"],["label/action",q.label_action_validity,q.label_action_validity==="fail"],["counterfactual",q.counterfactual_observability,q.counterfactual_observability!=="pass"],["rubric",q.rubric_judgeability,q.rubric_judgeability==="fail"]];return `<details><summary>Independent QC · 独立复核</summary><div class="qc-atom"><div class="qc-status">${fields.map(x=>`<span class="mini ${x[2]?"fail":""}">${esc(x[0])}: ${esc(x[1])}</span>`).join("")}</div><div>${esc(q.reason)}</div><div class="help">推荐：${esc(q.recommended_u_star)} / ${esc(q.recommended_memory_action)}</div></div></details>`}
  function parentView(p,memories,qcMap){return `<section class="parent"><div class="parent-head"><div><div class="eyebrow">Parent memory · ${esc(p.parent_memory_id)}</div><div class="parent-title">${esc(p.memory_text)}</div></div>${badge(p.source,"source")}</div><div class="parent-evidence"><b>Raw evidence</b><br>${esc(p.raw_evidence)}</div><div class="help">Atomization note: ${esc(p.atomization_notes)}</div><div class="atoms">${memories.map(m=>atomView(m,qcMap)).join("")}</div></section>`}
  function auditPanel(r){const a=audits[r.id]||{};const select=(id,label,help,opts)=>`<div class="field"><label for="${id}">${label}</label><select id="${id}" data-audit>${opts.map(o=>`<option value="${o[0]}" ${a[id]===o[0]?"selected":""}>${o[1]}</option>`).join("")}</select><div class="help">${help}</div></div>`;return `<aside class="audit"><h2>人工审查</h2>${select("overall","审查结论","accept 可直接进入试验；revise 需重写但可保留；reject 应排除。",[["","未标注"],["accept","Accept"],["revise","Revise"],["reject","Reject"]])}${select("query_isolation","问题—记忆隔离","问题不得陈述、蕴含或预设计分原子。",[["","未标注"],["pass","通过"],["fail","失败"]])}${select("atomicity","原子拆分","每个原子应是一个独立可判断命题，必要限定语应保留。",[["","未标注"],["pass","通过"],["fail","失败"]])}${select("label_action","标签与方向","A 只能 ignore；明确纠正应为 B/C + correct。",[["","未标注"],["pass","通过"],["fail","失败"],["boundary","边界不确定"]])}${select("rubric","Rubric 可判定性","判据应能从回答文本直接观察，并区分正确、欠用与过用。",[["","未标注"],["pass","通过"],["fail","失败"]])}<div class="field"><label for="notes">备注</label><textarea id="notes" data-audit placeholder="记录具体 atom、错误原因或修改建议">${esc(a.notes||"")}</textarea><div class="help">只记录选择框无法表达的具体问题。</div></div><div class="audit-actions"><button class="command secondary" id="clearAudit">清空本条</button><button class="command" id="exportAudit">导出标注</button></div></aside>`}
  function render(){if(!filtered.length){document.getElementById("root").innerHTML='<div class="empty">当前筛选没有样本</div>';return}cursor=Math.max(0,Math.min(cursor,filtered.length-1));const r=filtered[cursor],qc=obj(r.independent_qc),qcMap=Object.fromEntries(arr(qc.atom_checks).map(x=>[x.atom_id,x]));const byParent={};arr(r.memories).forEach(m=>(byParent[m.parent_memory_id]??=[]).push(m));document.getElementById("position").textContent=`${cursor+1} / ${filtered.length}`;document.getElementById("recordId").textContent=r.id;document.getElementById("jump").max=filtered.length;document.getElementById("jump").value=cursor+1;document.getElementById("prev").disabled=cursor===0;document.getElementById("next").disabled=cursor===filtered.length-1;document.getElementById("root").innerHTML=`<article class="sample"><div class="main"><header class="sample-head"><div><div class="eyebrow">Model-facing question</div><h1>${esc(r.question)}</h1></div><div class="badges">${badge(r.review_decision,r.review_decision==="reject"?"reject":"strict")}${badge(r.source_dataset,"source")}</div></header><section class="band"><div class="section-title"><h2>源数据与去背景化任务</h2><span>${esc(r.source_topic)}</span></div><div class="source-grid"><div><div class="eyebrow">Raw query</div><div class="text-block">${esc(r.raw_query)}</div></div><div><div class="eyebrow">Source answer · 仅供审计</div><div class="text-block muted">${esc(r.source_answer)}</div></div></div></section><section class="band"><div class="section-title"><h2>模型可见记忆与隐藏原子标注</h2><span>${arr(r.memory_blocks).length} parents · ${arr(r.memories).length} atoms</span></div>${arr(r.memory_blocks).map(p=>parentView(p,byParent[p.parent_memory_id]||[],qcMap)).join("")}</section><section class="band qc"><div class="section-title"><h2>独立 QC 总结</h2><span>${esc(qc.decision)}</span></div>${kvRows(qc,["declared_decision","decision_reasons","issues"])}<details><summary>全部原子对复核</summary>${arr(qc.pair_checks).map(p=>`<div class="qc-atom"><b>${esc(p.left_atom_id)} ↔ ${esc(p.right_atom_id)}</b> · ${esc(p.relation)}<br>${esc(p.reason)}</div>`).join("")}</details></section></div>${auditPanel(r)}</article>`;document.querySelectorAll("[data-audit]").forEach(el=>el.addEventListener("change",saveAudit));document.getElementById("clearAudit").onclick=()=>{delete audits[r.id];localStorage.setItem(auditKey,JSON.stringify(audits));render()};document.getElementById("exportAudit").onclick=exportAudit;location.hash=encodeURIComponent(r.id)}
  function saveAudit(){const r=filtered[cursor],data={};document.querySelectorAll("[data-audit]").forEach(el=>data[el.id]=el.value);audits[r.id]=data;localStorage.setItem(auditKey,JSON.stringify(audits))}
  function move(delta){if(!filtered.length)return;cursor=Math.max(0,Math.min(filtered.length-1,cursor+delta));render();scrollTo({top:0,behavior:"instant"})}
  function applyFilter(){const f=document.getElementById("filter").value;filtered=f==="all"?[...records]:records.filter(r=>r.review_decision===f);cursor=0;render()}
  function exportAudit(){const blob=new Blob([JSON.stringify({schema_version:"crk2-v2-human-audit-v1",exported_at:new Date().toISOString(),annotations:audits},null,2)],{type:"application/json"});const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="crk2-v2-human-audit.json";a.click();URL.revokeObjectURL(a.href)}
  document.getElementById("prev").onclick=()=>move(-1);document.getElementById("next").onclick=()=>move(1);document.getElementById("filter").onchange=applyFilter;document.getElementById("go").onclick=()=>{const n=Number(document.getElementById("jump").value);if(Number.isFinite(n)){cursor=n-1;render()}};document.addEventListener("keydown",e=>{if(["INPUT","TEXTAREA","SELECT"].includes(document.activeElement.tagName))return;if(e.key==="ArrowLeft"||e.key==="k")move(-1);if(e.key==="ArrowRight"||e.key==="j")move(1)});const initial=decodeURIComponent(location.hash.slice(1));const initialIndex=records.findIndex(r=>r.id===initial);if(initialIndex>=0)cursor=initialIndex;renderMetrics();render();
  </script>
</body>
</html>'''.replace("__RECORDS__", payload).replace("__SUMMARY__", summary_payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a one-sample-per-page CRK-2 v2 review interface.")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--strict", type=Path, default=DEFAULT_STRICT)
    parser.add_argument("--reject", type=Path, default=DEFAULT_REJECT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--primary-summary", type=Path, default=DEFAULT_PRIMARY_SUMMARY)
    parser.add_argument("--repair-summary", type=Path, default=DEFAULT_REPAIR_SUMMARY)
    parser.add_argument("--qc-summary", type=Path, default=DEFAULT_QC_SUMMARY)
    parser.add_argument("--benchmark-package", type=Path, default=DEFAULT_BENCHMARK_PACKAGE)
    parser.add_argument("--strict-package", type=Path, default=DEFAULT_STRICT_PACKAGE)
    parser.add_argument("--reject-package", type=Path, default=DEFAULT_REJECT_PACKAGE)
    args = parser.parse_args()

    records = ordered_review_records(args.benchmark, args.strict, args.reject)
    summary = build_summary(records)
    primary_summary = load_json(args.primary_summary)
    repair_summary = load_json(args.repair_summary)
    qc_summary = load_json(args.qc_summary)
    summary["execution"] = {
        "construction": {
            "model": "qwen3.7-max",
            "initial": primary_summary.get("counts", {}),
            "repair_round_1": repair_summary.get("counts", {}),
            "api_failures": 0,
        },
        "independent_qc": {
            "model": "kimi-k2.6",
            "counts": qc_summary.get("counts", {}),
            "api_failures": 0,
            "structural_retries": 1,
        },
    }
    summary["lineage"] = {
        "benchmark": {"path": portable_path(args.benchmark), "sha256": file_sha256(args.benchmark)},
        "strict": {"path": portable_path(args.strict), "sha256": file_sha256(args.strict)},
        "reject": {"path": portable_path(args.reject), "sha256": file_sha256(args.reject)},
        "construction_summary": {"path": portable_path(args.primary_summary), "sha256": file_sha256(args.primary_summary)},
        "repair_summary": {"path": portable_path(args.repair_summary), "sha256": file_sha256(args.repair_summary)},
        "qc_summary": {"path": portable_path(args.qc_summary), "sha256": file_sha256(args.qc_summary)},
    }
    write_deterministic_gzip(args.benchmark, args.benchmark_package)
    write_deterministic_gzip(args.strict, args.strict_package)
    write_deterministic_gzip(args.reject, args.reject_package)
    summary["release_packages"] = {
        "benchmark_resolved": {
            "path": portable_path(args.benchmark_package),
            "sha256": file_sha256(args.benchmark_package),
            "records": len(records),
        },
        "strict_pass": {
            "path": portable_path(args.strict_package),
            "sha256": file_sha256(args.strict_package),
            "records": summary["decisions"].get("strict_pass", 0),
        },
        "qc_reject": {
            "path": portable_path(args.reject_package),
            "sha256": file_sha256(args.reject_package),
            "records": summary["decisions"].get("reject", 0),
        },
    }
    write_json(args.summary, summary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_html(records, summary), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": str(args.summary), **summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
