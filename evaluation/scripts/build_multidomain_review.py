#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from evaluation.common import iter_jsonl, sha256_file, stable_hash, write_json, write_jsonl
from evaluation.scripts.build_calibration_review import attach_translations
from evaluation.scripts.prepare_judge_requests import load_answers


ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "evaluation" / "releases" / "memcalib-ordered-v2.1-multidomain-pilot-200"
RUN = ROOT / "evaluation" / "runs" / "memcalib-ordered-v2.1-multidomain-pilot-200"
DEFAULT_CONFIG = ROOT / "evaluation" / "configs" / "memcalib-ordered-v2.1-multidomain-pilot-200.json"
DEFAULT_HIDDEN = RELEASE / "hidden-evaluation.jsonl"
DEFAULT_ANSWERS = RUN / "answers"
DEFAULT_PRIMARY = RUN / "judgments" / "primary.valid.jsonl"
DEFAULT_SECONDARY = RUN / "judgments" / "secondary.valid.jsonl"
DEFAULT_JSONL = RELEASE / "multidomain-human-review-30.jsonl"
DEFAULT_HTML = RELEASE / "multidomain-human-review-30.html"
DEFAULT_MANIFEST = RELEASE / "multidomain-human-review-30.manifest.json"
DEFAULT_TRANSLATIONS = RELEASE / "multidomain-human-review-30.translations-zh.jsonl"
DEFAULT_TRANSLATION_SUMMARY = RELEASE / "multidomain-human-review-30.translations-zh.summary.json"
DEFAULT_TEMPLATE = ROOT / "evaluation" / "templates" / "calibration-review-bilingual.html"

LEVEL = {"A": 0, "B": 1, "C": 2}
CATEGORY_LABELS = {
    "representative_random": "代表性随机抽样",
    "judge_disagreement": "双 Judge 分歧",
    "opb": "过度个性化（OPB）",
    "upb": "欠个性化（UPB）",
    "paired_contrast": "Full/No-memory 配对对照",
}
CATEGORY_ORDER = {
    "representative_random": 0,
    "judge_disagreement": 1,
    "opb": 2,
    "upb": 3,
    "paired_contrast": 4,
}
QUOTAS_PER_DOMAIN = {
    "representative_random": 5,
    "judge_disagreement": 3,
    "opb": 3,
    "upb": 2,
    "paired_contrast": 2,
}


def judgment_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["answer_request_id"]): row for row in rows}


def atom_map(judgment: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["atom_id"]): row for row in judgment.get("atom_judgments") or []}


def direction_details(judgment: dict[str, Any], direction: str) -> tuple[float, list[str]]:
    score = 0.0
    details: list[str] = []
    for atom in judgment.get("atom_judgments") or []:
        gold = str(atom.get("u_star") or "")
        predicted = str(atom.get("predicted_usage_level") or "")
        if gold not in LEVEL or predicted not in LEVEL:
            continue
        delta = LEVEL[predicted] - LEVEL[gold]
        if (direction == "over" and delta > 0) or (direction == "under" and delta < 0):
            magnitude = abs(delta)
            score += magnitude
            details.append(f"{atom['atom_id']}:{gold}->{predicted}")
    return score, details


def disagreement_details(
    primary: dict[str, Any], secondary: dict[str, Any]
) -> tuple[float, list[str]]:
    left = atom_map(primary)
    right = atom_map(secondary)
    score = 0.0
    details: list[str] = []
    for atom_id in sorted(set(left).intersection(right)):
        first = str(left[atom_id].get("predicted_usage_level") or "")
        second = str(right[atom_id].get("predicted_usage_level") or "")
        if first in LEVEL and second in LEVEL and first != second:
            score += abs(LEVEL[first] - LEVEL[second])
            details.append(f"{atom_id}:primary {first}/secondary {second}")
    return score, details


def paired_details(
    full: dict[str, Any], no_memory: dict[str, Any]
) -> tuple[float, list[str]]:
    full_atoms = atom_map(full)
    no_atoms = atom_map(no_memory)
    score = 0.0
    details: list[str] = []
    for atom_id in sorted(set(full_atoms).intersection(no_atoms)):
        full_level = str(full_atoms[atom_id].get("predicted_usage_level") or "")
        no_level = str(no_atoms[atom_id].get("predicted_usage_level") or "")
        if full_level in LEVEL and no_level in LEVEL and full_level != no_level:
            score += abs(LEVEL[full_level] - LEVEL[no_level])
            details.append(f"{atom_id}:no {no_level}->full {full_level}")
    return score, details


def candidate(
    answer: dict[str, Any],
    sample: dict[str, Any],
    category: str,
    score: float,
    details: list[str],
    *,
    counterpart_answer_id: str | None = None,
) -> dict[str, Any]:
    params = answer.get("user_defined_params") or {}
    return {
        "answer_request_id": str(answer["request_id"]),
        "sample_id": str(params["sample_id"]),
        "domain": str(sample["domain"]),
        "model_key": str(params["model_key"]),
        "condition": str(params["condition"]),
        "selection_category": category,
        "selection_label": CATEGORY_LABELS[category],
        "selection_score": score,
        "selection_reason": "; ".join(details) if details else "deterministic stratified random sample",
        "counterpart_answer_request_id": counterpart_answer_id,
    }


def _choose_singletons(
    pool: list[dict[str, Any]],
    count: int,
    *,
    seed: int,
    selected_answer_ids: set[str],
    selected_sample_ids: set[str],
    model_counts: Counter[str],
    condition_counts: Counter[str],
) -> list[dict[str, Any]]:
    chosen: list[dict[str, Any]] = []
    remaining = list(pool)
    while len(chosen) < count:
        eligible = [
            row
            for row in remaining
            if row["answer_request_id"] not in selected_answer_ids
            and row["sample_id"] not in selected_sample_ids
        ]
        if not eligible:
            raise ValueError(f"insufficient unique candidates: selected {len(chosen)} of {count}")
        row = min(
            eligible,
            key=lambda value: (
                model_counts[value["model_key"]],
                condition_counts[value["condition"]],
                -float(value["selection_score"]),
                stable_hash(seed, f'{value["selection_category"]}|{value["answer_request_id"]}'),
            ),
        )
        chosen.append(row)
        selected_answer_ids.add(row["answer_request_id"])
        selected_sample_ids.add(row["sample_id"])
        model_counts[row["model_key"]] += 1
        condition_counts[row["condition"]] += 1
        remaining.remove(row)
    return chosen


def select_review_answers(
    samples: list[dict[str, Any]],
    answers: list[dict[str, Any]],
    primary: list[dict[str, Any]],
    secondary: list[dict[str, Any]],
    *,
    seed: int,
    max_response_chars: int = 12000,
) -> list[dict[str, Any]]:
    samples_by_id = {str(row["id"]): row for row in samples}
    primary_by_id = judgment_map(primary)
    secondary_by_id = judgment_map(secondary)
    eligible_answers = {
        str(answer["request_id"]): answer
        for answer in answers
        if str(answer["request_id"]) in primary_by_id
        and str(answer["request_id"]) in secondary_by_id
        and len(str(answer.get("response") or "")) <= max_response_chars
    }
    pools: dict[str, dict[str, list[dict[str, Any]]]] = {
        domain: defaultdict(list) for domain in ("general", "coding")
    }
    for answer_id, answer in eligible_answers.items():
        params = answer.get("user_defined_params") or {}
        sample = samples_by_id[str(params["sample_id"])]
        domain = str(sample["domain"])
        if domain not in pools:
            continue
        pools[domain]["representative_random"].append(
            candidate(answer, sample, "representative_random", 0.0, [])
        )
        disagreement_score, disagreement = disagreement_details(
            primary_by_id[answer_id], secondary_by_id[answer_id]
        )
        if disagreement_score:
            pools[domain]["judge_disagreement"].append(
                candidate(answer, sample, "judge_disagreement", disagreement_score, disagreement)
            )
        if str(params["condition"]) == "full_memory":
            opb_score, opb = direction_details(primary_by_id[answer_id], "over")
            if opb_score:
                pools[domain]["opb"].append(candidate(answer, sample, "opb", opb_score, opb))
            upb_score, upb = direction_details(primary_by_id[answer_id], "under")
            if upb_score:
                pools[domain]["upb"].append(candidate(answer, sample, "upb", upb_score, upb))

    by_pair: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for answer_id, answer in eligible_answers.items():
        params = answer.get("user_defined_params") or {}
        by_pair[(str(params["sample_id"]), str(params["model_key"]))][str(params["condition"])] = answer_id
    paired_pools: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (sample_id, model_key), conditions in by_pair.items():
        if set(conditions) != {"full_memory", "no_memory"}:
            continue
        full_id = conditions["full_memory"]
        no_id = conditions["no_memory"]
        score, details = paired_details(primary_by_id[full_id], primary_by_id[no_id])
        if not score:
            continue
        sample = samples_by_id[sample_id]
        paired_pools[str(sample["domain"])].append(
            {
                "sample_id": sample_id,
                "model_key": model_key,
                "score": score,
                "details": details,
                "full_id": full_id,
                "no_id": no_id,
            }
        )

    selected: list[dict[str, Any]] = []
    for domain in ("general", "coding"):
        selected_answer_ids: set[str] = set()
        selected_sample_ids: set[str] = set()
        model_counts: Counter[str] = Counter()
        condition_counts: Counter[str] = Counter()
        pairs = paired_pools[domain]
        if not pairs:
            raise ValueError(f"no paired contrast candidates for {domain}")
        pair = min(
            pairs,
            key=lambda value: (
                -float(value["score"]),
                stable_hash(seed, f'{domain}|paired_contrast|{value["sample_id"]}|{value["model_key"]}'),
            ),
        )
        sample = samples_by_id[pair["sample_id"]]
        full_answer = eligible_answers[pair["full_id"]]
        no_answer = eligible_answers[pair["no_id"]]
        pair_rows = [
            candidate(
                full_answer,
                sample,
                "paired_contrast",
                pair["score"],
                pair["details"],
                counterpart_answer_id=pair["no_id"],
            ),
            candidate(
                no_answer,
                sample,
                "paired_contrast",
                pair["score"],
                pair["details"],
                counterpart_answer_id=pair["full_id"],
            ),
        ]
        selected.extend(pair_rows)
        selected_answer_ids.update(row["answer_request_id"] for row in pair_rows)
        selected_sample_ids.add(pair["sample_id"])
        model_counts[pair["model_key"]] += 2
        condition_counts.update({"full_memory": 1, "no_memory": 1})

        for category in ("representative_random", "judge_disagreement", "opb", "upb"):
            chosen = _choose_singletons(
                pools[domain][category],
                QUOTAS_PER_DOMAIN[category],
                seed=seed,
                selected_answer_ids=selected_answer_ids,
                selected_sample_ids=selected_sample_ids,
                model_counts=model_counts,
                condition_counts=condition_counts,
            )
            selected.extend(chosen)
        if len(selected_answer_ids) != sum(QUOTAS_PER_DOMAIN.values()):
            raise ValueError(f"selection count mismatch for {domain}: {len(selected_answer_ids)}")

    selected.sort(
        key=lambda row: (
            0 if row["domain"] == "general" else 1,
            CATEGORY_ORDER[row["selection_category"]],
            row["sample_id"],
            0 if row["condition"] == "full_memory" else 1,
        )
    )
    answer_ids = [row["answer_request_id"] for row in selected]
    if len(selected) != 30 or len(answer_ids) != len(set(answer_ids)):
        raise ValueError("review selection must contain 30 unique answer IDs")
    return selected


def build_review_records(
    selected: list[dict[str, Any]],
    samples: list[dict[str, Any]],
    answers: list[dict[str, Any]],
    primary: list[dict[str, Any]],
    secondary: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    samples_by_id = {str(row["id"]): row for row in samples}
    answers_by_id = {str(row["request_id"]): row for row in answers}
    primary_by_id = judgment_map(primary)
    secondary_by_id = judgment_map(secondary)
    records: list[dict[str, Any]] = []
    for selection in selected:
        answer_id = selection["answer_request_id"]
        answer = answers_by_id[answer_id]
        params = answer.get("user_defined_params") or {}
        sample = samples_by_id[str(params["sample_id"])]
        records.append(
            {
                **selection,
                "review_stratum": selection["selection_label"],
                "panel": sample["domain"],
                "answer_model": params.get("expected_model"),
                "source_dataset": sample.get("source_dataset"),
                "source_topic": sample.get("source_topic"),
                "question": sample["question"],
                "memory_blocks": [
                    {
                        "parent_memory_id": block["parent_memory_id"],
                        "memory_text": block["memory_text"],
                    }
                    for block in sample.get("memory_blocks") or []
                ],
                "model_response": answer["response"],
                "atomic_memories": [
                    {
                        "atom_id": atom["atom_id"],
                        "parent_memory_id": atom["parent_memory_id"],
                        "text": atom["text"],
                        "evidence": atom.get("evidence"),
                        "label_reason": atom.get("label_reason"),
                        "memory_type": atom.get("memory_type"),
                        "subtype": atom.get("subtype"),
                        "source": atom.get("source"),
                        "derivation": atom.get("derivation"),
                        "u_star": atom["u_star"],
                        "usage_rubric": atom["usage_rubric"],
                    }
                    for atom in sample.get("memories") or []
                ],
                "primary_judgment": primary_by_id[answer_id],
                "secondary_judgment": secondary_by_id[answer_id],
            }
        )
    return records


def render_review_html(records: list[dict[str, Any]], template_path: Path) -> str:
    payload = json.dumps(records, ensure_ascii=False).replace("</", "<\\/")
    template = template_path.read_text(encoding="utf-8")
    replacements = {
        "<title>MemCalib Judge 人工校准</title>": "<title>MemCalib 多领域有效性审查</title>",
        "<h1>Judge 人工校准</h1>": "<h1>多领域有效性审查</h1>",
        "30 条回答，每个原子独立判断实际使用强度。英文原文是正式依据，中文译文仅辅助阅读。": "30 条分层回答，核验多领域 Gold、rubric 与双 Judge。英文原文是正式依据，中文译文仅辅助阅读。",
        "const storageKey = 'memcalib-human-review-v2-bilingual';": "const storageKey = 'memcalib-multidomain-human-review-v1';",
        "[record.review_stratum, record.panel, record.model_key, conditionLabel]": "[record.selection_label || record.review_stratum, record.domain || record.panel, record.model_key, conditionLabel]",
        "record.review_stratum === 'diagnostic'": "record.selection_category !== 'representative_random'",
        "const conditionNote = record.condition === 'no_memory'": "const selectionNote = `<div class=\"condition-note\">抽样理由：${esc(record.selection_reason || record.selection_label || '')}</div>`;\n      const conditionNote = record.condition === 'no_memory'",
        "document.getElementById('content').innerHTML = `<section": "document.getElementById('content').innerHTML = `${selectionNote}<section",
        "schema_version: 'memcalib-calibration-human-annotation-v2'": "schema_version: 'memcalib-multidomain-human-annotation-v1'",
        "memcalib-calibration-human-annotations.json": "memcalib-multidomain-human-annotations.json",
    }
    for old, new in replacements.items():
        if template.count(old) != 1:
            raise ValueError(f"template customization anchor must occur exactly once: {old}")
        template = template.replace(old, new)
    placeholder = "__MEMCALIB_RECORDS_JSON__"
    if template.count(placeholder) != 1:
        raise ValueError(f"template must contain exactly one {placeholder} placeholder")
    return template.replace(placeholder, payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the 30-answer multi-domain validity review pack.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--hidden", type=Path, default=DEFAULT_HIDDEN)
    parser.add_argument("--answers", type=Path, default=DEFAULT_ANSWERS)
    parser.add_argument("--primary", type=Path, default=DEFAULT_PRIMARY)
    parser.add_argument("--secondary", type=Path, default=DEFAULT_SECONDARY)
    parser.add_argument("--jsonl", type=Path, default=DEFAULT_JSONL)
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--translations", type=Path, default=DEFAULT_TRANSLATIONS)
    parser.add_argument("--translation-summary", type=Path, default=DEFAULT_TRANSLATION_SUMMARY)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--max-response-chars", type=int, default=12000)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    samples = list(iter_jsonl(args.hidden))
    answers = load_answers(args.answers, config)
    primary = list(iter_jsonl(args.primary))
    secondary = list(iter_jsonl(args.secondary))
    selected = select_review_answers(
        samples,
        answers,
        primary,
        secondary,
        seed=int(config["seed"]) + 17,
        max_response_chars=args.max_response_chars,
    )
    records = build_review_records(selected, samples, answers, primary, secondary)
    write_jsonl(args.jsonl, records)
    localized_records = attach_translations(records, args.translations)
    args.html.parent.mkdir(parents=True, exist_ok=True)
    args.html.write_text(render_review_html(records, args.template), encoding="utf-8")
    category_counts = Counter(row["selection_category"] for row in selected)
    domain_counts = Counter(row["domain"] for row in selected)
    model_counts = Counter(row["model_key"] for row in selected)
    condition_counts = Counter(row["condition"] for row in selected)
    gold_atom_counts = Counter(
        str(atom["u_star"]) for record in records for atom in record.get("atomic_memories") or []
    )
    manifest = {
        "schema_version": "memcalib-multidomain-human-review-v1",
        "purpose": "human_validation_of_gold_rubric_and_ordered_usage_judges",
        "records": len(records),
        "unique_samples": len({row["sample_id"] for row in selected}),
        "selection_seed": int(config["seed"]) + 17,
        "max_response_chars": args.max_response_chars,
        "domains": dict(sorted(domain_counts.items())),
        "categories": dict(sorted(category_counts.items())),
        "models": dict(sorted(model_counts.items())),
        "conditions": dict(sorted(condition_counts.items())),
        "gold_atoms": dict(sorted(gold_atom_counts.items())),
        "mixed_label_records": sum(
            len({str(atom["u_star"]) for atom in record.get("atomic_memories") or []}) > 1
            for record in records
        ),
        "all_have_secondary_judge": all(row.get("secondary_judgment") for row in records),
        "localized_records": localized_records,
        "inputs": {
            str(path.relative_to(ROOT)): {"sha256": sha256_file(path)}
            for path in (args.config, args.hidden, args.primary, args.secondary, args.template)
        },
        "artifacts": {
            args.jsonl.name: {"sha256": sha256_file(args.jsonl)},
            args.html.name: {"sha256": sha256_file(args.html)},
        },
    }
    if args.translations.exists():
        manifest["artifacts"][args.translations.name] = {"sha256": sha256_file(args.translations)}
    if args.translation_summary.exists():
        manifest["artifacts"][args.translation_summary.name] = {
            "sha256": sha256_file(args.translation_summary)
        }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
