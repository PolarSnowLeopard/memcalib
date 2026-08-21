from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from evaluation.common import request_fingerprint


ROOT = Path(__file__).resolve().parents[1]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def result_for(request: dict, model: str) -> dict:
    return {
        "request_id": request["request_id"],
        "input_fingerprint": request_fingerprint(request),
        "response": "answer",
        "raw_response": {
            "model": model,
            "choices": [{"finish_reason": "stop", "message": {"content": "answer"}}],
        },
    }


class CompleteCaseAnswerRunTest(unittest.TestCase):
    def test_filters_same_sample_from_every_cell(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            config = {
                "schema_version": "test",
                "sample_count": 3,
                "release": "parent",
                "answer_models": [
                    {"key": "m1", "model": "model-1"},
                    {"key": "m2", "model": "model-2"},
                ],
            }
            config_path = tmp_path / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            requests_root = tmp_path / "requests"
            results_root = tmp_path / "results"
            samples = [{"id": f"s{i}", "question": f"q{i}"} for i in range(3)]
            sample_release = tmp_path / "sample-release"
            write_jsonl(sample_release / "model-facing.jsonl", samples)
            write_jsonl(sample_release / "hidden-evaluation.jsonl", samples)

            for model_key, model in (("m1", "model-1"), ("m2", "model-2")):
                for condition in ("full_memory", "no_memory"):
                    requests = [
                        {
                            "request_id": f"{model_key}:{condition}:s{i}",
                            "prompt": [],
                            "user_defined_params": {
                                "sample_id": f"s{i}",
                                "condition": condition,
                                "model_key": model_key,
                            },
                        }
                        for i in range(3)
                    ]
                    results = [result_for(request, model) for request in requests]
                    if model_key == "m2" and condition == "no_memory":
                        results = results[:2]
                    write_jsonl(requests_root / model_key / f"{condition}.jsonl", requests)
                    write_jsonl(results_root / model_key / f"{condition}.jsonl", results)

            output_config = tmp_path / "complete-config.json"
            output_requests = tmp_path / "complete-run" / "requests"
            output_results = tmp_path / "complete-run" / "answers"
            output_release = tmp_path / "complete-release"
            manifest = tmp_path / "complete-run" / "manifest.json"
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "evaluation/scripts/build_complete_case_answer_run.py"),
                    "--config",
                    str(config_path),
                    "--requests",
                    str(requests_root),
                    "--results",
                    str(results_root),
                    "--sample-release",
                    str(sample_release),
                    "--output-config",
                    str(output_config),
                    "--output-requests",
                    str(output_requests),
                    "--output-results",
                    str(output_results),
                    "--output-sample-release",
                    str(output_release),
                    "--manifest",
                    str(manifest),
                ],
                check=True,
                cwd=ROOT,
            )

            summary = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(summary["complete_case_samples"], 2)
            self.assertEqual(summary["excluded_sample_ids"], ["s2"])
            self.assertEqual(summary["formal_answers"], 8)
            self.assertEqual(
                json.loads(output_config.read_text(encoding="utf-8"))["sample_count"],
                2,
            )
            for model_key in ("m1", "m2"):
                for condition in ("full_memory", "no_memory"):
                    row_count = len(
                        (output_results / model_key / f"{condition}.jsonl")
                        .read_text()
                        .splitlines()
                    )
                    self.assertEqual(row_count, 2)

    def test_respects_configured_full_memory_only_condition(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            config = {
                "schema_version": "test",
                "sample_count": 2,
                "release": "parent",
                "evaluation_modes": {"official_research_conditions": ["full_memory"]},
                "answer_models": [{"key": "m1", "model": "model-1"}],
            }
            config_path = tmp_path / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            requests_root = tmp_path / "requests"
            results_root = tmp_path / "results"
            samples = [{"id": f"s{i}", "question": f"q{i}"} for i in range(2)]
            sample_release = tmp_path / "sample-release"
            write_jsonl(sample_release / "model-facing.jsonl", samples)
            write_jsonl(sample_release / "hidden-evaluation.jsonl", samples)

            requests = [
                {
                    "request_id": f"m1:full_memory:s{i}",
                    "prompt": [],
                    "user_defined_params": {
                        "sample_id": f"s{i}",
                        "condition": "full_memory",
                        "model_key": "m1",
                    },
                }
                for i in range(2)
            ]
            write_jsonl(requests_root / "m1/full_memory.jsonl", requests)
            write_jsonl(
                results_root / "m1/full_memory.jsonl",
                [result_for(request, "model-1") for request in requests],
            )

            output_config = tmp_path / "complete-config.json"
            output_requests = tmp_path / "complete-run/requests"
            output_results = tmp_path / "complete-run/answers"
            output_release = tmp_path / "complete-release"
            manifest = tmp_path / "complete-run/manifest.json"
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "evaluation/scripts/build_complete_case_answer_run.py"),
                    "--config",
                    str(config_path),
                    "--requests",
                    str(requests_root),
                    "--results",
                    str(results_root),
                    "--sample-release",
                    str(sample_release),
                    "--output-config",
                    str(output_config),
                    "--output-requests",
                    str(output_requests),
                    "--output-results",
                    str(output_results),
                    "--output-sample-release",
                    str(output_release),
                    "--manifest",
                    str(manifest),
                ],
                check=True,
                cwd=ROOT,
            )

            summary = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(2, summary["complete_case_samples"])
            self.assertEqual(2, summary["formal_answers"])
            self.assertTrue((output_results / "m1/full_memory.jsonl").exists())
            self.assertFalse((output_results / "m1/no_memory.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
