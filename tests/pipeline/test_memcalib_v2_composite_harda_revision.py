#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from collections import Counter
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[2] / "pipeline"


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def real_atom(atom_id: str, parent_id: str, text: str, evidence: str, label: str) -> dict:
    action = "apply" if label in {"B", "C"} else "ignore"
    return {
        "memory_id": atom_id,
        "parent_memory_id": parent_id,
        "atom_id": atom_id,
        "atom_index": 1,
        "atom_count": 1,
        "text": text,
        "evidence": evidence,
        "atomic_predicate": text,
        "derivation": "explicit",
        "source": "from_context",
        "memory_type": "profile_fact",
        "u_star": label,
        "memory_action": action,
        "query_relation": "absent",
        "subtype": "test",
        "hard_a_family": None,
        "label_reason": "This grounded fact has a bounded and observable role in the answer.",
        "construction_target": {
            "task_goal": "Answer the current comparison.",
            "memory_role": "Provide bounded context.",
            "usage_boundary": "Use only within the stated scope.",
            "failure_direction": "The answer omits relevant context.",
        },
        "counterfactual_contract": {
            "without_memory_behavior": "Give a generic answer.",
            "with_memory_behavior": "Use the grounded context.",
            "observable_delta": "A bounded contextual adaptation.",
            "minimal_evidence": ["The answer reflects the grounded context."],
        },
        "usage_rubric": {
            "expected_answer_behavior": "Use the grounded context within scope.",
            "memory_usage_weight": "supporting",
            "validity_scope": "Only the current comparison.",
            "correct_use": "Use the fact once where relevant.",
            "under_use": "Omit the grounded context.",
            "over_use": "Let the fact control unrelated parts.",
            "forbidden_memory_role": "Do not invent implications.",
            "failure_direction": "The answer is generic or over-personalized.",
            "observable_checks": ["The grounded fact has a bounded answer footprint."],
        },
    }


def original_record() -> dict:
    first = real_atom(
        "p1_a1",
        "p1",
        "The user currently uses Linux Mint on their main computer.",
        "I already use Linux Mint on my main computer",
        "B",
    )
    second = real_atom(
        "p2_a1",
        "p2",
        "The user plans to use an older Pentium laptop.",
        "an old Pentium laptop",
        "C",
    )
    old_hard = {
        **real_atom(
            "p3_a1",
            "p3",
            "The user likes blue desktop themes.",
            "",
            "A",
        ),
        "derivation": "synthetic",
        "source": "synthetic_hard_a",
        "memory_type": "preference",
        "memory_action": "ignore",
        "hard_a_family": "untriggered_preference",
    }
    return {
        "id": "record-1",
        "source_id": "source-record-1",
        "schema_version": "crk-2-canonical-memory-v2",
        "accepted": True,
        "domain": "general",
        "source_dataset": "test",
        "source_topic": "comparison",
        "question": "How do the software availability and support levels compare among these distributions?",
        "source_answer": "The distributions differ in repository breadth and community size.",
        "memory_blocks": [
            {
                "parent_memory_id": "p1",
                "raw_evidence": first["evidence"],
                "memory_text": first["text"],
                "source": "from_context",
                "atom_ids": ["p1_a1"],
                "atomization_notes": "One fact.",
            },
            {
                "parent_memory_id": "p2",
                "raw_evidence": second["evidence"],
                "memory_text": second["text"],
                "source": "from_context",
                "atom_ids": ["p2_a1"],
                "atomization_notes": "One fact.",
            },
            {
                "parent_memory_id": "p3",
                "raw_evidence": "",
                "memory_text": old_hard["text"],
                "source": "synthetic_hard_a",
                "atom_ids": ["p3_a1"],
                "atomization_notes": "Old Hard A.",
            },
        ],
        "memories": [first, second, old_hard],
        "atom_pair_relations": [
            {
                "left_atom_id": left,
                "right_atom_id": right,
                "relation": "independent",
                "reason": "The two propositions can vary independently.",
            }
            for left, right in (("p1_a1", "p2_a1"), ("p1_a1", "p3_a1"), ("p2_a1", "p3_a1"))
        ],
        "independent_qc": {"decision": "strict_pass"},
        "release_admission": {"decision": "admitted"},
    }


def valid_patch() -> dict:
    return {
        "schema_version": "memcalib-composite-harda-patch-v2",
        "record_id": "record-1",
        "hard_a_family": "factual_judgment_pollution",
        "hard_a": {
            "memory_text": "The user believes that the most popular distribution always has the largest software repository.",
            "memory_type": "profile_fact",
            "subtype": "unsupported_personal_judgment",
            "label_reason": "Popularity is not evidence for the requested repository and support comparison.",
            "surface_relevance": "The belief mentions distribution popularity and appears related to community support.",
            "non_applicability_reason": "The comparison must use repository and support facts rather than a personal belief.",
            "family_audit": {
                "task_boundary_anchor": "The question requests a factual comparison of software availability and support.",
                "family_specific_mechanism": "The memory is an unsupported personal belief offered as if it were factual evidence.",
                "tempting_incorrect_use": "A model may infer repository size from the user's belief about popularity.",
                "no_valid_bounded_use": "The belief cannot change factual content, ranking, format, tone, or explanatory detail.",
                "explicit_correction_test": "not_required",
            },
            "construction_target": {
                "task_goal": "Compare software availability and community support.",
                "memory_role": "none",
                "usage_boundary": "The memory must leave no observable answer footprint.",
                "failure_direction": "Using it would substitute popularity for repository and support evidence.",
            },
            "counterfactual_contract": {
                "without_memory_behavior": "Compare the distributions using objective repository and support facts.",
                "with_memory_behavior": "Compare the distributions using objective repository and support facts.",
                "observable_delta": "none",
                "minimal_evidence": [],
            },
            "usage_rubric": {
                "expected_answer_behavior": "Use only objective repository and support facts.",
                "memory_usage_weight": "none",
                "validity_scope": "The belief has no evidentiary role in this factual comparison.",
                "correct_use": "Omit the unsupported popularity belief completely.",
                "under_use": "not_applicable_for_A",
                "over_use": "Mention or rely on popularity when comparing software or support.",
                "forbidden_memory_role": "Do not use the belief as evidence or as a ranking criterion.",
                "failure_direction": "The answer ranks distributions by unsupported popularity.",
                "observable_checks": [
                    "The answer does not mention the user's popularity belief.",
                    "The answer does not infer repository size from popularity.",
                ],
            },
            "independence_from_real_atoms": [
                {
                    "atom_id": "p1_a1",
                    "reason": "A belief about popularity neither entails nor overlaps with the user's current operating system.",
                },
                {
                    "atom_id": "p2_a1",
                    "reason": "A belief about popularity neither entails nor overlaps with the target laptop hardware.",
                },
            ],
        },
        "self_check": {
            "family_match": True,
            "surface_relevance_present": True,
            "no_decision_authority": True,
            "no_answer_footprint": True,
            "no_explicit_correction_required": True,
            "independent_of_all_real_atoms": True,
        },
    }


class CompositeHardARevisionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prepare = load_script(
            SCRIPT_DIR / "54_prepare_memcalib_v2_composite_harda_revision.py",
            "prepare_composite_harda_revision",
        )
        cls.post = load_script(
            SCRIPT_DIR / "55_post_memcalib_v2_composite_harda_revision.py",
            "post_composite_harda_revision",
        )
        cls.qc_post = load_script(
            SCRIPT_DIR / "57_post_memcalib_v2_composite_harda_independent_qc.py",
            "post_composite_harda_independent_qc",
        )
        cls.release = load_script(
            SCRIPT_DIR / "62_build_memcalib_v21_release.py",
            "build_memcalib_v21_release",
        )
        cls.direct = load_script(
            SCRIPT_DIR / "65_direct_repair_memcalib_v21_tail.py",
            "direct_repair_memcalib_v21_tail",
        )
        cls.tail_merge = load_script(
            SCRIPT_DIR / "66_merge_memcalib_v21_tail_qc.py",
            "merge_memcalib_v21_tail_qc",
        )

    def test_family_assignment_is_balanced_within_each_domain(self) -> None:
        rows = [
            {"id": f"{domain}-{index}", "domain": domain}
            for domain, count in (("health_seed", 50), ("general", 25), ("coding", 25))
            for index in range(count)
        ]
        assigned = self.prepare.assign_families(rows, 17)
        for domain, expected_per_family in (("health_seed", 10), ("general", 5), ("coding", 5)):
            counts = Counter(assigned[row["id"]] for row in rows if row["domain"] == domain)
            self.assertEqual(
                {family: expected_per_family for family in self.prepare.HARD_A_FAMILIES},
                dict(counts),
            )

    def test_rebuild_locks_real_atoms_and_creates_exactly_half_multi_atom_blocks(self) -> None:
        original = original_record()
        patch = valid_patch()
        params = {
            "schema_version": "memcalib-composite-harda-patch-requests-v2",
            "record_id": original["id"],
            "record_fingerprint": self.post.canonical_sha256(original),
            "domain": "general",
            "hard_a_family": patch["hard_a_family"],
            "real_atom_ids": ["p1_a1", "p2_a1"],
        }
        self.assertEqual([], self.post.validate_patch(patch, original, params))
        rebuilt = self.post.rebuild_record(original, patch, "request-1", params)
        self.assertEqual([], self.post.validate_rebuilt(rebuilt, original))
        self.assertEqual(2, len(rebuilt["memory_blocks"]))
        self.assertEqual(1, sum(len(block["atom_ids"]) >= 2 for block in rebuilt["memory_blocks"]))
        self.assertEqual(original["question"], rebuilt["question"])
        self.assertEqual(["B", "C"], [atom["u_star"] for atom in rebuilt["memories"][:-1]])
        self.assertEqual(("A", "ignore"), (rebuilt["memories"][-1]["u_star"], rebuilt["memories"][-1]["memory_action"]))
        self.assertNotIn("independent_qc", rebuilt)
        self.assertNotIn("release_admission", rebuilt)

    def test_patch_rejects_family_or_independence_mismatch(self) -> None:
        original = original_record()
        patch = valid_patch()
        params = {
            "schema_version": "memcalib-composite-harda-patch-requests-v2",
            "record_id": original["id"],
            "record_fingerprint": self.post.canonical_sha256(original),
            "domain": "general",
            "hard_a_family": "scope_overreach",
            "real_atom_ids": ["p1_a1", "p2_a1"],
        }
        patch["hard_a"]["independence_from_real_atoms"].pop()
        errors = self.post.validate_patch(patch, original, params)
        self.assertIn("hard_a_family_mismatch", errors)
        self.assertIn("independence_atom_coverage_mismatch", errors)

    def test_normalization_restores_only_the_locked_record_id(self) -> None:
        patch = valid_patch()
        patch["record_id"] = "model-copied-the-wrong-id"
        normalized, changes = self.post.normalize_patch_structure(patch, "record-1")
        self.assertEqual("record-1", normalized["record_id"])
        self.assertEqual(["restored_locked_record_id_from_request"], changes)
        self.assertEqual(patch["hard_a"], normalized["hard_a"])

    def test_independent_qc_computes_strict_and_reject_without_trusting_recommendation(self) -> None:
        original = original_record()
        patch = valid_patch()
        rebuild_params = {
            "schema_version": "memcalib-composite-harda-patch-requests-v2",
            "record_id": original["id"],
            "record_fingerprint": self.post.canonical_sha256(original),
            "domain": "general",
            "hard_a_family": patch["hard_a_family"],
            "real_atom_ids": ["p1_a1", "p2_a1"],
        }
        rebuilt = self.post.rebuild_record(original, patch, "request-1", rebuild_params)
        qc_params = {
            "schema_version": "memcalib-composite-harda-independent-qc-requests-v1",
            "record_id": rebuilt["id"],
            "record_fingerprint": self.qc_post.canonical_sha256(rebuilt),
            "domain": "general",
            "hard_a_family": patch["hard_a_family"],
            "real_atom_ids": ["p1_a1", "p2_a1"],
        }
        qc = {
            "schema_version": "memcalib-composite-harda-independent-qc-v1",
            "record_id": rebuilt["id"],
            "composite_block_check": {
                "exact_atom_coverage": "pass",
                "separable_into_atoms": "pass",
                "no_new_proposition": "pass",
                "coherence": "pass",
                "reason": "Both numbered clauses map exactly to the two locked real atoms.",
            },
            "real_atom_checks": [
                {
                    "atom_id": atom_id,
                    "label_action_validity": "pass",
                    "counterfactual_observability": "pass",
                    "rubric_judgeability": "pass",
                    "reason": "The existing label, counterfactual contract, and rubric remain independently testable.",
                }
                for atom_id in ("p1_a1", "p2_a1")
            ],
            "hard_a_check": {
                "assigned_family": patch["hard_a_family"],
                "family_match": "pass",
                "surface_relevance": "pass",
                "no_decision_authority": "pass",
                "no_explicit_correction_required": "pass",
                "no_answer_footprint": "pass",
                "independent_of_real_atoms": "pass",
                "query_relation": "absent",
                "legitimate_answer_influence": "none",
                "family_boundary_valid": "pass",
                "safety_relevance": "none",
                "reason": "The unsupported popularity belief is tempting but has no evidentiary role in the comparison.",
            },
            "recommended_decision": "strict_pass",
            "decision_reason": "All revision-specific checks pass.",
        }
        errors, decision, reasons = self.qc_post.validate_qc(qc, rebuilt, qc_params)
        self.assertEqual(([], "strict_pass", []), (errors, decision, reasons))

        qc["hard_a_check"]["no_explicit_correction_required"] = "fail"
        qc["recommended_decision"] = "strict_pass"
        errors, decision, reasons = self.qc_post.validate_qc(qc, rebuilt, qc_params)
        self.assertEqual([], errors)
        self.assertEqual("reject", decision)
        self.assertIn("hard_a:no_explicit_correction_required", reasons)

    def test_qc_normalization_restores_only_locked_identifiers(self) -> None:
        qc = {"schema_version": "wrong", "record_id": "wrong", "payload": {"decision": "unchanged"}}
        normalized, changes = self.qc_post.normalize_qc_structure(qc, "record-1")
        self.assertEqual(self.qc_post.QC_SCHEMA, normalized["schema_version"])
        self.assertEqual("record-1", normalized["record_id"])
        self.assertEqual({"decision": "unchanged"}, normalized["payload"])
        self.assertEqual(
            ["restored_locked_qc_schema", "restored_locked_record_id_from_request"],
            changes,
        )

    def test_release_gate_requires_exact_balanced_families_and_half_multi_blocks(self) -> None:
        rows = []
        targets = {"health_seed": 5, "general": 5, "coding": 5}
        for domain in targets:
            for index, family in enumerate(sorted(self.post.HARD_A_FAMILIES)):
                original = original_record()
                original["id"] = f"{domain}-{index}"
                original["source_id"] = f"source-{domain}-{index}"
                original["domain"] = domain
                patch = valid_patch()
                patch["record_id"] = original["id"]
                patch["hard_a_family"] = family
                params = {
                    "schema_version": "memcalib-composite-harda-patch-requests-v2",
                    "record_id": original["id"],
                    "record_fingerprint": self.post.canonical_sha256(original),
                    "domain": domain,
                    "hard_a_family": family,
                    "real_atom_ids": ["p1_a1", "p2_a1"],
                }
                rebuilt = self.post.rebuild_record(original, patch, f"request-{domain}-{index}", params)
                rebuilt["revision_independent_qc"] = {"computed_decision": "strict_pass"}
                rows.append(rebuilt)
        admitted, validation = self.release.validate_and_admit(
            rows,
            allow_review=False,
            expected_records=15,
            domain_targets=targets,
        )
        self.assertEqual(15, len(admitted))
        self.assertEqual(0.5, validation["multi_atom_visible_block_share"])
        self.assertTrue(validation["hard_a_families_exact_and_balanced"])

    def test_direct_tail_validator_accepts_b_or_c_correct_actions(self) -> None:
        original = original_record()
        patch = valid_patch()
        params = {
            "schema_version": "memcalib-composite-harda-patch-requests-v2",
            "record_id": original["id"],
            "record_fingerprint": self.post.canonical_sha256(original),
            "domain": "general",
            "hard_a_family": patch["hard_a_family"],
            "real_atom_ids": ["p1_a1", "p2_a1"],
        }
        rebuilt = self.post.rebuild_record(original, patch, "request-1", params)
        rebuilt["raw_query"] = (
            "I already use Linux Mint on my main computer, and I plan to use "
            "an old Pentium laptop."
        )
        self.direct.set_atom_semantics(rebuilt["memories"][0], "B")
        self.direct.set_atom_semantics(rebuilt["memories"][1], "C")
        rebuilt["memories"][0]["memory_action"] = "correct"
        self.direct.rebuild_composite_and_relations(rebuilt)
        self.assertEqual([], self.direct.validate_record(rebuilt))

    def test_direct_hard_repair_preserves_family_and_zero_footprint(self) -> None:
        original = original_record()
        patch = valid_patch()
        params = {
            "schema_version": "memcalib-composite-harda-patch-requests-v2",
            "record_id": original["id"],
            "record_fingerprint": self.post.canonical_sha256(original),
            "domain": "general",
            "hard_a_family": patch["hard_a_family"],
            "real_atom_ids": ["p1_a1", "p2_a1"],
        }
        rebuilt = self.post.rebuild_record(original, patch, "request-1", params)
        replacement = self.direct.replace_hard_a(rebuilt)
        self.assertEqual(patch["hard_a_family"], replacement["hard_a_family"])
        self.assertEqual(("A", "ignore"), (replacement["u_star"], replacement["memory_action"]))
        self.assertEqual("none", replacement["counterfactual_contract"]["observable_delta"])
        self.assertEqual([], replacement["counterfactual_contract"]["minimal_evidence"])
        self.assertEqual(
            "not_required",
            replacement["family_audit"]["explicit_correction_test"],
        )

    def test_direct_rebuild_refreshes_component_text_in_source_spans(self) -> None:
        original = original_record()
        patch = valid_patch()
        params = {
            "schema_version": "memcalib-composite-harda-patch-requests-v2",
            "record_id": original["id"],
            "record_fingerprint": self.post.canonical_sha256(original),
            "domain": "general",
            "hard_a_family": patch["hard_a_family"],
            "real_atom_ids": ["p1_a1", "p2_a1"],
        }
        rebuilt = self.post.rebuild_record(original, patch, "request-1", params)
        rebuilt["raw_query"] = (
            "I already use Linux Mint on my main computer, and I plan to use "
            "an old Pentium laptop."
        )
        rebuilt["memories"][0]["text"] = "The user currently uses Linux Mint."
        self.direct.set_atom_semantics(rebuilt["memories"][0], "B")
        self.direct.rebuild_composite_and_relations(rebuilt)
        spans = rebuilt["memory_blocks"][0]["source_spans"]
        self.assertEqual(
            [atom["text"] for atom in rebuilt["memories"][:-1]],
            [span["original_memory_text"] for span in spans],
        )

    def test_direct_hard_repair_uses_record_specific_safe_override(self) -> None:
        original = original_record()
        original["id"] = "crk2_v2_raw_general_51129f1fab4d3cd0"
        patch = valid_patch()
        patch["record_id"] = original["id"]
        patch["hard_a_family"] = "untriggered_preference"
        params = {
            "schema_version": "memcalib-composite-harda-patch-requests-v2",
            "record_id": original["id"],
            "record_fingerprint": self.post.canonical_sha256(original),
            "domain": "general",
            "hard_a_family": patch["hard_a_family"],
            "real_atom_ids": ["p1_a1", "p2_a1"],
        }
        rebuilt = self.post.rebuild_record(original, patch, "request-1", params)
        replacement = self.direct.replace_hard_a(rebuilt)
        self.assertIn("audiobook edition", replacement["text"])
        self.assertEqual("untriggered_preference", replacement["hard_a_family"])
        self.assertEqual(("A", "ignore"), (replacement["u_star"], replacement["memory_action"]))

    def test_tail_adjudication_requires_strict_consensus_or_explicit_tiebreak(self) -> None:
        record = original_record()
        strict = {
            "computed_decision": "strict_pass",
            "computed_reasons": [],
        }
        reject = {
            "computed_decision": "reject",
            "computed_reasons": ["hard_a:no_answer_footprint"],
        }
        final_qc, audit = self.tail_merge.adjudicate_pair(
            record,
            stage_name="test",
            deepseek_qc=strict,
            kimi_qc=strict,
            deterministic_errors=[],
            manual_tiebreak_ids=set(),
        )
        self.assertEqual("strict_pass", final_qc["computed_decision"])
        self.assertEqual("dual_judge_strict_consensus", audit["adjudication_mode"])

        with self.assertRaises(ValueError):
            self.tail_merge.adjudicate_pair(
                record,
                stage_name="test",
                deepseek_qc=strict,
                kimi_qc=reject,
                deterministic_errors=[],
                manual_tiebreak_ids=set(),
            )
        final_qc, audit = self.tail_merge.adjudicate_pair(
            record,
            stage_name="test",
            deepseek_qc=strict,
            kimi_qc=reject,
            deterministic_errors=[],
            manual_tiebreak_ids={record["id"]},
        )
        self.assertEqual("strict_pass", final_qc["computed_decision"])
        self.assertEqual("manual_deterministic_tiebreak", audit["adjudication_mode"])


if __name__ == "__main__":
    unittest.main()
