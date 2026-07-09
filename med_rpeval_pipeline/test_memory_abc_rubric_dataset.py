#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent / "09_build_memory_abc_rubric_dataset.py"


COMMON_RUBRIC_KEYS = {
    "expected_answer_behavior",
    "memory_usage_weight",
    "validity_scope",
    "correct_use",
    "under_use",
    "over_use",
    "forbidden_memory_role",
    "failure_direction",
    "observable_checks",
}


ATOM_KEYS = {
    "parent_memory_id",
    "atom_id",
    "atom_index",
    "atom_count",
    "atomic_predicate",
    "derivation",
    "overlap_group",
    "overlap_note",
}


def load_builder():
    spec = importlib.util.spec_from_file_location("memory_abc_rubric_dataset", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class MemoryAbcRubricDatasetTest(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = load_builder()

    def test_c_rubric_has_crk2_common_and_controlling_fields(self) -> None:
        memory = {
            "memory_id": "m1",
            "text": "用户只能使用 Python 标准库。",
            "u_star": "C",
            "subtype": "tool_constraint",
            "memory_type": "constraint",
            "label_reason": "该约束直接决定可用实现方案。",
        }

        rubric = self.builder.build_usage_rubric(memory, "请写一个 CSV 处理脚本。")

        self.assertTrue(COMMON_RUBRIC_KEYS.issubset(rubric))
        self.assertEqual("controlling", rubric["memory_usage_weight"])
        self.assertIn("controlling_factor", rubric)
        self.assertIn("missing_memory_failure", rubric)
        self.assertGreaterEqual(len(rubric["observable_checks"]), 3)
        self.assertIn("必须", rubric["correct_use"])

    def test_b_rubric_has_bounded_support_fields(self) -> None:
        memory = {
            "memory_id": "m2",
            "text": "用户喜欢先看一个小例子。",
            "u_star": "B",
            "subtype": "bounded_preference",
            "memory_type": "preference",
            "label_reason": "这会影响解释方式，但不能改变核心答案。",
        }

        rubric = self.builder.build_usage_rubric(memory, "请解释 Python 装饰器。")

        self.assertTrue(COMMON_RUBRIC_KEYS.issubset(rubric))
        self.assertEqual("supporting", rubric["memory_usage_weight"])
        self.assertIn("allowed_memory_use", rubric)
        self.assertIn("maximum_footprint", rubric)
        self.assertIn("不能主导", rubric["maximum_footprint"])

    def test_atomize_preference_splits_composite_memory_into_related_atoms(self) -> None:
        pref = {
            "preference": "用户有10年糖尿病史，且近期空腹血糖控制在 9.0 mmol/L 以上，属于控制不佳状态。",
            "u_star": "C",
            "reason": "影响感染和愈合风险。",
            "source": "from_question",
        }

        atoms = self.builder.atomize_preference(pref, "p1")

        self.assertGreaterEqual(len(atoms), 3)
        self.assertTrue(all(atom["parent_memory_id"] == "p1" for atom in atoms))
        self.assertEqual([1, 2, 3], [atom["atom_index"] for atom in atoms[:3]])
        self.assertIn("用户有10年糖尿病史", atoms[0]["text"])
        self.assertIn("空腹血糖控制在 9.0 mmol/L 以上", atoms[1]["text"])
        self.assertEqual("inferred", atoms[-1]["derivation"])
        self.assertTrue(all(atom["atom_count"] == len(atoms) for atom in atoms))

    def test_atomize_preference_keeps_english_coordinate_phrase_and_repairs_subject(self) -> None:
        coordinate_pref = {
            "preference": "The person is highly anxious about long hospital waits and medical bills, preferring quick and low-cost diagnostic options if they must be seen.",
            "u_star": "B",
            "reason": "affects communication style",
            "source": "from_question",
        }
        contrast_pref = {
            "preference": "The person was highly energetic before the incident but is now unusually sleepy and lethargic.",
            "u_star": "C",
            "reason": "changes triage risk",
            "source": "from_question",
        }

        coordinate_atoms = self.builder.atomize_preference(coordinate_pref, "p2")
        contrast_atoms = self.builder.atomize_preference(contrast_pref, "p3")

        self.assertEqual(1, len(coordinate_atoms))
        self.assertIn("medical bills", coordinate_atoms[0]["text"])
        self.assertIn("quick and low-cost", coordinate_atoms[0]["text"])
        self.assertEqual(2, len(contrast_atoms))
        self.assertEqual("The person is now unusually sleepy and lethargic.", contrast_atoms[1]["text"])

    def test_atomize_preference_splits_english_and_when_second_clause_has_predicate(self) -> None:
        pref = {
            "preference": "The user has a history of hypertension and is currently taking Amlodipine to control blood pressure.",
            "u_star": "C",
            "reason": "changes medication advice",
            "source": "from_question",
        }

        atoms = self.builder.atomize_preference(pref, "p4")

        self.assertEqual(2, len(atoms))
        self.assertEqual("The user has a history of hypertension.", atoms[0]["text"])
        self.assertEqual("The user is currently taking Amlodipine to control blood pressure.", atoms[1]["text"])

    def test_hard_a_is_topic_adjacent_and_marked_no_footprint(self) -> None:
        memory = self.builder.build_hard_a_memory("digestive", 2, "mA")

        self.assertEqual("A", memory["u_star"])
        self.assertIn(memory["hard_a_family"], self.builder.HARD_A_FAMILIES)
        self.assertTrue(memory["subtype"].startswith("hard_a_"))
        self.assertEqual("synthetic_hard_a", memory["source"])
        self.assertEqual(
            {"task_goal", "memory_role", "usage_boundary", "failure_direction"},
            set(memory["construction_target"]),
        )
        self.assertTrue(ATOM_KEYS.issubset(memory))
        self.assertEqual(memory["memory_id"], memory["parent_memory_id"])
        self.assertEqual("synthetic", memory["derivation"])
        self.assertEqual("none", memory["usage_rubric"]["memory_usage_weight"])
        self.assertIn("forbidden_memory_role", memory["usage_rubric"])
        self.assertIn("failure_direction", memory["usage_rubric"])
        self.assertIn("contamination_signals", memory["usage_rubric"])
        self.assertTrue(memory["usage_rubric"]["observable_checks"])

    def test_convert_record_keeps_bc_and_adds_hard_a_with_rubrics(self) -> None:
        record = {
            "id": "rec1",
            "source_dataset": "source",
            "source_split": "train",
            "topic": "coding",
            "question": "请解释 Python 装饰器。",
            "preferences": [
                {
                    "preference": "用户刚开始学 Python，不熟悉闭包。",
                    "u_star": "C",
                    "reason": "这决定解释起点。",
                    "source": "from_question",
                    "verify_reason": "需要从基础讲起。",
                },
                {
                    "preference": "用户喜欢先看小例子。",
                    "u_star": "B",
                    "reason": "影响解释方式。",
                    "source": "soft_preference_synthetic",
                },
                {
                    "preference": "用户的编辑器是深色主题。",
                    "u_star": "A",
                    "reason": "无关。",
                    "source": "easy_a_synthetic",
                },
            ],
        }

        sample = self.builder.convert_record(record, sample_index=1)

        self.assertEqual("rubricmem_000001", sample["id"])
        self.assertEqual("请解释 Python 装饰器。", sample["question"])
        self.assertEqual({"A", "B", "C"}, {memory["u_star"] for memory in sample["memories"]})
        self.assertIn("memory_blocks", sample)
        self.assertIn("construction_audit", sample)
        self.assertEqual(1, sum(1 for memory in sample["memories"] if memory["source"] == "synthetic_hard_a"))
        self.assertTrue(all("usage_rubric" in memory for memory in sample["memories"]))
        self.assertTrue(all(memory["usage_rubric"]["observable_checks"] for memory in sample["memories"]))
        self.assertTrue(all("construction_target" in memory for memory in sample["memories"]))
        self.assertTrue(all("hard_a_family" in memory for memory in sample["memories"]))
        self.assertTrue(all(ATOM_KEYS.issubset(memory) for memory in sample["memories"]))
        self.assertTrue(all(COMMON_RUBRIC_KEYS.issubset(memory["usage_rubric"]) for memory in sample["memories"]))
        self.assertIsInstance(sample["qc"]["atomicity_pass"], bool)
        self.assertIsInstance(sample["qc"]["duplicate_pass"], bool)
        self.assertIsInstance(sample["qc"]["question_memory_leakage_pass"], bool)
        self.assertIsInstance(sample["qc"]["hard_a_target_consistency_pass"], bool)
        self.assertNotIn("用户的编辑器是深色主题。", [memory["text"] for memory in sample["memories"]])

    def test_convert_record_excludes_old_synthetic_a_even_if_corrected_to_bc(self) -> None:
        record = {
            "id": "rec2",
            "topic": "general_other",
            "question": "帮我写一封请假邮件。",
            "preferences": [
                {
                    "preference": "用户不能透露具体家庭原因。",
                    "u_star": "C",
                    "reason": "这是信息边界。",
                    "source": "from_question",
                },
                {
                    "preference": "用户喜欢绿色便利贴。",
                    "u_star": "B",
                    "reason": "旧流程错误校正后的近邻信息。",
                    "source": "hard_a_synthetic",
                },
            ],
        }

        sample = self.builder.convert_record(record, sample_index=2)

        memory_texts = [memory["text"] for memory in sample["memories"]]
        self.assertIn("用户不能透露具体家庭原因。", memory_texts)
        self.assertNotIn("用户喜欢绿色便利贴。", memory_texts)

    def test_overlap_groups_mark_repeated_atomic_information(self) -> None:
        memories = [
            {
                "memory_id": "m1",
                "text": "用户必须使用 Python 标准库。",
                "u_star": "C",
                "source": "from_question",
                "memory_type": "constraint",
                "subtype": "answer_controlling_constraint",
                "hard_a_family": None,
                "parent_memory_id": "p1",
                "atom_id": "p1_a1",
                "atom_index": 1,
                "atom_count": 1,
                "atomic_predicate": "用户必须使用 Python 标准库。",
                "derivation": "explicit",
                "overlap_group": None,
                "overlap_note": "",
                "label_reason": "",
                "construction_target": {
                    "task_goal": "回答当前用户问题",
                    "memory_role": "controlling context",
                    "usage_boundary": "必须影响方案",
                    "failure_direction": "忽略会推荐第三方库",
                },
                "usage_rubric": {"memory_usage_weight": "controlling"},
                "judge_trace": {},
            },
            {
                "memory_id": "m2",
                "text": "用户只能使用 Python 标准库。",
                "u_star": "C",
                "source": "from_question",
                "memory_type": "constraint",
                "subtype": "answer_controlling_constraint",
                "hard_a_family": None,
                "parent_memory_id": "p2",
                "atom_id": "p2_a1",
                "atom_index": 1,
                "atom_count": 1,
                "atomic_predicate": "用户只能使用 Python 标准库。",
                "derivation": "explicit",
                "overlap_group": None,
                "overlap_note": "",
                "label_reason": "",
                "construction_target": {
                    "task_goal": "回答当前用户问题",
                    "memory_role": "controlling context",
                    "usage_boundary": "必须影响方案",
                    "failure_direction": "忽略会推荐第三方库",
                },
                "usage_rubric": {"memory_usage_weight": "controlling"},
                "judge_trace": {},
            },
        ]

        groups = self.builder.assign_overlap_groups(memories)

        self.assertEqual(1, len(groups))
        self.assertEqual(memories[0]["overlap_group"], memories[1]["overlap_group"])
        self.assertIn("overlap", memories[0]["overlap_note"])

    def test_build_html_renders_single_sample_keyboard_viewer(self) -> None:
        samples = [
            self.builder.convert_record(
                {
                    "id": "rec1",
                    "source_dataset": "source",
                    "topic": "general_other",
                    "question": "问题一",
                    "preferences": [
                        {
                            "preference": "用户必须使用 Python 标准库。",
                            "u_star": "C",
                            "reason": "核心约束。",
                            "source": "from_question",
                        }
                    ],
                },
                sample_index=1,
            ),
            self.builder.convert_record(
                {
                    "id": "rec2",
                    "source_dataset": "source",
                    "topic": "general_other",
                    "question": "问题二",
                    "preferences": [
                        {
                            "preference": "用户喜欢先看小例子。",
                            "u_star": "B",
                            "reason": "局部表达偏好。",
                            "source": "from_question",
                        }
                    ],
                },
                sample_index=2,
            ),
        ]
        summary = self.builder.summarize(samples)

        html = self.builder.build_html(samples, summary)

        self.assertIn('id="sample-viewer"', html)
        self.assertIn('id="prevSample"', html)
        self.assertIn('id="nextSample"', html)
        self.assertIn('id="sampleSelect"', html)
        self.assertIn('data-index="0"', html)
        self.assertIn('data-index="1"', html)
        self.assertIn('class="sample active"', html)
        self.assertIn("ArrowRight", html)
        self.assertIn("ArrowLeft", html)
        self.assertIn("showSample", html)


if __name__ == "__main__":
    unittest.main()
