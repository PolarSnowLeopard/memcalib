from __future__ import annotations

import importlib.util
import sys
import unittest
from itertools import combinations
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


def atom(atom_id: str, parent_id: str, label: str, source: str) -> dict:
    action = "ignore" if label == "A" else "apply"
    return {
        "memory_id": atom_id,
        "parent_memory_id": parent_id,
        "atom_id": atom_id,
        "atom_index": 1,
        "atom_count": 4,
        "text": f"The user has a distinct remembered fact for {atom_id}.",
        "evidence": f"evidence for {atom_id}" if source != "synthetic_hard_a" else "",
        "atomic_predicate": f"The user has a distinct remembered fact for {atom_id}.",
        "derivation": "synthetic" if source == "synthetic_hard_a" else "explicit",
        "source": source,
        "memory_type": "case_fact",
        "u_star": label,
        "memory_action": action,
        "query_relation": "absent",
        "subtype": "test",
        "hard_a_family": "scope_overreach" if source == "synthetic_hard_a" else None,
        "label_reason": "Test supervision remains locked.",
        "construction_target": {},
        "counterfactual_contract": {},
        "usage_rubric": {},
    }


def source_record(record_id: str = "record-1", domain: str = "general") -> dict:
    atoms = [
        atom("p1_a1", "p1", "B", "from_question"),
        atom("p2_a1", "p2", "C", "from_context"),
        atom("p3_a1", "p3", "B", "from_question"),
        atom("hard_a1", "hard", "A", "synthetic_hard_a"),
    ]
    relations = [
        {
            "left_atom_id": left["atom_id"],
            "right_atom_id": right["atom_id"],
            "relation": "independent",
            "reason": "The two facts are independently observable.",
        }
        for left, right in combinations(atoms, 2)
    ]
    return {
        "id": record_id,
        "source_id": f"source-{record_id}",
        "schema_version": "crk-2-canonical-memory-v2.2",
        "domain": domain,
        "source_dataset": "test/source",
        "question": "Which option best satisfies the current constraints?",
        "memory_blocks": [
            {
                "parent_memory_id": item["parent_memory_id"],
                "memory_text": item["text"],
                "source": item["source"],
                "atom_ids": [item["atom_id"]],
                "atomization_notes": "locked",
            }
            for item in atoms
        ],
        "memories": atoms,
        "atom_pair_relations": relations,
    }


def payload_for_plan(post, plan: dict) -> dict:
    blocks = []
    for block in plan["blocks"]:
        if not block["generated_atom_specs"]:
            continue
        generated = []
        for spec in block["generated_atom_specs"]:
            generated.append(
                {
                    "atom_id": spec["atom_id"],
                    "text": (
                        f"The user stored a separate archived note for {spec['atom_id']} "
                        "during an unrelated prior activity."
                    ),
                    "memory_type": "profile_fact",
                    "subtype": "archived_context",
                    "label_reason": "The archived note cannot alter the current answer.",
                    "coherence_reason": "It belongs to the same remembered prior activity.",
                    "non_applicability_reason": "The current decision does not depend on this note.",
                    "independence_reason": "The note states a distinct fact without entailing another atom.",
                }
            )
        blocks.append(
            {
                "parent_memory_id": block["parent_memory_id"],
                "generated_atoms": generated,
                "joint_zero_footprint_reason": (
                    "Removing all added notes leaves the ideal answer exactly unchanged."
                ),
            }
        )
    return {
        "schema_version": post.PAYLOAD_SCHEMA,
        "record_id": "record-1",
        "blocks": blocks,
        "self_check": {key: True for key in post.SELF_CHECK_KEYS},
    }


class MemCalibV23CompositeBlocksTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.common = load_script(
            PIPELINE_DIR / "memcalib_v23_common.py", "memcalib_v23_common_test"
        )
        cls.prepare = load_script(
            PIPELINE_DIR / "79_prepare_memcalib_v23_expansion.py",
            "prepare_memcalib_v23_expansion_test",
        )
        cls.post = load_script(
            PIPELINE_DIR / "80_post_memcalib_v23_expansion.py",
            "post_memcalib_v23_expansion_test",
        )
        cls.prepare_surface = load_script(
            PIPELINE_DIR / "81_prepare_memcalib_v23_surface_rewrite.py",
            "prepare_memcalib_v23_surface_rewrite_test",
        )
        cls.post_surface = load_script(
            PIPELINE_DIR / "82_post_memcalib_v23_surface_rewrite.py",
            "post_memcalib_v23_surface_rewrite_test",
        )
        cls.prepare_qc = load_script(
            PIPELINE_DIR / "83_prepare_memcalib_v23_independent_qc.py",
            "prepare_memcalib_v23_independent_qc_test",
        )
        cls.post_qc = load_script(
            PIPELINE_DIR / "84_post_memcalib_v23_independent_qc.py",
            "post_memcalib_v23_independent_qc_test",
        )
        cls.release = load_script(
            PIPELINE_DIR / "85_build_memcalib_v23_release.py",
            "build_memcalib_v23_release_test",
        )

    def test_scaled_level_quotas_have_three_levels(self) -> None:
        self.assertEqual(
            {"level_1": 38, "level_2": 75, "level_3": 37},
            self.common.scaled_level_quotas(150),
        )
        self.assertEqual(
            {"level_1": 19, "level_2": 37, "level_3": 19},
            self.common.scaled_level_quotas(75),
        )

    def test_each_level_satisfies_its_block_definition(self) -> None:
        record = source_record()
        for level in self.common.DIFFICULTY_LEVELS:
            plan = self.common.build_expansion_plan(record, level, seed=20260721)
            self.common.validate_expansion_plan(record, plan)
            targets = [block["target_atom_count"] for block in plan["blocks"]]
            self.assertLessEqual(max(targets), 20)
            self.assertEqual(1, targets[-1])
            self.assertGreater(plan["added_atom_count"], 0)
            if level == "level_1":
                self.assertLessEqual(max(targets[:-1]), 4)
                self.assertLessEqual(sum(value > 2 for value in targets[:-1]), 1)
            elif level == "level_2":
                self.assertGreaterEqual(max(targets[:-1]), 3)
                self.assertLessEqual(max(targets[:-1]), 7)
            else:
                self.assertTrue(
                    max(targets[:-1]) >= 8
                    or sum(value >= 5 for value in targets[:-1]) >= 2
                )

    def test_critical_tokens_exclude_sentence_initial_words(self) -> None:
        self.assertEqual(
            {"3-4", "mri", "cache_key", "v2"},
            self.common.critical_tokens(
                "The User discussed Natural Silica for 3-4 MRI scans using `cache_key` in v2."
            ),
        )

    def test_numeric_literals_accept_equivalent_number_words(self) -> None:
        self.assertTrue(
            self.post_surface.literal_token_present(
                "7", "The event occurred seven months ago."
            )
        )
        self.assertTrue(
            self.post_surface.literal_token_present(
                "3-4", "The course usually takes three to four weeks."
            )
        )
        self.assertFalse(
            self.post_surface.literal_token_present(
                "7", "The event occurred six months ago."
            )
        )

    def test_surface_metadata_detector_allows_domain_terms(self) -> None:
        legitimate = (
            "The transaction uses atomic commits, the course has an assessment rubric, "
            "and the user reads Atomic Habits."
        )
        self.assertIsNone(self.post_surface.ATOM_META_RE.search(legitimate))
        for leaked in ("atom boundary", "atomic label", "u_star", "memory_action"):
            self.assertIsNotNone(self.post_surface.ATOM_META_RE.search(leaked))

    def test_surface_fingerprint_preserves_raw_atom_text(self) -> None:
        source = source_record()
        plan = self.common.build_expansion_plan(source, "level_2", seed=20260721)
        expansion_params = {
            "record_id": source["id"],
            "record_fingerprint": self.common.canonical_sha256(source),
            "plan": plan,
        }
        expanded = self.post.build_record(
            source, payload_for_plan(self.post, plan), expansion_params
        )
        expanded["memories"][0]["text"] = "The  user preserves  raw spacing."
        request = self.prepare_surface.build_request(expanded, "{record_id}\n{blocks_json}")
        params = request["user_defined_params"]
        atoms = self.common.atom_index(expanded)
        payload = {
            "schema_version": self.post_surface.PAYLOAD_SCHEMA,
            "record_id": expanded["id"],
            "blocks": [
                {
                    "parent_memory_id": expected["parent_memory_id"],
                    "memory_text": " ".join(
                        atoms[atom_id]["text"] for atom_id in expected["atom_ids"]
                    ),
                }
                for expected in params["expected_blocks"]
            ],
            "self_check": {
                key: True for key in self.post_surface.SELF_CHECK_KEYS
            },
        }
        errors = self.post_surface.validate_payload(payload, expanded, params)
        self.assertFalse(any("atom_text_fingerprint" in error for error in errors))

    def test_independent_qc_request_allows_no_new_atoms(self) -> None:
        record = source_record()
        record["composite_block_revision"] = {"difficulty_level": "level_1"}
        request = self.prepare_qc.build_request(record, "{record_id}\n{blocks_json}")
        self.assertEqual([], request["user_defined_params"]["added_atom_ids"])
        self.assertEqual(
            len(record["memory_blocks"]),
            len(request["user_defined_params"]["expected_blocks"]),
        )

    def test_difficulty_assignment_is_domain_stratified_and_deterministic(self) -> None:
        records = [source_record(f"record-{index}") for index in range(20)]
        first, quotas = self.common.assign_difficulty_levels(records, seed=20260721)
        second, _ = self.common.assign_difficulty_levels(records, seed=20260721)
        self.assertEqual(first, second)
        self.assertEqual(
            quotas["general"],
            {"level_1": 5, "level_2": 10, "level_3": 5},
        )

    def test_level_one_eligibility_rejects_two_existing_dense_blocks(self) -> None:
        record = source_record()
        for parent_id in ("p1", "p2"):
            block = next(
                item
                for item in record["memory_blocks"]
                if item["parent_memory_id"] == parent_id
            )
            for suffix in ("a2", "a3"):
                atom_id = f"{parent_id}_{suffix}"
                record["memories"].append(
                    atom(atom_id, parent_id, "A", "from_question")
                )
                block["atom_ids"].append(atom_id)
        self.assertFalse(self.common.level_one_eligible(record))

    def test_valid_payload_builds_numbered_intermediate_with_locked_atoms(self) -> None:
        source = source_record()
        plan = self.common.build_expansion_plan(source, "level_3", seed=20260721)
        params = {
            "record_id": source["id"],
            "record_fingerprint": self.common.canonical_sha256(source),
            "plan": plan,
        }
        payload = payload_for_plan(self.post, plan)
        self.assertEqual([], self.post.validate_payload(payload, source, params))
        built = self.post.build_record(source, payload, params)
        self.assertEqual([], self.post.validate_record(built, source, plan))
        self.assertEqual(plan["target_atom_count"], len(built["memories"]))
        self.assertEqual(
            plan["difficulty_level"],
            built["composite_block_revision"]["difficulty_level"],
        )
        multi = [
            block for block in built["memory_blocks"] if len(block["atom_ids"]) > 1
        ]
        self.assertTrue(all(block["memory_text"].startswith("1. ") for block in multi))
        locked = {atom["atom_id"]: atom for atom in source["memories"]}
        rebuilt = {atom["atom_id"]: atom for atom in built["memories"]}
        for atom_id, original in locked.items():
            for key, value in original.items():
                if key not in {"atom_index", "atom_count"}:
                    self.assertEqual(value, rebuilt[atom_id][key])

    def test_payload_rejects_missing_generated_atom(self) -> None:
        source = source_record()
        plan = self.common.build_expansion_plan(source, "level_2", seed=20260721)
        params = {
            "record_id": source["id"],
            "record_fingerprint": self.common.canonical_sha256(source),
            "plan": plan,
        }
        payload = payload_for_plan(self.post, plan)
        payload["blocks"][0]["generated_atoms"].pop()
        errors = self.post.validate_payload(payload, source, params)
        self.assertTrue(any("generated_atom_ids_mismatch" in error for error in errors))

    def test_surface_rewrite_hides_numbered_boundaries_without_changing_atoms(self) -> None:
        source = source_record()
        plan = self.common.build_expansion_plan(source, "level_2", seed=20260721)
        expansion_params = {
            "record_id": source["id"],
            "record_fingerprint": self.common.canonical_sha256(source),
            "plan": plan,
        }
        expanded = self.post.build_record(
            source, payload_for_plan(self.post, plan), expansion_params
        )
        request = self.prepare_surface.build_request(expanded, "{record_id}\n{blocks_json}")
        params = request["user_defined_params"]
        atoms = self.common.atom_index(expanded)
        blocks = []
        for expected in params["expected_blocks"]:
            blocks.append(
                {
                    "parent_memory_id": expected["parent_memory_id"],
                    "memory_text": " ".join(
                        atoms[atom_id]["text"] for atom_id in expected["atom_ids"]
                    ),
                }
            )
        payload = {
            "schema_version": self.post_surface.PAYLOAD_SCHEMA,
            "record_id": expanded["id"],
            "blocks": blocks,
            "self_check": {
                key: True for key in self.post_surface.SELF_CHECK_KEYS
            },
        }
        self.assertEqual(
            [], self.post_surface.validate_payload(payload, expanded, params)
        )
        rewritten, audits = self.post_surface.build_record(expanded, payload, params)
        self.assertEqual([], self.post_surface.validate_record(rewritten, expanded))
        self.assertEqual(expanded["memories"], rewritten["memories"])
        self.assertEqual(
            expanded["atom_pair_relations"], rewritten["atom_pair_relations"]
        )
        self.assertEqual(len(blocks), len(audits))
        self.assertTrue(
            all(
                not block["memory_text"].startswith("1. ")
                for block in rewritten["memory_blocks"]
                if len(block["atom_ids"]) > 1
            )
        )

    def test_surface_rewrite_rejects_numbered_clauses(self) -> None:
        source = source_record()
        plan = self.common.build_expansion_plan(source, "level_1", seed=20260721)
        expansion_params = {
            "record_id": source["id"],
            "record_fingerprint": self.common.canonical_sha256(source),
            "plan": plan,
        }
        expanded = self.post.build_record(
            source, payload_for_plan(self.post, plan), expansion_params
        )
        request = self.prepare_surface.build_request(expanded, "{record_id}\n{blocks_json}")
        params = request["user_defined_params"]
        payload = {
            "schema_version": self.post_surface.PAYLOAD_SCHEMA,
            "record_id": expanded["id"],
            "blocks": [
                {
                    "parent_memory_id": expected["parent_memory_id"],
                    "memory_text": "1. The first proposition remains. 2. The second proposition remains.",
                }
                for expected in params["expected_blocks"]
            ],
            "self_check": {
                key: True for key in self.post_surface.SELF_CHECK_KEYS
            },
        }
        errors = self.post_surface.validate_payload(payload, expanded, params)
        self.assertTrue(any("visible_atom_markers" in error for error in errors))

    def build_rewritten_record(self, level: str = "level_2"):
        source = source_record()
        plan = self.common.build_expansion_plan(source, level, seed=20260721)
        expansion_params = {
            "record_id": source["id"],
            "record_fingerprint": self.common.canonical_sha256(source),
            "plan": plan,
        }
        expanded = self.post.build_record(
            source, payload_for_plan(self.post, plan), expansion_params
        )
        request = self.prepare_surface.build_request(expanded, "{record_id}\n{blocks_json}")
        params = request["user_defined_params"]
        atoms = self.common.atom_index(expanded)
        payload = {
            "schema_version": self.post_surface.PAYLOAD_SCHEMA,
            "record_id": expanded["id"],
            "blocks": [
                {
                    "parent_memory_id": expected["parent_memory_id"],
                    "memory_text": " ".join(
                        atoms[atom_id]["text"] for atom_id in expected["atom_ids"]
                    ),
                }
                for expected in params["expected_blocks"]
            ],
            "self_check": {
                key: True for key in self.post_surface.SELF_CHECK_KEYS
            },
        }
        rewritten, _ = self.post_surface.build_record(expanded, payload, params)
        return rewritten

    def valid_qc_payload(self, record: dict, params: dict) -> dict:
        return {
            "schema_version": self.post_qc.QC_SCHEMA,
            "record_id": record["id"],
            "added_atom_checks": [
                {
                    "atom_id": atom_id,
                    "atomicity": "pass",
                    "same_user_plausibility": "pass",
                    "query_relation": "absent",
                    "answer_footprint": "none",
                    "explicit_correction_required": False,
                    "distinct_from_block_atoms": "pass",
                    "block_coherence": "pass",
                    "reason": "The proposition is distinct, plausible, and has no answer footprint.",
                }
                for atom_id in params["added_atom_ids"]
            ],
            "block_checks": [
                {
                    "parent_memory_id": block["parent_memory_id"],
                    "atom_coverage": [
                        {
                            "atom_id": atom_id,
                            "entailed_by_memory_text": "pass",
                            "fidelity_reason": "The paragraph preserves this proposition exactly.",
                        }
                        for atom_id in block["atom_ids"]
                    ],
                    "extra_propositions": "none",
                    "critical_value_fidelity": "pass",
                    "cross_block_contamination": False,
                    "natural_paragraph": "pass",
                    "visible_atom_boundaries": False,
                    "reason": "The paragraph is complete, faithful, and naturally composed.",
                }
                for block in params["expected_blocks"]
            ],
            "declared_decision": "strict_pass",
            "decision_reasons": ["All added atoms and rewritten blocks pass."],
            "self_check": {key: True for key in self.post_qc.SELF_CHECK_KEYS},
        }

    def test_independent_qc_accepts_complete_strict_payload(self) -> None:
        record = self.build_rewritten_record()
        request = self.prepare_qc.build_request(record, "{record_id}\n{blocks_json}")
        params = request["user_defined_params"]
        payload = self.valid_qc_payload(record, params)
        errors, decision, reasons = self.post_qc.validate_qc(payload, record, params)
        self.assertEqual([], errors)
        self.assertEqual("strict_pass", decision)
        self.assertEqual([], reasons)

    def test_independent_qc_rejects_query_overlap(self) -> None:
        record = self.build_rewritten_record()
        request = self.prepare_qc.build_request(record, "{record_id}\n{blocks_json}")
        params = request["user_defined_params"]
        payload = self.valid_qc_payload(record, params)
        payload["added_atom_checks"][0]["query_relation"] = "overlap"
        errors, decision, reasons = self.post_qc.validate_qc(payload, record, params)
        self.assertEqual([], errors)
        self.assertEqual("reject", decision)
        self.assertTrue(any("query_relation_overlap" in reason for reason in reasons))

    def test_release_validation_accepts_one_level_two_record(self) -> None:
        record = self.build_rewritten_record("level_2")
        record["v23_independent_qc"] = {
            "schema_version": self.post_qc.QC_SCHEMA,
            "decision": "strict_pass",
        }
        validation = self.release.validate_release(
            [record], {"general": 1}, allow_review=False
        )
        self.assertEqual([], validation["violations"])
        self.assertEqual(1, validation["atoms_per_block_range"][0])
        self.assertTrue(3 <= validation["atoms_per_block_range"][1] <= 7)


if __name__ == "__main__":
    unittest.main()
