#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PIPELINE_DIR = Path(__file__).resolve().parents[2] / "pipeline"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))


def load_script(filename: str, name: str):
    path = PIPELINE_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class MultidomainReleaseSelectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source_admission = load_script(
            "38_select_multidomain_source_admission.py", "test_multidomain_source_admission"
        )
        cls.merge = load_script("39_merge_multidomain_construction_seeds.py", "test_multidomain_seed_merge")
        cls.release = load_script("40_select_multidomain_benchmark_release.py", "test_multidomain_release")

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
    def row(row_id: str, domain: str, source: str, state: str = "strict_pass") -> dict:
        return {
            "id": row_id,
            "domain": domain,
            "source_dataset": source,
            "topic": "topic",
            "memories": [{"u_star": "B"}],
            "raw_selection": {
                "eligible": True,
                "quality_score": 80,
                "seed_complexity": "medium",
            },
            "semantic_qc": {"state": "strict_pass"},
            "independent_qc": {"decision": state},
        }

    def test_source_admission_uses_strict_rows_per_domain(self) -> None:
        rows = [
            self.row("g1", "general", "g-a"),
            self.row("g2", "general", "g-b"),
            self.row("g3", "general", "g-b"),
            self.row("c1", "coding", "c-a"),
            self.row("c2", "coding", "c-b"),
        ]
        rows.append(self.row("ignored", "general", "g-a"))
        rows[-1]["semantic_qc"]["state"] = "review"
        selected, audit = self.source_admission.select_admitted(
            rows, {"general": 2, "coding": 2}, 5, self.config()
        )
        self.assertEqual({"general": 2, "coding": 2}, audit["distribution"]["domain"])
        self.assertNotIn("ignored", {row["id"] for row in selected})

    def test_merge_assigns_health_domain_without_overwriting_new_domains(self) -> None:
        medical = [{"id": "m1", "source_dataset": "medical"}]
        general = [self.row("g1", "general", "general")]
        merged = self.merge.merge_seeds(medical, general)
        self.assertEqual("health_seed", merged[0]["domain"])
        self.assertEqual("general", merged[1]["domain"])

    def test_release_prefers_strict_and_uses_review_only_for_shortfall(self) -> None:
        strict = [
            self.row("g1", "general", "g-a"),
            self.row("g2", "general", "g-b"),
            self.row("c1", "coding", "c-a"),
        ]
        review = [
            self.row("g-review", "general", "g-a", "review"),
            self.row("c-review", "coding", "c-a", "review"),
        ]
        selected, audit = self.release.select_release(
            strict, review, {"general": 2, "coding": 2}, 7, self.config()
        )
        self.assertEqual(4, len(selected))
        self.assertEqual(3, audit["admission_states"]["admitted_strict"])
        self.assertEqual(1, audit["admission_states"]["admitted_nonblocking_review"])


if __name__ == "__main__":
    unittest.main()
