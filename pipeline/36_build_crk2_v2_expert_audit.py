#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from utils import iter_jsonl, load_json, write_json


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
RELEASE_DIR = REPO_ROOT / "evaluation" / "releases" / "memcalib-v0.2-construction-pilot-100"
DEFAULT_BENCHMARK = SCRIPT_DIR / "data" / "crk2_v2_memory_benchmark_100.resolved.jsonl"
DEFAULT_STRICT = SCRIPT_DIR / "data" / "crk2_v2_independent_qc_100.resolved.strict_pass.jsonl"
DEFAULT_REJECT = SCRIPT_DIR / "data" / "crk2_v2_independent_qc_100.resolved.reject.jsonl"
DEFAULT_ANNOTATIONS = RELEASE_DIR / "expert-audit-30.annotations.json"
DEFAULT_OUTPUT = RELEASE_DIR / "expert-audit-30.html"
DEFAULT_SUMMARY = RELEASE_DIR / "expert-audit-30.summary.json"
DEFAULT_FINDINGS = RELEASE_DIR / "expert-audit-30.md"


def percent(numerator: int, denominator: int) -> float:
    return round(100.0 * numerator / denominator, 1) if denominator else 0.0


def index_review_records(strict_path: Path, reject_path: Path) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for prior_decision, path in (("strict_pass", strict_path), ("reject", reject_path)):
        for record in iter_jsonl(path):
            record_id = str(record.get("id") or "")
            if not record_id or record_id in indexed:
                raise ValueError(f"bad or duplicate record id: {record_id}")
            item = dict(record)
            item["prior_qc_decision"] = prior_decision
            indexed[record_id] = item
    return indexed


def validate_and_join(
    annotations: dict[str, Any],
    indexed: dict[str, dict[str, Any]],
    benchmark_path: Path,
) -> list[dict[str, Any]]:
    rows = annotations.get("records")
    if not isinstance(rows, list) or len(rows) != 30:
        raise ValueError("expert audit must contain exactly 30 records")
    ids = [str(row.get("id") or "") for row in rows]
    if len(set(ids)) != len(ids) or any(not record_id for record_id in ids):
        raise ValueError("expert audit ids must be non-empty and unique")

    benchmark = list(iter_jsonl(benchmark_path))
    all_reject_ids = {record_id for record_id, record in indexed.items() if record["prior_qc_decision"] == "reject"}
    all_correct_ids = {
        str(record.get("id") or "")
        for record in benchmark
        if any(memory.get("memory_action") == "correct" for memory in record.get("memories", []))
    }
    all_multi_strict_ids = {
        record_id
        for record_id, record in indexed.items()
        if record["prior_qc_decision"] == "strict_pass"
        and any(len(block.get("atom_ids", [])) > 1 for block in record.get("memory_blocks", []))
    }
    selected = set(ids)
    coverage = {
        "qc_reject": all_reject_ids - selected,
        "correct_action": all_correct_ids - selected,
        "multi_atom_strict": all_multi_strict_ids - selected,
    }
    missing = {name: sorted(values) for name, values in coverage.items() if values}
    if missing:
        raise ValueError(f"expert audit coverage incomplete: {missing}")

    joined: list[dict[str, Any]] = []
    for position, annotation in enumerate(rows, start=1):
        record_id = str(annotation["id"])
        if record_id not in indexed:
            raise ValueError(f"expert audit id not found in QC outputs: {record_id}")
        record = indexed[record_id]
        if annotation.get("prior_qc_decision") != record["prior_qc_decision"]:
            raise ValueError(f"prior QC decision mismatch for {record_id}")
        if annotation.get("decision") not in {"accept", "revise", "reject"}:
            raise ValueError(f"bad expert decision for {record_id}")
        if not isinstance(annotation.get("failed_dimensions"), list):
            raise ValueError(f"failed_dimensions must be a list for {record_id}")
        item = dict(record)
        item["expert_audit"] = dict(annotation)
        item["expert_audit"]["position"] = position
        joined.append(item)
    return joined


def build_summary(records: list[dict[str, Any]], annotations: dict[str, Any]) -> dict[str, Any]:
    decision_counts = Counter(record["expert_audit"]["decision"] for record in records)
    prior_counts = Counter(record["prior_qc_decision"] for record in records)
    source_counts = Counter(str(record.get("source_dataset") or "") for record in records)
    topic_counts = Counter(str(record.get("source_topic") or "") for record in records)
    dimension_counts: Counter[str] = Counter()
    finding_type_counts: Counter[str] = Counter()
    rationale_counts = Counter(record["expert_audit"].get("qc_rationale_assessment") for record in records)
    strata_counts: Counter[str] = Counter()
    for record in records:
        audit = record["expert_audit"]
        dimension_counts.update(audit.get("failed_dimensions", []))
        strata_counts.update(audit.get("selection_strata", []))
        finding_type_counts.update(
            str(finding.get("type") or "") for finding in audit.get("findings", []) if finding.get("type")
        )

    strict_records = [record for record in records if record["prior_qc_decision"] == "strict_pass"]
    strict_non_accept = sum(record["expert_audit"]["decision"] != "accept" for record in strict_records)
    rejected_records = [record for record in records if record["prior_qc_decision"] == "reject"]
    qc_false_rejects = sum(record["expert_audit"]["decision"] == "accept" for record in rejected_records)
    exact_reject_rationales = sum(
        record["expert_audit"].get("qc_rationale_assessment") == "exact" for record in rejected_records
    )

    return {
        "schema_version": "memcalib-v0.2-expert-audit-summary-v1",
        "audit_scope": annotations.get("audit_scope"),
        "selection_note_cn": annotations.get("selection_note_cn"),
        "records": len(records),
        "parent_memories": sum(len(record.get("memory_blocks", [])) for record in records),
        "atomic_memories": sum(len(record.get("memories", [])) for record in records),
        "expert_decisions": dict(sorted(decision_counts.items())),
        "prior_qc_decisions": dict(sorted(prior_counts.items())),
        "source_dataset": dict(sorted(source_counts.items())),
        "source_topic": dict(sorted(topic_counts.items())),
        "selection_strata": dict(sorted(strata_counts.items())),
        "failed_dimensions": dict(sorted(dimension_counts.items())),
        "finding_types": dict(sorted(finding_type_counts.items())),
        "qc_rationale_assessment": dict(sorted((str(key), value) for key, value in rationale_counts.items())),
        "rates": {
            "strict_stress_non_accept": {
                "numerator": strict_non_accept,
                "denominator": len(strict_records),
                "percent": percent(strict_non_accept, len(strict_records)),
                "interpretation_cn": "风险富集 strict-pass 子样本中需要修订或排除的比例；不能外推为全体 91 条的无偏缺陷率。",
            },
            "qc_reject_record_level_false_reject": {
                "numerator": qc_false_rejects,
                "denominator": len(rejected_records),
                "percent": percent(qc_false_rejects, len(rejected_records)),
                "interpretation_cn": "在 9 条 QC reject 中，人工审查认为可原样直接接收的比例。",
            },
            "qc_reject_exact_rationale": {
                "numerator": exact_reject_rationales,
                "denominator": len(rejected_records),
                "percent": percent(exact_reject_rationales, len(rejected_records)),
                "interpretation_cn": "QC reject 的拒绝理由与人工审查完全一致的比例；partial 与 incorrect 均不计入。",
            },
        },
    }


def render_markdown(records: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines = [
        "# MemCalib v0.2 专家协议验收（30 条）",
        "",
        "> 这是风险富集压力审查，覆盖全部 QC reject、correct-action 和 strict-pass 多原子 parent；不能把结果直接外推为 100 条总体缺陷率。",
        "",
        "## 结论",
        "",
        f"- Accept: {summary['expert_decisions'].get('accept', 0)}",
        f"- Revise: {summary['expert_decisions'].get('revise', 0)}",
        f"- Reject: {summary['expert_decisions'].get('reject', 0)}",
        f"- Strict-pass 压力样本非直接可用率: {summary['rates']['strict_stress_non_accept']['numerator']}/{summary['rates']['strict_stress_non_accept']['denominator']} ({summary['rates']['strict_stress_non_accept']['percent']}%)",
        f"- QC reject 记录级误拒绝率: {summary['rates']['qc_reject_record_level_false_reject']['numerator']}/{summary['rates']['qc_reject_record_level_false_reject']['denominator']} ({summary['rates']['qc_reject_record_level_false_reject']['percent']}%)",
        f"- QC reject 理由完全一致率: {summary['rates']['qc_reject_exact_rationale']['numerator']}/{summary['rates']['qc_reject_exact_rationale']['denominator']} ({summary['rates']['qc_reject_exact_rationale']['percent']}%)",
        "",
        "## 逐条结论",
        "",
        "| # | ID | 原 QC | 专家结论 | 主要问题 |",
        "|---:|---|---|---|---|",
    ]
    for index, record in enumerate(records, start=1):
        audit = record["expert_audit"]
        dimensions = ", ".join(audit.get("failed_dimensions", [])) or "none"
        lines.append(
            f"| {index} | `{record['id']}` | {record['prior_qc_decision']} | **{audit['decision']}** | {dimensions} |"
        )
    lines.extend(
        [
            "",
            "## 协议决策",
            "",
            "当前 v0.2 不能直接冻结并扩展。优先修订原子边界、反事实可归因性、医学/领域正确性与 hard-A 零足迹验证，再用同一 100 条候选重建并重复独立 QC 和 30 条压力审查。",
            "",
        ]
    )
    return "\n".join(lines)


def render_html(records: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    records_payload = json.dumps(records, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    summary_payload = json.dumps(summary, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MemCalib v0.2 · 专家协议验收 30 条</title>
  <style>
    :root{--ink:#172033;--muted:#627086;--line:#d5dde5;--paper:#fff;--canvas:#eaf0f1;--teal:#087c72;--teal-bg:#e4f3f0;--red:#a52b38;--red-bg:#fae9ec;--amber:#9a5b08;--amber-bg:#fff1d7;--blue:#315f91;--blue-bg:#eaf1f8;--violet:#71518d;--violet-bg:#f1eaf6;--shadow:0 12px 35px rgba(24,39,58,.08)}
    *{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--canvas);color:var(--ink);font-family:"Noto Sans SC","PingFang SC","Microsoft YaHei",system-ui,sans-serif;line-height:1.62;letter-spacing:0}.topbar{position:sticky;top:0;z-index:30;background:rgba(255,255,255,.97);border-bottom:1px solid var(--line)}.topbar-inner{width:min(1480px,calc(100% - 28px));min-height:68px;margin:auto;display:grid;grid-template-columns:240px minmax(280px,1fr) 410px;align-items:center;gap:18px}.nav{display:grid;grid-template-columns:1fr 1fr;gap:8px}.button{height:38px;border:1px solid #aeb9c6;background:#fff;color:var(--ink);font-weight:750;cursor:pointer}.button:hover:not(:disabled),.button:focus-visible{border-color:var(--teal);color:var(--teal);outline:2px solid rgba(8,124,114,.18);outline-offset:1px}.button:disabled{opacity:.35;cursor:not-allowed}.identity{text-align:center;min-width:0}.position{font:800 15px/1.15 ui-monospace,SFMono-Regular,Menlo,monospace}.record-id{margin-top:5px;color:var(--muted);font:650 11px/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.tools{display:grid;grid-template-columns:145px 145px 72px 1fr;gap:7px}.tools select,.tools input{height:38px;border:1px solid #b8c3cf;background:#fff;color:var(--ink);padding:0 8px;min-width:0}.page{width:min(1480px,calc(100% - 28px));margin:18px auto 48px}.overview{display:grid;grid-template-columns:minmax(340px,1.4fr) repeat(4,1fr);background:var(--paper);border:1px solid var(--line);box-shadow:var(--shadow);margin-bottom:16px}.thesis{padding:18px 20px;border-right:1px solid var(--line)}.thesis strong{display:block;font-size:17px}.thesis span{display:block;color:var(--muted);font-size:12px;margin-top:5px}.metric{padding:17px;border-right:1px solid var(--line)}.metric:last-child{border-right:0}.metric b{display:block;font:800 22px/1 ui-monospace,SFMono-Regular,Menlo,monospace}.metric span{display:block;color:var(--muted);font-size:11px;margin-top:7px}.sample{background:var(--paper);border:1px solid var(--line);box-shadow:var(--shadow)}.sample-head{display:grid;grid-template-columns:10px minmax(0,1fr) auto;border-bottom:1px solid var(--line)}.verdict-rail.accept{background:var(--teal)}.verdict-rail.revise{background:var(--amber)}.verdict-rail.reject{background:var(--red)}.question{padding:24px 28px}.eyebrow{font:750 11px/1.25 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted);text-transform:uppercase}.question h1{font-size:22px;line-height:1.45;margin:8px 0 0;max-width:980px}.badges{display:flex;align-content:flex-start;justify-content:flex-end;gap:7px;flex-wrap:wrap;padding:24px 24px 0 12px;max-width:350px}.badge{display:inline-flex;align-items:center;min-height:28px;padding:0 9px;border:1px solid currentColor;font:750 11px/1 ui-monospace,SFMono-Regular,Menlo,monospace}.accept{color:var(--teal);background:var(--teal-bg)}.revise{color:var(--amber);background:var(--amber-bg)}.reject{color:var(--red);background:var(--red-bg)}.strict_pass{color:var(--blue);background:var(--blue-bg)}.source{color:var(--violet);background:var(--violet-bg)}.expert{display:grid;grid-template-columns:240px minmax(0,1fr);border-bottom:1px solid var(--line);background:#fbfcfc}.verdict{padding:22px 24px;border-right:1px solid var(--line)}.verdict strong{display:block;font-size:28px;line-height:1.1;text-transform:uppercase}.verdict .severity{margin-top:8px;color:var(--muted);font-size:12px}.audit-body{padding:21px 26px}.audit-summary{font-size:16px;font-weight:700;margin-bottom:14px}.dimension-row{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:15px}.dimension{padding:5px 8px;border:1px solid #e0b777;background:var(--amber-bg);color:#784504;font:700 10px/1 ui-monospace,SFMono-Regular,Menlo,monospace}.finding{display:grid;grid-template-columns:140px minmax(0,1fr);gap:16px;padding:12px 0;border-top:1px solid var(--line)}.finding:first-of-type{border-top:0}.finding-key{font:750 11px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted)}.finding-text b{display:block;font-size:13px;margin-bottom:3px}.finding-text p{margin:0;color:#334158;font-size:13px}.recommendation{margin-top:5px!important;color:var(--teal)!important}.band{padding:22px 28px;border-bottom:1px solid var(--line)}.band:last-child{border-bottom:0}.section-title{display:flex;align-items:baseline;justify-content:space-between;gap:16px;margin-bottom:13px}.section-title h2{font-size:16px;margin:0}.section-title span{color:var(--muted);font-size:11px}.source-grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}.text{white-space:pre-wrap;overflow-wrap:anywhere}.muted{color:var(--muted)}details{margin-top:12px;border-top:1px solid var(--line);padding-top:11px}summary{cursor:pointer;color:var(--blue);font-weight:750}.parent{padding-top:20px;margin-top:24px;border-top:3px solid var(--teal)}.parent:first-of-type{margin-top:0}.parent-head{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:16px}.parent-title{font-size:18px;font-weight:750}.evidence{margin-top:10px;padding:12px 14px;border-left:3px solid #aab6c5;background:#f5f7f9;color:#455269}.atom-note{font-size:12px;color:var(--muted);margin-top:7px}.atoms{display:grid;gap:12px;margin-top:14px}.atom{border:1px solid var(--line);padding:17px;background:#fff}.atom.flagged{border-left:5px solid var(--amber);padding-left:13px}.atom-head{display:flex;align-items:center;gap:7px;flex-wrap:wrap;padding-bottom:11px;margin-bottom:12px;border-bottom:1px solid var(--line)}.atom-id{margin-right:auto;color:var(--muted);font:750 12px/1 ui-monospace,SFMono-Regular,Menlo,monospace}.label-a{color:#526174;background:#f1f4f6}.label-b{color:var(--blue);background:var(--blue-bg)}.label-c{color:var(--teal);background:var(--teal-bg)}.action-ignore{color:#526174;background:#f1f4f6}.action-apply{color:var(--violet);background:var(--violet-bg)}.action-correct{color:var(--amber);background:var(--amber-bg)}.predicate{font-size:16px;font-weight:750;margin-bottom:10px}.atom-finding{margin:12px 0;padding:12px 14px;background:var(--amber-bg);border-left:3px solid var(--amber);font-size:13px}.atom-finding b{display:block}.kv{display:grid;grid-template-columns:160px minmax(0,1fr);gap:6px 13px;font-size:13px}.kv dt{color:var(--muted);font-family:ui-monospace,SFMono-Regular,Menlo,monospace}.kv dd{margin:0;overflow-wrap:anywhere}.contract{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line);border:1px solid var(--line);margin-top:14px}.contract>div{padding:12px;background:#f8fafb}.contract strong{display:block;color:var(--muted);font-size:10px;margin-bottom:5px}.delta{grid-column:1/-1}.rubric{margin-top:14px;padding-left:14px;border-left:3px solid var(--blue)}.rubric h3{font-size:13px;margin:0 0 8px}.qc{border-top:3px solid var(--amber)}.qc-grid{display:grid;grid-template-columns:210px minmax(0,1fr);gap:18px}.qc-call{padding-right:18px;border-right:1px solid var(--line)}.qc-call strong{font-size:20px}.qc-note{font-size:13px}.qc-atom{padding:12px 0;border-bottom:1px solid var(--line)}.qc-atom:last-child{border-bottom:0}.mini-row{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:7px}.mini{padding:5px 7px;border:1px solid var(--line);background:#fff;font:700 10px/1 ui-monospace,SFMono-Regular,Menlo,monospace}.mini.fail{color:var(--red);background:var(--red-bg);border-color:#dfaab1}.empty{padding:70px;text-align:center;color:var(--muted)}
    @media(max-width:1080px){.topbar-inner{grid-template-columns:180px 1fr 330px}.tools{grid-template-columns:1fr 1fr 62px}.tools select:first-child{display:none}.overview{grid-template-columns:1.6fr repeat(2,1fr)}.metric:nth-of-type(n+3){border-top:1px solid var(--line)}.expert{grid-template-columns:190px 1fr}}
    @media(max-width:760px){.topbar-inner{grid-template-columns:1fr;gap:7px;padding:8px 0}.identity{grid-row:1}.nav{grid-row:2}.tools{grid-row:3}.page{margin-top:10px}.overview{grid-template-columns:1fr 1fr}.thesis{grid-column:1/-1;border-right:0;border-bottom:1px solid var(--line)}.sample-head{grid-template-columns:7px 1fr}.badges{grid-column:2;padding:0 20px 18px;justify-content:flex-start}.question{padding:20px}.expert{grid-template-columns:1fr}.verdict{border-right:0;border-bottom:1px solid var(--line)}.finding,.source-grid,.qc-grid,.contract{grid-template-columns:1fr}.delta{grid-column:auto}.qc-call{border-right:0;border-bottom:1px solid var(--line);padding:0 0 14px}.band{padding:19px}.kv{grid-template-columns:1fr}.kv dt{margin-top:5px}}
  </style>
</head>
<body>
  <header class="topbar"><div class="topbar-inner">
    <div class="nav"><button class="button" id="prev" title="上一条（← / K）">← 上一条</button><button class="button" id="next" title="下一条（→ / J）">下一条 →</button></div>
    <div class="identity"><div class="position" id="position"></div><div class="record-id" id="recordId"></div></div>
    <div class="tools"><select id="expertFilter" title="专家结论"><option value="all">全部专家结论</option><option value="accept">Accept</option><option value="revise">Revise</option><option value="reject">Reject</option></select><select id="qcFilter" title="原 QC"><option value="all">全部原 QC</option><option value="strict_pass">Strict pass</option><option value="reject">QC reject</option></select><input id="jump" type="number" min="1" title="跳转序号"><button class="button" id="go">跳转</button></div>
  </div></header>
  <main class="page"><section class="overview" id="overview"></section><div id="root"></div></main>
  <script>
  const records=__RECORDS__,summary=__SUMMARY__;let filtered=[...records],cursor=0;
  const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const arr=v=>Array.isArray(v)?v:[],obj=v=>(v&&typeof v==="object"&&!Array.isArray(v))?v:{};
  const badge=(text,cls="")=>`<span class="badge ${cls}">${esc(text)}</span>`;
  function renderOverview(){const d=summary.expert_decisions||{},rate=summary.rates.strict_stress_non_accept;document.getElementById("overview").innerHTML=`<div class="thesis"><strong>协议验收压力审查</strong><span>风险富集抽样：全部 QC reject、correct-action、多原子 strict-pass，并补齐数据源与主题。${esc(rate.interpretation_cn)}</span></div><div class="metric"><b>${summary.records}</b><span>audited records</span></div><div class="metric"><b>${d.accept||0}</b><span>accept</span></div><div class="metric"><b>${d.revise||0}</b><span>revise</span></div><div class="metric"><b>${rate.numerator}/${rate.denominator}</b><span>strict stress non-accept</span></div>`}
  function kvRows(data,keys){data=obj(data);return `<dl class="kv">${keys.map(k=>`<dt>${esc(k)}</dt><dd>${Array.isArray(data[k])?data[k].map(esc).join(" · "):esc(data[k])}</dd>`).join("")}</dl>`}
  function expertView(r){const a=r.expert_audit,findings=arr(a.findings);return `<section class="expert"><div class="verdict ${esc(a.decision)}"><div class="eyebrow">Expert decision</div><strong>${esc(a.decision)}</strong><div class="severity">severity: ${esc(a.severity)}<br>prior QC: ${esc(r.prior_qc_decision)}</div></div><div class="audit-body"><div class="audit-summary">${esc(a.summary_cn)}</div><div class="dimension-row">${arr(a.failed_dimensions).map(x=>`<span class="dimension">${esc(x)}</span>`).join("")||'<span class="badge accept">no blocking issue</span>'}</div>${findings.map(f=>`<div class="finding"><div class="finding-key">${esc(arr(f.atoms).join(" + "))}<br>${esc(f.type)}</div><div class="finding-text"><b>${esc(f.finding_cn)}</b><p class="recommendation">修改：${esc(f.action_cn)}</p></div></div>`).join("")}</div></section>`}
  function qcAtomView(q){const fields=[["query",q.query_relation,q.query_relation!=="absent"],["atomic",q.atomicity,q.atomicity!=="pass"],["label/action",q.label_action_validity,q.label_action_validity==="fail"],["counterfactual",q.counterfactual_observability,q.counterfactual_observability!=="pass"],["rubric",q.rubric_judgeability,q.rubric_judgeability==="fail"]];return `<div class="qc-atom"><div class="mini-row">${fields.map(x=>`<span class="mini ${x[2]?"fail":""}">${esc(x[0])}: ${esc(x[1])}</span>`).join("")}</div><div>${esc(q.reason)}</div><div class="muted">QC 推荐：${esc(q.recommended_u_star)} / ${esc(q.recommended_memory_action)}</div></div>`}
  function rubricView(r){return `<div class="rubric"><h3>Judge rubric · 完整判分规则</h3>${kvRows(r,["expected_answer_behavior","memory_usage_weight","validity_scope","correct_use","under_use","over_use","forbidden_memory_role","failure_direction","observable_checks"])}</div>`}
  function atomView(m,qcMap,findingMap){const id=m.atom_id||m.memory_id,c=obj(m.counterfactual_contract),t=obj(m.construction_target),q=qcMap[id],findings=findingMap[id]||[];return `<article class="atom ${findings.length?"flagged":""}"><div class="atom-head"><span class="atom-id">${esc(id)}</span>${badge(m.u_star,"label-"+String(m.u_star||"").toLowerCase())}${badge(m.memory_action,"action-"+m.memory_action)}${badge(m.source,"source")}</div><div class="predicate">${esc(m.text||m.atomic_predicate)}</div>${findings.map(f=>`<div class="atom-finding"><b>专家发现 · ${esc(f.type)}</b>${esc(f.finding_cn)}<br><span class="recommendation">修改：${esc(f.action_cn)}</span></div>`).join("")}${kvRows(m,["evidence","atomic_predicate","derivation","memory_type","subtype","hard_a_family","label_reason"])}<details><summary>Construction target · 构建目标</summary>${kvRows(t,["task_goal","memory_role","usage_boundary","failure_direction"])}</details><div class="contract"><div><strong>WITHOUT MEMORY</strong>${esc(c.without_memory_behavior)}</div><div><strong>WITH MEMORY</strong>${esc(c.with_memory_behavior)}</div><div class="delta"><strong>OBSERVABLE DELTA</strong>${esc(c.observable_delta)}<br><b>Minimal evidence:</b> ${arr(c.minimal_evidence).map(esc).join(" · ")||"none"}</div></div>${rubricView(m.usage_rubric)}${q?`<details><summary>Independent QC · 独立原子复核</summary>${qcAtomView(q)}</details>`:""}</article>`}
  function parentView(p,memories,qcMap,findingMap){return `<section class="parent"><div class="parent-head"><div><div class="eyebrow">Parent memory · ${esc(p.parent_memory_id)}</div><div class="parent-title">${esc(p.memory_text)}</div></div>${badge(p.source,"source")}</div><div class="evidence"><b>Raw evidence</b><br>${esc(p.raw_evidence)}</div><div class="atom-note">Atomization note: ${esc(p.atomization_notes)}</div><div class="atoms">${memories.map(m=>atomView(m,qcMap,findingMap)).join("")}</div></section>`}
  function render(){if(!filtered.length){document.getElementById("root").innerHTML='<div class="empty">当前筛选没有样本</div>';return}cursor=Math.max(0,Math.min(cursor,filtered.length-1));const r=filtered[cursor],a=r.expert_audit,qc=obj(r.independent_qc),qcMap=Object.fromEntries(arr(qc.atom_checks).map(x=>[x.atom_id,x])),findingMap={};arr(a.findings).forEach(f=>arr(f.atoms).forEach(id=>(findingMap[id]??=[]).push(f)));const byParent={};arr(r.memories).forEach(m=>(byParent[m.parent_memory_id]??=[]).push(m));document.getElementById("position").textContent=`${cursor+1} / ${filtered.length}`;document.getElementById("recordId").textContent=r.id;document.getElementById("jump").max=filtered.length;document.getElementById("jump").value=cursor+1;document.getElementById("prev").disabled=cursor===0;document.getElementById("next").disabled=cursor===filtered.length-1;document.getElementById("root").innerHTML=`<article class="sample"><header class="sample-head"><div class="verdict-rail ${esc(a.decision)}"></div><div class="question"><div class="eyebrow">Model-facing question</div><h1>${esc(r.question)}</h1></div><div class="badges">${badge(a.decision,a.decision)}${badge(r.prior_qc_decision,r.prior_qc_decision)}${badge(r.source_dataset,"source")}</div></header>${expertView(r)}<section class="band"><div class="section-title"><h2>源数据与去背景化任务</h2><span>${esc(r.source_topic)}</span></div><div class="source-grid"><div><div class="eyebrow">Raw query</div><div class="text">${esc(r.raw_query)}</div></div><div><div class="eyebrow">Source answer · 只用于证据审计</div><div class="text muted">${esc(r.source_answer)}</div></div></div></section><section class="band"><div class="section-title"><h2>模型可见记忆与隐藏原子标注</h2><span>${arr(r.memory_blocks).length} parents · ${arr(r.memories).length} atoms</span></div>${arr(r.memory_blocks).map(p=>parentView(p,byParent[p.parent_memory_id]||[],qcMap,findingMap)).join("")}</section><section class="band qc"><div class="section-title"><h2>独立 QC 与专家复核差异</h2><span>${esc(a.qc_rationale_assessment)}</span></div><div class="qc-grid"><div class="qc-call"><div class="eyebrow">Independent QC</div><strong>${esc(qc.decision)}</strong><div>${arr(qc.decision_reasons).map(esc).join(" · ")||"no reject reason"}</div></div><div class="qc-note"><b>专家对 QC 理由的判断：${esc(a.qc_rationale_assessment)}</b><br>${esc(a.qc_rationale_note_cn)}</div></div><details><summary>查看全部原子对复核</summary>${arr(qc.pair_checks).map(p=>`<div class="qc-atom"><b>${esc(p.left_atom_id)} ↔ ${esc(p.right_atom_id)}</b> · ${esc(p.relation)}<br>${esc(p.reason)}</div>`).join("")}</details></section></article>`;location.hash=encodeURIComponent(r.id)}
  function move(delta){if(!filtered.length)return;cursor=Math.max(0,Math.min(filtered.length-1,cursor+delta));render();scrollTo({top:0,behavior:"instant"})}
  function applyFilters(){const e=document.getElementById("expertFilter").value,q=document.getElementById("qcFilter").value;filtered=records.filter(r=>(e==="all"||r.expert_audit.decision===e)&&(q==="all"||r.prior_qc_decision===q));cursor=0;render()}
  document.getElementById("prev").onclick=()=>move(-1);document.getElementById("next").onclick=()=>move(1);document.getElementById("expertFilter").onchange=applyFilters;document.getElementById("qcFilter").onchange=applyFilters;document.getElementById("go").onclick=()=>{const n=Number(document.getElementById("jump").value);if(Number.isFinite(n)){cursor=n-1;render()}};document.addEventListener("keydown",e=>{if(["INPUT","TEXTAREA","SELECT"].includes(document.activeElement.tagName))return;if(e.key==="ArrowLeft"||e.key==="k")move(-1);if(e.key==="ArrowRight"||e.key==="j")move(1)});const initial=decodeURIComponent(location.hash.slice(1)),initialIndex=records.findIndex(r=>r.id===initial);if(initialIndex>=0)cursor=initialIndex;renderOverview();render();
  </script>
</body>
</html>'''.replace("__RECORDS__", records_payload).replace("__SUMMARY__", summary_payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the CRK-2 v2 30-record expert protocol audit report.")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--strict", type=Path, default=DEFAULT_STRICT)
    parser.add_argument("--reject", type=Path, default=DEFAULT_REJECT)
    parser.add_argument("--annotations", type=Path, default=DEFAULT_ANNOTATIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--findings", type=Path, default=DEFAULT_FINDINGS)
    args = parser.parse_args()

    annotations = load_json(args.annotations)
    indexed = index_review_records(args.strict, args.reject)
    records = validate_and_join(annotations, indexed, args.benchmark)
    summary = build_summary(records, annotations)
    write_json(args.summary, summary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_html(records, summary), encoding="utf-8")
    args.findings.write_text(render_markdown(records, summary), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": str(args.summary), **summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
