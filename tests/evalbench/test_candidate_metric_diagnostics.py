import unittest

from evaluation.scripts.plot_candidate_metric_diagnostics import (
    build_tail_profiles,
    build_visualization_data,
    render_fragment,
)


class CandidateMetricDiagnosticsTest(unittest.TestCase):
    def test_tail_profile_uses_worst_ten_percent_of_full_memory_samples(self) -> None:
        rows = []
        for sample_index in range(500):
            rows.append(
                {
                    "model_key": "model",
                    "condition": "full_memory",
                    "sample_id": f"s{sample_index:02d}",
                    "atom_judgments": [
                        {
                            "u_star": "A",
                            "predicted_usage_level": (
                                "C" if sample_index >= 450 else "A"
                            ),
                            "scorable": True,
                        }
                    ],
                }
            )
            rows.append(
                {
                    "model_key": "model",
                    "condition": "no_memory",
                    "sample_id": f"s{sample_index:02d}",
                    "atom_judgments": [
                        {
                            "u_star": "A",
                            "predicted_usage_level": "C",
                            "scorable": True,
                        }
                    ],
                }
            )

        profile = build_tail_profiles(rows)["model"]
        self.assertEqual(500, profile["samples"])
        self.assertEqual(50, profile["tail_samples"])
        self.assertAlmostEqual(1.0, profile["cvar90"])
        self.assertAlmostEqual(0.1, profile["mean"])

    def test_visualization_ranks_lower_cvar_as_better(self) -> None:
        def model(h: float, cvar: float) -> dict:
            return {
                "display_name": "model",
                "standard": {
                    "full_memory": {
                        "opb_error_rate": 0.2,
                        "upb_error_rate": 0.3,
                    }
                },
                "classification": {
                    "multiclass_mcc": h,
                    "linear_weighted_kappa": h,
                    "quadratic_weighted_kappa": h,
                },
                "composites": {
                    "harmonic_h": h,
                    "mincalib": h,
                },
                "sample_risk": {
                    "linear_loss": {"cvar90": cvar},
                    "strict_sample_accuracy": h,
                },
                "paired_utility": {"pmu_lambda_1_0": h},
            }

        metrics = {"models": {"strong": model(0.8, 0.2), "weak": model(0.4, 0.7)}}
        profile = {
            "samples": 500,
            "tail_samples": 50,
            "mean": 0.1,
            "p80": 0.1,
            "p90": 0.2,
            "p95": 0.3,
            "cvar90": 0.2,
            "cvar95": 0.3,
            "maximum": 0.5,
            "tail_severe_sample_rate": 0.0,
            "tail_severe_atom_rate": 0.0,
            "tail_mean_atom_count": 3.0,
            "quantile_curve": [
                {"percentile": 70.0, "loss": 0.1},
                {"percentile": 100.0, "loss": 0.5},
            ],
        }
        data = build_visualization_data(
            metrics,
            {"strong": profile, "weak": {**profile, "cvar90": 0.7}},
        )
        by_key = {item["key"]: item for item in data["models"]}
        self.assertEqual(1, by_key["strong"]["ranks"]["cvar90"])
        self.assertEqual(2, by_key["weak"]["ranks"]["cvar90"])
        self.assertEqual(1, by_key["strong"]["ranks"]["h"])

    def test_fragment_is_self_contained_and_accessible(self) -> None:
        fragment = render_fragment(
            {
                "models": [],
                "metric_columns": [],
                "tail_definition": {},
            }
        )
        self.assertIn('id="memcalib-metric-diagnostics"', fragment)
        self.assertIn('role="img"', fragment)
        self.assertIn("application/json", fragment)
        self.assertNotIn("fetch(", fragment)
        self.assertNotIn("<!doctype", fragment.lower())


if __name__ == "__main__":
    unittest.main()
