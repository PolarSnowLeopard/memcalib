from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PIPELINE = Path(__file__).resolve().parents[2] / "pipeline"
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))
SPEC = importlib.util.spec_from_file_location(
    "direct_question_repair",
    PIPELINE / "119_direct_repair_memcalib_v241_questions.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DirectQuestionRepairTests(unittest.TestCase):
    def test_restores_original_scope_without_changing_supervision(self) -> None:
        candidate = {
            "id": "coding-test-1",
            "question": "Explain a different logging task.",
            "reference_answer": "Preserve this reference answer.",
            "usage_rubric": {"observable_checks": ["Preserve this rubric."]},
            "coding_text_observability_revision": {
                "task_family": "debugging_diagnosis"
            },
        }
        source = {
            "id": "coding-test-1",
            "question": "Write a service that returns RETRY_EXHAUSTED after 3 failures.",
        }

        repaired, audit = MODULE.repair_record(candidate, source)

        self.assertIn("RETRY_EXHAUSTED", repaired["question"])
        self.assertIn("3 failures", repaired["question"])
        self.assertIn("step-by-step implementation plan", repaired["question"])
        self.assertNotIn("different logging task", repaired["question"])
        self.assertEqual(
            repaired["reference_answer"], candidate["reference_answer"]
        )
        self.assertEqual(repaired["usage_rubric"], candidate["usage_rubric"])
        self.assertEqual(audit["new_task_family"], "implementation_plan")

    def test_removes_code_fence_delimiters_from_original_question(self) -> None:
        cleaned = MODULE.clean_original_question(
            "Debug this code:\n```python\nraise RuntimeError('failed')\n```"
        )

        self.assertNotIn("```", cleaned)
        self.assertIn("RuntimeError", cleaned)

    def test_classifies_debugging_and_behavior_questions(self) -> None:
        self.assertEqual(
            MODULE.infer_task_family("Why does this parser fail on empty input?"),
            "debugging_diagnosis",
        )
        self.assertEqual(
            MODULE.infer_task_family("What happens when the input is empty?"),
            "behavior_prediction",
        )


if __name__ == "__main__":
    unittest.main()
