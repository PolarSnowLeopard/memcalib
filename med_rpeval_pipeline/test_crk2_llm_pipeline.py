#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PREPARE_SCRIPT = SCRIPT_DIR / "10_prepare_crk2_generation.py"
POST_SCRIPT = SCRIPT_DIR / "11_post_crk2_generation.py"


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class Crk2LlmPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.prepare = load_script(PREPARE_SCRIPT, "prepare_crk2")
        self.post = load_script(POST_SCRIPT, "post_crk2")

    def test_prepare_request_contains_crk2_schema_and_raw_record(self) -> None:
        row = {
            "id": "raw1",
            "source_dataset": "OpenMed/MedDialog",
            "source_split": "train",
            "source_index": 1,
            "topic": "digestive",
            "raw_question": "I ate chili and now have abdominal pain.",
            "doctor_answer": "This may be gastritis.",
        }

        request = self.prepare.build_request(row, request_index=1, target_memory_count="3-6")

        self.assertEqual("crk2_raw1", request["request_id"])
        self.assertEqual("raw1", request["user_defined_params"]["id"])
        content = request["prompt"][0]["content"]
        self.assertIn("memory_blocks", content)
        self.assertIn("raw_evidence", content)
        self.assertIn("memory_text", content)
        self.assertIn("atomic memories", content)
        self.assertIn("usage_rubric", content)
        self.assertIn("I ate chili", content)
        self.assertIn("只允许补充 hard A", content)
        self.assertIn("至少补充 1 条 synthetic_hard_a", content)

    def test_select_balanced_records_round_robins_topics(self) -> None:
        rows = [
            {"id": "a1", "topic": "a"},
            {"id": "a2", "topic": "a"},
            {"id": "b1", "topic": "b"},
            {"id": "b2", "topic": "b"},
        ]

        selected = self.prepare.select_balanced_records(rows, limit=3, seed=7)

        self.assertEqual(3, len(selected))
        self.assertEqual({"a", "b"}, {row["topic"] for row in selected})

    def test_normalize_model_record_preserves_parent_blocks_and_atomic_memories(self) -> None:
        params = {
            "id": "raw1",
            "source_dataset": "OpenMed/MedDialog",
            "source_split": "train",
            "source_index": 1,
            "topic": "digestive",
            "raw_question": "raw q",
            "doctor_answer": "raw a",
        }
        raw = {
            "question": "去背景化后的当前任务测试问题",
            "memory_blocks": [
                {
                    "parent_memory_id": "p1",
                    "raw_evidence": "I ate homemade chili and now have upper abdominal pain with nausea.",
                    "memory_text": "用户吃了自制辣椒后出现上腹痛，并伴有恶心。",
                    "source": "from_question",
                    "u_star": "C",
                    "atom_ids": ["p1_a1", "p1_a2"],
                    "atomization_notes": "同一事件拆为暴露和症状两个原子事实。",
                },
                {
                    "parent_memory_id": "p2",
                    "raw_evidence": "synthetic hard A: user tends to attribute stomach upset to stress.",
                    "memory_text": "用户过去认为胃部不适通常只是压力导致。",
                    "source": "synthetic_hard_a",
                    "u_star": "A",
                    "hard_a_family": "evidence_conflict",
                    "atom_ids": ["p2_a1"],
                },
            ],
            "memories": [
                {
                    "memory_id": "m1",
                    "parent_memory_id": "p1",
                    "atom_id": "p1_a1",
                    "text": "用户吃了自制辣椒。",
                    "evidence": "I ate homemade chili.",
                    "atomic_predicate": "用户吃了自制辣椒。",
                    "atom_index": 1,
                    "atom_count": 2,
                    "derivation": "explicit",
                    "source": "from_question",
                    "memory_type": "case_fact",
                    "u_star": "C",
                    "subtype": "answer_controlling_context",
                    "hard_a_family": None,
                    "label_reason": "该暴露决定病因判断。",
                    "construction_target": {
                        "task_goal": "回答当前问题",
                        "memory_role": "controlling exposure",
                        "usage_boundary": "影响病因判断，不扩展到食物过敏诊断。",
                        "failure_direction": "忽略暴露史或过度诊断。",
                    },
                    "usage_rubric": {
                        "expected_answer_behavior": "回答需考虑食物刺激。",
                        "memory_usage_weight": "controlling",
                        "validity_scope": "当前消化症状问题。",
                        "correct_use": "把辣椒暴露作为核心背景。",
                        "under_use": "完全忽略暴露史。",
                        "over_use": "直接诊断严重疾病。",
                        "forbidden_memory_role": "不得扩展为长期饮食画像。",
                        "failure_direction": "忽略或过度诊断。",
                        "observable_checks": ["是否考虑辣椒暴露"],
                    },
                    "controlling_factor": "辣椒暴露影响病因。",
                    "missing_memory_failure": "忽略会导致病因判断不完整。",
                },
                {
                    "memory_id": "m2",
                    "parent_memory_id": "p1",
                    "atom_id": "p1_a2",
                    "text": "用户伴有恶心。",
                    "evidence": "with nausea.",
                    "atomic_predicate": "用户伴有恶心。",
                    "atom_index": 2,
                    "atom_count": 2,
                    "derivation": "explicit",
                    "source": "from_question",
                    "memory_type": "case_fact",
                    "u_star": "B",
                    "subtype": "bounded_context",
                    "hard_a_family": None,
                    "label_reason": "影响解释完整性。",
                    "construction_target": {
                        "task_goal": "回答当前问题",
                        "memory_role": "supporting symptom",
                        "usage_boundary": "局部补充症状解释。",
                        "failure_direction": "忽略会不够贴合，过用会误判急症。",
                    },
                    "usage_rubric": {
                        "expected_answer_behavior": "局部提及恶心。",
                        "memory_usage_weight": "supporting",
                        "validity_scope": "当前症状解释。",
                        "correct_use": "有限使用。",
                        "under_use": "完全忽略。",
                        "over_use": "主导结论。",
                        "forbidden_memory_role": "不得升级为核心诊断。",
                        "failure_direction": "漏用或过用。",
                        "allowed_memory_use": "局部解释。",
                        "maximum_footprint": "不能主导答案。",
                        "observable_checks": ["是否局部体现"],
                    },
                },
                {
                    "memory_id": "m3",
                    "parent_memory_id": "p2",
                    "atom_id": "p2_a1",
                    "text": "用户过去认为胃部不适通常只是压力导致。",
                    "evidence": "synthetic hard A: user tends to attribute stomach upset to stress.",
                    "atomic_predicate": "用户过去认为胃部不适通常只是压力导致。",
                    "atom_index": 1,
                    "atom_count": 1,
                    "derivation": "synthetic",
                    "source": "synthetic_hard_a",
                    "memory_type": "profile_fact",
                    "u_star": "A",
                    "subtype": "hard_a_evidence_conflict",
                    "hard_a_family": "evidence_conflict",
                    "label_reason": "当前证据优先。",
                    "construction_target": {
                        "task_goal": "回答当前问题",
                        "memory_role": "near-topic no-footprint distractor",
                        "usage_boundary": "不得影响病因判断。",
                        "failure_direction": "偏向压力解释。",
                    },
                    "usage_rubric": {
                        "expected_answer_behavior": "不体现该记忆。",
                        "memory_usage_weight": "none",
                        "validity_scope": "当前无合法使用范围。",
                        "correct_use": "完全不用。",
                        "under_use": "A 无 under-use。",
                        "over_use": "提及即过用。",
                        "forbidden_memory_role": "不得作为证据。",
                        "failure_direction": "偏向压力解释。",
                        "contamination_signals": ["把旧经验当证据"],
                        "observable_checks": ["是否提及旧经验"],
                    },
                },
            ],
            "qc": {
                "atomicity_pass": True,
                "duplicate_pass": True,
                "question_memory_leakage_pass": True,
                "hard_a_target_consistency_pass": True,
                "rubric_objectivity_pass": True,
                "counterfactual_pass": "pending_model_test",
                "manual_audit": "not_sampled",
            },
            "construction_audit": {"schema_version": "crk-2-llm-v1", "quality_subset": "clean", "pipeline_steps": []},
        }

        self.assertEqual([], self.post.validate_model_record(raw))
        rec = self.post.normalize_model_record(raw, params)

        self.assertEqual("crk2_raw1", rec["id"])
        self.assertEqual("raw q", rec["raw_query"])
        self.assertEqual(2, len(rec["memory_blocks"]))
        self.assertEqual(3, len(rec["memories"]))
        self.assertEqual("用户吃了自制辣椒后出现上腹痛，并伴有恶心。", rec["memory_blocks"][0]["memory_text"])
        self.assertEqual(["B", "C"], rec["memory_blocks"][0]["parent_label_set"])
        self.assertEqual("mixed", rec["memory_blocks"][0]["parent_label_mode"])
        self.assertEqual(["A"], rec["memory_blocks"][1]["parent_label_set"])
        self.assertEqual("homogeneous", rec["memory_blocks"][1]["parent_label_mode"])
        self.assertEqual(1, rec["composition"]["mixed_parent_count"])
        self.assertEqual({"B+C": 1, "A": 1}, rec["composition"]["parent_label_set_counts"])
        self.assertEqual("I ate homemade chili and now have upper abdominal pain with nausea.", rec["memory_blocks"][0]["raw_evidence"])
        self.assertEqual("p1_a1", rec["memories"][0]["atom_id"])
        self.assertEqual("I ate homemade chili.", rec["memories"][0]["evidence"])
        self.assertEqual("辣椒暴露影响病因。", rec["memories"][0]["usage_rubric"]["controlling_factor"])
        self.assertEqual("clean", rec["split"])

    def test_validate_model_record_rejects_first_person_stored_memory(self) -> None:
        rec = {
            "question": "去背景化后的当前任务测试问题",
            "memory_blocks": [
                {
                    "parent_memory_id": "p1",
                    "raw_evidence": "I ate homemade chili.",
                    "memory_text": "I ate homemade chili.",
                    "source": "from_question",
                    "u_star": "C",
                    "atom_ids": ["p1_a1"],
                },
                {
                    "parent_memory_id": "p2",
                    "raw_evidence": "synthetic hard A",
                    "memory_text": "用户过去认为胃部不适通常只是压力导致。",
                    "source": "synthetic_hard_a",
                    "u_star": "A",
                    "atom_ids": ["p2_a1"],
                },
            ],
            "memories": [
                {
                    "memory_id": "m1",
                    "parent_memory_id": "p1",
                    "atom_id": "p1_a1",
                    "atom_index": 1,
                    "atom_count": 1,
                    "text": "I ate homemade chili.",
                    "evidence": "I ate homemade chili.",
                    "atomic_predicate": "用户吃了自制辣椒。",
                    "derivation": "explicit",
                    "source": "from_question",
                    "memory_type": "case_fact",
                    "u_star": "C",
                    "subtype": "answer_controlling_context",
                    "hard_a_family": None,
                    "label_reason": "该暴露决定病因判断。",
                    "construction_target": {
                        "task_goal": "回答当前问题",
                        "memory_role": "controlling",
                        "usage_boundary": "影响病因判断。",
                        "failure_direction": "忽略暴露史。",
                    },
                    "usage_rubric": {
                        "expected_answer_behavior": "回答需考虑食物刺激。",
                        "memory_usage_weight": "controlling",
                        "validity_scope": "当前消化症状问题。",
                        "correct_use": "把辣椒暴露作为核心背景。",
                        "under_use": "完全忽略暴露史。",
                        "over_use": "直接诊断严重疾病。",
                        "forbidden_memory_role": "不得扩展为长期饮食画像。",
                        "failure_direction": "忽略或过度诊断。",
                        "controlling_factor": "辣椒暴露影响病因。",
                        "missing_memory_failure": "忽略会导致病因判断不完整。",
                        "observable_checks": ["是否考虑辣椒暴露"],
                    },
                },
                {
                    "memory_id": "m2",
                    "parent_memory_id": "p2",
                    "atom_id": "p2_a1",
                    "atom_index": 1,
                    "atom_count": 1,
                    "text": "用户过去认为胃部不适通常只是压力导致。",
                    "evidence": "synthetic hard A",
                    "atomic_predicate": "用户过去认为胃部不适通常只是压力导致。",
                    "derivation": "synthetic",
                    "source": "synthetic_hard_a",
                    "memory_type": "profile_fact",
                    "u_star": "A",
                    "subtype": "hard_a_evidence_conflict",
                    "hard_a_family": "evidence_conflict",
                    "label_reason": "当前证据优先。",
                    "construction_target": {
                        "task_goal": "回答当前问题",
                        "memory_role": "none",
                        "usage_boundary": "不得影响病因判断。",
                        "failure_direction": "偏向压力解释。",
                    },
                    "usage_rubric": {
                        "expected_answer_behavior": "不体现该记忆。",
                        "memory_usage_weight": "none",
                        "validity_scope": "当前无合法使用范围。",
                        "correct_use": "完全不用。",
                        "under_use": "A 无 under-use。",
                        "over_use": "提及即过用。",
                        "forbidden_memory_role": "不得作为证据。",
                        "failure_direction": "偏向压力解释。",
                        "contamination_signals": ["把旧经验当证据"],
                        "observable_checks": ["是否提及旧经验"],
                    },
                },
            ],
        }

        errors = self.post.validate_model_record(rec)

        self.assertIn("block_0_first_person_memory_text", errors)
        self.assertIn("memory_0_first_person_text", errors)

    def test_validate_model_record_rejects_missing_parent_atom_link(self) -> None:
        rec = {
            "question": "去背景化问题",
            "memory_blocks": [
                {
                    "parent_memory_id": "p1",
                    "raw_evidence": "原始证据",
                    "memory_text": "规范化记忆",
                    "source": "from_question",
                    "u_star": "C",
                    "atom_ids": ["p1_a1"],
                }
            ],
            "memories": [],
            "qc": {},
        }

        errors = self.post.validate_model_record(rec)

        self.assertIn("missing_required_memories", errors)


if __name__ == "__main__":
    unittest.main()
