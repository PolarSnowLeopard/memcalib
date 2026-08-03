from __future__ import annotations

import unittest

from evaluation.scripts.aggregate_repeated_evaluations import OFFICIAL_FIELDS, SAMPLE_FIELDS, aggregate


class RepeatedEvaluationAggregationTests(unittest.TestCase):
    def test_aggregate_preserves_repeat_values_and_population_statistics(self) -> None:
        repeats = []
        for index, value in enumerate((0.2, 0.4, 0.6), start=1):
            cell = {field: value for field in OFFICIAL_FIELDS + SAMPLE_FIELDS}
            repeats.append(
                {
                    "label": f"repeat-{index}",
                    "official": {"path": f"official-{index}", "sha256": str(index)},
                    "sample_level": {"path": f"sample-{index}", "sha256": str(index)},
                    "rows": {"model-a": {"full_memory": dict(cell), "no_memory": dict(cell)}},
                }
            )

        result = aggregate(repeats)
        metric = result["models"]["model-a"]["full_memory"]["scs_0_5"]

        self.assertEqual(result["repeat_count"], 3)
        self.assertAlmostEqual(metric["mean"], 0.4)
        self.assertAlmostEqual(metric["population_sd"], 0.1632993161855452)
        self.assertEqual(metric["minimum"], 0.2)
        self.assertEqual(metric["maximum"], 0.6)
        self.assertEqual(
            result["models"]["model-a"]["full_memory"]["repeat_values"]["repeat-2"]["scs_0_5"],
            0.4,
        )

    def test_aggregate_rejects_mismatched_model_sets(self) -> None:
        cell = {field: 0.5 for field in OFFICIAL_FIELDS + SAMPLE_FIELDS}
        first = {
            "label": "repeat-1",
            "official": {},
            "sample_level": {},
            "rows": {"model-a": {"full_memory": cell, "no_memory": cell}},
        }
        second = {
            "label": "repeat-2",
            "official": {},
            "sample_level": {},
            "rows": {"model-b": {"full_memory": cell, "no_memory": cell}},
        }

        with self.assertRaisesRegex(ValueError, "model sets differ"):
            aggregate([first, second])


if __name__ == "__main__":
    unittest.main()
