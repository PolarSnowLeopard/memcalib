#!/usr/bin/env python3
from __future__ import annotations

import unittest

from evaluation.scripts.analyze_evaluation import (
    cohen_kappa,
    compute_metrics,
    paired_bootstrap,
)


def judgment(sample: str, condition: str, verdicts: list[tuple[str, str, str]]) -> dict:
    return {
        "answer_request_id": f"answer:m1:{condition}:{sample}",
        "sample_id": sample,
        "panel": "representative",
        "condition": condition,
        "model_key": "m1",
        "answer_model": "model-1",
        "judge_role": "primary",
        "judge_model": "judge-1",
        "atom_judgments": [
            {
                "atom_id": atom_id,
                "u_star": label,
                "verdict": verdict,
                "evidence_quote": "",
                "reason": "reason",
                "confidence": 0.9,
            }
            for atom_id, label, verdict in verdicts
        ],
        "task_quality": 3,
        "safety_failure": False,
    }


class AnalysisTest(unittest.TestCase):
    def test_compute_metrics_uses_label_macro_and_paired_effects(self) -> None:
        rows = [
            judgment(
                "s1",
                "full_memory",
                [
                    ("a", "A", "correct_suppression"),
                    ("b", "B", "correct_bounded_use"),
                    ("c", "C", "correct_control"),
                ],
            ),
            judgment(
                "s1",
                "no_memory",
                [
                    ("a", "A", "correct_suppression"),
                    ("b", "B", "under_use"),
                    ("c", "C", "under_use"),
                ],
            ),
            judgment(
                "s2",
                "full_memory",
                [
                    ("a", "A", "over_use"),
                    ("b", "B", "correct_bounded_use"),
                    ("c", "C", "under_use"),
                ],
            ),
            judgment(
                "s2",
                "no_memory",
                [
                    ("a", "A", "correct_suppression"),
                    ("b", "B", "under_use"),
                    ("c", "C", "under_use"),
                ],
            ),
        ]

        metrics = compute_metrics(rows)
        model = metrics["models"]["m1"]

        self.assertAlmostEqual(0.5, model["full_memory"]["label_success"]["A"])
        self.assertAlmostEqual(1.0, model["full_memory"]["label_success"]["B"])
        self.assertAlmostEqual(0.5, model["full_memory"]["label_success"]["C"])
        self.assertAlmostEqual(2 / 3, model["full_memory"]["memcalib_score"])
        self.assertAlmostEqual(1.0, model["paired"]["delta_B"])
        self.assertAlmostEqual(0.5, model["paired"]["delta_C"])
        self.assertAlmostEqual(0.5, model["paired"]["A_contamination_effect"])
        self.assertAlmostEqual(0.5, model["full_memory"]["strict_sample_accuracy"])

    def test_cohen_kappa_handles_agreement_beyond_chance(self) -> None:
        first = ["pass", "pass", "fail", "fail"]
        second = ["pass", "pass", "fail", "pass"]

        result = cohen_kappa(first, second)

        self.assertAlmostEqual(0.75, result["exact_agreement"])
        self.assertAlmostEqual(0.5, result["kappa"])

    def test_paired_bootstrap_is_deterministic(self) -> None:
        values = [("s1", 1.0), ("s1", 0.0), ("s2", -1.0), ("s3", 0.5)]

        first = paired_bootstrap(values, replicates=200, seed=20260712)
        second = paired_bootstrap(values, replicates=200, seed=20260712)

        self.assertEqual(first, second)
        self.assertAlmostEqual(0.125, first["estimate"])
        self.assertLessEqual(first["ci_low"], first["estimate"])
        self.assertGreaterEqual(first["ci_high"], first["estimate"])


if __name__ == "__main__":
    unittest.main()
