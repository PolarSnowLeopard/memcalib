#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PIPELINE_DIR = Path(__file__).resolve().parents[2] / "pipeline"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))


def load_script(filename: str, module_name: str):
    path = PIPELINE_DIR / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class MultidomainFullPoolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pool = load_script("37_build_multidomain_full_candidate_pool.py", "multidomain_full_pool")
        cls.extension = load_script(
            "41_build_multidomain_source_extension.py",
            "multidomain_source_extension",
        )

    @staticmethod
    def config() -> dict:
        return {
            "near_duplicate_jaccard": 0.88,
            "min_quality_score": 60,
            "topic_alpha": 0.5,
            "quality_weight_beta": 2.0,
            "complexity_targets": {"simple": 0.25, "medium": 0.5, "complex": 0.25},
        }

    @staticmethod
    def row(row_id: str, domain: str, source: str, question: str) -> dict:
        return {
            "id": row_id,
            "domain": domain,
            "source_dataset": source,
            "raw_question": question,
            "topic": "general_other" if domain == "general" else "implementation",
            "raw_selection": {
                "eligible": True,
                "quality_score": 80,
                "seed_complexity": "medium",
                "dedup_status": "unique",
            },
        }

    def test_build_pool_deduplicates_and_fills_shortfall_within_domain(self) -> None:
        rows = [
            self.row("g1", "general", "human", "Plan a quiet two day trip with a small budget and public transit."),
            self.row("g2", "general", "synthetic", "Plan a quiet two day trip with a small budget and public transit."),
            self.row("g3", "general", "synthetic", "Write a polite email that declines a meeting and suggests next week."),
            self.row("c1", "coding", "code_a", "Implement a parser in Python without pandas and preserve input order."),
            self.row("c2", "coding", "code_b", "Create unit tests for an API client that retries timeout errors."),
        ]

        selected, audit = self.pool.build_pool(
            rows,
            {"human": 1, "synthetic": 1, "code_a": 1, "code_b": 1},
            7,
            self.config(),
        )

        self.assertEqual(4, len(selected))
        self.assertEqual({"general": 2, "coding": 2}, audit["actual_distribution"]["domain"])
        self.assertEqual(1, audit["cross_source_duplicates_removed"])
        self.assertEqual(4, len({row["id"] for row in selected}))

    def test_parse_source_quotas_rejects_duplicates(self) -> None:
        with self.assertRaises(ValueError):
            self.pool.parse_source_quotas(["source=2", "source=3"])

    def test_exclude_records_requires_unique_existing_ids(self) -> None:
        rows = [
            self.row("g1", "general", "human", "Plan a quiet trip with a small budget."),
            self.row("g2", "general", "human", "Write a polite email declining a meeting."),
        ]

        retained, excluded = self.pool.exclude_records(rows, ["g1"])

        self.assertEqual(["g2"], [row["id"] for row in retained])
        self.assertEqual(["g1"], [row["id"] for row in excluded])
        with self.assertRaises(ValueError):
            self.pool.exclude_records(rows, ["missing"])
        with self.assertRaises(ValueError):
            self.pool.exclude_records(rows, ["g1", "g1"])

    def test_extension_preserves_locked_pool_and_filters_near_duplicates(self) -> None:
        locked = [
            self.row("locked", "general", "general_source", "Plan a quiet trip with a small budget and public transit."),
        ]
        candidates = [
            self.row("duplicate", "general", "general_source", "Plan a quiet trip with a small budget and public transit."),
            self.row("general-new", "general", "general_source", "Write a polite email declining a meeting next week."),
            self.row("coding-new", "coding", "coding_source", "Fix a Python parser that fails on empty input without pandas."),
        ]

        selected, audit = self.extension.build_extension(
            locked,
            candidates,
            {"general_source": 1, "coding_source": 1},
            7,
            self.config(),
        )

        self.assertEqual({"general-new", "coding-new"}, {row["id"] for row in selected})
        self.assertEqual(1, audit["duplicates_of_locked_pool"])
        self.assertEqual({"coding": 1, "general": 1}, audit["selected_distribution"]["domain"])

    def test_extension_rejects_duplicate_ids_across_locked_inputs(self) -> None:
        locked = [
            self.row("locked", "general", "general_source", "Plan a quiet trip with a small budget."),
            self.row("locked", "general", "general_source", "Plan another quiet trip with a small budget."),
        ]
        candidates = [
            self.row("new", "general", "general_source", "Write a polite email declining a meeting."),
        ]

        with self.assertRaisesRegex(ValueError, "locked pool IDs"):
            self.extension.build_extension(
                locked,
                candidates,
                {"general_source": 1},
                7,
                self.config(),
            )


if __name__ == "__main__":
    unittest.main()
