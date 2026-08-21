from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evaluation.scripts.aggregate_repeated_candidate_metrics import (
    aggregate,
    flatten_numeric,
)


class RepeatedCandidateMetricAggregationTest(unittest.TestCase):
    def test_flattens_metrics_but_not_display_or_bootstrap_intervals(self) -> None:
        values = {
            "display_name": "Model",
            "standard": {"full_memory": {"h": 0.8}},
            "bootstrap_ci95": {"H": [0.7, 0.9]},
            "flag": True,
        }

        self.assertEqual(
            {"standard.full_memory.h": 0.8},
            flatten_numeric(values),
        )

    def test_aggregates_every_shared_scalar_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repeats = []
            for index, value in enumerate((0.2, 0.4, 0.6), start=1):
                path = root / f"repeat-{index}.json"
                path.write_text(
                    json.dumps(
                        {
                            "models": {
                                "model-a": {
                                    "display_name": "Model A",
                                    "standard": {"full_memory": {"h": value}},
                                    "ordinal": {"mae": 1 - value},
                                }
                            }
                        }
                    ),
                    encoding="utf-8",
                )
                repeats.append((f"repeat-{index}", path))

            result = aggregate(repeats)

        metric = result["models"]["model-a"]["metrics"][
            "standard.full_memory.h"
        ]
        self.assertAlmostEqual(0.4, metric["mean"])
        self.assertAlmostEqual(0.1632993161855452, metric["population_sd"])
        self.assertEqual(
            {"repeat-1": 0.2, "repeat-2": 0.4, "repeat-3": 0.6},
            metric["repeat_values"],
        )


if __name__ == "__main__":
    unittest.main()
