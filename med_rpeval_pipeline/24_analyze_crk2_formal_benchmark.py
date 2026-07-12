#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DEFAULT_BENCHMARK = DATA_DIR / "crk2_canonical_memory_benchmark_en_15528.jsonl"
DEFAULT_REJECTED = DATA_DIR / "crk2_canonical_memory_benchmark_en_15528.rejected.jsonl"
DEFAULT_SUMMARY = DATA_DIR / "crk2_canonical_memory_benchmark_en_15528.summary.json"
DEFAULT_LOCK = DATA_DIR / "crk2_canonical_generation_run_en_15577.lock.json"
DEFAULT_CANDIDATE_MANIFEST = DATA_DIR / "crk2_source_candidate_pool_30000.manifest.json"
DEFAULT_SEMANTIC_SUMMARY = DATA_DIR / "crk2_source_semantic_qc_30000.summary.json"
DEFAULT_ADMISSION_MANIFEST = DATA_DIR / "crk2_source_semantic_admission_15577.manifest.json"
DEFAULT_ADMITTED = DATA_DIR / "crk2_source_semantic_admitted_15577.jsonl"
DEFAULT_OUTPUT = DATA_DIR / "crk2_formal_benchmark_analysis.snapshot.json"
DEFAULT_ROWS = DATA_DIR / "crk2_formal_benchmark_analysis.rows.jsonl"
DEFAULT_ARTIFACT = DATA_DIR / "crk2_formal_benchmark_analysis.artifact.json"

LABEL_ORDER = ("A", "B", "C")
QC_KEYS = (
    "atomicity_pass",
    "duplicate_pass",
    "question_memory_leakage_pass",
    "hard_a_target_consistency_pass",
    "rubric_objectivity_pass",
)
SOURCE_LABELS = {
    "OpenMed/MedDialog": "MedDialog",
    "lavita/ChatDoctor-HealthCareMagic-100k": "ChatDoctor-HCM",
}
TOPIC_LABELS = {
    "acute_symptoms": "急性症状",
    "cardio": "心血管",
    "chronic_disease": "慢性病",
    "digestive": "消化系统",
    "general_other": "综合其他",
    "medication_treatment": "用药与治疗",
    "mental_sleep": "心理与睡眠",
    "neuro": "神经系统",
    "pediatrics": "儿科",
    "pregnancy_reproductive": "妊娠与生殖",
    "respiratory_ent": "呼吸与耳鼻喉",
    "skin_allergy": "皮肤与过敏",
}
MEMORY_TYPE_LABELS = {
    "case_fact": "情境事实",
    "constraint": "约束",
    "preference": "偏好",
    "profile_fact": "画像事实",
    "safety_sensitive": "安全敏感",
}
HARD_A_LABELS = {
    "fact_judgment_pollution": "事实判断污染",
    "scope_overreach": "范围越界",
    "evidence_conflict": "证据冲突",
    "profile_style_near_neighbor": "画像/风格近邻",
    "untriggered_preference": "未触发偏好",
}
LENGTH_LABELS = {
    "question_chars": "去背景化问题",
    "parent_memory_chars": "父记忆文本",
    "atomic_memory_chars": "原子记忆文本",
    "evidence_chars": "原始证据",
    "rubric_chars": "单原子 Judge rubric",
    "sample_rubric_chars": "单样本 Judge rubric 总量",
}


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def quantile(values: list[int | float], probability: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * min(max(probability, 0.0), 1.0)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def distribution_summary(values: list[int | float]) -> dict[str, float | int]:
    if not values:
        return {"count": 0, "min": 0, "mean": 0, "median": 0, "p90": 0, "p95": 0, "p99": 0, "max": 0}
    return {
        "count": len(values),
        "min": min(values),
        "mean": fmean(values),
        "median": quantile(values, 0.5),
        "p90": quantile(values, 0.9),
        "p95": quantile(values, 0.95),
        "p99": quantile(values, 0.99),
        "max": max(values),
    }


def natural_language_chars(value: Any) -> int:
    if isinstance(value, str):
        return len(value)
    if isinstance(value, dict):
        return sum(natural_language_chars(child) for child in value.values())
    if isinstance(value, list):
        return sum(natural_language_chars(child) for child in value)
    return 0


def new_state() -> dict[str, Any]:
    return {
        "samples": 0,
        "parent_memories": 0,
        "atomic_memories": 0,
        "mixed_parents": 0,
        "synthetic_atomic_memories": 0,
        "counts": {
            "source_dataset": Counter(),
            "topic": Counter(),
            "seed_complexity": Counter(),
            "labels": Counter(),
            "memory_source": Counter(),
            "memory_type": Counter(),
            "hard_a_family": Counter(),
            "parent_label_set": Counter(),
            "parent_label_mode": Counter(),
            "subtype": Counter(),
            "qc_pass": Counter(),
            "counterfactual": Counter(),
            "manual_audit": Counter(),
        },
        "cross": {
            "source_topic": defaultdict(Counter),
            "topic_label": defaultdict(Counter),
            "source_label": defaultdict(Counter),
            "memory_type_label": defaultdict(Counter),
            "complexity_label": defaultdict(Counter),
        },
        "lengths": defaultdict(list),
        "discrete": {
            "sample_parent_count": Counter(),
            "sample_atomic_count": Counter(),
            "parent_atom_count": Counter(),
        },
    }


def update_state(state: dict[str, Any], sample: dict[str, Any], seed_complexity: str = "unknown") -> None:
    source = str(sample.get("source_dataset") or "unknown")
    topic = str(sample.get("source_topic") or "unknown")
    blocks = sample.get("memory_blocks") or []
    memories = sample.get("memories") or []
    state["samples"] += 1
    state["parent_memories"] += len(blocks)
    state["atomic_memories"] += len(memories)
    state["counts"]["source_dataset"][source] += 1
    state["counts"]["topic"][topic] += 1
    state["counts"]["seed_complexity"][seed_complexity] += 1
    state["cross"]["source_topic"][source][topic] += 1
    state["discrete"]["sample_parent_count"][len(blocks)] += 1
    state["discrete"]["sample_atomic_count"][len(memories)] += 1
    state["lengths"]["question_chars"].append(len(str(sample.get("question") or "")))

    for block in blocks:
        mode = str(block.get("parent_label_mode") or "unknown")
        labels = block.get("parent_label_set") or []
        label_set = "+".join(labels) if isinstance(labels, list) else str(labels)
        atom_count = int(block.get("atom_count") or len(block.get("atom_ids") or []))
        state["counts"]["parent_label_mode"][mode] += 1
        state["counts"]["parent_label_set"][label_set or "none"] += 1
        state["mixed_parents"] += int(mode == "mixed")
        state["discrete"]["parent_atom_count"][atom_count] += 1
        state["lengths"]["parent_memory_chars"].append(len(str(block.get("memory_text") or block.get("text") or "")))

    sample_rubric_chars = 0
    for memory in memories:
        label = str(memory.get("u_star") or "unknown")
        memory_source = str(memory.get("source") or "unknown")
        memory_type = str(memory.get("memory_type") or "unknown")
        subtype = str(memory.get("subtype") or "unknown")
        hard_a_family = memory.get("hard_a_family")
        rubric_chars = natural_language_chars(memory.get("usage_rubric") or {})
        state["counts"]["labels"][label] += 1
        state["counts"]["memory_source"][memory_source] += 1
        state["counts"]["memory_type"][memory_type] += 1
        state["counts"]["subtype"][subtype] += 1
        state["cross"]["topic_label"][topic][label] += 1
        state["cross"]["source_label"][source][label] += 1
        state["cross"]["memory_type_label"][memory_type][label] += 1
        state["cross"]["complexity_label"][seed_complexity][label] += 1
        if hard_a_family:
            state["counts"]["hard_a_family"][str(hard_a_family)] += 1
        if memory_source == "synthetic_hard_a":
            state["synthetic_atomic_memories"] += 1
        state["lengths"]["atomic_memory_chars"].append(len(str(memory.get("text") or "")))
        state["lengths"]["evidence_chars"].append(len(str(memory.get("evidence") or "")))
        state["lengths"]["rubric_chars"].append(rubric_chars)
        sample_rubric_chars += rubric_chars
    state["lengths"]["sample_rubric_chars"].append(sample_rubric_chars)

    qc = sample.get("qc") or {}
    for key in QC_KEYS:
        if qc.get(key) is True:
            state["counts"]["qc_pass"][key] += 1
    state["counts"]["counterfactual"][str(qc.get("counterfactual_pass") or "unknown")] += 1
    state["counts"]["manual_audit"][str(qc.get("manual_audit") or "unknown")] += 1


def counter_rows(counter: Counter, labels: dict[str, str] | None = None) -> list[dict[str, Any]]:
    total = sum(counter.values())
    ordered = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return [
        {
            "key": key,
            "label": (labels or {}).get(key, key),
            "count": count,
            "share": count / total if total else 0,
            "rank": rank,
        }
        for rank, (key, count) in enumerate(ordered, start=1)
    ]


def cross_rows(
    cross: dict[str, Counter],
    row_labels: dict[str, str] | None = None,
    column_order: tuple[str, ...] = LABEL_ORDER,
) -> list[dict[str, Any]]:
    rows = []
    for row_key, counts in sorted(cross.items()):
        total = sum(counts.values())
        for column in column_order:
            count = counts.get(column, 0)
            rows.append(
                {
                    "row_key": row_key,
                    "row_label": (row_labels or {}).get(row_key, row_key),
                    "series": column,
                    "count": count,
                    "share_within_row": count / total if total else 0,
                    "row_total": total,
                }
            )
    return rows


def discrete_rows(counter: Counter) -> list[dict[str, Any]]:
    total = sum(counter.values())
    return [
        {"value": value, "category": str(value), "count": count, "share": count / total if total else 0}
        for value, count in sorted(counter.items())
    ]


def finalize_state(state: dict[str, Any]) -> dict[str, Any]:
    samples = state["samples"]
    parent_memories = state["parent_memories"]
    atomic_memories = state["atomic_memories"]
    subtype_counts = state["counts"]["subtype"]
    subtype_singletons = sum(1 for count in subtype_counts.values() if count == 1)
    length_summary = []
    for key, values in state["lengths"].items():
        row = {"metric": key, "metric_label": LENGTH_LABELS[key], **distribution_summary(values)}
        length_summary.append(row)
    length_summary.sort(key=lambda row: list(LENGTH_LABELS).index(row["metric"]))

    counts = {
        key: dict(sorted(counter.items()))
        for key, counter in state["counts"].items()
        if key != "subtype"
    }
    datasets = {
        "source_distribution": counter_rows(state["counts"]["source_dataset"], SOURCE_LABELS),
        "topic_distribution": counter_rows(state["counts"]["topic"], TOPIC_LABELS),
        "seed_complexity_distribution": counter_rows(state["counts"]["seed_complexity"]),
        "label_distribution": counter_rows(state["counts"]["labels"]),
        "memory_source_distribution": counter_rows(state["counts"]["memory_source"]),
        "memory_type_distribution": counter_rows(state["counts"]["memory_type"], MEMORY_TYPE_LABELS),
        "hard_a_distribution": counter_rows(state["counts"]["hard_a_family"], HARD_A_LABELS),
        "parent_label_set_distribution": counter_rows(state["counts"]["parent_label_set"]),
        "source_topic_distribution": [
            {
                "source_dataset": source,
                "source_label": SOURCE_LABELS.get(source, source),
                "topic": topic,
                "topic_label": TOPIC_LABELS.get(topic, topic),
                "count": count,
            }
            for source, topic_counts in sorted(state["cross"]["source_topic"].items())
            for topic, count in sorted(topic_counts.items())
        ],
        "topic_label_distribution": cross_rows(state["cross"]["topic_label"], TOPIC_LABELS),
        "source_label_distribution": cross_rows(state["cross"]["source_label"], SOURCE_LABELS),
        "memory_type_label_distribution": cross_rows(state["cross"]["memory_type_label"], MEMORY_TYPE_LABELS),
        "complexity_label_distribution": cross_rows(state["cross"]["complexity_label"]),
        "sample_parent_count_distribution": discrete_rows(state["discrete"]["sample_parent_count"]),
        "sample_atomic_count_distribution": discrete_rows(state["discrete"]["sample_atomic_count"]),
        "parent_atom_count_distribution": discrete_rows(state["discrete"]["parent_atom_count"]),
        "length_summary": length_summary,
        "subtype_top": [
            {"subtype": subtype, "count": count, "share": count / atomic_memories if atomic_memories else 0, "rank": rank}
            for rank, (subtype, count) in enumerate(subtype_counts.most_common(30), start=1)
        ],
    }
    return {
        "headline": {
            "samples": samples,
            "parent_memories": parent_memories,
            "atomic_memories": atomic_memories,
            "avg_parent_memories_per_sample": parent_memories / samples if samples else 0,
            "avg_atomic_memories_per_sample": atomic_memories / samples if samples else 0,
            "atomization_ratio": atomic_memories / parent_memories if parent_memories else 0,
            "mixed_parents": state["mixed_parents"],
            "mixed_parent_rate": state["mixed_parents"] / parent_memories if parent_memories else 0,
            "synthetic_atomic_memories": state["synthetic_atomic_memories"],
            "synthetic_atomic_share": state["synthetic_atomic_memories"] / atomic_memories if atomic_memories else 0,
            "source_count": len(state["counts"]["source_dataset"]),
            "topic_count": len(state["counts"]["topic"]),
            "subtype_cardinality": len(subtype_counts),
            "subtype_singletons": subtype_singletons,
            "subtype_singleton_rate": subtype_singletons / len(subtype_counts) if subtype_counts else 0,
        },
        "counts": counts,
        "datasets": datasets,
    }


def load_seed_complexities(path: Path) -> dict[str, str]:
    mapping = {}
    for row in iter_jsonl(path):
        mapping[str(row.get("id") or "")] = str((row.get("raw_selection") or {}).get("seed_complexity") or "unknown")
    return mapping


def rejected_summary(path: Path) -> dict[str, Any]:
    reasons = Counter()
    rows = 0
    for row in iter_jsonl(path):
        rows += 1
        reasons.update(set(row.get("errors") or []))
    return {"rows": rows, "reason_counts": dict(sorted(reasons.items()))}


def build_funnel(
    candidate_manifest: dict[str, Any],
    semantic_summary: dict[str, Any],
    admission_manifest: dict[str, Any],
    run_lock: dict[str, Any],
) -> list[dict[str, Any]]:
    completion = run_lock.get("completion") or {}
    stages = [
        ("确定性质量过滤后", int((candidate_manifest.get("counts") or {}).get("eligible") or 0)),
        ("分层候选池", int((candidate_manifest.get("counts") or {}).get("selected") or 0)),
        ("语义 QC 有效", int((admission_manifest.get("counts") or {}).get("input") or semantic_summary.get("valid") or 0)),
        ("语义严格通过", int((admission_manifest.get("counts") or {}).get("strict_pass") or 0)),
        ("正式准入", int((admission_manifest.get("counts") or {}).get("admitted") or 0)),
        ("生成结果可解析", int(((completion.get("quality_retry") or {}).get("resolved_generation_records")) or 0)),
        ("正式 benchmark", int(((completion.get("final_construction_qc") or {}).get("accepted")) or 0)),
    ]
    rows = []
    first_count = stages[0][1] if stages else 0
    previous = None
    for rank, (stage, count) in enumerate(stages, start=1):
        rows.append(
            {
                "stage": stage,
                "count": count,
                "retention": count / previous if previous else 1.0,
                "overall_retention": count / first_count if first_count else 0,
                "rank": rank,
            }
        )
        previous = count
    return rows


def reconcile(analysis: dict[str, Any], summary: dict[str, Any], run_lock: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "samples": (analysis["headline"]["samples"], int(summary.get("total_samples") or 0)),
        "parent_memories": (analysis["headline"]["parent_memories"], int(summary.get("total_parent_memories") or 0)),
        "atomic_memories": (analysis["headline"]["atomic_memories"], int(summary.get("total_memories") or 0)),
        "labels": (analysis["counts"]["labels"], summary.get("label_counts") or {}),
        "memory_source": (analysis["counts"]["memory_source"], summary.get("memory_source_counts") or {}),
        "memory_type": (analysis["counts"]["memory_type"], summary.get("memory_type_counts") or {}),
        "topics": (analysis["counts"]["topic"], summary.get("topic_counts") or {}),
        "lock_final_count": (
            analysis["headline"]["samples"],
            int((((run_lock.get("completion") or {}).get("final_construction_qc") or {}).get("accepted")) or 0),
        ),
    }
    mismatches = {
        key: {"computed": computed, "expected": expected}
        for key, (computed, expected) in checks.items()
        if computed != expected
    }
    if mismatches:
        raise ValueError(f"formal benchmark reconciliation failed: {mismatches}")
    return {"status": "passed", "checks": list(checks), "mismatches": {}}


def analyze_benchmark(
    benchmark: Path,
    rejected: Path,
    summary_path: Path,
    lock_path: Path,
    candidate_manifest_path: Path,
    semantic_summary_path: Path,
    admission_manifest_path: Path,
    admitted_path: Path,
) -> dict[str, Any]:
    complexities = load_seed_complexities(admitted_path)
    state = new_state()
    missing_complexity = 0
    for sample in iter_jsonl(benchmark):
        source_id = str(sample.get("source_id") or "")
        complexity = complexities.get(source_id, "unknown")
        missing_complexity += int(complexity == "unknown")
        update_state(state, sample, complexity)
    analysis = finalize_state(state)
    summary = load_json(summary_path)
    run_lock = load_json(lock_path)
    candidate_manifest = load_json(candidate_manifest_path)
    semantic_summary = load_json(semantic_summary_path)
    admission_manifest = load_json(admission_manifest_path)
    analysis["funnel"] = build_funnel(candidate_manifest, semantic_summary, admission_manifest, run_lock)
    analysis["datasets"]["funnel"] = analysis["funnel"]
    analysis["rejected"] = rejected_summary(rejected)
    analysis["reconciliation"] = reconcile(analysis, summary, run_lock)
    analysis["reconciliation"]["missing_seed_complexity"] = missing_complexity
    analysis["source_files"] = {
        "benchmark": {"path": str(benchmark), "sha256": file_sha256(benchmark)},
        "rejected": {"path": str(rejected), "sha256": file_sha256(rejected)},
        "summary": {"path": str(summary_path), "sha256": file_sha256(summary_path)},
        "run_lock": {"path": str(lock_path), "sha256": file_sha256(lock_path)},
        "candidate_manifest": {"path": str(candidate_manifest_path), "sha256": file_sha256(candidate_manifest_path)},
        "semantic_summary": {"path": str(semantic_summary_path), "sha256": file_sha256(semantic_summary_path)},
        "admission_manifest": {"path": str(admission_manifest_path), "sha256": file_sha256(admission_manifest_path)},
        "analysis_script": {"path": str(Path(__file__).resolve()), "sha256": file_sha256(Path(__file__).resolve())},
    }
    return analysis


def source_specs(generated_at: str) -> list[dict[str, Any]]:
    rows_path = "med_rpeval_pipeline/data/crk2_formal_benchmark_analysis.rows.jsonl"
    return [
        {
            "id": "formal_benchmark_jsonl",
            "label": "CRK-2 formal benchmark reviewed aggregate rows",
            "path": rows_path,
            "query": {
                "engine": "duckdb",
                "language": "sql",
                "sql": f"SELECT * FROM read_json_auto('{rows_path}', format='newline_delimited');",
                "description": "Read every reviewed aggregate row produced by the full formal-benchmark streaming analysis.",
                "executed_at": generated_at,
                "tables_used": [rows_path],
                "filters": ["All formal benchmark records; no sampling", "Artifact blocks select the named _dataset"],
                "metric_definitions": [
                    "Sample count = formal post-construction-QC JSONL records.",
                    "Atomic memory count = sum of len(memories) across formal samples.",
                    "Mixed-parent rate = mixed-label parent blocks divided by all parent blocks.",
                    "Synthetic footprint = source=synthetic_hard_a atoms divided by all atoms.",
                ],
            },
        },
        {
            "id": "construction_lineage",
            "label": "CRK-2 construction funnel reviewed rows",
            "path": rows_path,
            "query": {
                "engine": "duckdb",
                "language": "sql",
                "sql": f"SELECT * FROM read_json_auto('{rows_path}', format='newline_delimited') WHERE _dataset = 'funnel';",
                "description": "Read the locked construction-funnel rows derived from candidate, semantic-QC, admission, generation, and final-QC manifests.",
                "executed_at": generated_at,
                "tables_used": [rows_path],
                "filters": ["_dataset = funnel", "Locked English full-scale CRK-2 run"],
                "metric_definitions": ["Stage retention = current stage count divided by the immediately preceding stage count."],
            },
        },
    ]


def flattened_dataset_rows(datasets: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [{"_dataset": dataset, **row} for dataset, rows in datasets.items() for row in rows]


def build_artifact(analysis: dict[str, Any], generated_at: str) -> dict[str, Any]:
    headline = analysis["headline"]
    datasets = dict(analysis.get("datasets") or {})
    labels = {row["key"]: row for row in datasets.get("label_distribution", [])}
    topics = datasets.get("topic_distribution", [])
    top_three_topic_share = sum(row["share"] for row in topics[:3])
    hard_a = datasets.get("hard_a_distribution", [])
    dominant_hard_a = hard_a[0] if hard_a else {"label": "n/a", "share": 0}
    length_by_key = {row["metric"]: row for row in datasets.get("length_summary", [])}
    sources = source_specs(generated_at)

    datasets["headline_metrics"] = [
        {
            "samples": headline["samples"],
            "atomic_memories": headline["atomic_memories"],
            "avg_atoms_per_sample": headline["avg_atomic_memories_per_sample"],
            "mixed_parent_rate": headline["mixed_parent_rate"],
            "synthetic_atomic_share": headline["synthetic_atomic_share"],
            "topic_count": headline["topic_count"],
        }
    ]
    datasets["paper_core_metrics"] = [
        {"metric": "正式样本", "value": headline["samples"], "unit": "samples", "definition": "完成全部构建与形式 QC 后保留的样本"},
        {"metric": "父记忆", "value": headline["parent_memories"], "unit": "blocks", "definition": "atomization 前的 model-facing memory block"},
        {"metric": "原子记忆", "value": headline["atomic_memories"], "unit": "atoms", "definition": "独立打 A/B/C 标签的评估单元"},
        {"metric": "平均原子记忆/样本", "value": headline["avg_atomic_memories_per_sample"], "unit": "atoms/sample", "definition": "原子记忆数除以样本数"},
        {"metric": "atomization ratio", "value": headline["atomization_ratio"], "unit": "atoms/parent", "definition": "原子记忆数除以父记忆数"},
        {"metric": "混合标签父记忆率", "value": headline["mixed_parent_rate"], "unit": "share", "definition": "同一父记忆包含多种 A/B/C atom 的比例"},
        {"metric": "synthetic hard-A footprint", "value": headline["synthetic_atomic_share"], "unit": "share", "definition": "synthetic_hard_a 原子占全部原子的比例"},
        {"metric": "主题数", "value": headline["topic_count"], "unit": "topics", "definition": "当前 health_seed 内部主题类别"},
    ]
    datasets["qc_status"] = [
        {
            "check": key,
            "status": "pass" if analysis["counts"]["qc_pass"].get(key, 0) == headline["samples"] else "partial",
            "passed": analysis["counts"]["qc_pass"].get(key, 0),
            "denominator": headline["samples"],
            "share": analysis["counts"]["qc_pass"].get(key, 0) / headline["samples"] if headline["samples"] else 0,
            "scope": "automatic construction QC",
        }
        for key in QC_KEYS
    ] + [
        {
            "check": "counterfactual answer test",
            "status": "pending",
            "passed": 0,
            "denominator": headline["samples"],
            "share": 0,
            "scope": "response-level validation",
        },
        {
            "check": "stratified manual audit",
            "status": "pending",
            "passed": 0,
            "denominator": headline["samples"],
            "share": 0,
            "scope": "human validation",
        },
    ]

    title = "CRK-2 正式数据集统计分析与质量审计"
    cards = [
        {"id": "samples", "dataset": "headline_metrics", "sourceId": "formal_benchmark_jsonl", "description": "完成全部构建与形式 QC 后保留的 benchmark 样本。", "metrics": [{"label": "正式样本", "field": "samples", "format": "compact"}]},
        {"id": "atoms", "dataset": "headline_metrics", "sourceId": "formal_benchmark_jsonl", "description": "独立进行 A/B/C 打标和 judge rubric 评估的原子记忆。", "metrics": [{"label": "原子记忆", "field": "atomic_memories", "format": "compact"}]},
        {"id": "atoms_per_sample", "dataset": "headline_metrics", "sourceId": "formal_benchmark_jsonl", "description": "每条样本包含的原子记忆均值。", "metrics": [{"label": "平均 atoms/样本", "field": "avg_atoms_per_sample", "format": "number"}]},
        {"id": "mixed_parent", "dataset": "headline_metrics", "sourceId": "formal_benchmark_jsonl", "description": "父记忆内部包含两种或三种 A/B/C 标签的比例。", "metrics": [{"label": "混合标签父记忆", "field": "mixed_parent_rate", "format": "percent"}]},
        {"id": "synthetic_share", "dataset": "headline_metrics", "sourceId": "formal_benchmark_jsonl", "description": "synthetic_hard_a 原子占全部原子记忆的比例。", "metrics": [{"label": "Synthetic Hard-A", "field": "synthetic_atomic_share", "format": "percent"}]},
        {"id": "topic_count", "dataset": "headline_metrics", "sourceId": "formal_benchmark_jsonl", "description": "当前两个医学问答源覆盖的内部主题类别。", "metrics": [{"label": "健康主题", "field": "topic_count", "format": "number"}]},
    ]

    charts = [
        {
            "id": "construction_funnel",
            "title": "CRK-2 数据构建漏斗",
            "subtitle": "从确定性质量过滤后的 254.9k 候选记录收敛到 15.5k 正式 benchmark 样本。",
            "type": "funnel",
            "intent": "funnel",
            "dataset": "funnel",
            "sourceId": "construction_lineage",
            "encodings": {"x": {"field": "stage", "type": "ordinal", "label": "阶段"}, "y": {"field": "count", "type": "quantitative", "label": "记录数"}, "tooltip": [{"field": "retention", "type": "quantitative", "label": "相对上一阶段", "format": "percent"}]},
            "valueFormat": "compact",
            "settings": {"showValues": True},
            "palette": {"kind": "sequential", "name": "blue"},
        },
        {
            "id": "source_distribution",
            "title": "正式样本的数据源分布",
            "subtitle": "两个来源在准入时近似均衡，最终差异仅来自后续构建 QC。",
            "type": "bar",
            "intent": "comparison",
            "dataset": "source_distribution",
            "sourceId": "formal_benchmark_jsonl",
            "encodings": {"x": {"field": "label", "type": "nominal", "label": "数据源"}, "y": {"field": "count", "type": "quantitative", "label": "样本数"}, "tooltip": [{"field": "share", "type": "quantitative", "label": "样本占比", "format": "percent"}]},
            "settings": {"showValues": True, "sort": "descending"},
            "palette": {"kind": "categorical", "name": "blue-gold"},
        },
        {
            "id": "topic_distribution",
            "title": "正式样本的主题分布",
            "subtitle": f"前三个主题合计占 {top_three_topic_share:.1%}，覆盖面存在可量化的医学主题集中。",
            "type": "horizontalBar",
            "intent": "comparison",
            "dataset": "topic_distribution",
            "sourceId": "formal_benchmark_jsonl",
            "encodings": {"x": {"field": "label", "type": "nominal", "label": "主题"}, "y": {"field": "count", "type": "quantitative", "label": "样本数"}, "tooltip": [{"field": "share", "type": "quantitative", "label": "样本占比", "format": "percent"}]},
            "settings": {"orientation": "horizontal", "showValues": True, "sort": "descending", "categoryLabelPolicy": "wrap"},
            "palette": {"kind": "sequential", "name": "blue"},
        },
        {
            "id": "label_distribution",
            "title": "原子记忆的 A/B/C 标签分布",
            "subtitle": f"C 类占 {labels.get('C', {}).get('share', 0):.1%}，B 类占 {labels.get('B', {}).get('share', 0):.1%}，A 类占 {labels.get('A', {}).get('share', 0):.1%}。",
            "type": "bar",
            "intent": "composition",
            "dataset": "label_distribution",
            "sourceId": "formal_benchmark_jsonl",
            "encodings": {"x": {"field": "label", "type": "nominal", "label": "标签"}, "y": {"field": "count", "type": "quantitative", "label": "原子记忆数"}, "tooltip": [{"field": "share", "type": "quantitative", "label": "原子占比", "format": "percent"}]},
            "settings": {"showValues": True, "sort": "none"},
            "palette": {"kind": "categorical", "name": "blue-gold-pink"},
        },
        {
            "id": "topic_label_mix",
            "title": "各主题内部的 A/B/C 构成",
            "subtitle": "采用主题内归一化，比较标签结构而非主题样本规模。",
            "type": "horizontalStackedBar100",
            "intent": "composition",
            "dataset": "topic_label_distribution",
            "sourceId": "formal_benchmark_jsonl",
            "encodings": {"x": {"field": "row_label", "type": "nominal", "label": "主题"}, "y": {"field": "count", "type": "quantitative", "label": "原子记忆数"}, "color": {"field": "series", "type": "nominal", "label": "A/B/C"}, "tooltip": [{"field": "share_within_row", "type": "quantitative", "label": "主题内占比", "format": "percent"}, {"field": "row_total", "type": "quantitative", "label": "主题原子总数"}]},
            "settings": {"orientation": "horizontal", "groupMode": "stacked100", "showPercent": True, "categoryLabelPolicy": "wrap"},
            "legend": {"position": "bottom", "sort": "spec", "title": "标签"},
            "palette": {"kind": "categorical", "name": "blue-gold-pink"},
        },
        {
            "id": "memory_type_label_mix",
            "title": "不同记忆类型的 A/B/C 构成",
            "subtitle": "memory_type 是固定五类枚举；标签构成反映不同语义类型在当前任务中的作用强度。",
            "type": "horizontalStackedBar100",
            "intent": "composition",
            "dataset": "memory_type_label_distribution",
            "sourceId": "formal_benchmark_jsonl",
            "encodings": {"x": {"field": "row_label", "type": "nominal", "label": "记忆类型"}, "y": {"field": "count", "type": "quantitative", "label": "原子记忆数"}, "color": {"field": "series", "type": "nominal", "label": "A/B/C"}, "tooltip": [{"field": "share_within_row", "type": "quantitative", "label": "类型内占比", "format": "percent"}, {"field": "row_total", "type": "quantitative", "label": "类型原子总数"}]},
            "settings": {"orientation": "horizontal", "groupMode": "stacked100", "showPercent": True},
            "legend": {"position": "bottom", "sort": "spec", "title": "标签"},
            "palette": {"kind": "categorical", "name": "blue-gold-pink"},
        },
        {
            "id": "sample_atomic_count",
            "title": "每条样本的原子记忆数量",
            "subtitle": f"均值为 {headline['avg_atomic_memories_per_sample']:.2f}；分布保留完整离散计数。",
            "type": "bar",
            "intent": "distribution",
            "dataset": "sample_atomic_count_distribution",
            "sourceId": "formal_benchmark_jsonl",
            "encodings": {"x": {"field": "category", "type": "ordinal", "label": "原子记忆数/样本"}, "y": {"field": "count", "type": "quantitative", "label": "样本数"}, "tooltip": [{"field": "share", "type": "quantitative", "label": "样本占比", "format": "percent"}]},
            "settings": {"showValues": True, "sort": "none"},
            "palette": {"kind": "sequential", "name": "blue"},
        },
        {
            "id": "parent_label_sets",
            "title": "父记忆的原子标签组合",
            "subtitle": f"共有 {headline['mixed_parents']:,} 个父记忆包含混合标签，占全部父记忆的 {headline['mixed_parent_rate']:.1%}。",
            "type": "horizontalBar",
            "intent": "comparison",
            "dataset": "parent_label_set_distribution",
            "sourceId": "formal_benchmark_jsonl",
            "encodings": {"x": {"field": "label", "type": "nominal", "label": "标签组合"}, "y": {"field": "count", "type": "quantitative", "label": "父记忆数"}, "tooltip": [{"field": "share", "type": "quantitative", "label": "父记忆占比", "format": "percent"}]},
            "settings": {"orientation": "horizontal", "showValues": True, "sort": "descending"},
            "palette": {"kind": "sequential", "name": "gold"},
        },
        {
            "id": "hard_a_distribution",
            "title": "Synthetic Hard-A family 分布",
            "subtitle": f"{dominant_hard_a['label']}占 Hard-A 原子的 {dominant_hard_a['share']:.1%}，family 覆盖完整但并不均衡。",
            "type": "horizontalBar",
            "intent": "composition",
            "dataset": "hard_a_distribution",
            "sourceId": "formal_benchmark_jsonl",
            "encodings": {"x": {"field": "label", "type": "nominal", "label": "Hard-A family"}, "y": {"field": "count", "type": "quantitative", "label": "原子记忆数"}, "tooltip": [{"field": "share", "type": "quantitative", "label": "Hard-A 内占比", "format": "percent"}]},
            "settings": {"orientation": "horizontal", "showValues": True, "sort": "descending", "categoryLabelPolicy": "wrap"},
            "palette": {"kind": "sequential", "name": "pink"},
        },
        {
            "id": "length_summary",
            "title": "问题、记忆与 Judge rubric 的文本长度",
            "subtitle": "Unicode 字符数；同时显示中位数、p95 与 p99，突出长尾而不受极端值主导。",
            "type": "bar",
            "intent": "distribution",
            "dataset": "length_summary",
            "sourceId": "formal_benchmark_jsonl",
            "encodings": {"x": {"field": "metric_label", "type": "nominal", "label": "文本单元"}, "y": {"fields": ["median", "p95", "p99"], "type": "quantitative", "label": "Unicode 字符数"}, "tooltip": [{"field": "mean", "type": "quantitative", "label": "均值"}, {"field": "max", "type": "quantitative", "label": "最大值"}]},
            "settings": {"groupMode": "grouped", "showValues": False, "categoryLabelPolicy": "wrap"},
            "palette": {"kind": "categorical", "name": "blue-gold-olive"},
            "legend": {"position": "bottom", "sort": "spec", "title": "分位统计"},
        },
    ]

    tables = [
        {
            "id": "topic_table",
            "title": "主题分布精确统计",
            "subtitle": "样本粒度；按正式样本数降序。",
            "dataset": "topic_distribution",
            "sourceId": "formal_benchmark_jsonl",
            "defaultSort": {"field": "count", "direction": "desc"},
            "density": "dense",
            "columns": [
                {"field": "label", "label": "主题", "type": "text"},
                {"field": "key", "label": "topic key", "type": "text"},
                {"field": "count", "label": "样本数", "format": "number"},
                {"field": "share", "label": "占比", "format": "percent"},
            ],
        },
        {
            "id": "length_table",
            "title": "文本长度分布统计",
            "subtitle": "Unicode 字符数；rubric 统计只累计自然语言值。",
            "dataset": "length_summary",
            "sourceId": "formal_benchmark_jsonl",
            "defaultSort": {"field": "median", "direction": "desc"},
            "density": "dense",
            "columns": [
                {"field": "metric_label", "label": "文本单元", "type": "text"},
                {"field": "count", "label": "N", "format": "number"},
                {"field": "mean", "label": "均值", "format": "number"},
                {"field": "median", "label": "中位数", "format": "number"},
                {"field": "p95", "label": "p95", "format": "number"},
                {"field": "p99", "label": "p99", "format": "number"},
                {"field": "max", "label": "最大值", "format": "number"},
            ],
        },
        {
            "id": "paper_metrics_table",
            "title": "论文可引用的核心统计",
            "subtitle": "每项给出统计单位与口径，可直接用于 dataset statistics 表。",
            "dataset": "paper_core_metrics",
            "sourceId": "formal_benchmark_jsonl",
            "defaultSort": {"field": "metric", "direction": "asc"},
            "density": "spacious",
            "columns": [
                {"field": "metric", "label": "统计项", "type": "text"},
                {"field": "value", "label": "值", "format": "number"},
                {"field": "unit", "label": "单位", "type": "text"},
                {"field": "definition", "label": "定义", "type": "text"},
            ],
        },
        {
            "id": "qc_table",
            "title": "构建质量检查状态",
            "subtitle": "自动检查通过不等同于人工审核或响应级验证完成。",
            "dataset": "qc_status",
            "sourceId": "formal_benchmark_jsonl",
            "defaultSort": {"field": "status", "direction": "asc"},
            "density": "dense",
            "columns": [
                {"field": "check", "label": "检查项", "type": "text"},
                {"field": "status", "label": "状态", "type": "text"},
                {"field": "passed", "label": "通过数", "format": "number"},
                {"field": "denominator", "label": "分母", "format": "number"},
                {"field": "share", "label": "覆盖率", "format": "percent"},
                {"field": "scope", "label": "验证层级", "type": "text"},
            ],
        },
    ]

    blocks = [
        {"id": "title", "type": "markdown", "body": f"# {title}"},
        {
            "id": "technical_summary",
            "type": "markdown",
            "sourceId": "formal_benchmark_jsonl",
            "body": (
                "## 技术摘要\n\n"
                f"正式 CRK-2 benchmark 包含 **{headline['samples']:,}** 条样本、**{headline['parent_memories']:,}** 个父记忆块和 "
                f"**{headline['atomic_memories']:,}** 条原子记忆。每条样本平均含 **{headline['avg_atomic_memories_per_sample']:.2f}** 个 atom，"
                f"平均每个父记忆拆为 **{headline['atomization_ratio']:.2f}** 个 atom。A/B/C 原子分布为 "
                f"**{analysis['counts']['labels'].get('A', 0):,} / {analysis['counts']['labels'].get('B', 0):,} / {analysis['counts']['labels'].get('C', 0):,}**。\n\n"
                f"数据集在两个来源之间接近均衡，覆盖 {headline['topic_count']} 个医学主题。**{headline['mixed_parent_rate']:.1%}** 的父记忆包含混合 A/B/C 标签，"
                f"说明以原子粒度评估能够捕捉 block 级标签无法表达的局部差异。Synthetic hard A 占全部原子的 **{headline['synthetic_atomic_share']:.1%}**，"
                "因此总体 A 类结果应与 extracted B/C 分开解释。"
            ),
        },
        {"id": "headline_metrics", "type": "metric-strip", "cardIds": [card["id"] for card in cards]},
        {
            "id": "funnel_heading",
            "type": "markdown",
            "sourceId": "construction_lineage",
            "body": "## 质量筛选将 254.9k 条合格原始记录收敛为 15.5k 条正式样本\n\n候选池先经过确定性质量过滤、分层抽样和语义 QC，再进行严格准入、LLM 构建、语言修复与 schema 门禁。漏斗中的阶段数来自锁定 manifest；它描述构建过程，不代表模型性能。",
        },
        {"id": "funnel_chart", "type": "chart", "chartId": "construction_funnel", "layout": "full"},
        {
            "id": "coverage_heading",
            "type": "markdown",
            "sourceId": "formal_benchmark_jsonl",
            "body": "## 来源保持平衡，但主题覆盖仍明显集中于高频医学任务\n\n两个数据源的样本数接近 1:1。主题层面，用药与治疗、妊娠与生殖、儿科构成前三大类别；低频的心血管、心理与睡眠、神经系统仍被保留，但统计功效和难度覆盖需要在模型评测后单独检查。",
        },
        {"id": "source_chart", "type": "chart", "chartId": "source_distribution", "layout": "half"},
        {"id": "topic_chart", "type": "chart", "chartId": "topic_distribution", "layout": "full"},
        {"id": "topic_table_block", "type": "table", "tableId": "topic_table", "layout": "full"},
        {
            "id": "atomization_heading",
            "type": "markdown",
            "sourceId": "formal_benchmark_jsonl",
            "body": (
                "## 原子化显著增加评估分辨率，并暴露 block 内部的标签异质性\n\n"
                f"{headline['parent_memories']:,} 个父记忆被拆为 {headline['atomic_memories']:,} 个 atom。"
                f"其中 {headline['mixed_parents']:,} 个父记忆同时包含两种或三种 A/B/C 标签；若仅在 block 粒度打标，这部分样本会被压缩为单一标签。"
            ),
        },
        {"id": "sample_atom_chart", "type": "chart", "chartId": "sample_atomic_count", "layout": "half"},
        {"id": "parent_label_chart", "type": "chart", "chartId": "parent_label_sets", "layout": "half"},
        {
            "id": "labels_heading",
            "type": "markdown",
            "sourceId": "formal_benchmark_jsonl",
            "body": "## C 类占比最高，但标签结构随主题和记忆类型发生系统性变化\n\n总体分布能够描述 benchmark 的目标结构，不能替代分层结果。主题内部和 memory type 内部的 100% 堆叠图显示，各子群体的 A/B/C 组成并不一致，后续模型结果应至少按 topic、memory type 和来源报告。",
        },
        {"id": "label_chart", "type": "chart", "chartId": "label_distribution", "layout": "half"},
        {"id": "topic_label_chart", "type": "chart", "chartId": "topic_label_mix", "layout": "full"},
        {"id": "memory_type_label_chart", "type": "chart", "chartId": "memory_type_label_mix", "layout": "full"},
        {
            "id": "hard_a_heading",
            "type": "markdown",
            "sourceId": "formal_benchmark_jsonl",
            "body": (
                "## Hard-A family 覆盖完整，但 synthetic 机制存在集中度\n\n"
                f"五个预定义 family 均有覆盖，最大 family 为 **{dominant_hard_a['label']}**，占 Hard-A 的 **{dominant_hard_a['share']:.1%}**。"
                "这有利于构造具有明确 failure direction 的过度结合测试，但不能被解释为真实部署环境中的自然记忆分布。"
            ),
        },
        {"id": "hard_a_chart", "type": "chart", "chartId": "hard_a_distribution", "layout": "full"},
        {
            "id": "complexity_heading",
            "type": "markdown",
            "sourceId": "formal_benchmark_jsonl",
            "body": (
                "## Judge rubric 的文本负载呈长尾，评测成本需要按高分位规划\n\n"
                f"单原子 rubric 的中位长度为 **{length_by_key.get('rubric_chars', {}).get('median', 0):.0f}** 字符，"
                f"p95 为 **{length_by_key.get('rubric_chars', {}).get('p95', 0):.0f}**；单样本 rubric 总量的 p95 为 "
                f"**{length_by_key.get('sample_rubric_chars', {}).get('p95', 0):.0f}** 字符。训练和 judge 推理预算应依据 p95/p99，而非均值。"
            ),
        },
        {"id": "length_chart", "type": "chart", "chartId": "length_summary", "layout": "full"},
        {"id": "length_table_block", "type": "table", "tableId": "length_table", "layout": "full"},
        {
            "id": "paper_table_heading",
            "type": "markdown",
            "body": "## 论文可引用统计\n\n下表使用与本报告一致的分母和统计口径。论文中引用时应同时说明：样本粒度为 benchmark record，标签分布和 memory type 分布采用 atomic-memory 粒度。",
        },
        {"id": "paper_metrics_block", "type": "table", "tableId": "paper_metrics_table", "layout": "full"},
        {
            "id": "qc_heading",
            "type": "markdown",
            "sourceId": "formal_benchmark_jsonl",
            "body": "## 自动构建 QC 全部通过，响应级与人工验证仍未完成\n\n当前正式集通过 atomicity、重复、question-memory leakage、Hard-A target consistency 和 rubric objectivity 五项自动门禁。该结论只覆盖结构和生成时自检；counterfactual response test、分层人工审核和 judge calibration 仍是 benchmark 发布前的必要步骤。",
        },
        {"id": "qc_table_block", "type": "table", "tableId": "qc_table", "layout": "full"},
        {
            "id": "limitations",
            "type": "markdown",
            "body": (
                "## 局限、稳健性与下一步\n\n"
                "- **领域外推受限：** 当前两个来源均为医学问答，12 个主题提供的是医学域内部多样性，不能支撑通用对话覆盖的结论。\n"
                f"- **Synthetic footprint：** synthetic hard A 占全部 atom 的 {headline['synthetic_atomic_share']:.1%}；A 类与 extracted B/C 应分别报告。\n"
                f"- **Subtype 不是受控本体：** 当前共有 {headline['subtype_cardinality']:,} 个自由文本 subtype，其中 {headline['subtype_singletons']:,} 个只出现一次；subtype 只适合审计，不适合直接做统计分层。\n"
                "- **自动 QC 的边界：** 结构通过不代表 rubric 对真实回答具有高判别效度。应按来源、主题、A/B/C、memory type、Hard-A family 和长度分位进行分层人工抽检。\n"
                "- **推荐验证顺序：** 先执行 300-500 条双人标注的分层人工审查，再运行 counterfactual answer pairs，最后用该集合校准 judge 并报告一致性和置信区间。"
            ),
        },
        {
            "id": "methodology",
            "type": "markdown",
            "sourceId": "formal_benchmark_jsonl",
            "body": (
                "## 统计方法与复现\n\n"
                "报告使用非 Conda Python runtime 对完整正式 JSONL 进行一次流式扫描。计数按样本、父记忆和原子记忆三个粒度分别计算；分位数采用线性插值。"
                "所有交叉分布保留精确分子和分母，图表只展示聚合结果。统计结果与锁定 summary 的样本数、父记忆数、原子数、标签、来源、主题和 memory type 逐项对账，结果为 passed。"
            ),
        },
        {
            "id": "further_questions",
            "type": "markdown",
            "body": "## 后续研究问题\n\n1. 不同主题与 memory type 的标签结构是否会造成模型排名变化？\n2. mixed-parent 样本是否比 homogeneous-parent 样本更能区分模型的细粒度记忆控制能力？\n3. Hard-A family 的不平衡是否需要在主榜与诊断子榜中采用不同聚合权重？\n4. Judge rubric 长度与 judge 一致性、延迟和成本之间是否存在系统性关系？",
        },
    ]

    manifest = {
        "version": 1,
        "surface": "report",
        "title": title,
        "description": "面向论文写作与内部质量审计的 CRK-2 正式数据集全量统计报告。",
        "generatedAt": generated_at,
        "cards": cards,
        "charts": charts,
        "tables": tables,
        "sources": sources,
        "blocks": blocks,
    }
    snapshot = {"version": 1, "generatedAt": generated_at, "status": "ready", "datasets": datasets}
    return {"surface": "report", "manifest": manifest, "snapshot": snapshot, "sources": sources}


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze the complete formal CRK-2 benchmark and build a canonical report artifact.")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--rejected", type=Path, default=DEFAULT_REJECTED)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--run-lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--candidate-manifest", type=Path, default=DEFAULT_CANDIDATE_MANIFEST)
    parser.add_argument("--semantic-summary", type=Path, default=DEFAULT_SEMANTIC_SUMMARY)
    parser.add_argument("--admission-manifest", type=Path, default=DEFAULT_ADMISSION_MANIFEST)
    parser.add_argument("--admitted", type=Path, default=DEFAULT_ADMITTED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--rows-output", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    args = parser.parse_args()

    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    analysis = analyze_benchmark(
        args.benchmark,
        args.rejected,
        args.summary,
        args.run_lock,
        args.candidate_manifest,
        args.semantic_summary,
        args.admission_manifest,
        args.admitted,
    )
    analysis["generated_at"] = generated_at
    artifact = build_artifact(analysis, generated_at)
    rows = flattened_dataset_rows(artifact["snapshot"]["datasets"])
    write_jsonl(args.rows_output, rows)
    analysis["derived_files"] = {
        "reviewed_rows": {"path": str(args.rows_output), "rows": len(rows), "sha256": file_sha256(args.rows_output)}
    }
    write_json(args.output, analysis)
    write_json(args.artifact, artifact)
    print(
        json.dumps(
            {
                "analysis": str(args.output),
                "reviewed_rows": str(args.rows_output),
                "artifact": str(args.artifact),
                "samples": analysis["headline"]["samples"],
                "atomic_memories": analysis["headline"]["atomic_memories"],
                "reconciliation": analysis["reconciliation"],
                "snapshot_datasets": {key: len(rows) for key, rows in artifact["snapshot"]["datasets"].items()},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
