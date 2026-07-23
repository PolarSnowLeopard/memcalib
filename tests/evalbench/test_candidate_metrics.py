import unittest

from evaluation.scripts.analyze_candidate_metrics import (
    bootstrap_candidate_intervals,
    classification_metrics,
    composite_metrics,
    fit_bradley_terry,
    fit_rasch,
    ordinal_metrics,
    sample_risk_metrics,
    validate_input,
)


class CandidateMetricsTest(unittest.TestCase):
    def test_identity_confusion_is_perfect(self) -> None:
        confusion = {
            "A": {"A": 2, "B": 0, "C": 0},
            "B": {"A": 0, "B": 2, "C": 0},
            "C": {"A": 0, "B": 0, "C": 2},
        }
        classification = classification_metrics(confusion)
        ordinal = ordinal_metrics(confusion)
        self.assertEqual(1.0, classification["atom_exact_accuracy"])
        self.assertEqual(1.0, classification["multiclass_mcc"])
        self.assertEqual(1.0, classification["linear_weighted_kappa"])
        self.assertEqual(0.0, ordinal["ordinal_mae"])
        self.assertEqual(0.0, ordinal["severe_two_step_atom_error_rate"])

    def test_composites_penalize_the_weaker_direction(self) -> None:
        metrics = composite_metrics(0.2, 0.4)
        self.assertAlmostEqual(0.6, metrics["mincalib"])
        self.assertGreater(metrics["harmonic_h"], metrics["mincalib"])
        self.assertGreater(metrics["softmin_p_minus_2"], metrics["mincalib"])
        self.assertGreater(
            metrics["softmin_p_minus_2"], metrics["softmin_p_minus_8"]
        )

    def test_sample_tail_risk(self) -> None:
        atoms = [
            {
                "sample_id": "s1",
                "gold": "A",
                "predicted": "A",
            },
            {
                "sample_id": "s2",
                "gold": "A",
                "predicted": "C",
            },
        ]
        metrics, losses = sample_risk_metrics(atoms)
        self.assertEqual({"s1": 0.0, "s2": 1.0}, losses)
        self.assertAlmostEqual(0.5, metrics["strict_sample_accuracy"])
        self.assertAlmostEqual(0.5, metrics["severe_two_step_sample_rate"])
        self.assertAlmostEqual(1.0, metrics["linear_loss"]["cvar90"])

    def test_bradley_terry_orders_consistent_winner(self) -> None:
        comparisons = [
            {
                "left": "strong",
                "right": "weak",
                "samples": 100,
                "left_wins": 80,
                "ties": 0,
                "right_wins": 20,
            }
        ]
        result = fit_bradley_terry(comparisons)
        self.assertGreater(result["strong"]["ability"], result["weak"]["ability"])

    def test_rasch_orders_model_abilities(self) -> None:
        atoms = []
        for item in range(20):
            atoms.append(
                {
                    "sample_id": f"s{item}",
                    "atom_id": "a",
                    "model_key": "strong",
                    "gold": "A",
                    "predicted": "A",
                }
            )
            atoms.append(
                {
                    "sample_id": f"s{item}",
                    "atom_id": "a",
                    "model_key": "weak",
                    "gold": "A",
                    "predicted": "C" if item < 15 else "A",
                }
            )
        result = fit_rasch(atoms, ["strong", "weak"], direction="over")
        self.assertTrue(result["converged"])
        self.assertGreater(
            result["model_abilities"]["strong"]["theta"],
            result["model_abilities"]["weak"]["theta"],
        )

    def test_bootstrap_candidate_intervals_cluster_samples(self) -> None:
        atoms = []
        for sample_id, predicted in (("s1", "A"), ("s2", "C")):
            for condition in ("full_memory", "no_memory"):
                atoms.extend(
                    {
                        "sample_id": sample_id,
                        "atom_id": atom_id,
                        "condition": condition,
                        "gold": gold,
                        "predicted": predicted if gold == "A" else gold,
                    }
                    for atom_id, gold in (("a", "A"), ("b", "B"), ("c", "C"))
                )
        result = bootstrap_candidate_intervals(atoms, replicates=50, seed=7)
        self.assertEqual(2, result["H"]["clusters"])
        self.assertEqual(50, result["H"]["replicates"])
        self.assertLessEqual(result["H"]["ci_low"], result["H"]["ci_high"])

    def test_bootstrap_candidate_intervals_supports_full_memory_only(self) -> None:
        atoms = []
        for sample_id, predicted in (("s1", "A"), ("s2", "C")):
            atoms.extend(
                {
                    "sample_id": sample_id,
                    "atom_id": atom_id,
                    "condition": "full_memory",
                    "gold": gold,
                    "predicted": predicted if gold == "A" else gold,
                }
                for atom_id, gold in (("a", "A"), ("b", "B"), ("c", "C"))
            )

        result = bootstrap_candidate_intervals(atoms, replicates=50, seed=7)

        self.assertEqual(2, result["H"]["clusters"])
        self.assertNotIn("pmu_lambda_1_0", result)

    def test_validate_input_requires_identical_samples(self) -> None:
        rows = []
        for model in ("m1", "m2"):
            for condition in ("full_memory", "no_memory"):
                rows.append(
                    {
                        "answer_request_id": f"{model}:{condition}:s1",
                        "model_key": model,
                        "condition": condition,
                        "sample_id": "s1",
                        "atom_judgments": [
                            {
                                "atom_id": "a",
                                "u_star": "A",
                                "scorable": True,
                            }
                        ],
                    }
                )
        result = validate_input(rows)
        self.assertEqual(4, result["unique_answer_request_ids"])
        self.assertEqual(1, result["samples_per_bucket"])
        self.assertTrue(result["atom_signatures_consistent"])


if __name__ == "__main__":
    unittest.main()
