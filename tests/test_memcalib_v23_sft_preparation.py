from __future__ import annotations

import unittest

from sft.scripts.prepare_memcalib_v23_splits import build_split, proportional_quotas
from sft.scripts.prepare_memcalib_v23_teacher_requests import build_request
from sft.scripts.build_memcalib_v23_swift_sft import inspect_judgment, swift_record


def sample(index: int) -> dict:
    domain = ("health_seed", "general", "coding")[index % 3]
    level = ("level_1", "level_2", "level_2", "level_3")[index % 4]
    label = ("A", "B", "C")[index % 3]
    action = "ignore" if label == "A" else "apply"
    return {
        "id": f"sample-{index:05d}",
        "domain": domain,
        "question": f"Question {index}",
        "source_answer": f"Draft {index}",
        "source_dataset": f"source-{index % 4}",
        "source_topic": f"topic-{index % 7}",
        "composite_block_revision": {"difficulty_level": level},
        "memory_blocks": [{"parent_memory_id": "p1", "memory_text": f"Memory {index}"}],
        "memories": [
            {
                "atom_id": "a1",
                "parent_memory_id": "p1",
                "text": f"Memory {index}",
                "u_star": label,
                "memory_action": action,
                "query_relation": "absent",
                "usage_rubric": {
                    "expected_answer_behavior": "Expected",
                    "correct_use": "Correct",
                    "under_use": "Under",
                    "over_use": "Over",
                    "forbidden_memory_role": "Forbidden",
                    "validity_scope": "Scope",
                    "observable_checks": ["Check"],
                },
            }
        ],
    }


class SplitTests(unittest.TestCase):
    def test_proportional_quotas_are_exact(self) -> None:
        quotas = proportional_quotas({"a": 7, "b": 3}, 5)
        self.assertEqual(sum(quotas.values()), 5)
        self.assertEqual(quotas, {"a": 4, "b": 1})

    def test_real_scale_split_is_disjoint_and_locks_test(self) -> None:
        rows = [sample(index) for index in range(15000)]
        locked = {row["id"] for row in rows[:500]}
        splits, report = build_split(rows, locked, seed=17)
        self.assertEqual({key: len(value) for key, value in splits.items()}, {
            "train": 12000,
            "dev": 1500,
            "test": 1500,
            "pilot_train": 500,
        })
        self.assertTrue(locked.issubset(splits["test"]))
        self.assertTrue(splits["pilot_train"].issubset(splits["train"]))
        self.assertFalse(splits["train"] & splits["dev"])
        self.assertFalse(splits["train"] & splits["test"])
        self.assertEqual(report["pilot_train"]["records"], 500)


class TeacherRequestTests(unittest.TestCase):
    def test_privileged_fields_stay_in_teacher_payload(self) -> None:
        request = build_request(sample(1), "Teacher system", "qwen3.7-max", "teacher")
        payload = request["prompt"][1]["content"]
        self.assertIn("atomic_supervision", payload)
        self.assertIn("source_answer", payload)
        self.assertEqual(request["user_defined_params"]["condition"], "full_memory")
        self.assertEqual(request["user_defined_params"]["target_kind"], "privileged_sft_teacher")

    def test_strict_judgment_and_swift_loss_policy(self) -> None:
        judgment = {
            "atom_judgments": [
                {
                    "atom_id": "a1",
                    "u_star": "B",
                    "predicted_usage_level": "B",
                    "scorable": True,
                    "explicit_contradiction": False,
                    "constraint_violation": False,
                }
            ],
            "task_quality": 4,
            "safety_failure": False,
        }
        self.assertTrue(inspect_judgment(judgment)["strict"])
        converted = swift_record(sample(1), "Final answer", "System")
        self.assertEqual([message["loss"] for message in converted["messages"]], [False, False, True])

    def test_explicit_correction_is_not_an_auxiliary_failure(self) -> None:
        judgment = {
            "atom_judgments": [
                {
                    "atom_id": "a1",
                    "u_star": "B",
                    "predicted_usage_level": "B",
                    "scorable": True,
                    "explicit_contradiction": True,
                    "constraint_violation": False,
                }
            ],
            "task_quality": 4,
            "safety_failure": False,
        }
        self.assertTrue(inspect_judgment(judgment, {"a1": "correct"})["strict"])
        self.assertFalse(inspect_judgment(judgment, {"a1": "apply"})["strict"])


if __name__ == "__main__":
    unittest.main()
