#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def finite_float(value: Any, label: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label}: expected a finite number")
    return result


def select_model(
    metrics: dict[str, Any], mode: str, model_key: str | None
) -> tuple[str, dict[str, Any]]:
    try:
        models = metrics["modes"][mode]["models"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"metrics do not contain mode {mode!r}") from exc
    if not isinstance(models, dict) or not models:
        raise ValueError(f"metrics mode {mode!r} has no models")
    if model_key is None:
        if len(models) != 1:
            raise ValueError(
                "--model-key is required; available models: "
                + ", ".join(sorted(models))
            )
        model_key = next(iter(models))
    if model_key not in models:
        raise ValueError(
            f"model {model_key!r} not found; available: "
            + ", ".join(sorted(models))
        )
    return model_key, models[model_key]


def condition_scalars(condition: dict[str, Any], prefix: str) -> dict[str, float]:
    try:
        overall = condition["overall"]
        directional = overall["directional_risk"]["0.5"]
        event = overall["event_guardrail"]
        values = {
            f"{prefix}/scs_rho_0_5": overall["scs"]["0.5"]["mean"],
            f"{prefix}/sopb_rho_0_5": directional["opb"],
            f"{prefix}/supb_rho_0_5": directional["upb"],
            f"{prefix}/directional_h": directional["harmonic"],
            f"{prefix}/exact": overall["sample_exact_accuracy"],
            f"{prefix}/any_opb": event["opb"],
            f"{prefix}/any_upb": event["upb"],
            f"{prefix}/event_h": event["harmonic"],
            f"{prefix}/mean_over_budget": overall["mean_over_budget"],
            f"{prefix}/mean_under_budget": overall["mean_under_budget"],
            f"{prefix}/mean_total_budget": overall["mean_total_budget"],
            f"{prefix}/samples": overall["samples"],
            f"{prefix}/atoms": overall["atoms"],
            f"{prefix}/mean_atoms_per_sample": overall["mean_atoms_per_sample"],
        }
    except (KeyError, TypeError) as exc:
        raise ValueError(
            "metrics do not match the MemCalib sample-level schema"
        ) from exc
    return {key: finite_float(value, key) for key, value in values.items()}


def collect_scalars(
    metrics: dict[str, Any],
    *,
    mode: str,
    model_key: str | None,
    conditions: list[str],
    prefix: str,
    expected_samples: int | None,
) -> tuple[str, dict[str, float]]:
    selected_key, model = select_model(metrics, mode, model_key)
    model_conditions = model.get("conditions")
    if not isinstance(model_conditions, dict):
        raise ValueError(f"model {selected_key!r} has no conditions")

    scalars: dict[str, float] = {}
    sample_counts: list[int] = []
    for condition_name in conditions:
        condition = model_conditions.get(condition_name)
        if not isinstance(condition, dict):
            raise ValueError(
                f"model {selected_key!r} is missing {condition_name!r}"
            )
        condition_prefix = f"{prefix}/{condition_name}"
        values = condition_scalars(condition, condition_prefix)
        scalars.update(values)
        sample_counts.append(int(values[f"{condition_prefix}/samples"]))

    retained = min(sample_counts)
    scalars[f"{prefix}/coverage/samples"] = float(retained)
    if expected_samples:
        scalars[f"{prefix}/coverage/sample_fraction"] = retained / expected_samples
    return selected_key, dict(sorted(scalars.items()))


def make_writer(log_dir: Path):
    try:
        from torch.utils.tensorboard import SummaryWriter
    except ImportError:
        try:
            from tensorboardX import SummaryWriter
        except ImportError as exc:
            raise RuntimeError(
                "install tensorboard support through PyTorch or tensorboardX"
            ) from exc
    return SummaryWriter(log_dir=str(log_dir))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export MemCalib sample-level metrics to TensorBoard."
    )
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--log-dir", type=Path, required=True)
    parser.add_argument("--model-key")
    parser.add_argument("--mode", default="nonthinking")
    parser.add_argument(
        "--conditions",
        nargs="+",
        default=["full_memory", "no_memory"],
        choices=["full_memory", "no_memory"],
    )
    parser.add_argument("--prefix", default="memcalib")
    parser.add_argument("--expected-samples", type=int)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.step < 0:
        raise ValueError("--step must be nonnegative")
    if args.expected_samples is not None and args.expected_samples <= 0:
        raise ValueError("--expected-samples must be positive")

    model_key, scalars = collect_scalars(
        load_json(args.metrics),
        mode=args.mode,
        model_key=args.model_key,
        conditions=args.conditions,
        prefix=args.prefix.rstrip("/"),
        expected_samples=args.expected_samples,
    )
    summary = {
        "model_key": model_key,
        "step": args.step,
        "log_dir": str(args.log_dir),
        "scalars": scalars,
    }
    if args.dry_run:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    args.log_dir.mkdir(parents=True, exist_ok=True)
    writer = make_writer(args.log_dir)
    try:
        for tag, value in scalars.items():
            writer.add_scalar(tag, value, global_step=args.step)
        writer.flush()
    finally:
        writer.close()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
