from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PIPELINE_DIR = Path(__file__).resolve().parents[2] / "pipeline"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CuratedFinalizationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_script(
            PIPELINE_DIR / "123_finalize_memcalib_v241_curated_residual.py",
            "finalize_memcalib_v241_curated_residual_test",
        )

    def test_manual_override_scope_is_small_and_complete(self) -> None:
        self.assertEqual(9, len(self.module.OVERRIDES))
        for override in self.module.OVERRIDES.values():
            self.assertIn(
                override["family"],
                {
                    "conceptual_explanation",
                    "debugging_diagnosis",
                    "implementation_plan",
                    "recommendation_or_evaluation",
                },
            )
            self.assertGreaterEqual(len(override["question"]), 120)
            self.assertGreaterEqual(len(override["reference"]), 300)
            self.assertTrue(override["evidence"])

    def test_correct_actions_get_explicit_correction_contracts(self) -> None:
        atom = {
            "atom_id": "x",
            "u_star": "C",
            "memory_action": "correct",
            "text": "The user plans to block requests.",
        }
        output = self.module.scored_supervision(
            atom, "Do not block requests; schedule the work independently."
        )
        expected = output["usage_rubric"]["expected_answer_behavior"]
        self.assertIn("explicitly reject", expected)
        self.assertIn("Do not block requests", expected)

    def test_a_supervision_has_no_counterfactual_delta(self) -> None:
        atom = {
            "atom_id": "a",
            "u_star": "A",
            "memory_action": "ignore",
            "text": "Irrelevant preference.",
        }
        output = self.module.a_supervision(atom)
        self.assertEqual(
            "none", output["counterfactual_contract"]["observable_delta"]
        )
        self.assertEqual("none", output["usage_rubric"]["memory_usage_weight"])


if __name__ == "__main__":
    unittest.main()
