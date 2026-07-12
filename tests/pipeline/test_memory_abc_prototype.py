#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "pipeline" / "07_build_memory_abc_prototype.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("memory_abc_prototype", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class MemoryAbcPrototypeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = load_builder()

    def test_convert_record_preserves_atom_labels_and_marks_mixed_block(self) -> None:
        record = {
            "id": "rec_1",
            "source_dataset": "source_a",
            "source_split": "train",
            "topic": "travel",
            "question": "Plan a three-day food itinerary in Tokyo.",
            "preferences": [
                {
                    "preference": "The user has a severe peanut allergy.",
                    "u_star": "C",
                    "reason": "Ignoring this would make the itinerary unsafe.",
                    "source": "from_question",
                    "verify_reason": "A severe allergy must constrain food choices.",
                    "boundary_case": "none",
                },
                {
                    "preference": "The user likes quiet neighborhood restaurants.",
                    "u_star": "B",
                    "reason": "This improves recommendations but is not required.",
                    "source": "soft_preference_synthetic",
                },
                {
                    "preference": "The user works as a software engineer.",
                    "u_star": "A",
                    "reason": "This is unrelated to the itinerary.",
                    "source": "easy_a_synthetic",
                },
            ],
        }

        sample = self.builder.convert_record(record, 7)

        self.assertEqual("memabc_000007", sample["sample_id"])
        self.assertEqual(record["question"], sample["query"])
        self.assertIn("The user has a severe peanut allergy.", sample["memory_block"])
        self.assertEqual({"A": 1, "B": 1, "C": 1}, sample["block_composition"]["label_counts"])
        self.assertTrue(sample["block_composition"]["mixed_label"])
        self.assertIn("mixed_label_block", sample["diagnostic_tags"])
        self.assertEqual(["necessary", "auxiliary", "non_applicable"], [atom["relation"] for atom in sample["atoms"]])
        self.assertEqual(["constraint", "preference", "profile_fact"], [atom["atom_type"] for atom in sample["atoms"]])

    def test_select_diverse_records_round_robins_topics(self) -> None:
        records = []
        for idx, topic in enumerate(["alpha", "alpha", "beta", "beta", "gamma"]):
            records.append({"id": f"r{idx}", "topic": topic, "preferences": [{"preference": "x", "u_star": "A"}]})

        selected = self.builder.select_diverse_records(records, limit=4, seed=3)

        self.assertEqual(4, len(selected))
        self.assertGreaterEqual(len({row["topic"] for row in selected}), 3)
        self.assertEqual([row["id"] for row in selected], [row["id"] for row in self.builder.select_diverse_records(records, limit=4, seed=3)])

    def test_infer_atom_type_handles_medical_history_and_chinese_counter_words(self) -> None:
        self.assertEqual("safety_sensitive", self.builder.infer_atom_type("用户有10年糖尿病史，近期血糖控制不佳。"))
        self.assertEqual("episodic_fact", self.builder.infer_atom_type("用户最近刚领养了一只两个月大的幼猫。"))

    def test_build_html_escapes_content(self) -> None:
        sample = {
            "sample_id": "s1",
            "query": "<script>alert(1)</script>",
            "memory_block": "safe memory",
            "block_composition": {"label_counts": {"A": 1}, "mixed_label": False, "atom_count": 1},
            "diagnostic_tags": [],
            "source": {"topic": "topic"},
            "atoms": [
                {
                    "atom_id": "a1",
                    "atom_text": "<b>atom</b>",
                    "label": "A",
                    "relation": "non_applicable",
                    "atom_type": "profile_fact",
                    "rationale": "irrelevant",
                }
            ],
        }

        html = self.builder.build_html([sample], {"total_samples": 1})

        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertIn("&lt;b&gt;atom&lt;/b&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)


if __name__ == "__main__":
    unittest.main()
