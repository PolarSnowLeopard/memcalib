#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ANALYSIS_SCRIPT = SCRIPT_DIR / "24_analyze_crk2_formal_benchmark.py"


def load_analysis():
    spec = importlib.util.spec_from_file_location("formal_benchmark_analysis", ANALYSIS_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


FIXTURE_SAMPLE = {
    "id": "crk2_fixture",
    "source_dataset": "OpenMed/MedDialog",
    "source_topic": "digestive",
    "question": "What should be done for abdominal pain?",
    "memory_blocks": [
        {
            "parent_memory_id": "p1",
            "memory_text": "The user has abdominal pain after eating spicy food.",
            "raw_evidence": "I ate spicy food and now have pain.",
            "source": "from_question",
            "parent_label_set": ["B", "C"],
            "parent_label_mode": "mixed",
            "atom_count": 2,
        },
        {
            "parent_memory_id": "p2",
            "memory_text": "The user prefers an unrelated supplement brand.",
            "raw_evidence": "synthetic rationale",
            "source": "synthetic_hard_a",
            "parent_label_set": ["A"],
            "parent_label_mode": "homogeneous",
            "atom_count": 1,
        },
    ],
    "memories": [
        {
            "parent_memory_id": "p1",
            "text": "The user ate spicy food.",
            "evidence": "I ate spicy food.",
            "source": "from_question",
            "memory_type": "case_fact",
            "u_star": "C",
            "subtype": "exposure",
            "hard_a_family": None,
            "usage_rubric": {"memory_usage_weight": "controlling", "correct_use": "Use the exposure."},
        },
        {
            "parent_memory_id": "p1",
            "text": "The user has abdominal pain.",
            "evidence": "I have pain.",
            "source": "from_question",
            "memory_type": "case_fact",
            "u_star": "B",
            "subtype": "symptom",
            "hard_a_family": None,
            "usage_rubric": {"memory_usage_weight": "supporting", "correct_use": "Mention locally."},
        },
        {
            "parent_memory_id": "p2",
            "text": "The user prefers an unrelated supplement brand.",
            "evidence": "synthetic rationale",
            "source": "synthetic_hard_a",
            "memory_type": "preference",
            "u_star": "A",
            "subtype": "untriggered_preference",
            "hard_a_family": "untriggered_preference",
            "usage_rubric": {"memory_usage_weight": "none", "correct_use": "Leave no footprint."},
        },
    ],
    "qc": {
        "atomicity_pass": True,
        "duplicate_pass": True,
        "question_memory_leakage_pass": True,
        "hard_a_target_consistency_pass": True,
        "rubric_objectivity_pass": True,
        "counterfactual_pass": "pending_model_test",
        "manual_audit": "not_sampled",
    },
    "split": "clean",
}


class FormalBenchmarkAnalysisTest(unittest.TestCase):
    def setUp(self) -> None:
        self.analysis = load_analysis()

    def test_quantile_uses_linear_interpolation(self) -> None:
        self.assertEqual(2.5, self.analysis.quantile([1, 2, 3, 4], 0.5))
        self.assertEqual(1.0, self.analysis.quantile([1], 0.99))

    def test_sample_aggregation_counts_labels_and_mixed_parent(self) -> None:
        state = self.analysis.new_state()
        self.analysis.update_state(state, FIXTURE_SAMPLE, seed_complexity="medium")
        result = self.analysis.finalize_state(state)

        self.assertEqual(1, result["headline"]["samples"])
        self.assertEqual(2, result["headline"]["parent_memories"])
        self.assertEqual(3, result["headline"]["atomic_memories"])
        self.assertEqual(1, result["headline"]["mixed_parents"])
        self.assertEqual({"A": 1, "B": 1, "C": 1}, result["counts"]["labels"])
        self.assertEqual({"medium": 1}, result["counts"]["seed_complexity"])
        self.assertEqual(1 / 3, result["headline"]["synthetic_atomic_share"])

    def test_artifact_has_report_title_chart_and_bounded_snapshot(self) -> None:
        state = self.analysis.new_state()
        self.analysis.update_state(state, FIXTURE_SAMPLE, seed_complexity="medium")
        aggregate = self.analysis.finalize_state(state)
        aggregate["funnel"] = [{"stage": "Formal benchmark", "count": 1, "retention": 1.0, "rank": 1}]
        aggregate["reconciliation"] = {"status": "passed"}

        artifact = self.analysis.build_artifact(aggregate, "2026-07-12T00:00:00+08:00")

        title = artifact["manifest"]["title"]
        self.assertEqual("report", artifact["surface"])
        self.assertEqual(f"# {title}", artifact["manifest"]["blocks"][0]["body"])
        self.assertTrue(any(block["type"] == "chart" for block in artifact["manifest"]["blocks"]))
        self.assertLessEqual(max(len(rows) for rows in artifact["snapshot"]["datasets"].values()), 2000)
        source_query = artifact["sources"][0]["query"]
        self.assertIn("read_json_auto", source_query["sql"])
        self.assertEqual("duckdb", source_query["engine"])


if __name__ == "__main__":
    unittest.main()
