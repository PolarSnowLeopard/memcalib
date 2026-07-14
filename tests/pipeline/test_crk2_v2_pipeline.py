#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[2] / "pipeline"


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def rubric(weight: str) -> dict:
    return {
        "expected_answer_behavior": "The answer exhibits the required behavior.",
        "memory_usage_weight": weight,
        "validity_scope": "Only the current task.",
        "correct_use": "Use the stated constraint within scope.",
        "under_use": "Omit the required observable behavior.",
        "over_use": "Extend the memory beyond its stated scope.",
        "forbidden_memory_role": "Do not invent additional facts.",
        "failure_direction": "The answer becomes insufficient or excessive.",
        "observable_checks": ["The required behavior is visible in the answer."],
    }


def contract(label: str, signal: str) -> dict:
    if label == "A":
        return {
            "without_memory_behavior": "Give the same general answer.",
            "with_memory_behavior": "Give the same general answer.",
            "observable_delta": "none",
            "minimal_evidence": [],
        }
    return {
        "without_memory_behavior": "Give general options without the user-specific restriction.",
        "with_memory_behavior": f"Add the user-specific restriction: {signal}.",
        "observable_delta": signal,
        "minimal_evidence": [signal],
    }


def memory(atom_id: str, parent_id: str, text: str, evidence: str, label: str, source: str) -> dict:
    action = "ignore" if label == "A" else "apply"
    return {
        "memory_id": atom_id,
        "parent_memory_id": parent_id,
        "atom_id": atom_id,
        "atom_index": 1,
        "atom_count": 1,
        "text": text,
        "evidence": evidence,
        "atomic_predicate": text,
        "derivation": "synthetic" if source == "synthetic_hard_a" else "explicit",
        "source": source,
        "memory_type": "preference" if source == "synthetic_hard_a" else "case_fact",
        "u_star": label,
        "memory_action": action,
        "query_relation": "absent",
        "subtype": "test_case",
        "hard_a_family": "untriggered_preference" if source == "synthetic_hard_a" else None,
        "label_reason": "This atom has a directly testable causal role in the answer.",
        "construction_target": {
            "task_goal": "Recommend a safe general option.",
            "memory_role": "Constrain or leave unchanged the answer.",
            "usage_boundary": "Only the stated restriction may be used.",
            "failure_direction": "Ignoring or overextending the restriction.",
        },
        "counterfactual_contract": contract(label, text),
        "usage_rubric": rubric({"A": "none", "B": "supporting", "C": "controlling"}[label]),
    }


def valid_record() -> tuple[dict, dict]:
    params = {
        "id": "raw1",
        "source_dataset": "OpenMed/MedDialog",
        "topic": "medication_treatment",
        "raw_question": "I take warfarin daily. I am allergic to aspirin. Which pain-relief option would be safest?",
        "dialogue_context": "",
    }
    memories = [
        memory("p1_a1", "p1", "The user takes warfarin daily.", "I take warfarin daily.", "C", "from_question"),
        memory("p2_a1", "p2", "The user is allergic to aspirin.", "I am allergic to aspirin.", "C", "from_question"),
        memory(
            "p3_a1",
            "p3",
            "The user prefers morning appointments.",
            "Synthetic near-topic preference for a different workflow.",
            "A",
            "synthetic_hard_a",
        ),
    ]
    blocks = [
        {
            "parent_memory_id": "p1",
            "raw_evidence": "I take warfarin daily.",
            "memory_text": "The user takes warfarin daily.",
            "source": "from_question",
            "atom_ids": ["p1_a1"],
            "atomization_notes": "One medication-use proposition.",
        },
        {
            "parent_memory_id": "p2",
            "raw_evidence": "I am allergic to aspirin.",
            "memory_text": "The user is allergic to aspirin.",
            "source": "from_question",
            "atom_ids": ["p2_a1"],
            "atomization_notes": "One allergy proposition.",
        },
        {
            "parent_memory_id": "p3",
            "raw_evidence": "Synthetic near-topic preference for a different workflow.",
            "memory_text": "The user prefers morning appointments.",
            "source": "synthetic_hard_a",
            "atom_ids": ["p3_a1"],
            "atomization_notes": "One scheduling preference.",
        },
    ]
    pairs = [
        {"left_atom_id": left, "right_atom_id": right, "relation": "independent", "reason": "The propositions can vary independently."}
        for left, right in (("p1_a1", "p2_a1"), ("p1_a1", "p3_a1"), ("p2_a1", "p3_a1"))
    ]
    record = {
        "schema_version": "crk-2-canonical-memory-v2",
        "accepted": True,
        "question": "What general factors should guide selection of a suitable over-the-counter option?",
        "memory_blocks": blocks,
        "memories": memories,
        "atom_pair_relations": pairs,
        "qc": {
            "evidence_grounding_pass": True,
            "query_isolation_pass": True,
            "atomicity_pass": True,
            "pairwise_independence_pass": True,
            "counterfactual_observability_pass": True,
            "label_action_consistency_pass": True,
            "rubric_objectivity_pass": True,
            "issues": [],
        },
        "notes": "",
    }
    return record, params


class Crk2V2PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prepare = load_script(SCRIPT_DIR / "29_prepare_crk2_v2_generation.py", "prepare_crk2_v2")
        cls.post = load_script(SCRIPT_DIR / "30_post_crk2_v2_generation.py", "post_crk2_v2")
        cls.qc_post = load_script(SCRIPT_DIR / "32_post_crk2_v2_independent_qc.py", "post_crk2_v2_qc")
        cls.repair = load_script(SCRIPT_DIR / "33_prepare_crk2_v2_repair.py", "repair_crk2_v2")
        cls.review = load_script(SCRIPT_DIR / "35_build_crk2_v2_review.py", "review_crk2_v2")
        cls.expert_audit = load_script(SCRIPT_DIR / "36_build_crk2_v2_expert_audit.py", "expert_audit_crk2_v2")

    def test_prompt_formalizes_correction_as_observable_use(self) -> None:
        prompt = (SCRIPT_DIR / "prompts" / "generate_crk2_memory_benchmark_record_v2_en.txt").read_text()
        self.assertIn("A plus correct is forbidden", prompt)
        self.assertIn("observable_delta", prompt)
        self.assertIn("atom_pair_relations", prompt)
        self.assertNotIn("unreasonable user request, such as avoiding necessary examination", prompt)

    def test_source_balanced_selection_is_exact_and_deterministic(self) -> None:
        rows = []
        for source in ("source-a", "source-b"):
            for index in range(60):
                rows.append(
                    {
                        "id": f"{source}-{index}",
                        "source_dataset": source,
                        "topic": f"topic-{index % 4}",
                        "raw_selection": {"seed_complexity": ("simple", "medium", "complex")[index % 3]},
                    }
                )
        first = self.prepare.select_source_balanced(rows, 100, 9)
        second = self.prepare.select_source_balanced(rows, 100, 9)
        self.assertEqual([row["id"] for row in first], [row["id"] for row in second])
        self.assertEqual(50, sum(row["source_dataset"] == "source-a" for row in first))
        self.assertEqual(50, sum(row["source_dataset"] == "source-b" for row in first))

    def test_valid_record_passes_deterministic_gate(self) -> None:
        record, params = valid_record()
        errors, audit = self.post.validate_record(record, params)
        self.assertEqual([], errors)
        self.assertEqual(3, len(audit))
        self.assertFalse(any(item["flag"] for item in audit))

    def test_a_cannot_use_correct_action(self) -> None:
        record, params = valid_record()
        record["memories"][2]["memory_action"] = "correct"
        errors, _ = self.post.validate_record(record, params)
        self.assertIn("memory_2_label_action_mismatch", errors)
        self.assertIn("memory_2_bad_synthetic_hard_a", errors)

    def test_bc_requires_observable_counterfactual_delta(self) -> None:
        record, params = valid_record()
        record["memories"][0]["counterfactual_contract"]["observable_delta"] = "none"
        record["memories"][0]["counterfactual_contract"]["minimal_evidence"] = []
        errors, _ = self.post.validate_record(record, params)
        self.assertIn("memory_0_bc_lacks_observable_delta", errors)

    def test_query_memory_lexical_leakage_is_rejected(self) -> None:
        record, params = valid_record()
        record["question"] = "The user takes warfarin daily. What option should be selected?"
        errors, audit = self.post.validate_record(record, params)
        self.assertIn("memory_0_query_lexical_leakage", errors)
        self.assertTrue(audit[0]["flag"])

    def test_pairwise_overlap_is_rejected(self) -> None:
        record, params = valid_record()
        record["atom_pair_relations"][0]["relation"] = "overlap"
        errors, _ = self.post.validate_record(record, params)
        self.assertIn("pair_0_not_independent", errors)

    def test_independent_qc_recomputes_declared_decision(self) -> None:
        record, _ = valid_record()
        record["id"] = "crk2_v2_raw1"
        checks = []
        for item in record["memories"]:
            checks.append(
                {
                    "atom_id": item["atom_id"],
                    "query_relation": "absent",
                    "atomicity": "pass",
                    "label_action_validity": "pass",
                    "counterfactual_observability": "pass",
                    "rubric_judgeability": "pass",
                    "recommended_u_star": item["u_star"],
                    "recommended_memory_action": item["memory_action"],
                    "reason": "The supplied behavior is independently observable and consistent.",
                }
            )
        checks[0]["query_relation"] = "overlap"
        qc = {
            "schema_version": "crk-2-independent-qc-v2",
            "record_id": record["id"],
            "atom_checks": checks,
            "pair_checks": record["atom_pair_relations"],
            "record_decision": "strict_pass",
            "issues": [],
        }
        errors, decision, reasons = self.qc_post.validate_qc(qc, record)
        self.assertEqual([], errors)
        self.assertEqual("reject", decision)
        self.assertIn("declared_strict_pass_overridden_by_reject", reasons)

    def test_repair_request_preserves_v2_contract_and_source_id(self) -> None:
        record, params = valid_record()
        request = self.repair.build_repair_request(
            {
                "errors": ["memory_0_ungrounded_evidence"],
                "user_defined_params": params,
                "parsed_record": record,
            },
            retry_round=1,
        )
        self.assertEqual("crk2_v2_raw1", request["request_id"])
        self.assertEqual(1, request["user_defined_params"]["crk2_v2_repair_round"])
        content = request["prompt"][0]["content"]
        self.assertIn("character-for-character", content)
        self.assertIn("B/C + correct, never A", content)
        self.assertIn("memory_0_ungrounded_evidence", content)

    def test_review_orders_rejects_first_and_exposes_full_protocol(self) -> None:
        accepted, _ = valid_record()
        rejected, _ = valid_record()
        accepted.update({"id": "accepted", "source_dataset": "source-a", "review_decision": "strict_pass"})
        rejected.update({"id": "rejected", "source_dataset": "source-b", "review_decision": "reject"})
        records = [rejected, accepted]
        summary = self.review.build_summary(records)
        page = self.review.render_html(records, summary)
        self.assertEqual({"reject": 1, "strict_pass": 1}, summary["decisions"])
        self.assertIn("counterfactual_contract", page)
        self.assertIn("问题—记忆隔离", page)
        self.assertIn("ArrowRight", page)
        self.assertIn("导出标注", page)

    def test_expert_audit_summary_marks_stress_sample_as_non_random(self) -> None:
        accepted, _ = valid_record()
        revised, _ = valid_record()
        accepted.update(
            {
                "id": "accepted",
                "source_dataset": "source-a",
                "source_topic": "topic-a",
                "prior_qc_decision": "strict_pass",
                "expert_audit": {
                    "decision": "accept",
                    "review_dimensions": ["rubric_objectivity"],
                    "selection_strata": ["multi_atom_parent"],
                    "findings": [],
                    "qc_rationale_assessment": "not_applicable",
                },
            }
        )
        revised.update(
            {
                "id": "revised",
                "source_dataset": "source-b",
                "source_topic": "topic-b",
                "prior_qc_decision": "strict_pass",
                "expert_audit": {
                    "decision": "revise",
                    "review_dimensions": ["atomicity"],
                    "selection_strata": ["strict_stratified"],
                    "findings": [{"type": "atomicity"}],
                    "qc_rationale_assessment": "not_applicable",
                },
            }
        )
        summary = self.expert_audit.build_summary(
            [accepted, revised],
            {
                "audit_scope": "practical_protocol_acceptance_audit",
                "selection_note_cn": "风险富集压力审查",
                "acceptance_threshold_cn": {"blocking": ["实质错误"], "advisory": ["措辞优化"]},
            },
        )
        self.assertEqual(50.0, summary["rates"]["strict_stress_non_accept"]["percent"])
        self.assertIn("不能外推", summary["rates"]["strict_stress_non_accept"]["interpretation_cn"])
        self.assertEqual({"atomicity": 1, "rubric_objectivity": 1}, summary["observed_dimensions"])
        self.assertEqual({"atomicity": 1}, summary["blocking_dimensions"])
        page = self.expert_audit.render_html([accepted, revised], summary)
        self.assertIn("Expert decision", page)
        self.assertIn("ArrowRight", page)
        self.assertIn("practical_protocol_acceptance_audit", page)
        self.assertIn("advisory-dimension", page)


if __name__ == "__main__":
    unittest.main()
