#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = SCRIPT_DIR / "data" / "verified_records.jsonl"
DEFAULT_OUTPUT = SCRIPT_DIR / "data" / "memory_abc_prototype_100.jsonl"
DEFAULT_SUMMARY = SCRIPT_DIR / "data" / "memory_abc_prototype_100.summary.json"
DEFAULT_HTML = SCRIPT_DIR / "data" / "memory_abc_prototype_100.html"

LABEL_TO_RELATION = {
    "A": "non_applicable",
    "B": "auxiliary",
    "C": "necessary",
}


def norm_text(text: Any) -> str:
    return " ".join(str(text or "").split())


def stable_id(*parts: str, prefix: str = "memabc") -> str:
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def infer_atom_type(text: str, source: str = "") -> str:
    value = f"{text} {source}".lower()
    profile_terms = (
        "works as",
        "job",
        "profession",
        "student",
        "engineer",
        "teacher",
        "年龄",
        "职业",
        "学生",
        "工程师",
        "老师",
    )
    constraint_terms = (
        "allergy",
        "allergic",
        "contraindication",
        "cannot",
        "can't",
        "must",
        "avoid",
        "budget",
        "deadline",
        "only",
        "format",
        "过敏",
        "禁忌",
        "不能",
        "必须",
        "避免",
        "预算",
        "截止",
        "格式",
    )
    preference_terms = (
        "prefer",
        "prefers",
        "preference",
        "likes",
        "like ",
        "loves",
        "favorite",
        "dislikes",
        "hates",
        "wants",
        "hopes",
        "reluctant",
        "喜欢",
        "偏好",
        "不喜欢",
        "讨厌",
        "希望",
        "想要",
        "倾向",
    )
    history_terms = (
        "history",
        "previously",
        "last year",
        "last week",
        "recently",
        "used to",
        "past",
        "曾经",
        "去年",
        "上周",
        "最近",
        "过去",
        "历史",
    )
    safety_terms = (
        "suicidal",
        "self-harm",
        "abuse",
        "unsafe",
        "diabetes",
        "blood glucose",
        "hypertension",
        "怀孕",
        "糖尿病",
        "血糖",
        "高血压",
        "自杀",
        "自残",
        "暴力",
        "安全",
    )
    if any(term in value for term in safety_terms):
        return "safety_sensitive"
    if any(term in value for term in profile_terms):
        return "profile_fact"
    if any(term in value for term in constraint_terms):
        return "constraint"
    if any(term in value for term in preference_terms):
        return "preference"
    if any(term in value for term in history_terms):
        return "episodic_fact"
    if "soft_preference" in source:
        return "preference"
    if "from_question" in source or "from_answer" in source:
        return "case_fact"
    return "profile_fact"


def convert_record(record: dict[str, Any], sample_index: int) -> dict[str, Any]:
    sample_id = f"memabc_{sample_index:06d}"
    preferences = record.get("preferences") or []
    atoms = []
    for idx, pref in enumerate(preferences, start=1):
        label = str(pref.get("u_star", "")).strip().upper()
        atom_text = norm_text(pref.get("preference", ""))
        source = norm_text(pref.get("source", ""))
        atoms.append(
            {
                "atom_id": f"{sample_id}_atom_{idx:02d}",
                "atom_text": atom_text,
                "atom_type": infer_atom_type(atom_text, source),
                "label": label,
                "relation": LABEL_TO_RELATION.get(label, "unknown"),
                "rationale": norm_text(pref.get("reason", "")),
                "verifier_rationale": norm_text(pref.get("verify_reason", "")),
                "source": source,
                "boundary_case": norm_text(pref.get("boundary_case", "none")) or "none",
            }
        )

    labels = [atom["label"] for atom in atoms]
    label_counts = {label: count for label, count in sorted(Counter(labels).items())}
    diagnostic_tags = []
    if len(label_counts) > 1:
        diagnostic_tags.append("mixed_label_block")
    else:
        diagnostic_tags.append("single_label_block")
    if any(atom.get("verifier_rationale") for atom in atoms):
        diagnostic_tags.append("has_verifier_audit")
    if record.get("source_dataset"):
        diagnostic_tags.append("medical_seed")

    return {
        "sample_id": sample_id,
        "source_record_id": record.get("id", ""),
        "query": norm_text(record.get("question", "")),
        "memory_block": "；".join(atom["atom_text"] for atom in atoms if atom["atom_text"]),
        "atoms": atoms,
        "block_composition": {
            "atom_count": len(atoms),
            "label_counts": label_counts,
            "mixed_label": len(label_counts) > 1,
        },
        "diagnostic_tags": diagnostic_tags,
        "source": {
            "dataset": record.get("source_dataset", ""),
            "split": record.get("source_split", ""),
            "topic": record.get("topic", ""),
            "source_raw_id": record.get("source_raw_id", ""),
            "source_index": record.get("source_index", ""),
        },
        "prototype_notes": "Converted from prior verified preference records; preferences are treated as draft atomic memories for format review.",
    }


def select_diverse_records(records: list[dict[str, Any]], limit: int, seed: int) -> list[dict[str, Any]]:
    if limit <= 0 or len(records) <= limit:
        return list(records)
    rng = random.Random(seed)
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if not record.get("preferences"):
            continue
        buckets[str(record.get("topic") or "unknown")].append(record)
    for topic, rows in buckets.items():
        topic_rng = random.Random(f"{seed}:{topic}")
        topic_rng.shuffle(rows)

    selected = []
    topics = sorted(buckets)
    while len(selected) < limit and topics:
        next_topics = []
        for topic in topics:
            if buckets[topic] and len(selected) < limit:
                selected.append(buckets[topic].pop(0))
            if buckets[topic]:
                next_topics.append(topic)
        topics = next_topics
    if len(selected) < limit:
        remaining = [row for rows in buckets.values() for row in rows]
        rng.shuffle(remaining)
        selected.extend(remaining[: limit - len(selected)])
    return selected[:limit]


def summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    label_counts: Counter = Counter()
    relation_counts: Counter = Counter()
    atom_type_counts: Counter = Counter()
    topic_counts: Counter = Counter()
    atom_count = 0
    mixed_count = 0
    for sample in samples:
        atom_count += len(sample.get("atoms", []))
        if sample.get("block_composition", {}).get("mixed_label"):
            mixed_count += 1
        topic_counts[sample.get("source", {}).get("topic", "unknown")] += 1
        for atom in sample.get("atoms", []):
            label_counts[atom.get("label", "")] += 1
            relation_counts[atom.get("relation", "")] += 1
            atom_type_counts[atom.get("atom_type", "")] += 1
    return {
        "total_samples": len(samples),
        "total_atoms": atom_count,
        "avg_atoms_per_sample": atom_count / len(samples) if samples else 0,
        "mixed_label_blocks": mixed_count,
        "label_counts": dict(sorted(label_counts.items())),
        "relation_counts": dict(sorted(relation_counts.items())),
        "atom_type_counts": dict(sorted(atom_type_counts.items())),
        "topic_counts": dict(sorted(topic_counts.items())),
        "prototype_limitations": [
            "Source data is still medical-domain seed data.",
            "Existing preferences are treated as draft atomic memories; no fresh atomic decomposition model was run.",
            "Overlap and conflict subsets are not constructed yet.",
        ],
    }


def tag_html(text: str) -> str:
    return f'<span class="tag">{html.escape(text)}</span>'


def build_html(samples: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    rows = []
    for sample in samples:
        atom_rows = []
        for atom in sample.get("atoms", []):
            atom_rows.append(
                f"""
                <tr>
                  <td><span class="label label-{html.escape(atom.get('label', ''))}">{html.escape(atom.get('label', ''))}</span></td>
                  <td>{html.escape(atom.get('relation', ''))}</td>
                  <td>{html.escape(atom.get('atom_type', ''))}</td>
                  <td>{html.escape(atom.get('atom_text', ''))}</td>
                  <td>{html.escape(atom.get('rationale', ''))}</td>
                </tr>
                """
            )
        tags = " ".join(tag_html(tag) for tag in sample.get("diagnostic_tags", []))
        label_counts = ", ".join(f"{label}:{count}" for label, count in sample.get("block_composition", {}).get("label_counts", {}).items())
        rows.append(
            f"""
            <article class="sample">
              <div class="sample-head">
                <div>
                  <h2>{html.escape(sample.get('sample_id', ''))}</h2>
                  <p>{html.escape(sample.get('source', {}).get('topic', 'unknown'))} · {html.escape(label_counts)}</p>
                </div>
                <div class="tags">{tags}</div>
              </div>
              <section>
                <h3>Query</h3>
                <p class="query">{html.escape(sample.get('query', ''))}</p>
              </section>
              <section>
                <h3>Memory block</h3>
                <p>{html.escape(sample.get('memory_block', ''))}</p>
              </section>
              <section>
                <h3>Atomic memories</h3>
                <table>
                  <thead><tr><th>Label</th><th>Relation</th><th>Type</th><th>Atom</th><th>Rationale</th></tr></thead>
                  <tbody>{''.join(atom_rows)}</tbody>
                </table>
              </section>
            </article>
            """
        )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Memory ABC Prototype 100</title>
  <style>
    :root {{
      --ink: #18212f;
      --muted: #647084;
      --line: #d8dee8;
      --paper: #f7f9fb;
      --panel: #ffffff;
      --a: #6c7888;
      --b: #1f6f8b;
      --c: #9a3b2f;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--paper);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.62;
      letter-spacing: 0;
    }}
    header {{
      padding: 34px min(5vw, 60px) 22px;
      border-bottom: 1px solid var(--line);
      background: #fff;
    }}
    header h1 {{ margin: 0; font-size: clamp(30px, 5vw, 54px); line-height: 1; }}
    header p {{ max-width: 900px; margin: 14px 0 0; color: #3c4858; font-size: 17px; }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      padding: 18px min(5vw, 60px);
    }}
    .metric, .sample {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 14px 34px rgba(24, 33, 47, 0.07);
    }}
    .metric {{ padding: 13px 15px; }}
    .metric strong {{ display: block; font-size: 24px; }}
    .metric span {{ color: var(--muted); font-size: 13px; }}
    main {{ display: grid; gap: 16px; padding: 10px min(5vw, 60px) 60px; }}
    .sample {{ overflow: hidden; }}
    .sample-head {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      padding: 15px 17px;
      border-bottom: 1px solid var(--line);
      background: #fbfcfe;
    }}
    .sample h2 {{ margin: 0; font-size: 18px; }}
    .sample-head p {{ margin: 3px 0 0; color: var(--muted); font-size: 13px; }}
    .tags {{ display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 6px; }}
    .tag {{
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 0 8px;
      border-radius: 999px;
      background: #eef3f8;
      color: #344054;
      border: 1px solid var(--line);
      font-size: 12px;
      font-weight: 720;
    }}
    section {{ padding: 13px 17px; border-bottom: 1px solid var(--line); }}
    section:last-child {{ border-bottom: 0; }}
    h3 {{ margin: 0 0 7px; font-size: 13px; text-transform: uppercase; color: var(--muted); letter-spacing: 0.04em; }}
    p {{ margin: 0; }}
    .query {{ font-size: 18px; font-weight: 720; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 9px 8px; border-top: 1px solid var(--line); vertical-align: top; text-align: left; }}
    th {{ color: #344054; background: #f4f7fa; }}
    .label {{
      display: inline-grid;
      place-items: center;
      width: 28px;
      height: 28px;
      color: white;
      border-radius: 50%;
      font-weight: 900;
    }}
    .label-A {{ background: var(--a); }}
    .label-B {{ background: var(--b); }}
    .label-C {{ background: var(--c); }}
    @media (max-width: 900px) {{
      .summary {{ grid-template-columns: 1fr 1fr; }}
      .sample-head {{ flex-direction: column; }}
      .tags {{ justify-content: flex-start; }}
      table {{ display: block; overflow-x: auto; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Memory ABC Prototype 100</h1>
    <p>First-pass atom-level conversion from existing verified records. This preview is for judging format and label framing, not final benchmark quality.</p>
  </header>
  <div class="summary">
    <div class="metric"><strong>{summary.get('total_samples', 0)}</strong><span>samples</span></div>
    <div class="metric"><strong>{summary.get('total_atoms', 0)}</strong><span>atomic memories</span></div>
    <div class="metric"><strong>{summary.get('mixed_label_blocks', 0)}</strong><span>mixed-label blocks</span></div>
    <div class="metric"><strong>{summary.get('avg_atoms_per_sample', 0):.2f}</strong><span>avg atoms/sample</span></div>
  </div>
  <main>{''.join(rows)}</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a 100-row atom-level Memory ABC prototype from verified records.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    records = list(iter_jsonl(args.input))
    selected = select_diverse_records(records, args.limit, args.seed)
    samples = [convert_record(record, idx + 1) for idx, record in enumerate(selected)]
    summary = summarize(samples)

    write_jsonl(args.output, samples)
    write_json(args.summary, summary)
    args.html.parent.mkdir(parents=True, exist_ok=True)
    args.html.write_text(build_html(samples, summary), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": str(args.summary), "html": str(args.html), **summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
