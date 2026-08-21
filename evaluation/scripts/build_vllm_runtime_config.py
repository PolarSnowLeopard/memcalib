#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from evaluation.common import write_json


def build_runtime_config(config: dict[str, Any], answers_dir: Path) -> dict[str, Any]:
    runtime = copy.deepcopy(config)
    configured = {str(model["key"]): model for model in runtime["answer_models"]}
    models = []
    for served_path in sorted(answers_dir.glob("*/served-model-name.txt")):
        key = served_path.parent.name
        metadata_path = served_path.parent / "model-metadata.json"
        if metadata_path.exists():
            model = json.loads(metadata_path.read_text(encoding="utf-8"))
        elif key in configured:
            model = copy.deepcopy(configured[key])
        else:
            model = {
                "key": key,
                "model": key,
                "display_name": key,
                "answer_mode": "nonthinking",
                "checkpoint_role": "legacy_or_custom",
            }
        model["key"] = key
        model.setdefault("model", key)
        model.setdefault("display_name", key)
        model.setdefault("answer_mode", "nonthinking")
        model.setdefault("checkpoint_role", "baseline")
        model["served_model_name"] = served_path.read_text(encoding="utf-8").strip()
        if not model["served_model_name"]:
            raise ValueError(f"empty served model metadata: {served_path}")
        models.append(model)
    if not models:
        raise ValueError(f"no model metadata found under {answers_dir}")
    runtime["answer_models"] = models
    return runtime


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a runtime evaluation config from model answer directories."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    runtime = build_runtime_config(config, args.answers)
    write_json(args.output, runtime)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "models": [model["key"] for model in runtime["answer_models"]],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
