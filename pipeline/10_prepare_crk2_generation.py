#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from utils import iter_jsonl, load_json, resolve_config_path, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR / "config.json"
DEFAULT_PROMPT = SCRIPT_DIR / "prompts" / "generate_crk2_memory_benchmark_record.txt"
DEFAULT_EN_PROMPT = SCRIPT_DIR / "prompts" / "generate_crk2_memory_benchmark_record_en.txt"
DEFAULT_PROMPTS = {"zh": DEFAULT_PROMPT, "en": DEFAULT_EN_PROMPT}
DEFAULT_OUTPUT = SCRIPT_DIR / "data" / "crk2_generation_input_100.jsonl"
RUNNER_PATH = SCRIPT_DIR / "06_run_bailian_api.py"
POSTPROCESS_PATH = SCRIPT_DIR / "11_post_crk2_generation.py"
SCHEMA_VERSION = "crk2-generation-requests-v1"
LANGUAGE_POLICIES = {
    "zh": """语言规范：
- 所有生成字段必须使用简体中文，包括 question、memory_text、atomic memory text、atomic_predicate、label_reason、construction_target、usage_rubric、qc 说明和 notes。
- raw_evidence 和 evidence 字段保留原始证据语言；如果原始问答是英文，这两个字段可以是英文，用于审计和复现。
- schema key、枚举值、source、hard_a_family、memory_type、derivation 等机器可读字段保持 schema 中规定的英文值。
- 医学缩写、专有名词、产品名、地名和无法自然翻译的术语可以保留英文，但不得让整句生成内容中英混杂。
- synthetic_hard_a 的 memory_text、atomic memory text、label_reason、construction_target 和 usage_rubric 也必须使用简体中文；只有 synthetic rationale 形式的 evidence 可以包含必要英文术语。""",
    "en": """Language policy:
- All generated natural-language fields must be written in English, including question, memory_text, atomic memory text, atomic_predicate, label_reason, construction_target, usage_rubric, qc explanations, and notes.
- raw_evidence and evidence fields preserve the original evidence language for auditability and reproducibility.
- Schema keys, enum values, source, hard_a_family, memory_type, derivation, and other machine-readable fields must keep the exact English values defined by the schema.
- Domain abbreviations, code identifiers, proper names, product names, place names, and terms that are conventionally written in another language may remain unchanged, but do not mix languages within generated prose unless the term itself requires it.
- synthetic_hard_a fields must also be generated in English, except evidence fields that intentionally record a synthetic rationale.""",
}
DOMAIN_CONSTRUCTION_GUIDANCE = {
    "general": """General-dialogue boundary guidance:
- C memories are explicit facts or hard constraints whose omission would make the answer materially wrong for this user or current situation.
- B memories may adapt tone, format, examples, prioritization, or implementation while preserving the answer backbone.
- A memories include semantically related but inapplicable, stale, over-specific, or untriggered preferences that should leave no footprint.
- Preserve a coherent user or conversation history. Do not combine unrelated profile facts merely to increase atom count.""",
    "coding": """Coding boundary guidance:
- C memories include applicable runtime or language versions, interface contracts, forbidden dependencies, compatibility requirements, security constraints, and test-defining behavior.
- B memories include code style, naming, explanation depth, secondary implementation preferences, and non-controlling tooling choices.
- A memories include another repository's stack, stale versions, previously failed approaches, and preferences that conflict with the current project or specification.
- Do not turn the reference solution into memory or leak its implementation. Extract real B/C constraints only from source context and the current question.
- Keep one project event or configuration coherent when atomizing it. A version and the library it qualifies normally form one atomic proposition.""",
    "health_seed": """Medical boundary guidance:
- Apply the locked v0.1 medical A/B/C boundary standard.
- Safety-critical facts may control the answer; unsafe preferences must not control it.""",
}
TARGET_INSTRUCTIONS = {
    "zh": "目标：优先构造 {target_memory_count} 个 memory block；最终 atomic memory 数量由语义拆分决定。只允许补充 hard A。",
    "en": "Target: construct {target_memory_count} memory blocks when supported by the evidence; let semantic atomization determine the final number of atomic memories. Only hard A memories may be supplemented.",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_input_lineage(input_path: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    expected_hash = str((((manifest.get("outputs") or {}).get("admitted") or {}).get("sha256") or ""))
    actual_hash = file_sha256(input_path)
    if not expected_hash or expected_hash != actual_hash:
        raise ValueError("admitted input hash does not match admission manifest")
    expected_count = int((manifest.get("counts") or {}).get("admitted") or 0)
    if expected_count:
        actual_count = sum(1 for _ in iter_jsonl(input_path))
        if actual_count != expected_count:
            raise ValueError(f"admitted input count does not match admission manifest: {actual_count} != {expected_count}")
    return manifest


def ordered_request_id_sha256(requests: list[dict[str, Any]]) -> str:
    payload = "\n".join(str(request.get("request_id") or "") for request in requests)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def request_distribution(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    return {
        "domain": dict(sorted(Counter(str(row.get("domain") or "health_seed") for row in rows).items())),
        "source_dataset": dict(sorted(Counter(str(row.get("source_dataset") or "unknown") for row in rows).items())),
        "topic": dict(sorted(Counter(str(row.get("topic") or "unknown") for row in rows).items())),
        "seed_complexity": dict(
            sorted(
                Counter(
                    str((row.get("raw_selection") or {}).get("seed_complexity") or "unknown")
                    for row in rows
                ).items()
            )
        ),
        "semantic_qc_state": dict(
            sorted(
                Counter(
                    str((row.get("semantic_qc") or {}).get("state") or "unknown")
                    for row in rows
                ).items()
            )
        ),
    }


def select_balanced_records(rows: list[dict[str, Any]], limit: int, seed: int) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get("topic") or "unknown")].append(row)

    for topic, topic_rows in buckets.items():
        topic_rng = random.Random(f"{seed}:{topic}")
        topic_rng.shuffle(topic_rows)

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
    return selected


def build_request(
    row: dict[str, Any],
    request_index: int,
    target_memory_count: str,
    prompt_template: str | None = None,
    output_language: str = "zh",
) -> dict[str, Any]:
    if output_language not in LANGUAGE_POLICIES:
        raise ValueError(f"Unsupported output_language={output_language!r}; expected one of {sorted(LANGUAGE_POLICIES)}")
    template = prompt_template
    if template is None:
        template = DEFAULT_PROMPTS[output_language].read_text(encoding="utf-8")
    language_policy = LANGUAGE_POLICIES[output_language]
    if "{language_policy}" not in template:
        template = f"{template.rstrip()}\n\n{language_policy}\n"
    source_id = str(row.get("id") or f"row_{request_index:06d}")
    domain = str(row.get("domain") or "health_seed")
    source_answer = str(row.get("source_answer") or row.get("doctor_answer") or "")
    content = (
        template.replace("{domain}", domain)
        .replace("{domain_guidance}", DOMAIN_CONSTRUCTION_GUIDANCE.get(domain, DOMAIN_CONSTRUCTION_GUIDANCE["general"]))
        .replace("{source_dataset}", str(row.get("source_dataset", "")))
        .replace("{source_id}", source_id)
        .replace("{topic}", str(row.get("topic", "")))
        .replace("{source_context}", str(row.get("source_context", "")))
        .replace("{raw_question}", str(row.get("raw_question", "")))
        .replace("{source_answer}", source_answer)
        .replace("{doctor_answer}", source_answer)
        .replace("{language_policy}", language_policy)
    )
    content += "\n\n" + TARGET_INSTRUCTIONS[output_language].format(target_memory_count=target_memory_count)
    params = dict(row)
    params["crk2_request_index"] = request_index
    params["target_memory_count"] = target_memory_count
    params["output_language"] = output_language
    return {
        "request_id": f"crk2_{source_id}",
        "prompt": [{"role": "user", "content": content}],
        "user_defined_params": params,
    }


def collect_excluded_ids(paths: list[Path]) -> set[str]:
    excluded = set()
    for path in paths:
        for row in iter_jsonl(path):
            params = row.get("user_defined_params") or row.get("passParams") or row.get("params") or {}
            source_id = params.get("id") or params.get("source_raw_id")
            if source_id:
                excluded.add(str(source_id))
    return excluded


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare CRK-2 full LLM construction requests from raw public QA records.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--input-manifest", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--prompt-template", type=Path)
    parser.add_argument("--target-memory-count", default="3-6")
    parser.add_argument("--output-language", choices=sorted(LANGUAGE_POLICIES), default="zh")
    parser.add_argument("--primus-string-prompt", action="store_true")
    parser.add_argument("--exclude-requests", type=Path, action="append", default=[])
    args = parser.parse_args()

    cfg = load_json(args.config)
    output_dir = resolve_config_path(args.config, str(cfg["output_dir"]))
    input_path = args.input or output_dir / f"crk2_selected_raw_seeds_{args.limit}.jsonl"
    seed = args.seed if args.seed is not None else int(cfg.get("sampling", {}).get("seed", 42))
    parent_manifest = verify_input_lineage(input_path, args.input_manifest) if args.input_manifest else None
    rows = list(iter_jsonl(input_path))
    excluded_ids = collect_excluded_ids(args.exclude_requests)
    if excluded_ids:
        rows = [row for row in rows if str(row.get("id")) not in excluded_ids]
    selected = select_balanced_records(rows, args.limit, seed)
    prompt_path = args.prompt_template or DEFAULT_PROMPTS[args.output_language]
    template = prompt_path.read_text(encoding="utf-8")
    requests = []
    for index, row in enumerate(selected, start=1):
        request = build_request(row, index, args.target_memory_count, template, args.output_language)
        if args.primus_string_prompt:
            request["prompt"] = json.dumps(request["prompt"], ensure_ascii=False)
        requests.append(request)

    write_jsonl(args.output, requests)
    if args.manifest:
        api_cfg = dict(cfg.get("api") or {})
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "parent": (
                {
                    "path": str(args.input_manifest),
                    "sha256": file_sha256(args.input_manifest),
                    "schema_version": str((parent_manifest or {}).get("schema_version") or ""),
                }
                if args.input_manifest
                else None
            ),
            "input": {
                "path": str(input_path),
                "sha256": file_sha256(input_path),
                "records": len(rows),
            },
            "implementation": {
                "prepare": {"path": str(Path(__file__).resolve()), "sha256": file_sha256(Path(__file__).resolve())},
                "runner": {"path": str(RUNNER_PATH), "sha256": file_sha256(RUNNER_PATH)},
                "postprocess": {"path": str(POSTPROCESS_PATH), "sha256": file_sha256(POSTPROCESS_PATH)},
                "prompt": {"path": str(prompt_path), "sha256": file_sha256(prompt_path)},
                "config": {"path": str(args.config), "sha256": file_sha256(args.config)},
            },
            "parameters": {
                "limit": args.limit,
                "seed": seed,
                "target_memory_count": args.target_memory_count,
                "output_language": args.output_language,
                "primus_string_prompt": args.primus_string_prompt,
                "excluded": len(excluded_ids),
            },
            "api": {
                "base_url": api_cfg.get("base_url"),
                "model": api_cfg.get("model"),
                "temperature": api_cfg.get("temperature"),
                "max_tokens": api_cfg.get("max_tokens"),
                "timeout": api_cfg.get("timeout"),
            },
            "distributions": request_distribution(selected),
            "output": {
                "path": str(args.output),
                "sha256": file_sha256(args.output),
                "requests": len(requests),
                "ordered_request_id_sha256": ordered_request_id_sha256(requests),
            },
        }
        write_json(args.manifest, manifest)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "requests": len(requests),
                "input": str(input_path),
                "seed": seed,
                "excluded": len(excluded_ids),
                "output_language": args.output_language,
                "manifest": str(args.manifest) if args.manifest else None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
