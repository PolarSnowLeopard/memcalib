#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PACK_SCRIPT = SCRIPT_DIR / "14_build_judge_calibration_pack.py"


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class JudgeCalibrationPackTest(unittest.TestCase):
    def setUp(self) -> None:
        self.pack = load_script(PACK_SCRIPT, "judge_calibration_pack")

    def sample(self, sid: str, topic: str, *, mixed: bool, family: str) -> dict:
        return {
            "id": sid,
            "source_topic": topic,
            "source_dataset": "unit",
            "question": f"question {sid}",
            "memory_blocks": [
                {
                    "parent_memory_id": "p1",
                    "memory_text": f"memory {sid}",
                    "parent_label_mode": "mixed" if mixed else "homogeneous",
                    "parent_label_set": ["B", "C"] if mixed else ["C"],
                }
            ],
            "memories": [
                {
                    "atom_id": "p1_a1",
                    "parent_memory_id": "p1",
                    "text": f"atom {sid}",
                    "u_star": "C",
                    "hard_a_family": None,
                    "usage_rubric": {"memory_usage_weight": "controlling"},
                },
                {
                    "atom_id": "p2_a1",
                    "parent_memory_id": "p2",
                    "text": f"hard a {sid}",
                    "u_star": "A",
                    "source": "synthetic_hard_a",
                    "hard_a_family": family,
                    "usage_rubric": {"memory_usage_weight": "none"},
                },
            ],
        }

    def test_select_calibration_samples_prefers_coverage_and_mixed_cases(self) -> None:
        samples = [
            self.sample("s1", "topic_a", mixed=False, family="fact_judgment_pollution"),
            self.sample("s2", "topic_a", mixed=True, family="evidence_conflict"),
            self.sample("s3", "topic_b", mixed=False, family="scope_overreach"),
        ]

        selected = self.pack.select_calibration_samples(samples, limit=2)

        self.assertEqual(2, len(selected))
        self.assertEqual("s2", selected[0]["id"])
        self.assertTrue(any(sample["source_topic"] == "topic_b" for sample in selected))

    def test_build_pack_rows_exposes_model_input_and_hidden_rubrics(self) -> None:
        rows = self.pack.build_calibration_rows([self.sample("s1", "topic_a", mixed=True, family="evidence_conflict")])

        self.assertEqual(1, len(rows))
        self.assertIn("question s1", rows[0]["model_input"])
        self.assertIn("memory s1", rows[0]["model_input"])
        self.assertIn("hidden_annotation", rows[0])
        self.assertIn("judge_rubric_bundle", rows[0])

    def test_write_pack_outputs_jsonl_and_html(self) -> None:
        rows = self.pack.build_calibration_rows([self.sample("s1", "topic_a", mixed=True, family="evidence_conflict")])
        with tempfile.TemporaryDirectory() as td:
            jsonl_path = Path(td) / "pack.jsonl"
            html_path = Path(td) / "pack.html"
            self.pack.write_calibration_jsonl(jsonl_path, rows)
            self.pack.write_calibration_html(html_path, rows, {"total_samples": 1})
            jsonl_rows = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
            html = html_path.read_text(encoding="utf-8")

        self.assertEqual("s1", jsonl_rows[0]["sample_id"])
        self.assertIn("Judge Calibration Pack", html)
        self.assertIn("model-facing input", html)


if __name__ == "__main__":
    unittest.main()
