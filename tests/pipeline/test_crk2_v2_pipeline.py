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
        "domain": "health_seed",
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
        cls.grounding_repair = load_script(
            SCRIPT_DIR / "43_repair_crk2_v2_evidence_grounding.py", "grounding_repair_crk2_v2"
        )
        cls.pass_merge = load_script(
            SCRIPT_DIR / "44_merge_crk2_v2_deterministic_pass.py", "merge_crk2_v2_deterministic_pass"
        )
        cls.semantic_repair = load_script(
            SCRIPT_DIR / "45_prepare_crk2_v2_semantic_repair.py", "prepare_crk2_v2_semantic_repair"
        )
        cls.semantic_merge = load_script(
            SCRIPT_DIR / "46_merge_crk2_v2_semantic_repairs.py", "merge_crk2_v2_semantic_repairs"
        )
        cls.qc_candidates = load_script(
            SCRIPT_DIR / "47_build_crk2_v2_semantic_qc_candidates.py", "build_crk2_v2_semantic_qc_candidates"
        )
        cls.qc_merge = load_script(
            SCRIPT_DIR / "48_merge_crk2_v2_independent_qc_repairs.py", "merge_crk2_v2_independent_qc_repairs"
        )
        cls.reserve_reconstruction = load_script(
            SCRIPT_DIR / "49_prepare_crk2_v2_reserve_reconstruction.py", "prepare_crk2_v2_reserve_reconstruction"
        )
        cls.metadata_backfill = load_script(
            SCRIPT_DIR / "52_backfill_crk2_v2_source_metadata.py", "backfill_crk2_v2_source_metadata"
        )
        cls.release_artifacts = load_script(
            SCRIPT_DIR / "53_build_multidomain_release_artifacts.py", "build_multidomain_release_artifacts"
        )
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

    def test_domain_balanced_selection_respects_domain_targets_and_source_capacity(self) -> None:
        rows = []
        for domain, sources in (("health_seed", ("med-a", "med-b")), ("general", ("human", "synthetic"))):
            for source in sources:
                count = 10 if source != "human" else 2
                for index in range(count):
                    rows.append(
                        {
                            "id": f"{domain}-{source}-{index}",
                            "domain": domain,
                            "source_dataset": source,
                            "topic": f"topic-{index % 2}",
                            "raw_selection": {"seed_complexity": "medium"},
                        }
                    )
        selected = self.prepare.select_domain_balanced(rows, {"health_seed": 8, "general": 8}, 11)
        self.assertEqual(8, sum(row["domain"] == "health_seed" for row in selected))
        self.assertEqual(8, sum(row["domain"] == "general" for row in selected))
        self.assertEqual(2, sum(row["source_dataset"] == "human" for row in selected))
        self.assertEqual(6, sum(row["source_dataset"] == "synthetic" for row in selected))

    def test_valid_record_passes_deterministic_gate(self) -> None:
        record, params = valid_record()
        errors, audit = self.post.validate_record(record, params)
        self.assertEqual([], errors)
        self.assertEqual(3, len(audit))
        self.assertFalse(any(item["flag"] for item in audit))

    def test_normalization_preserves_domain_and_upstream_lineage(self) -> None:
        record, params = valid_record()
        params["source_license"] = "test-license"
        params["raw_selection"] = {"eligible": True}
        params["semantic_qc"] = {"state": "strict_pass"}
        params["semantic_admission"] = {"decision": "admitted_strict"}
        params["source_metadata"] = {"dataset_revision": "test-revision"}
        normalized = self.post.normalize_record(record, params, "request", [])
        self.assertEqual("health_seed", normalized["domain"])
        self.assertEqual("test-license", normalized["source_license"])
        self.assertEqual({"eligible": True}, normalized["raw_selection"])
        self.assertEqual("strict_pass", normalized["semantic_qc"]["state"])
        self.assertEqual({"dataset_revision": "test-revision"}, normalized["source_metadata"])

    def test_source_metadata_backfill_requires_complete_stack_exchange_attribution(self) -> None:
        record, _ = valid_record()
        record.update(
            {
                "id": "request",
                "source_id": "raw1",
                "source_dataset": self.metadata_backfill.STACK_EXCHANGE_DATASET,
            }
        )
        metadata = {
            "question_author_name": "Question Author",
            "question_author_profile": "https://stackoverflow.com/users/1/example",
            "answer_author": "Answer Author",
            "answer_author_profile": "https://stackoverflow.com/users/2/example",
            "question_url": "https://stackoverflow.com/questions/3/example",
            "attribution_complete": True,
        }
        repaired, audit = self.metadata_backfill.backfill_rows([record], {"raw1": metadata})
        self.assertEqual(metadata, repaired[0]["source_metadata"])
        self.assertEqual(1, audit["stack_exchange_attribution_complete"])

        incomplete = dict(metadata)
        incomplete["question_author_name"] = ""
        with self.assertRaisesRegex(ValueError, "incomplete Stack Exchange attribution"):
            self.metadata_backfill.backfill_rows([record], {"raw1": incomplete})

    def test_release_artifact_validation_rejects_incomplete_attribution(self) -> None:
        record, params = valid_record()
        normalized = self.post.normalize_record(record, params, "request", [])
        normalized["source_dataset"] = self.release_artifacts.STACK_EXCHANGE_DATASET
        normalized["release_admission"] = {"decision": "admitted_strict"}
        normalized["independent_qc"] = {"decision": "strict_pass"}
        normalized["source_metadata"] = {
            "question_author_name": "Question Author",
            "question_author_profile": "https://stackoverflow.com/users/1/example",
            "answer_author": "Answer Author",
            "answer_author_profile": "https://stackoverflow.com/users/2/example",
            "question_url": "https://stackoverflow.com/questions/3/example",
            "attribution_complete": True,
        }
        audit = self.release_artifacts.validate_release([normalized], 1, {"health_seed": 1})
        self.assertEqual(1, audit["stack_exchange_attribution_complete"])

        normalized["source_metadata"]["attribution_complete"] = False
        with self.assertRaisesRegex(ValueError, "attribution_not_complete"):
            self.release_artifacts.validate_release([normalized], 1, {"health_seed": 1})
        self.assertEqual("#", self.release_artifacts.safe_url("javascript:alert(1)"))

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

    def test_independent_qc_treats_local_atomicity_concern_as_review(self) -> None:
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
                    "reason": "The supplied behavior is observable and otherwise valid for this task.",
                }
            )
        checks[0]["atomicity"] = "fail"
        qc = {
            "schema_version": "crk-2-independent-qc-v2",
            "record_id": record["id"],
            "atom_checks": checks,
            "pair_checks": record["atom_pair_relations"],
            "record_decision": "reject",
            "issues": ["The first atom may preserve more than one tightly coupled qualifier."],
        }
        errors, decision, reasons = self.qc_post.validate_qc(qc, record)
        self.assertEqual([], errors)
        self.assertEqual("review", decision)
        self.assertIn("p1_a1:atomicity_advisory", reasons)

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

    def test_grounding_repair_uses_exact_source_span_and_passes_validator(self) -> None:
        record, params = valid_record()
        record["memory_blocks"][0]["raw_evidence"] = "The person uses warfarin every day."
        record["memories"][0]["evidence"] = "The person uses warfarin every day."
        record["qc"]["evidence_grounding_pass"] = False
        errors, _ = self.post.validate_record(record, params)
        repaired, actions, failures = self.grounding_repair.repair_record(
            {
                "errors": errors,
                "user_defined_params": params,
                "parsed_record": record,
            },
            min_score=0.25,
        )
        self.assertEqual([], failures)
        self.assertEqual(2, len(actions))
        self.assertEqual("I take warfarin daily.", repaired["memory_blocks"][0]["raw_evidence"])
        self.assertEqual("I take warfarin daily.", repaired["memories"][0]["evidence"])
        self.assertEqual([], self.post.validate_record(repaired, params)[0])

    def test_grounding_repair_refuses_records_with_other_errors(self) -> None:
        record, params = valid_record()
        repaired, actions, failures = self.grounding_repair.repair_record(
            {
                "errors": ["memory_0_ungrounded_evidence", "memory_0_bad_label"],
                "user_defined_params": params,
                "parsed_record": record,
            },
            min_score=0.25,
        )
        self.assertEqual({}, repaired)
        self.assertEqual([], actions)
        self.assertEqual(["not_grounding_only"], failures)

    def test_grounding_repair_corrects_empty_context_source(self) -> None:
        record, params = valid_record()
        record["memory_blocks"][0]["source"] = "from_context"
        record["memory_blocks"][0]["raw_evidence"] = "The person uses warfarin every day."
        record["memories"][0]["source"] = "from_context"
        record["memories"][0]["evidence"] = "The person uses warfarin every day."
        record["qc"]["evidence_grounding_pass"] = False
        errors, _ = self.post.validate_record(record, params)
        repaired, actions, failures = self.grounding_repair.repair_record(
            {
                "errors": errors,
                "user_defined_params": params,
                "parsed_record": record,
            },
            min_score=0.25,
        )
        self.assertEqual([], failures)
        self.assertEqual("from_question", repaired["memory_blocks"][0]["source"])
        self.assertEqual("from_question", repaired["memories"][0]["source"])
        self.assertTrue(any(action.get("reason") == "declared_source_empty" for action in actions))
        self.assertEqual([], self.post.validate_record(repaired, params)[0])

    def test_deterministic_pass_merge_preserves_request_order_and_exclusions(self) -> None:
        requests = [
            {"request_id": f"request-{source_id}", "user_defined_params": {"id": source_id, "domain": "general"}}
            for source_id in ("source-a", "source-b", "source-c")
        ]
        records = [
            {"id": "record-c", "source_id": "source-c"},
            {"id": "record-a", "source_id": "source-a"},
        ]
        resolved, excluded = self.pass_merge.merge_in_request_order(requests, records)
        self.assertEqual(["source-a", "source-c"], [row["source_id"] for row in resolved])
        self.assertEqual(["source-b"], [row["source_id"] for row in excluded])
        self.assertEqual("deterministic_reject", excluded[0]["exclusion_reason"])

    def test_semantic_repair_request_preserves_record_id_and_qc_feedback(self) -> None:
        record, params = valid_record()
        record.update(
            {
                "id": "crk2_v2_raw1",
                "source_id": "raw1",
                "domain": "health_seed",
                "source_dataset": "source-a",
                "independent_qc": {
                    "decision": "reject",
                    "declared_decision": "reject",
                    "decision_reasons": ["p1_a1:hard_failure"],
                    "issues": ["The question repeats the first memory atom."],
                    "atom_checks": [],
                    "pair_checks": [],
                },
            }
        )
        template = (SCRIPT_DIR / "prompts" / "repair_crk2_memory_benchmark_record_v2_semantic_en.txt").read_text()
        request = self.semantic_repair.build_semantic_repair_request(
            record,
            {"request_id": "crk2_v2_raw1", "user_defined_params": params},
            retry_round=1,
            template=template,
        )
        self.assertEqual("crk2_v2_raw1", request["request_id"])
        lineage = request["user_defined_params"]["crk2_v2_semantic_repair"]
        self.assertEqual("crk2_v2_raw1", lineage["original_record_id"])
        content = request["prompt"][0]["content"]
        self.assertIn("must not state, paraphrase, entail", content)
        self.assertIn("The question repeats the first memory atom.", content)
        self.assertIn("B or C + correct, never A", content)

    def test_semantic_repair_v2_prompt_preserves_leaked_atoms_and_rewrites_question(self) -> None:
        content = (SCRIPT_DIR / "prompts" / "repair_crk2_memory_benchmark_record_v2_semantic_v2_en.txt").read_text()
        self.assertIn("keep the atom in memory and remove", content)
        self.assertIn("Use 3-6 parent memory_blocks and 3-8 atomic memories", content)
        self.assertIn("query_relation must equal absent", content)
        self.assertIn("B or C + correct, never A", content)

    def test_normalization_preserves_semantic_repair_lineage(self) -> None:
        record, params = valid_record()
        params["crk2_v2_semantic_repair"] = {
            "schema_version": "crk2-v2-semantic-repair-requests-v1",
            "retry_round": 1,
        }
        normalized = self.post.normalize_record(record, params, "crk2_v2_raw1", [])
        self.assertEqual(1, normalized["semantic_repair"]["retry_round"])

    def test_semantic_merge_replaces_targets_and_retains_unresolved_originals(self) -> None:
        base = [
            {"id": "record-a", "source_id": "source-a", "domain": "general"},
            {"id": "record-b", "source_id": "source-b", "domain": "coding"},
            {"id": "record-c", "source_id": "source-c", "domain": "health_seed"},
        ]
        targets = [
            {"id": "record-b", "independent_qc": {"decision_reasons": ["p1:hard_failure"]}},
            {"id": "record-c", "independent_qc": {"decision_reasons": ["p2:hard_failure"]}},
        ]
        repaired = [{"id": "record-b", "source_id": "source-b", "domain": "coding", "repaired": True}]
        merged, unresolved = self.semantic_merge.merge_semantic_repairs(base, targets, repaired)
        self.assertEqual(["record-a", "record-b", "record-c"], [row["id"] for row in merged])
        self.assertTrue(merged[1]["repaired"])
        self.assertEqual("source-c", merged[2]["source_id"])
        self.assertEqual(["record-c"], [row["record_id"] for row in unresolved])

    def test_semantic_merge_appends_nonoverlapping_reserve_records(self) -> None:
        base = [{"id": "record-a", "source_id": "source-a", "domain": "general"}]
        additional = [{"id": "record-b", "source_id": "source-b", "domain": "coding"}]
        merged, unresolved = self.semantic_merge.merge_semantic_repairs(base, [], [], additional)
        self.assertEqual(["record-a", "record-b"], [row["id"] for row in merged])
        self.assertEqual([], unresolved)

    def test_semantic_qc_candidates_include_only_repairs_and_prior_invalid(self) -> None:
        benchmark = [
            {"id": "record-a", "source_id": "source-a", "domain": "general"},
            {"id": "record-b", "source_id": "source-b", "domain": "coding"},
            {"id": "record-c", "source_id": "source-c", "domain": "health_seed"},
        ]
        repaired = [{"id": "record-b", "source_id": "source-b", "domain": "coding", "repaired": True}]
        prior_invalid = [{"record_id": "record-c", "errors": ["bad_json"]}]
        candidates = self.qc_candidates.build_candidates(benchmark, repaired, prior_invalid)
        self.assertEqual(["record-b", "record-c"], [row["id"] for row in candidates])
        self.assertTrue(candidates[0]["repaired"])

    def test_semantic_qc_candidates_append_reserve_records(self) -> None:
        benchmark = [{"id": "record-a", "source_id": "source-a", "domain": "general"}]
        additional = [{"id": "record-b", "source_id": "source-b", "domain": "coding"}]
        candidates = self.qc_candidates.build_candidates(benchmark, [], [], additional)
        self.assertEqual(["record-b"], [row["id"] for row in candidates])

    def test_qc_merge_replaces_only_retried_records(self) -> None:
        prior = {
            "strict_pass": [{"id": "strict-old"}],
            "review": [{"id": "review-old"}],
            "reject": [{"id": "repair-me"}, {"id": "reject-old"}],
            "invalid": [{"record_id": "retry-invalid"}],
        }
        retry = {
            "strict_pass": [{"id": "repair-me"}],
            "review": [{"id": "retry-invalid"}],
            "reject": [],
            "invalid": [],
        }
        merged = self.qc_merge.merge_qc_buckets(prior, retry)
        self.assertEqual(["strict-old", "repair-me"], [row["id"] for row in merged["strict_pass"]])
        self.assertEqual(["review-old", "retry-invalid"], [row["id"] for row in merged["review"]])
        self.assertEqual(["reject-old"], [row["id"] for row in merged["reject"]])
        self.assertEqual([], merged["invalid"])

    def test_qc_merge_appends_new_reserve_record(self) -> None:
        prior = {"strict_pass": [{"id": "old"}], "review": [], "reject": [], "invalid": []}
        retry = {"strict_pass": [{"id": "reserve"}], "review": [], "reject": [], "invalid": []}
        merged = self.qc_merge.merge_qc_buckets(prior, retry)
        self.assertEqual(["old", "reserve"], [row["id"] for row in merged["strict_pass"]])

    def test_reserve_reconstruction_request_requires_real_applied_memory(self) -> None:
        record, params = valid_record()
        row = {
            "request_id": "crk2_v2_raw1",
            "errors": ["missing_real_applied_memory"],
            "user_defined_params": params,
            "parsed_record": record,
        }
        template = (SCRIPT_DIR / "prompts" / "reconstruct_crk2_memory_benchmark_record_v2_en.txt").read_text()
        request = self.reserve_reconstruction.build_reconstruction_request(row, 1, template)
        self.assertEqual("crk2_v2_raw1", request["request_id"])
        self.assertIn("Include at least one real B/C atom", request["prompt"][0]["content"])
        self.assertEqual(1, request["user_defined_params"]["crk2_v2_reserve_reconstruction"]["retry_round"])

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
