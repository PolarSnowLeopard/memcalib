import unittest

from evaluation.scripts.summarize_three_layer_metrics import (
    methodology_markdown,
    paired_delta_bootstrap,
)


def sample_row(sample_id: str, over: int, under: int) -> dict:
    return {
        "sample_id": sample_id,
        "over_budget": over,
        "under_budget": under,
        "sample_any_opb": int(over > 0),
        "sample_any_upb": int(under > 0),
        "sample_exact": int(over + under == 0),
        "scs_rho_0_5": 0.5 ** (over + under),
    }


class ThreeLayerMetricSummaryTests(unittest.TestCase):
    def test_paired_delta_preserves_direction(self) -> None:
        before = {
            "a": sample_row("a", 2, 0),
            "b": sample_row("b", 1, 1),
            "c": sample_row("c", 0, 0),
        }
        after = {
            "a": sample_row("a", 0, 1),
            "b": sample_row("b", 0, 2),
            "c": sample_row("c", 0, 0),
        }
        result = paired_delta_bootstrap(
            before,
            after,
            replicates=200,
            seed=11,
        )
        self.assertEqual(result["samples"], 3)
        self.assertGreater(result["metrics"]["scs"]["estimate"], 0)
        self.assertLess(result["metrics"]["directional_opb"]["estimate"], 0)
        self.assertGreater(result["metrics"]["directional_upb"]["estimate"], 0)

    def test_paired_delta_requires_identical_samples(self) -> None:
        with self.assertRaisesRegex(ValueError, "identical sample IDs"):
            paired_delta_bootstrap(
                {"a": sample_row("a", 0, 0)},
                {"b": sample_row("b", 0, 0)},
                replicates=10,
                seed=3,
            )

    def test_methodology_defines_sample_and_atom_indices(self) -> None:
        report = "\n".join(methodology_markdown())
        self.assertIn("### 1. 评估单位、索引集合与符号", report)
        self.assertIn("$s\\in\\mathcal S$", report)
        self.assertIn("每个 $i=(b,j)$", report)
        self.assertIn("\\sum_{i\\in\\mathcal I_s}", report)
        self.assertNotIn("\\sum_{i\\in s}", report)
        self.assertEqual(report.count("$$") % 2, 0)


if __name__ == "__main__":
    unittest.main()
