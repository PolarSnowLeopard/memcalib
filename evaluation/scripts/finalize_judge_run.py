#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from evaluation.common import display_path, iter_jsonl, sha256_file, write_json


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "evaluation" / "archive" / "configs" / "memcalib-v0.1-500.json"
DEFAULT_RUN = ROOT / "evaluation" / "runs" / "memcalib-v0.1-500"
DEFAULT_REQUEST_MANIFEST = ROOT / "evaluation" / "archive" / "releases" / "memcalib-v0.1-500" / "judge-request.manifest.json"
DEFAULT_MANIFEST = ROOT / "evaluation" / "archive" / "releases" / "memcalib-v0.1-500" / "judge-run.manifest.json"


def summarize_judgment_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    answer_ids = [str(row["answer_request_id"]) for row in rows]
    if len(answer_ids) != len(set(answer_ids)):
        raise ValueError("duplicate answer_request_id in normalized judgments")
    judges: Counter[str] = Counter()
    warning_counts: Counter[str] = Counter()
    repairs = 0
    atoms = 0
    for row in rows:
        judges[str(row.get("judge_model") or "unknown")] += 1
        atoms += len(row.get("atom_judgments") or [])
        warning_counts.update(str(item).split(":", 1)[0] for item in row.get("validation_warnings") or [])
        repairs += len(row.get("schema_repairs") or [])
    return {
        "rows": len(rows),
        "unique_answer_request_ids": len(set(answer_ids)),
        "atoms": atoms,
        "judge_models": dict(sorted(judges.items())),
        "rows_with_warnings": sum(bool(row.get("validation_warnings")) for row in rows),
        "warning_counts": dict(sorted(warning_counts.items())),
        "rows_with_schema_repairs": sum(bool(row.get("schema_repairs")) for row in rows),
        "schema_repairs": repairs,
    }


def artifact(path: Path) -> dict[str, Any]:
    return {
        "path": display_path(path, ROOT),
        "sha256": sha256_file(path),
        "rows": sum(1 for _ in iter_jsonl(path)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and lock the normalized MemCalib judge run.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--run", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--request-manifest", type=Path, default=DEFAULT_REQUEST_MANIFEST)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    request_manifest = json.loads(args.request_manifest.read_text(encoding="utf-8"))
    primary_path = args.run / "judgments" / "primary.valid.jsonl"
    secondary_path = args.run / "judgments" / "secondary.valid.jsonl"
    primary = list(iter_jsonl(primary_path))
    secondary = list(iter_jsonl(secondary_path))
    primary_summary = summarize_judgment_rows(primary)
    secondary_summary = summarize_judgment_rows(secondary)
    expected_primary = int(request_manifest["primary_requests"])
    expected_secondary = int(request_manifest["secondary_requests"])
    if primary_summary["rows"] != expected_primary:
        raise ValueError(f"primary judgment count mismatch: {primary_summary['rows']} != {expected_primary}")
    if secondary_summary["rows"] != expected_secondary:
        raise ValueError(f"secondary judgment count mismatch: {secondary_summary['rows']} != {expected_secondary}")

    retry_artifacts = {}
    for relative_dir in (Path("requests/judges"), Path("api"), Path("judgments")):
        for path in sorted((args.run / relative_dir).glob("*retry*.jsonl")):
            retry_artifacts[str(relative_dir / path.name)] = artifact(path)
    manifest = {
        "schema_version": "memcalib-judge-run-v1",
        "status": "completed",
        "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "generation": config["judge_generation"],
        "primary_judge": config["primary_judge"],
        "secondary_judges": [config["secondary_judge"], config["deepseek_secondary_judge"]],
        "request_manifest": {
            "path": display_path(args.request_manifest, ROOT),
            "sha256": sha256_file(args.request_manifest),
        },
        "normalized": {
            "primary": {**artifact(primary_path), "summary": primary_summary},
            "secondary": {**artifact(secondary_path), "summary": secondary_summary},
        },
        "targeted_retry_outputs": retry_artifacts,
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
