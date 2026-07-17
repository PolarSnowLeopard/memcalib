#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import shutil
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from utils import iter_jsonl, write_json


SCHEMA_VERSION = "memcalib-multidomain-release-artifacts-v1"
STACK_EXCHANGE_DATASET = "HuggingFaceH4/stack-exchange-preferences"
STACK_EXCHANGE_REQUIRED_FIELDS = (
    "question_author_name",
    "question_author_profile",
    "answer_author",
    "answer_author_profile",
    "question_url",
)
ADMISSION_TO_QC = {
    "admitted_strict": "strict_pass",
    "admitted_nonblocking_review": "review",
}
LABEL_ACTIONS = {
    "A": {"ignore"},
    "B": {"apply", "correct"},
    "C": {"apply", "correct"},
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_domain_targets(values: Iterable[str]) -> dict[str, int]:
    targets: dict[str, int] = {}
    for value in values:
        domain, separator, count = value.partition("=")
        if not separator or not domain or not count.isdigit() or int(count) <= 0:
            raise ValueError(f"invalid domain target: {value!r}")
        if domain in targets:
            raise ValueError(f"duplicate domain target: {domain}")
        targets[domain] = int(count)
    return targets


def stack_exchange_attribution_errors(metadata: dict[str, Any]) -> list[str]:
    errors = [
        f"missing_{field}"
        for field in STACK_EXCHANGE_REQUIRED_FIELDS
        if not str(metadata.get(field) or "").strip()
    ]
    if metadata.get("attribution_complete") is not True:
        errors.append("attribution_not_complete")
    return errors


def validate_release(
    rows: list[dict[str, Any]],
    expected_records: int,
    domain_targets: dict[str, int],
) -> dict[str, Any]:
    violations: list[str] = []
    ids: set[str] = set()
    source_ids: set[str] = set()
    domains: Counter[str] = Counter()
    stack_exchange_records = 0
    metadata_records = 0
    for index, row in enumerate(rows):
        record_id = str(row.get("id") or "")
        row_source_id = str(row.get("source_id") or "")
        domain = str(row.get("domain") or "")
        if not record_id:
            violations.append(f"row_{index}_missing_id")
        elif record_id in ids:
            violations.append(f"duplicate_id_{record_id}")
        if not row_source_id:
            violations.append(f"row_{index}_missing_source_id")
        elif row_source_id in source_ids:
            violations.append(f"duplicate_source_id_{row_source_id}")
        ids.add(record_id)
        source_ids.add(row_source_id)
        domains[domain] += 1

        deterministic_decision = str((row.get("deterministic_qc") or {}).get("decision") or "")
        if deterministic_decision != "pass":
            violations.append(f"{record_id}_deterministic_not_pass")
        admission = str((row.get("release_admission") or {}).get("decision") or "")
        qc_decision = str((row.get("independent_qc") or {}).get("decision") or "")
        if admission not in ADMISSION_TO_QC:
            violations.append(f"{record_id}_forbidden_release_admission_{admission}")
        elif qc_decision != ADMISSION_TO_QC[admission]:
            violations.append(f"{record_id}_admission_qc_mismatch")

        memories = row.get("memories")
        if not isinstance(memories, list) or not memories:
            violations.append(f"{record_id}_missing_memories")
            memories = []
        for memory_index, memory in enumerate(memories):
            label = str(memory.get("u_star") or "")
            action = str(memory.get("memory_action") or "")
            if label not in LABEL_ACTIONS:
                violations.append(f"{record_id}_memory_{memory_index}_bad_label")
            elif action not in LABEL_ACTIONS[label]:
                violations.append(f"{record_id}_memory_{memory_index}_label_action_mismatch")

        metadata = row.get("source_metadata")
        if isinstance(metadata, dict) and metadata:
            metadata_records += 1
        if str(row.get("source_dataset") or "") == STACK_EXCHANGE_DATASET:
            stack_exchange_records += 1
            errors = stack_exchange_attribution_errors(metadata if isinstance(metadata, dict) else {})
            violations.extend(f"{record_id}_{error}" for error in errors)

    if len(rows) != expected_records:
        violations.append(f"record_count_{len(rows)}_expected_{expected_records}")
    if len(ids) != len(rows):
        violations.append(f"unique_id_count_{len(ids)}_expected_{len(rows)}")
    if len(source_ids) != len(rows):
        violations.append(f"unique_source_id_count_{len(source_ids)}_expected_{len(rows)}")
    if dict(domains) != domain_targets:
        violations.append(f"domain_distribution_{dict(sorted(domains.items()))}_expected_{domain_targets}")
    if violations:
        preview = ", ".join(violations[:10])
        raise ValueError(f"release validation failed with {len(violations)} violation(s): {preview}")
    return {
        "records": len(rows),
        "unique_record_ids": len(ids),
        "unique_source_ids": len(source_ids),
        "domain_targets_exact": True,
        "deterministic_pass_only": True,
        "release_admission_valid": True,
        "label_action_consistent": True,
        "metadata_records": metadata_records,
        "stack_exchange_records": stack_exchange_records,
        "stack_exchange_attribution_complete": stack_exchange_records,
        "violations": [],
    }


def counter(rows: Iterable[dict[str, Any]], key) -> dict[str, int]:
    return dict(sorted(Counter(str(key(row) or "unknown") for row in rows).items()))


def nested_counter(rows: Iterable[dict[str, Any]], outer, inner) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        counts[str(outer(row) or "unknown")][str(inner(row) or "unknown")] += 1
    return {key: dict(sorted(value.items())) for key, value in sorted(counts.items())}


def numeric_summary(values: list[int]) -> dict[str, float | int]:
    return {
        "min": min(values),
        "max": max(values),
        "mean": round(statistics.fmean(values), 4),
        "median": statistics.median(values),
    }


def build_statistics(rows: list[dict[str, Any]], validation: dict[str, Any]) -> dict[str, Any]:
    memories = [memory for row in rows for memory in row.get("memories") or []]
    blocks = [block for row in rows for block in row.get("memory_blocks") or []]
    memory_counts = [len(row.get("memories") or []) for row in rows]
    block_counts = [len(row.get("memory_blocks") or []) for row in rows]
    atom_label_by_domain: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        atom_label_by_domain[str(row.get("domain") or "unknown")].update(
            str(memory.get("u_star") or "unknown") for memory in row.get("memories") or []
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "validation": validation,
        "record_distribution": {
            "domain": counter(rows, lambda row: row.get("domain")),
            "release_admission": counter(
                rows, lambda row: (row.get("release_admission") or {}).get("decision")
            ),
            "independent_qc_decision": counter(
                rows, lambda row: (row.get("independent_qc") or {}).get("decision")
            ),
            "source_dataset": counter(rows, lambda row: row.get("source_dataset")),
            "source_license": counter(rows, lambda row: row.get("source_license")),
            "source_topic": counter(rows, lambda row: row.get("source_topic")),
            "source_dataset_by_domain": nested_counter(
                rows, lambda row: row.get("domain"), lambda row: row.get("source_dataset")
            ),
            "release_admission_by_domain": nested_counter(
                rows,
                lambda row: row.get("domain"),
                lambda row: (row.get("release_admission") or {}).get("decision"),
            ),
        },
        "structure": {
            "memory_atoms": len(memories),
            "memory_blocks": len(blocks),
            "memories_per_record": numeric_summary(memory_counts),
            "memory_blocks_per_record": numeric_summary(block_counts),
            "records_by_memory_count": counter(rows, lambda row: len(row.get("memories") or [])),
            "records_by_memory_block_count": counter(
                rows, lambda row: len(row.get("memory_blocks") or [])
            ),
        },
        "memory_distribution": {
            "atomic_label": counter(memories, lambda memory: memory.get("u_star")),
            "memory_action": counter(memories, lambda memory: memory.get("memory_action")),
            "label_action": counter(
                memories,
                lambda memory: f"{memory.get('u_star', 'unknown')}:{memory.get('memory_action', 'unknown')}",
            ),
            "source": counter(memories, lambda memory: memory.get("source")),
            "derivation": counter(memories, lambda memory: memory.get("derivation")),
            "memory_type": counter(memories, lambda memory: memory.get("memory_type")),
            "hard_a_family": counter(memories, lambda memory: memory.get("hard_a_family") or "none"),
            "atomic_label_by_domain": {
                domain: dict(sorted(counts.items()))
                for domain, counts in sorted(atom_label_by_domain.items())
            },
        },
    }


def stable_sample(
    rows: list[dict[str, Any]],
    strict_per_domain: int,
    seed: int,
) -> list[dict[str, Any]]:
    review = [
        row
        for row in rows
        if (row.get("release_admission") or {}).get("decision") == "admitted_nonblocking_review"
    ]
    strict_by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if (row.get("release_admission") or {}).get("decision") == "admitted_strict":
            strict_by_domain[str(row.get("domain") or "unknown")].append(row)
    selected = list(review)
    for domain, candidates in sorted(strict_by_domain.items()):
        ranked = sorted(
            candidates,
            key=lambda row: hashlib.sha256(
                f"{seed}:{domain}:{row.get('id')}".encode("utf-8")
            ).hexdigest(),
        )
        selected.extend(ranked[:strict_per_domain])
    return sorted(
        selected,
        key=lambda row: (
            str((row.get("release_admission") or {}).get("decision") or ""),
            str(row.get("domain") or ""),
            str(row.get("id") or ""),
        ),
    )


def escape(value: Any) -> str:
    return html.escape(str(value or ""))


def safe_url(value: Any) -> str:
    url = str(value or "").strip()
    if not url.startswith(("https://", "http://")):
        return "#"
    return html.escape(url, quote=True)


def render_record(row: dict[str, Any]) -> str:
    admission = str((row.get("release_admission") or {}).get("decision") or "")
    domain = str(row.get("domain") or "")
    source = str(row.get("source_dataset") or "")
    memories = []
    for memory in row.get("memories") or []:
        memories.append(
            "<tr>"
            f"<td><strong>{escape(memory.get('u_star'))}</strong></td>"
            f"<td>{escape(memory.get('memory_action'))}</td>"
            f"<td>{escape(memory.get('source'))}</td>"
            f"<td>{escape(memory.get('text'))}</td>"
            f"<td>{escape(memory.get('evidence'))}</td>"
            f"<td>{escape(memory.get('label_reason'))}</td>"
            "</tr>"
        )
    attribution = ""
    metadata = row.get("source_metadata") or {}
    if source == STACK_EXCHANGE_DATASET:
        attribution = (
            "<div class=\"attribution\"><strong>Attribution:</strong> "
            f"<a href=\"{safe_url(metadata.get('question_author_profile'))}\">"
            f"{escape(metadata.get('question_author_name'))}</a> asked; "
            f"<a href=\"{safe_url(metadata.get('answer_author_profile'))}\">"
            f"{escape(metadata.get('answer_author'))}</a> answered; "
            f"<a href=\"{safe_url(metadata.get('question_url'))}\">source question</a>.</div>"
        )
    independent_qc = row.get("independent_qc") or {}
    qc_details = {
        "decision": independent_qc.get("decision"),
        "decision_reasons": independent_qc.get("decision_reasons") or [],
        "issues": independent_qc.get("issues") or [],
    }
    searchable = " ".join(
        [
            str(row.get("id") or ""),
            domain,
            admission,
            source,
            str(row.get("question") or ""),
            str(row.get("source_topic") or ""),
        ]
    ).casefold()
    return (
        f"<article class=\"record\" data-domain=\"{escape(domain)}\" "
        f"data-admission=\"{escape(admission)}\" data-search=\"{escape(searchable)}\">"
        "<header>"
        f"<div><span class=\"badge domain\">{escape(domain)}</span>"
        f"<span class=\"badge admission\">{escape(admission)}</span></div>"
        f"<code>{escape(row.get('id'))}</code>"
        "</header>"
        f"<h2>{escape(row.get('question'))}</h2>"
        f"<p class=\"meta\">{escape(source)} | {escape(row.get('source_topic'))} | "
        f"{escape(row.get('source_license'))}</p>"
        f"{attribution}"
        "<div class=\"table-wrap\"><table><thead><tr>"
        "<th>Label</th><th>Action</th><th>Source</th><th>Memory</th><th>Evidence</th><th>Reason</th>"
        "</tr></thead><tbody>"
        f"{''.join(memories)}"
        "</tbody></table></div>"
        "<details><summary>Independent QC</summary>"
        f"<pre>{escape(json.dumps(qc_details, ensure_ascii=False, indent=2))}</pre>"
        "</details>"
        "</article>"
    )


def render_review_html(
    rows: list[dict[str, Any]],
    source_path: Path,
    source_sha256: str,
    strict_per_domain: int,
    seed: int,
) -> str:
    sample = stable_sample(rows, strict_per_domain, seed)
    review_count = sum(
        (row.get("release_admission") or {}).get("decision") == "admitted_nonblocking_review"
        for row in sample
    )
    records = "\n".join(render_record(row) for row in sample)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MemCalib v0.2 Multidomain Release Review</title>
<style>
:root {{ color-scheme: light; --ink:#17212b; --muted:#66717d; --line:#d8dee4; --paper:#fff; --wash:#f4f6f8; --accent:#0f6b58; --review:#9a5b00; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--wash); color:var(--ink); font:14px/1.5 ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
.top {{ position:sticky; top:0; z-index:3; background:rgba(255,255,255,.97); border-bottom:1px solid var(--line); padding:18px 24px; }}
.top h1 {{ margin:0 0 4px; font-size:22px; letter-spacing:0; }}
.top p {{ margin:0 0 12px; color:var(--muted); }}
.controls {{ display:grid; grid-template-columns:minmax(220px,1fr) 180px 250px auto; gap:8px; align-items:center; }}
input,select {{ width:100%; min-height:36px; border:1px solid #b8c1ca; border-radius:4px; background:#fff; padding:7px 10px; color:var(--ink); }}
#visible {{ min-width:88px; text-align:right; color:var(--muted); }}
main {{ max-width:1500px; margin:0 auto; padding:20px 24px 60px; }}
.record {{ background:var(--paper); border:1px solid var(--line); border-radius:6px; margin:0 0 14px; padding:16px; }}
.record header {{ display:flex; justify-content:space-between; gap:16px; align-items:center; }}
.record h2 {{ font-size:17px; line-height:1.35; margin:12px 0 6px; letter-spacing:0; }}
.badge {{ display:inline-block; border:1px solid var(--line); border-radius:4px; padding:2px 7px; margin-right:6px; font-size:12px; }}
.domain {{ color:var(--accent); border-color:#8fc5b9; }}
.admission {{ color:var(--review); border-color:#d5b071; }}
.meta,.attribution {{ color:var(--muted); margin:6px 0 10px; }}
a {{ color:#075e9a; }}
.table-wrap {{ overflow:auto; border:1px solid var(--line); }}
table {{ width:100%; border-collapse:collapse; min-width:1100px; }}
th,td {{ text-align:left; vertical-align:top; padding:8px; border-bottom:1px solid var(--line); }}
th {{ background:#eef1f4; font-size:12px; }}
td:nth-child(1),td:nth-child(2),td:nth-child(3) {{ white-space:nowrap; }}
details {{ margin-top:10px; }}
pre {{ overflow:auto; background:#f6f8fa; border:1px solid var(--line); padding:10px; }}
code {{ font-size:12px; color:var(--muted); }}
@media (max-width:800px) {{ .controls {{ grid-template-columns:1fr; }} #visible {{ text-align:left; }} .record header {{ align-items:flex-start; flex-direction:column; }} }}
</style>
</head>
<body>
<section class="top">
  <h1>MemCalib v0.2 Multidomain Release Review</h1>
  <p>Deterministic audit sample: all {review_count} admitted reviews plus up to {strict_per_domain} strict records per domain. Source: {escape(source_path.name)} ({source_sha256}).</p>
  <div class="controls">
    <input id="search" type="search" placeholder="Search ID, question, source, or topic">
    <select id="domain"><option value="">All domains</option><option value="health_seed">health_seed</option><option value="general">general</option><option value="coding">coding</option></select>
    <select id="admission"><option value="">All admissions</option><option value="admitted_strict">admitted_strict</option><option value="admitted_nonblocking_review">admitted_nonblocking_review</option></select>
    <span id="visible"></span>
  </div>
</section>
<main>{records}</main>
<script>
const records=[...document.querySelectorAll('.record')];
const search=document.querySelector('#search');
const domain=document.querySelector('#domain');
const admission=document.querySelector('#admission');
const visible=document.querySelector('#visible');
function applyFilters(){{
  const query=search.value.trim().toLowerCase();
  let count=0;
  for(const record of records){{
    const show=(!query||record.dataset.search.includes(query))&&(!domain.value||record.dataset.domain===domain.value)&&(!admission.value||record.dataset.admission===admission.value);
    record.hidden=!show;
    if(show) count++;
  }}
  visible.textContent=`${{count}} / ${{records.length}}`;
}}
for(const control of [search,domain,admission]) control.addEventListener('input',applyFilters);
applyFilters();
</script>
</body>
</html>
"""


def write_deterministic_gzip(input_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with input_path.open("rb") as source, output_path.open("wb") as raw_output:
        with gzip.GzipFile(filename="", mode="wb", compresslevel=9, fileobj=raw_output, mtime=0) as compressed:
            shutil.copyfileobj(source, compressed, length=1024 * 1024)


def artifact(path: Path) -> dict[str, Any]:
    return {"path": str(path), "sha256": file_sha256(path), "bytes": path.stat().st_size}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and package the final MemCalib multidomain release.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--stats", type=Path, required=True)
    parser.add_argument("--review-html", type=Path, required=True)
    parser.add_argument("--gzip", type=Path, required=True)
    parser.add_argument("--package-manifest", type=Path, required=True)
    parser.add_argument("--expected-records", type=int, default=15000)
    parser.add_argument("--domain-target", action="append", required=True)
    parser.add_argument("--strict-sample-per-domain", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20260715)
    args = parser.parse_args()

    rows = list(iter_jsonl(args.input))
    targets = parse_domain_targets(args.domain_target)
    validation = validate_release(rows, args.expected_records, targets)
    source_sha256 = file_sha256(args.input)
    statistics_payload = build_statistics(rows, validation)
    statistics_payload["input"] = {
        "path": str(args.input),
        "sha256": source_sha256,
        "bytes": args.input.stat().st_size,
    }
    statistics_payload["parameters"] = {
        "expected_records": args.expected_records,
        "domain_targets": targets,
        "strict_sample_per_domain": args.strict_sample_per_domain,
        "seed": args.seed,
    }
    args.review_html.parent.mkdir(parents=True, exist_ok=True)
    args.review_html.write_text(
        render_review_html(
            rows,
            args.input,
            source_sha256,
            args.strict_sample_per_domain,
            args.seed,
        ),
        encoding="utf-8",
    )
    write_deterministic_gzip(args.input, args.gzip)
    write_json(args.stats, statistics_payload)
    package_manifest = {
        "schema_version": SCHEMA_VERSION,
        "validation": validation,
        "artifacts": {
            "jsonl": artifact(args.input),
            "gzip": artifact(args.gzip),
            "statistics": artifact(args.stats),
            "review_html": artifact(args.review_html),
        },
        "implementation": artifact(Path(__file__).resolve()),
    }
    write_json(args.package_manifest, package_manifest)
    print(json.dumps(package_manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
