#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from evaluation.common import display_path, iter_jsonl, sha256_file, stable_hash, write_json, write_jsonl


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "evaluation" / "configs" / "memcalib-v0.1-500.json"
DEFAULT_HIDDEN = ROOT / "evaluation" / "releases" / "memcalib-v0.1-500" / "hidden-evaluation.jsonl"
DEFAULT_ANSWERS = ROOT / "evaluation" / "runs" / "memcalib-v0.1-500" / "answers"
DEFAULT_PROMPT = ROOT / "evaluation" / "prompts" / "judge-system.txt"
DEFAULT_OUTPUT = ROOT / "evaluation" / "runs" / "memcalib-v0.1-500" / "requests" / "judges"
DEFAULT_MANIFEST = ROOT / "evaluation" / "releases" / "memcalib-v0.1-500" / "judge-request.manifest.json"
CONDITIONS = ("full_memory", "no_memory")


def atom_count_bucket(count: int) -> str:
    if count <= 3:
        return "2-3"
    if count <= 5:
        return "4-5"
    if count <= 7:
        return "6-7"
    return "8+"


def _proportional_quotas(
    counts: Counter[tuple[str, ...]], total: int
) -> dict[tuple[str, ...], int]:
    population = sum(counts.values())
    if total <= 0 or total > population:
        raise ValueError(f"invalid proportional sample size: {total} for population {population}")
    exact = {key: total * count / population for key, count in counts.items()}
    quotas = {key: math.floor(value) for key, value in exact.items()}
    remaining = total - sum(quotas.values())
    order = sorted(counts, key=lambda key: (-(exact[key] - quotas[key]), key))
    for key in order[:remaining]:
        quotas[key] += 1
    return quotas


def select_formal_secondary_answer_ids(
    answers: list[dict[str, Any]],
    samples_by_id: dict[str, dict[str, Any]],
    *,
    seed: int,
    per_model: int | None = None,
    per_model_condition: int | None = None,
) -> set[str]:
    if (per_model is None) == (per_model_condition is None):
        raise ValueError("set exactly one of per_model or per_model_condition")
    by_group_cell: dict[
        tuple[str, str | None], dict[tuple[str, str, str, str], list[dict[str, Any]]]
    ] = defaultdict(
        lambda: defaultdict(list)
    )
    for answer in answers:
        params = answer.get("user_defined_params") or {}
        sample = samples_by_id[str(params["sample_id"])]
        cell = (
            str(sample["source_dataset"]),
            str(sample["source_topic"]),
            str((sample.get("composite_block_revision") or {}).get("difficulty_level") or "unassigned"),
            atom_count_bucket(len(sample.get("memories") or [])),
        )
        condition = str(params["condition"]) if per_model_condition is not None else None
        by_group_cell[(str(params["model_key"]), condition)][cell].append(answer)
    selected: set[str] = set()
    target = int(per_model_condition if per_model_condition is not None else per_model)
    for (model_key, condition), cells in sorted(by_group_cell.items()):
        counts = Counter({cell: len(rows) for cell, rows in cells.items()})
        quotas = _proportional_quotas(counts, target)
        for cell, rows in sorted(cells.items()):
            ordered = sorted(rows, key=lambda row: stable_hash(seed, str(row["request_id"])))
            selected.update(str(row["request_id"]) for row in ordered[: quotas[cell]])
        group_selected = sum(
            str(answer["request_id"]) in selected
            for model_rows in cells.values()
            for answer in model_rows
        )
        if group_selected != target:
            group_name = f"{model_key}:{condition}" if condition is not None else model_key
            raise ValueError(f"formal secondary selection mismatch for {group_name}: {group_selected} != {target}")
    return selected


def build_judge_request(
    sample: dict[str, Any],
    answer: dict[str, Any],
    judge_role: str,
    judge_model: str,
    system_prompt: str,
    judge_protocol: str = "verdict-v1",
) -> dict[str, Any]:
    answer_params = answer.get("user_defined_params") or {}
    atoms = [
        {
            "atom_id": str(memory["atom_id"]),
            "parent_memory_id": str(memory["parent_memory_id"]),
            "text": str(memory["text"]),
            "u_star": str(memory["u_star"]),
            "usage_rubric": memory["usage_rubric"],
        }
        for memory in sample.get("memories") or []
    ]
    evaluation_payload = {
        "current_query": str(sample["question"]),
        "model_facing_memory": [
            {
                "parent_memory_id": str(block["parent_memory_id"]),
                "memory_text": str(block["memory_text"]),
            }
            for block in sample.get("memory_blocks") or []
        ],
        "answer_condition": str(answer_params["condition"]),
        "model_response": str(answer["response"]),
        "atomic_rubrics": atoms,
    }
    answer_request_id = str(answer["request_id"])
    return {
        "request_id": f"judge:{judge_role}:{answer_request_id}",
        "prompt": [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": json.dumps(evaluation_payload, ensure_ascii=False, indent=2)},
        ],
        "user_defined_params": {
            "stage": "judge",
            "judge_role": judge_role,
            "judge_model": judge_model,
            "judge_protocol": judge_protocol,
            "answer_request_id": answer_request_id,
            "sample_id": str(sample["id"]),
            "panel": str(answer_params["panel"]),
            "condition": str(answer_params["condition"]),
            "model_key": str(answer_params["model_key"]),
            "answer_model": str(answer_params["expected_model"]),
            "expected_atoms": {str(memory["atom_id"]): str(memory["u_star"]) for memory in sample["memories"]},
            "model_response": str(answer["response"]),
        },
    }


def select_stratified_answer_ids(
    answers: list[dict[str, Any]], *, seed: int, representative_per_cell: int, diagnostic_per_cell: int
) -> set[str]:
    cells: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for answer in answers:
        params = answer.get("user_defined_params") or {}
        cell = (str(params["model_key"]), str(params["condition"]), str(params["panel"]))
        cells[cell].append(answer)
    models = sorted({cell[0] for cell in cells})
    conditions = sorted({cell[1] for cell in cells})
    selected: set[str] = set()
    for model in models:
        for condition in conditions:
            for panel, count in (("representative", representative_per_cell), ("diagnostic", diagnostic_per_cell)):
                rows = sorted(
                    cells.get((model, condition, panel), []),
                    key=lambda row: stable_hash(seed, str(row["request_id"])),
                )
                if len(rows) < count:
                    raise ValueError(f"insufficient answers for {(model, condition, panel)}: {len(rows)} < {count}")
                selected.update(str(row["request_id"]) for row in rows[:count])
    return selected


def load_answers(
    answer_root: Path, config: dict[str, Any], conditions: tuple[str, ...] = CONDITIONS
) -> list[dict[str, Any]]:
    answers = []
    expected_per_file = int(config.get("sample_count") or 500)
    for model in config["answer_models"]:
        for condition in conditions:
            path = answer_root / str(model["key"]) / f"{condition}.jsonl"
            rows = list(iter_jsonl(path))
            if len(rows) != expected_per_file:
                raise ValueError(f"expected {expected_per_file} answers in {path}, found {len(rows)}")
            answers.extend(rows)
    ids = [str(row["request_id"]) for row in answers]
    expected = expected_per_file * len(conditions) * len(config["answer_models"])
    if len(ids) != expected or len(ids) != len(set(ids)):
        raise ValueError(f"answer set must contain {expected:,} unique request IDs")
    return answers


def prepare_judge_requests(
    samples: list[dict[str, Any]],
    answers: list[dict[str, Any]],
    config: dict[str, Any],
    system_prompt: str,
    output_dir: Path,
) -> dict[str, Any]:
    samples_by_id = {str(row["id"]): row for row in samples}
    seed = int(config["seed"])
    formal_sampling = config.get("secondary_judge_sampling") or {}
    if formal_sampling:
        per_model_condition = formal_sampling.get("per_model_per_condition")
        secondary_ids = select_formal_secondary_answer_ids(
            answers,
            samples_by_id,
            seed=seed,
            per_model=int(formal_sampling["per_model"]) if per_model_condition is None else None,
            per_model_condition=int(per_model_condition) if per_model_condition is not None else None,
        )
        human_random_ids: set[str] = set()
    else:
        secondary_ids = select_stratified_answer_ids(
            answers, seed=seed, representative_per_cell=70, diagnostic_per_cell=30
        )
        human_random_ids = select_stratified_answer_ids(
            answers, seed=seed + 1, representative_per_cell=4, diagnostic_per_cell=2
        )
    primary_model = str(config["primary_judge"]["model"])
    default_secondary = str(config["secondary_judge"]["model"])
    deepseek_secondary = str(config["deepseek_secondary_judge"]["model"])
    judge_protocol = str(config.get("judge_protocol") or "verdict-v1")
    primary = []
    secondary_default = []
    secondary_deepseek = []
    for answer in answers:
        params = answer["user_defined_params"]
        sample = samples_by_id[str(params["sample_id"])]
        primary.append(build_judge_request(sample, answer, "primary", primary_model, system_prompt, judge_protocol))
        if str(answer["request_id"]) in secondary_ids:
            if str(params["model_key"]).startswith("deepseek"):
                secondary_deepseek.append(
                    build_judge_request(sample, answer, "secondary", deepseek_secondary, system_prompt, judge_protocol)
                )
            else:
                secondary_default.append(
                    build_judge_request(sample, answer, "secondary", default_secondary, system_prompt, judge_protocol)
                )
    artifacts = {}
    for name, rows in (
        ("primary.jsonl", primary),
        ("secondary-deepseek.jsonl", secondary_default),
        ("secondary-kimi.jsonl", secondary_deepseek),
    ):
        path = output_dir / name
        write_jsonl(path, rows)
        artifacts[name] = {"rows": len(rows), "sha256": sha256_file(path)}
    secondary_path = output_dir / "secondary-answer-ids.txt"
    human_path = output_dir / "human-random-answer-ids.txt"
    secondary_path.parent.mkdir(parents=True, exist_ok=True)
    secondary_path.write_text("".join(f"{value}\n" for value in sorted(secondary_ids)), encoding="utf-8")
    human_path.write_text("".join(f"{value}\n" for value in sorted(human_random_ids)), encoding="utf-8")
    artifacts[secondary_path.name] = {"rows": len(secondary_ids), "sha256": sha256_file(secondary_path)}
    artifacts[human_path.name] = {"rows": len(human_random_ids), "sha256": sha256_file(human_path)}
    return {
        "schema_version": f"memcalib-judge-requests-{judge_protocol}",
        "primary_requests": len(primary),
        "secondary_requests": len(secondary_default) + len(secondary_deepseek),
        "secondary_by_judge": {default_secondary: len(secondary_default), deepseek_secondary: len(secondary_deepseek)},
        "human_random_ids": len(human_random_ids),
        "secondary_sampling": formal_sampling or {"representative_per_cell": 70, "diagnostic_per_cell": 30},
        "conditions": sorted({str(answer["user_defined_params"]["condition"]) for answer in answers}),
        "artifacts": artifacts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare primary and secondary MemCalib judge requests.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--hidden", type=Path, default=DEFAULT_HIDDEN)
    parser.add_argument("--answers", type=Path, default=DEFAULT_ANSWERS)
    parser.add_argument("--prompt", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--conditions", nargs="+", choices=CONDITIONS)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    prompt_path = args.prompt or ROOT / str(config.get("judge_prompt") or display_path(DEFAULT_PROMPT, ROOT))
    configured_conditions = config.get("evaluation_modes", {}).get("official_research_conditions")
    conditions = tuple(args.conditions or configured_conditions or CONDITIONS)
    samples = list(iter_jsonl(args.hidden))
    answers = load_answers(args.answers, config, conditions)
    manifest = prepare_judge_requests(samples, answers, config, prompt_path.read_text(encoding="utf-8"), args.output_dir)
    expected_answer_rows = int(config.get("sample_count") or 500)
    manifest["inputs"] = {
        "config": {"path": display_path(args.config, ROOT), "sha256": sha256_file(args.config)},
        "hidden": {"path": display_path(args.hidden, ROOT), "sha256": sha256_file(args.hidden)},
        "prompt": {"path": display_path(prompt_path, ROOT), "sha256": sha256_file(prompt_path)},
        "answers": [
            {
                "path": display_path(args.answers / str(model["key"]) / f"{condition}.jsonl", ROOT),
                "sha256": sha256_file(args.answers / str(model["key"]) / f"{condition}.jsonl"),
                "rows": expected_answer_rows,
            }
            for model in config["answer_models"]
            for condition in conditions
        ],
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
