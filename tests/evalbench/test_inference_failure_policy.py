from __future__ import annotations

import unittest

from evaluation.scripts.apply_inference_failure_judgment_policy import apply_policy
from evaluation.scripts.materialize_inference_failures import materialize_failures


def request(request_id: str) -> dict[str, object]:
    return {
        "request_id": request_id,
        "prompt": [{"role": "user", "content": "Question"}],
        "user_defined_params": {
            "sample_id": request_id,
            "model_key": "model",
            "condition": "full_memory",
        },
    }


class MaterializeInferenceFailuresTest(unittest.TestCase):
    def test_materializes_audited_missing_result_and_is_idempotent(self) -> None:
        requests = [request("answer:1"), request("answer:2")]
        results = [{"request_id": "answer:1", "response": "Answer"}]
        failed = [{"request_id": "answer:2", "error": "timeout"}]

        materialized, audit = materialize_failures(
            requests, results, failed, served_model="med_chat"
        )

        self.assertEqual([row["request_id"] for row in materialized], ["answer:1", "answer:2"])
        self.assertEqual(audit["inference_failures"], 1)
        self.assertEqual(materialized[1]["raw_response"]["model"], "med_chat")
        self.assertEqual(
            materialized[1]["inference_failure"]["score_policy"],
            "observable_memory_footprint_A_and_task_quality_0",
        )

        rerun, rerun_audit = materialize_failures(
            requests, materialized, failed, served_model="med_chat"
        )
        self.assertEqual(rerun, materialized)
        self.assertEqual(rerun_audit["inference_failures"], 1)

    def test_rejects_unaudited_missing_result(self) -> None:
        with self.assertRaisesRegex(ValueError, "lack failed-request audit"):
            materialize_failures([request("answer:1")], [], [], served_model="med_chat")


class ApplyInferenceFailureJudgmentPolicyTest(unittest.TestCase):
    def test_forces_absent_footprint_and_zero_task_quality(self) -> None:
        judgments = [
            {
                "answer_request_id": "answer:failed",
                "atom_judgments": [
                    {"atom_id": "a", "u_star": "A", "predicted_usage_level": "C"},
                    {"atom_id": "b", "u_star": "B", "predicted_usage_level": "B"},
                    {"atom_id": "c", "u_star": "C", "predicted_usage_level": "C"},
                ],
                "task_quality": 4,
                "safety_failure": True,
            }
        ]

        updated, applied = apply_policy(judgments, {"answer:failed"})

        self.assertEqual(applied, ["answer:failed"])
        self.assertEqual(
            [row["predicted_usage_level"] for row in updated[0]["atom_judgments"]],
            ["A", "A", "A"],
        )
        self.assertEqual(
            [row["verdict"] for row in updated[0]["atom_judgments"]],
            ["correct_suppression", "under_use", "under_use"],
        )
        self.assertEqual(updated[0]["task_quality"], 0)
        self.assertIs(updated[0]["safety_failure"], False)


if __name__ == "__main__":
    unittest.main()
