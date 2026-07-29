import unittest

from evaluation.scripts.analyze_sample_level_calibration import (
    bootstrap_headline_metrics,
    budget_distribution,
    harmonic_resistance,
    score_judgment_row,
    summarize_scores,
)


class SampleLevelCalibrationTests(unittest.TestCase):
    def test_score_judgment_row_accumulates_direction_and_severity(self) -> None:
        row = {
            "answer_request_id": "answer-1",
            "sample_id": "sample-1",
            "model_key": "model",
            "condition": "full_memory",
            "atom_judgments": [
                {"u_star": "A", "predicted_usage_level": "B", "scorable": True},
                {"u_star": "B", "predicted_usage_level": "C", "scorable": True},
                {"u_star": "C", "predicted_usage_level": "A", "scorable": True},
                {"u_star": "A", "predicted_usage_level": None, "scorable": False},
            ],
        }
        scored = score_judgment_row(
            row,
            mode="thinking",
            metadata={"sample-1": {"domain": "general", "difficulty": "level_2"}},
            rhos=(0.25, 0.5, 0.75),
        )
        self.assertEqual(scored["atom_count"], 3)
        self.assertEqual(scored["over_budget"], 2)
        self.assertEqual(scored["under_budget"], 2)
        self.assertEqual(scored["total_budget"], 4)
        self.assertEqual(scored["sample_any_opb"], 1)
        self.assertEqual(scored["sample_any_upb"], 1)
        self.assertEqual(scored["sample_exact"], 0)
        self.assertEqual(scored["severe_two_step"], 1)
        self.assertAlmostEqual(scored["scs_rho_0_5"], 0.5**4)

    def test_exact_answer_has_unit_score(self) -> None:
        row = {
            "answer_request_id": "answer-2",
            "sample_id": "sample-2",
            "model_key": "model",
            "condition": "full_memory",
            "atom_judgments": [
                {"u_star": "A", "predicted_usage_level": "A"},
                {"u_star": "B", "predicted_usage_level": "B"},
                {"u_star": "C", "predicted_usage_level": "C"},
            ],
        }
        scored = score_judgment_row(
            row,
            mode="thinking",
            metadata={"sample-2": {"domain": "coding", "difficulty": "level_1"}},
            rhos=(0.5,),
        )
        self.assertEqual(scored["sample_exact"], 1)
        self.assertEqual(scored["sample_any_error"], 0)
        self.assertEqual(scored["scs_rho_0_5"], 1.0)

    def test_summary_uses_equal_sample_weight(self) -> None:
        rows = [
            {
                "atom_count": 2,
                "sample_any_opb": 0,
                "sample_any_upb": 0,
                "sample_any_error": 0,
                "sample_exact": 1,
                "severe_two_step": 0,
                "over_budget": 0,
                "under_budget": 0,
                "total_budget": 0,
                "scs_rho_0_5": 1.0,
            },
            {
                "atom_count": 20,
                "sample_any_opb": 1,
                "sample_any_upb": 0,
                "sample_any_error": 1,
                "sample_exact": 0,
                "severe_two_step": 0,
                "over_budget": 1,
                "under_budget": 0,
                "total_budget": 1,
                "scs_rho_0_5": 0.5,
            },
        ]
        summary = summarize_scores(rows, (0.5,))
        self.assertEqual(summary["samples"], 2)
        self.assertEqual(summary["atoms"], 22)
        self.assertEqual(summary["sample_any_opb_rate"], 0.5)
        self.assertEqual(summary["sample_exact_accuracy"], 0.5)
        self.assertEqual(summary["scs"]["0.5"]["mean"], 0.75)
        self.assertEqual(summary["directional_risk"]["0.5"]["opb"], 0.25)
        self.assertEqual(summary["directional_risk"]["0.5"]["upb"], 0.0)
        self.assertEqual(summary["event_guardrail"]["opb"], 0.5)

    def test_harmonic_resistance_uses_directional_resistance(self) -> None:
        self.assertAlmostEqual(
            harmonic_resistance(0.25, 0.5),
            2 * 0.75 * 0.5 / (0.75 + 0.5),
        )

    def test_bootstrap_is_deterministic_and_contains_estimate(self) -> None:
        rows = [
            {
                "over_budget": over,
                "under_budget": under,
                "sample_any_opb": int(over > 0),
                "sample_any_upb": int(under > 0),
                "sample_exact": int(over + under == 0),
                "scs_rho_0_5": 0.5 ** (over + under),
            }
            for over, under in [(0, 0), (1, 0), (0, 2), (2, 1)]
        ]
        first = bootstrap_headline_metrics(
            rows, rho=0.5, replicates=200, seed=17
        )
        second = bootstrap_headline_metrics(
            rows, rho=0.5, replicates=200, seed=17
        )
        self.assertEqual(first, second)
        for values in first.values():
            self.assertLessEqual(values["ci_low"], values["estimate"])
            self.assertGreaterEqual(values["ci_high"], values["estimate"])

    def test_budget_distribution_has_stable_bins(self) -> None:
        distribution = budget_distribution([0, 1, 2, 3, 4, 5, 9])
        self.assertEqual(distribution["0"]["count"], 1)
        self.assertEqual(distribution["5_plus"]["count"], 2)
        self.assertAlmostEqual(
            sum(value["share"] for value in distribution.values()), 1.0
        )


if __name__ == "__main__":
    unittest.main()
