#!/usr/bin/env python3
from __future__ import annotations

import unittest

from evaluation.scripts.analyze_evaluation import (
    assess_benchmark_validity,
    cohen_kappa,
    compute_judge_output_quality,
    compute_judge_agreement,
    compute_metrics,
    linear_weighted_kappa,
    paired_bootstrap,
    render_report,
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
    def test_judge_output_quality_separates_warnings_from_repairs(self) -> None:
        rows = [
            {
                "validation_warnings": ["invalid_confidence:a1", "ungrounded_evidence_quote:a2"],
                "schema_repairs": ["a1:correct_bounded_use->correct_control"],
            },
            {"validation_warnings": ["invalid_confidence:a3"], "schema_repairs": []},
        ]

        quality = compute_judge_output_quality(rows)

        self.assertEqual(2, quality["rows_with_warnings"])
        self.assertEqual({"invalid_confidence": 2, "ungrounded_evidence_quote": 1}, quality["warning_counts"])
        self.assertEqual(1, quality["rows_with_schema_repairs"])
        self.assertEqual(1, quality["schema_repairs"])

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

        samples = [
            {
                "id": sample_id,
                "memory_blocks": [{"parent_memory_id": "p1", "parent_label_mode": "mixed"}],
                "memories": [
                    {"atom_id": "a", "parent_memory_id": "p1"},
                    {"atom_id": "b", "parent_memory_id": "p1"},
                    {"atom_id": "c", "parent_memory_id": "p1"},
                ],
            }
            for sample_id in ("s1", "s2")
        ]

        metrics = compute_metrics(rows, samples=samples)
        model = metrics["models"]["m1"]

        self.assertAlmostEqual(0.5, model["full_memory"]["label_success"]["A"])
        self.assertAlmostEqual(1.0, model["full_memory"]["label_success"]["B"])
        self.assertAlmostEqual(0.5, model["full_memory"]["label_success"]["C"])
        self.assertAlmostEqual(2 / 3, model["full_memory"]["memcalib_score"])
        self.assertAlmostEqual(1.0, model["paired"]["delta_B"])
        self.assertAlmostEqual(0.5, model["paired"]["delta_C"])
        self.assertAlmostEqual(0.5, model["paired"]["A_contamination_effect"])
        self.assertAlmostEqual(0.5, model["full_memory"]["strict_sample_accuracy"])
        self.assertAlmostEqual(0.5, model["full_memory"]["mixed_parent_strict_accuracy"])
        self.assertAlmostEqual(0.25, model["full_memory"]["opb_error_rate"])
        self.assertAlmostEqual(0.25, model["full_memory"]["upb_error_rate"])
        self.assertAlmostEqual(0.75, model["full_memory"]["opb_resistance"])
        self.assertAlmostEqual(0.75, model["full_memory"]["upb_resistance"])
        self.assertAlmostEqual(0.75, model["full_memory"]["memcalib_h_score"])
        self.assertAlmostEqual(0.25, model["paired"]["memory_induced_opb"])
        self.assertAlmostEqual(0.75, model["paired"]["memory_reduced_upb"])
        self.assertFalse(model["full_memory"]["full_confusion_available"])

    def test_ordered_usage_levels_produce_complete_confusion_matrix(self) -> None:
        rows = [
            judgment(
                "s1",
                "full_memory",
                [
                    ("a", "A", "over_use"),
                    ("b", "B", "correct_bounded_use"),
                    ("c", "C", "under_use"),
                ],
            )
        ]
        predictions = {"a": "C", "b": "B", "c": "A"}
        for atom in rows[0]["atom_judgments"]:
            atom["predicted_usage_level"] = predictions[atom["atom_id"]]
            atom["scorable"] = True
            atom["contradiction"] = False

        condition = compute_metrics(rows)["models"]["m1"]["full_memory"]

        self.assertTrue(condition["full_confusion_available"])
        self.assertEqual(1, condition["confusion_matrix"]["A"]["C"])
        self.assertEqual(1, condition["confusion_matrix"]["B"]["B"])
        self.assertEqual(1, condition["confusion_matrix"]["C"]["A"])

    def test_cohen_kappa_handles_agreement_beyond_chance(self) -> None:
        first = ["pass", "pass", "fail", "fail"]
        second = ["pass", "pass", "fail", "pass"]

        result = cohen_kappa(first, second)

        self.assertAlmostEqual(0.75, result["exact_agreement"])
        self.assertAlmostEqual(0.5, result["kappa"])

    def test_linear_weighted_kappa_respects_ordered_usage_distance(self) -> None:
        result = linear_weighted_kappa(
            ["A", "A", "C", "C"],
            ["A", "B", "C", "B"],
        )

        self.assertEqual(4, result["n"])
        self.assertAlmostEqual(0.5, result["exact_agreement"])
        self.assertAlmostEqual(0.5, result["linear_weighted_kappa"])

    def test_judge_agreement_prefers_ordered_usage_fields_when_available(self) -> None:
        primary = [
            judgment(
                "s1",
                "full_memory",
                [("a", "A", "correct_suppression"), ("b", "B", "correct_bounded_use"), ("c", "C", "correct_control")],
            )
        ]
        secondary = [
            judgment(
                "s1",
                "full_memory",
                [("a", "A", "correct_suppression"), ("b", "B", "over_use"), ("c", "C", "correct_control")],
            )
        ]
        secondary[0]["judge_model"] = "judge-2"
        for atom, prediction in zip(primary[0]["atom_judgments"], ("A", "B", "C")):
            atom.update(predicted_usage_level=prediction, scorable=True, contradiction=False)
        for atom, prediction in zip(secondary[0]["atom_judgments"], ("A", "C", "C")):
            atom.update(predicted_usage_level=prediction, scorable=True, contradiction=False)

        agreement = compute_judge_agreement(primary, secondary)

        self.assertEqual(3, agreement["ordered_usage"]["n"])
        self.assertAlmostEqual(2 / 3, agreement["ordered_usage"]["exact_agreement"])
        self.assertEqual(1.0, agreement["scorable_exact_agreement"])

    def test_paired_bootstrap_is_deterministic(self) -> None:
        values = [("s1", 1.0), ("s1", 0.0), ("s2", -1.0), ("s3", 0.5)]

        first = paired_bootstrap(values, replicates=200, seed=20260712)
        second = paired_bootstrap(values, replicates=200, seed=20260712)

        self.assertEqual(first, second)
        self.assertAlmostEqual(0.125, first["estimate"])
        self.assertLessEqual(first["ci_low"], first["estimate"])
        self.assertGreaterEqual(first["ci_high"], first["estimate"])

    def test_directional_bootstrap_is_clustered_and_deterministic(self) -> None:
        rows = [
            judgment("s1", "full_memory", [("a", "A", "correct_suppression"), ("b", "B", "over_use"), ("c", "C", "correct_control")]),
            judgment("s1", "no_memory", [("a", "A", "correct_suppression"), ("b", "B", "under_use"), ("c", "C", "under_use")]),
            judgment("s2", "full_memory", [("a", "A", "over_use"), ("b", "B", "correct_bounded_use"), ("c", "C", "under_use")]),
            judgment("s2", "no_memory", [("a", "A", "correct_suppression"), ("b", "B", "under_use"), ("c", "C", "under_use")]),
        ]

        first = compute_metrics(rows, bootstrap_replicates=100, seed=9)
        second = compute_metrics(rows, bootstrap_replicates=100, seed=9)
        directional = first["models"]["m1"]["bootstrap"]["directional"]

        self.assertEqual(first, second)
        self.assertEqual(2, directional["full_memory"]["memcalib_h_score"]["clusters"])
        self.assertIn("memory_induced_opb", directional["paired"])

    def test_validity_assessment_requires_discrimination_and_judge_agreement(self) -> None:
        metrics = {
            "models": {
                f"m{index}": {
                    "full_memory": {"memcalib_score": 0.55 + index * 0.03},
                    "no_memory": {"answers": 1},
                    "paired": {"memory_reduced_upb": 0.10 if index < 4 else -0.01},
                }
                for index in range(5)
            },
            "judge_agreement": {"overall": {"exact_agreement": 0.8, "kappa": 0.65}},
        }

        assessment = assess_benchmark_validity(metrics)

        self.assertEqual("provisionally_supported", assessment["status"])
        self.assertEqual([], assessment["failed_checks"])

    def test_validity_assessment_keeps_narrow_macro_spread_as_a_caveat(self) -> None:
        label_profiles = [
            {"A": 0.46, "B": 0.75, "C": 0.83},
            {"A": 0.57, "B": 0.68, "C": 0.80},
            {"A": 0.51, "B": 0.69, "C": 0.78},
            {"A": 0.54, "B": 0.70, "C": 0.83},
            {"A": 0.48, "B": 0.71, "C": 0.80},
        ]
        metrics = {
            "models": {
                f"m{index}": {
                    "full_memory": {
                        "memcalib_score": 0.66 + index * 0.0065,
                        "label_success": profile,
                    },
                    "no_memory": {"answers": 1},
                    "paired": {"memory_reduced_upb": 0.30},
                }
                for index, profile in enumerate(label_profiles)
            },
            "judge_agreement": {"overall": {"exact_agreement": 0.88, "kappa": 0.84}},
        }

        assessment = assess_benchmark_validity(metrics)

        self.assertEqual("provisionally_supported_with_caveat", assessment["status"])
        self.assertEqual([], assessment["failed_checks"])
        self.assertIn("limited_single_score_discrimination", assessment["caveats"])
        self.assertAlmostEqual(0.11, assessment["max_label_profile_spread"])

    def test_report_contains_paired_panel_and_judge_sections(self) -> None:
        rows = [
            judgment(
                "s1",
                condition,
                [("a", "A", "correct_suppression"), ("b", "B", "correct_bounded_use"), ("c", "C", "correct_control")],
            )
            for condition in ("full_memory", "no_memory")
        ]
        metrics = compute_metrics(rows)
        metrics["judge_agreement"] = {"n": 0}
        metrics["validity_assessment"] = {"status": "pending", "failed_checks": ["judge_agreement"]}

        report = render_report(metrics)

        self.assertIn("OPB", report)
        self.assertIn("UPB", report)
        self.assertIn("配对因果诊断", report)
        self.assertIn("面板比较", report)
        self.assertIn("Judge 一致性", report)


if __name__ == "__main__":
    unittest.main()
