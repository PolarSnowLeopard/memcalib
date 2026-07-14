#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from utils import iter_jsonl, load_json, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = SCRIPT_DIR / "data" / "crk2_source_semantic_admitted_15577.jsonl"
DEFAULT_OUTPUT = SCRIPT_DIR / "data" / "crk2_v2_generation_input_100.jsonl"
DEFAULT_MANIFEST = SCRIPT_DIR / "data" / "crk2_v2_generation_input_100.manifest.json"
DEFAULT_PROMPT = SCRIPT_DIR / "prompts" / "generate_crk2_memory_benchmark_record_v2_en.txt"
DEFAULT_CONFIG = SCRIPT_DIR / "config.json"
RUNNER_PATH = SCRIPT_DIR / "06_run_bailian_api.py"
POSTPROCESS_PATH = SCRIPT_DIR / "30_post_crk2_v2_generation.py"
SCHEMA_VERSION = "crk2-generation-requests-v2"
DOMAIN_GUIDANCE = {
    "health_seed": (
        "Preserve medically relevant history, measurements, medication, allergies, symptom course, and safety "
        "constraints. Do not invent diagnoses or turn unsafe claims into hard-A memories."
    ),
    "general": (
        "Preserve user preferences, plans, relationships, prior experiences, resource limits, and earlier dialogue "
        "facts. The resulting task should remain a natural general-assistant request."
    ),
    "coding": (
        "Preserve project environment, language or library version, interface contract, prior failure, implementation "
        "constraint, coding preference, and deployment context. Reference solutions are task aids only and may never "
        "be copied into memory."
    ),
}


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(SCRIPT_DIR.parent))
    except ValueError:
        return str(resolved)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ordered_ids_sha256(rows: list[dict[str, Any]], key: str) -> str:
    payload = "\n".join(str(row.get(key) or "") for row in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _round_robin_strata(rows: list[dict[str, Any]], count: int, seed: int, source: str) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        topic = str(row.get("topic") or "unknown")
        complexity = str((row.get("raw_selection") or {}).get("seed_complexity") or "unknown")
        buckets[(topic, complexity)].append(row)
    for stratum, items in buckets.items():
        random.Random(f"{seed}:{source}:{stratum[0]}:{stratum[1]}").shuffle(items)

    selected: list[dict[str, Any]] = []
    active = sorted(buckets)
    while len(selected) < count and active:
        remaining: list[tuple[str, str]] = []
        for stratum in active:
            if buckets[stratum] and len(selected) < count:
                selected.append(buckets[stratum].pop())
            if buckets[stratum]:
                remaining.append(stratum)
        active = remaining
    if len(selected) != count:
        raise ValueError(f"source {source!r} has only {len(selected)} selectable records; expected {count}")
    return selected


def select_source_balanced(rows: list[dict[str, Any]], limit: int, seed: int) -> list[dict[str, Any]]:
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_source[str(row.get("source_dataset") or "unknown")].append(row)
    sources = sorted(by_source)
    if len(sources) != 2:
        raise ValueError(f"v2 core pilot expects exactly two source datasets, found {sources}")
    quotas = {sources[0]: limit // 2, sources[1]: limit - (limit // 2)}
    selected: list[dict[str, Any]] = []
    for source in sources:
        selected.extend(_round_robin_strata(by_source[source], quotas[source], seed, source))
    random.Random(f"{seed}:final-order").shuffle(selected)
    return selected


def parse_domain_quotas(values: list[str]) -> dict[str, int]:
    quotas: dict[str, int] = {}
    for value in values:
        domain, separator, count_text = value.rpartition("=")
        if not separator or not domain or not count_text.isdigit():
            raise ValueError(f"invalid domain quota {value!r}; expected DOMAIN=COUNT")
        count = int(count_text)
        if count <= 0 or domain in quotas:
            raise ValueError(f"domain quota must be unique and positive: {value!r}")
        quotas[domain] = count
    return quotas


def _equal_source_quotas(capacities: dict[str, int], target: int) -> dict[str, int]:
    quotas = {source: 0 for source in capacities}
    remaining = target
    active = sorted(source for source, capacity in capacities.items() if capacity > 0)
    while remaining > 0 and active:
        share = max(1, remaining // len(active))
        next_active: list[str] = []
        for source in active:
            available = capacities[source] - quotas[source]
            take = min(available, share, remaining)
            quotas[source] += take
            remaining -= take
            if quotas[source] < capacities[source]:
                next_active.append(source)
        active = next_active
    if remaining:
        raise ValueError(f"source capacities cannot satisfy domain target; short by {remaining}")
    return quotas


def select_domain_balanced(
    rows: list[dict[str, Any]], domain_quotas: dict[str, int], seed: int
) -> list[dict[str, Any]]:
    by_domain_source: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        domain = str(row.get("domain") or "health_seed")
        source = str(row.get("source_dataset") or "unknown")
        by_domain_source[domain][source].append(row)
    missing = sorted(set(domain_quotas) - set(by_domain_source))
    if missing:
        raise ValueError(f"domain quotas reference missing domains: {missing}")

    selected: list[dict[str, Any]] = []
    for domain, target in sorted(domain_quotas.items()):
        source_rows = by_domain_source[domain]
        source_quotas = _equal_source_quotas(
            {source: len(items) for source, items in source_rows.items()},
            target,
        )
        for source, quota in sorted(source_quotas.items()):
            if quota:
                selected.extend(_round_robin_strata(source_rows[source], quota, seed, f"{domain}:{source}"))
    random.Random(f"{seed}:domain-final-order").shuffle(selected)
    return selected


def build_request(row: dict[str, Any], index: int, template: str) -> dict[str, Any]:
    source_id = str(row.get("id") or f"row_{index:06d}")
    domain = str(row.get("domain") or "health_seed")
    content = (
        template.replace("{domain}", domain)
        .replace("{domain_guidance}", DOMAIN_GUIDANCE.get(domain, DOMAIN_GUIDANCE["general"]))
        .replace("{source_dataset}", str(row.get("source_dataset") or ""))
        .replace("{source_id}", source_id)
        .replace("{topic}", str(row.get("topic") or ""))
        .replace("{source_context}", str(row.get("dialogue_context") or row.get("source_context") or ""))
        .replace("{raw_question}", str(row.get("raw_question") or ""))
        .replace("{source_answer}", str(row.get("doctor_answer") or row.get("source_answer") or ""))
    )
    params = dict(row)
    params.update(
        {
            "crk2_v2_request_index": index,
            "construction_schema_version": "crk-2-canonical-memory-v2",
            "output_language": "en",
        }
    )
    return {
        "request_id": f"crk2_v2_{source_id}",
        "prompt": [{"role": "user", "content": content}],
        "user_defined_params": params,
    }


def distribution(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    return {
        "domain": dict(sorted(Counter(str(row.get("domain") or "health_seed") for row in rows).items())),
        "source_dataset": dict(sorted(Counter(str(row.get("source_dataset") or "unknown") for row in rows).items())),
        "topic": dict(sorted(Counter(str(row.get("topic") or "unknown") for row in rows).items())),
        "seed_complexity": dict(
            sorted(
                Counter(
                    str((row.get("raw_selection") or {}).get("seed_complexity") or "unknown") for row in rows
                ).items()
            )
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare the source-balanced CRK-2 v2 construction pilot.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--prompt-template", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--domain-quota", action="append", default=[])
    parser.add_argument("--seed", type=int, default=20260714)
    args = parser.parse_args()

    if args.limit < 2 and not args.domain_quota:
        raise ValueError("limit must be at least 2")
    rows = list(iter_jsonl(args.input))
    domain_quotas = parse_domain_quotas(args.domain_quota)
    selected = (
        select_domain_balanced(rows, domain_quotas, args.seed)
        if domain_quotas
        else select_source_balanced(rows, args.limit, args.seed)
    )
    template = args.prompt_template.read_text(encoding="utf-8")
    requests = [build_request(row, index, template) for index, row in enumerate(selected, start=1)]
    write_jsonl(args.output, requests)

    api_config = (load_json(args.config).get("api") or {}) if args.config.exists() else {}
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "input": {"path": portable_path(args.input), "sha256": file_sha256(args.input), "records": len(rows)},
        "implementation": {
            "prepare": {"path": portable_path(Path(__file__)), "sha256": file_sha256(Path(__file__).resolve())},
            "prompt": {"path": portable_path(args.prompt_template), "sha256": file_sha256(args.prompt_template)},
            "runner": {"path": portable_path(RUNNER_PATH), "sha256": file_sha256(RUNNER_PATH)},
            "postprocess": {"path": portable_path(POSTPROCESS_PATH), "sha256": file_sha256(POSTPROCESS_PATH)},
        },
        "parameters": {
            "limit": len(selected),
            "domain_quotas": domain_quotas,
            "seed": args.seed,
            "language": "en",
            "sources": len({str(row.get('source_dataset') or 'unknown') for row in selected}),
        },
        "api": {
            "base_url": api_config.get("base_url"),
            "model": api_config.get("model"),
            "temperature": api_config.get("temperature"),
            "max_tokens": api_config.get("max_tokens"),
            "timeout": api_config.get("timeout"),
        },
        "distribution": distribution(selected),
        "selected_source_ids": [str(row.get("id") or "") for row in selected],
        "selected_source_id_sha256": ordered_ids_sha256(selected, "id"),
        "output": {
            "path": portable_path(args.output),
            "sha256": file_sha256(args.output),
            "requests": len(requests),
            "ordered_request_id_sha256": ordered_ids_sha256(requests, "request_id"),
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps({"output": str(args.output), "manifest": str(args.manifest), **distribution(selected)}, indent=2))


if __name__ == "__main__":
    main()
