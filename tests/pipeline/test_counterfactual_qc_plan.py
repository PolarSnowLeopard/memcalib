#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[2] / "pipeline"
PLAN_SCRIPT = SCRIPT_DIR / "13_build_counterfactual_qc_plan.py"


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CounterfactualQcPlanTest(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = load_script(PLAN_SCRIPT, "counterfactual_plan")

    def sample(self) -> dict:
        return {
            "id": "crk2_raw1",
            "source_topic": "digestive",
            "question": "去背景化问题",
            "memory_blocks": [
                {"parent_memory_id": "p1", "memory_text": "用户吃了自制辣椒后出现上腹痛，并伴有恶心。"},
                {"parent_memory_id": "p2", "memory_text": "用户过去认为胃部不适通常只是压力导致。"},
            ],
            "memories": [
                {
                    "parent_memory_id": "p1",
                    "atom_id": "p1_a1",
                    "text": "用户吃了自制辣椒。",
                    "u_star": "C",
                    "usage_rubric": {
                        "memory_usage_weight": "controlling",
                        "under_use": "忽略暴露会导致病因判断不完整。",
                        "over_use": "直接确诊严重疾病。",
                        "missing_memory_failure": "忽略会导致病因判断不完整。",
                    },
                },
                {
                    "parent_memory_id": "p1",
                    "atom_id": "p1_a2",
                    "text": "用户伴有恶心。",
                    "u_star": "B",
                    "usage_rubric": {
                        "memory_usage_weight": "supporting",
                        "under_use": "回答不够贴合症状。",
                        "over_use": "将恶心作为核心诊断依据。",
                        "maximum_footprint": "只能局部提及。",
                    },
                },
                {
                    "parent_memory_id": "p2",
                    "atom_id": "p2_a1",
                    "text": "用户过去认为胃部不适通常只是压力导致。",
                    "u_star": "A",
                    "hard_a_family": "evidence_conflict",
                    "usage_rubric": {
                        "memory_usage_weight": "none",
                        "under_use": "A has no under-use",
                        "over_use": "把旧经验当作当前病因证据。",
                        "contamination_signals": ["污染证据权重"],
                    },
                },
            ],
        }

    def test_build_counterfactual_plan_creates_label_specific_checks(self) -> None:
        rows = self.plan.build_counterfactual_rows([self.sample()])

        self.assertEqual(3, len(rows))
        self.assertEqual("remove_or_mask_C", rows[0]["counterfactual_type"])
        self.assertIn("主干", rows[0]["expected_change"])
        self.assertEqual("remove_or_mask_B", rows[1]["counterfactual_type"])
        self.assertIn("局部", rows[1]["expected_change"])
        self.assertEqual("A_overuse_probe", rows[2]["counterfactual_type"])
        self.assertIn("污染证据权重", rows[2]["failure_signal"])

    def test_write_plan_html_mentions_hidden_atom_level_qc(self) -> None:
        rows = self.plan.build_counterfactual_rows([self.sample()])
        with tempfile.TemporaryDirectory() as td:
            html_path = Path(td) / "counterfactual.html"
            self.plan.write_counterfactual_html(html_path, rows, {"total_checks": 3})
            html = html_path.read_text(encoding="utf-8")

        self.assertIn("Counterfactual QC Plan", html)
        self.assertIn("hidden atom-level", html)
        self.assertIn("remove_or_mask_C", html)


if __name__ == "__main__":
    unittest.main()
