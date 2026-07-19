from __future__ import annotations

import copy
import importlib.util
import json
import math
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


def target(role: str = "none") -> dict:
    return {
        "task_goal": "Answer the current software comparison accurately.",
        "memory_role": role,
        "usage_boundary": "Use only information that legitimately bears on the comparison.",
        "failure_direction": "The response is biased by an irrelevant remembered preference.",
    }


def contract(delta: str = "none") -> dict:
    return {
        "without_memory_behavior": "Give the same objective comparison.",
        "with_memory_behavior": "Give the same objective comparison.",
        "observable_delta": delta,
        "minimal_evidence": [],
    }


def rubric(weight: str = "none") -> dict:
    return {
        "expected_answer_behavior": "Ignore this memory and answer the current question directly.",
        "memory_usage_weight": weight,
        "validity_scope": "The remembered detail has no role in the current comparison.",
        "correct_use": "Leave no atom-specific footprint in the answer.",
        "under_use": "A has no under-use.",
        "over_use": "Use the remembered detail to bias the current comparison.",
        "forbidden_memory_role": "Do not use the detail as evidence, framing, or a decision criterion.",
        "failure_direction": "The answer becomes unnecessarily personalized or factually biased.",
        "observable_checks": [
            "The response does not mention the remembered detail.",
            "The response reaches the same conclusion without the memory.",
        ],
    }


def real_atom(atom_id: str, label: str, text: str) -> dict:
    action = "apply"
    return {
        "memory_id": atom_id,
        "parent_memory_id": atom_id.rsplit("_a", 1)[0],
        "atom_id": atom_id,
        "atom_index": 1,
        "atom_count": 4,
        "text": text,
        "evidence": text,
        "atomic_predicate": text,
        "derivation": "explicit",
        "source": "from_context",
        "memory_type": "case_fact",
        "u_star": label,
        "memory_action": action,
        "query_relation": "absent",
        "subtype": "test",
        "hard_a_family": None,
        "label_reason": "This grounded detail has a specific role in the current answer.",
        "construction_target": target("support"),
        "counterfactual_contract": {
            **contract("The answer incorporates the grounded constraint."),
            "with_memory_behavior": "Use the grounded constraint in the comparison.",
        },
        "usage_rubric": {
            **rubric("supporting"),
            "expected_answer_behavior": "Use the grounded detail within its scope.",
        },
    }


def canonical_hard_a() -> dict:
    atom = {
        "memory_id": "v21_hard_a_a1",
        "parent_memory_id": "v21_hard_a",
        "atom_id": "v21_hard_a_a1",
        "atom_index": 4,
        "atom_count": 4,
        "text": "The user prefers blue wallpapers on personal desktop computers.",
        "evidence": "",
        "atomic_predicate": "The user prefers blue wallpapers on personal desktop computers.",
        "derivation": "synthetic",
        "source": "synthetic_hard_a",
        "memory_type": "preference",
        "u_star": "A",
        "memory_action": "ignore",
        "query_relation": "absent",
        "subtype": "visual_preference",
        "hard_a_family": "untriggered_preference",
        "label_reason": "Wallpaper color has no role in the requested software comparison.",
        "surface_relevance": "The question concerns software used on a desktop computer.",
        "non_applicability_reason": "No visual customization or wallpaper decision is requested.",
        "family_audit": {
            "task_boundary_anchor": "The question asks for an objective software comparison.",
            "family_specific_mechanism": "A nearby preference looks useful but has no decision authority.",
            "tempting_incorrect_use": "The model could use the preference to rank the software options.",
            "no_valid_bounded_use": "The objective comparison is complete without mentioning the preference.",
            "explicit_correction_test": "not_required",
        },
        "construction_target": target(),
        "counterfactual_contract": contract(),
        "usage_rubric": rubric(),
    }
    return atom


def source_record() -> dict:
    atoms = [
        real_atom(
            "p1_a1",
            "B",
            "The user currently runs Linux Mint on their primary workstation.",
        ),
        real_atom(
            "p2_a1",
            "C",
            "The target laptop has a Pentium processor and a mechanical hard drive.",
        ),
        real_atom(
            "p3_a1",
            "B",
            "The user wants a distribution with a maintained package repository.",
        ),
        canonical_hard_a(),
    ]
    relations = []
    for left_index, left in enumerate(atoms):
        for right in atoms[left_index + 1 :]:
            relations.append(
                {
                    "left_atom_id": left["atom_id"],
                    "right_atom_id": right["atom_id"],
                    "relation": "independent",
                    "reason": "The two propositions are independently observable.",
                }
            )
    return {
        "id": "record-1",
        "source_id": "source-1",
        "schema_version": "crk-2-canonical-memory-v2.1",
        "domain": "general",
        "source_dataset": "test/source",
        "source_topic": "learning_explanation",
        "question": "Compare lightweight Linux distributions for this old laptop.",
        "memory_blocks": [],
        "memories": atoms,
        "atom_pair_relations": relations,
    }


def generated_atom(atom_id: str, suffix: str) -> dict:
    return {
        "atom_id": atom_id,
        "text": (
            f"The user previously organized desktop wallpapers by season in an unrelated personal archive {suffix}."
        ),
        "memory_type": "profile_fact",
        "subtype": "unrelated_archive_habit",
        "label_reason": "The archive habit cannot affect the objective software comparison.",
        "surface_relevance": "Both the memory and question concern past desktop computer use.",
        "non_applicability_reason": "The current task does not request wallpaper or archive organization.",
        "independence_reason": "This archive habit is independent of hardware, package, and operating-system constraints.",
        "construction_target": target(),
        "counterfactual_contract": contract(),
        "usage_rubric": rubric(),
    }


def augmentation_for_plan(post, plan: dict) -> dict:
    blocks = []
    ordinal = 0
    for block_plan in plan["synthetic_blocks"]:
        atoms = []
        specs = {
            spec["atom_id"]: spec
            for spec in block_plan.get("generated_atom_specs") or []
        }
        for atom_id in block_plan["generated_atom_ids"]:
            ordinal += 1
            atom = generated_atom(atom_id, str(ordinal))
            required = specs.get(atom_id, {}).get("required_phrases") or []
            if required:
                atom["text"] = (
                    f"The user organized the {required[0]} in the {required[1]} "
                    f"{required[2]} for an unrelated household collection {ordinal}."
                )
            atoms.append(atom)
        blocks.append(
            {
                "parent_memory_id": block_plan["parent_memory_id"],
                "canonical_hard_a_family": block_plan[
                    "canonical_hard_a_family"
                ],
                "retrieval_noise_family": block_plan["retrieval_noise_family"],
                "generated_atoms": atoms,
                "joint_no_footprint_reason": (
                    "The remembered archive details do not change any objective part of the requested comparison."
                ),
            }
        )
    return {
        "schema_version": post.AUGMENTATION_SCHEMA,
        "record_id": "record-1",
        "synthetic_blocks": blocks,
        "self_check": {key: True for key in post.SELF_CHECK_KEYS},
    }


class MemCalibV22LongtailTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prepare = load_script(
            PIPELINE_DIR / "67_prepare_memcalib_v22_longtail.py",
            "prepare_memcalib_v22_longtail",
        )
        cls.post = load_script(
            PIPELINE_DIR / "68_post_memcalib_v22_longtail.py",
            "post_memcalib_v22_longtail",
        )
        cls.retry = load_script(
            PIPELINE_DIR / "71_prepare_memcalib_v22_longtail_retry.py",
            "prepare_memcalib_v22_longtail_retry",
        )
        cls.merge = load_script(
            PIPELINE_DIR / "72_merge_memcalib_v22_longtail_retry_results.py",
            "merge_memcalib_v22_longtail_retry_results",
        )
        cls.local_repair = load_script(
            PIPELINE_DIR / "73_repair_memcalib_v22_longtail_required_phrases.py",
            "repair_memcalib_v22_longtail_required_phrases",
        )
        cls.release = load_script(
            PIPELINE_DIR / "74_build_memcalib_v22_release.py",
            "build_memcalib_v22_release",
        )
        cls.tail_repair = load_script(
            PIPELINE_DIR / "77_direct_repair_memcalib_v22_longtail_tail.py",
            "direct_repair_memcalib_v22_longtail_tail",
        )

    def test_full_distribution_is_long_tailed_and_domain_divisible(self) -> None:
        distribution = self.prepare.TARGET_DISTRIBUTION
        self.assertEqual(15000, sum(distribution.values()))
        self.assertEqual(set(range(3, 21)), set(distribution))
        self.assertTrue(all(count % 4 == 0 for count in distribution.values()))
        total_blocks = sum(block_count * count for block_count, count in distribution.items())
        multi_blocks = sum(
            math.ceil(block_count / 2) * count
            for block_count, count in distribution.items()
        )
        self.assertEqual(74800, total_blocks)
        self.assertEqual(41700, multi_blocks)
        self.assertGreater(multi_blocks / total_blocks, 0.5)
        self.assertEqual(448, sum(distribution[key] for key in range(11, 21)))
        self.assertEqual(distribution, self.release.BLOCK_DISTRIBUTION)

    def test_plans_cover_three_to_twenty_without_duplicate_atom_slots(self) -> None:
        record = source_record()
        for block_count in range(3, 21):
            plan = self.prepare.build_plan(record, block_count, seed=20260719)
            self.assertEqual(block_count, len(plan["block_order"]))
            self.assertEqual(
                math.ceil(block_count / 2),
                plan["target_multi_atom_block_count"],
            )
            blocks = plan["grounded_blocks"] + plan["synthetic_blocks"]
            self.assertEqual(
                math.ceil(block_count / 2),
                sum(block["atom_count"] >= 2 for block in blocks),
            )
            generated_ids = [
                atom_id
                for block in plan["synthetic_blocks"]
                for atom_id in block["generated_atom_ids"]
            ]
            self.assertEqual(len(generated_ids), len(set(generated_ids)))
            canonical_blocks = [
                block
                for block in plan["synthetic_blocks"]
                if block["contains_canonical_hard_a"]
            ]
            self.assertEqual(1, len(canonical_blocks))
            self.assertEqual(1, canonical_blocks[0]["atom_count"])
            self.assertEqual([], canonical_blocks[0]["generated_atom_ids"])
            self.assertIsNone(canonical_blocks[0]["retrieval_noise_family"])
            self.assertTrue(
                all(
                    not block["contains_canonical_hard_a"]
                    and block["canonical_hard_a_family"] is None
                    for block in plan["synthetic_blocks"]
                    if block is not canonical_blocks[0]
                )
            )

    def test_assigned_auxiliary_scenes_are_globally_unique(self) -> None:
        first = source_record()
        second = copy.deepcopy(first)
        second["id"] = "record-2"
        second["question"] = "Explain how lunar eclipses occur."
        records = {first["id"]: first, second["id"]: second}
        plans = {
            first["id"]: self.prepare.build_plan(first, 20, seed=20260719),
            second["id"]: self.prepare.build_plan(second, 20, seed=20260719),
        }
        self.prepare.assign_scene_specs(records, plans, seed=20260719)
        scenes = [
            (
                block["scene_spec"]["object_phrase"],
                block["scene_spec"]["setting_phrase"],
                block["scene_spec"]["time_phrase"],
            )
            for plan in plans.values()
            for block in plan["synthetic_blocks"]
            if block["generated_atom_ids"]
        ]
        self.assertEqual(len(scenes), len(set(scenes)))

    def test_valid_augmentation_builds_fully_mapped_record(self) -> None:
        source = source_record()
        plan = self.prepare.build_plan(source, 9, seed=20260719)
        self.prepare.assign_scene_specs(
            {source["id"]: source}, {source["id"]: plan}, seed=20260719
        )
        params = {
            "schema_version": self.prepare.REQUEST_SCHEMA,
            "record_id": source["id"],
            "record_fingerprint": self.prepare.canonical_sha256(source),
            "plan": plan,
        }
        payload = augmentation_for_plan(self.post, plan)
        self.assertEqual([], self.post.validate_augmentation(payload, source, params))

        built = self.post.build_record(source, payload, params)
        self.assertEqual([], self.post.validate_record(built, source, plan))
        self.assertEqual(9, len(built["memory_blocks"]))
        self.assertEqual(5, sum(len(block["atom_ids"]) >= 2 for block in built["memory_blocks"]))
        mapped = [
            atom_id
            for block in built["memory_blocks"]
            for atom_id in block["atom_ids"]
        ]
        self.assertCountEqual(
            [atom["atom_id"] for atom in built["memories"]],
            mapped,
        )
        self.assertEqual(
            math.comb(len(built["memories"]), 2),
            len(built["atom_pair_relations"]),
        )

    def test_duplicate_generated_text_is_rejected(self) -> None:
        source = source_record()
        plan = self.prepare.build_plan(source, 6, seed=20260719)
        self.prepare.assign_scene_specs(
            {source["id"]: source}, {source["id"]: plan}, seed=20260719
        )
        params = {
            "schema_version": self.prepare.REQUEST_SCHEMA,
            "record_id": source["id"],
            "record_fingerprint": self.prepare.canonical_sha256(source),
            "plan": plan,
        }
        payload = augmentation_for_plan(self.post, plan)
        generated = [
            atom
            for block in payload["synthetic_blocks"]
            for atom in block["generated_atoms"]
        ]
        self.assertGreaterEqual(len(generated), 2)
        generated[1]["text"] = generated[0]["text"]
        errors = self.post.validate_augmentation(payload, source, params)
        self.assertIn("generated_atom_text_duplicate", errors)

    def test_locked_real_atom_change_is_rejected(self) -> None:
        source = source_record()
        plan = self.prepare.build_plan(source, 5, seed=20260719)
        self.prepare.assign_scene_specs(
            {source["id"]: source}, {source["id"]: plan}, seed=20260719
        )
        params = {
            "schema_version": self.prepare.REQUEST_SCHEMA,
            "record_id": source["id"],
            "record_fingerprint": self.prepare.canonical_sha256(source),
            "plan": plan,
        }
        payload = augmentation_for_plan(self.post, plan)
        built = self.post.build_record(source, payload, params)
        tampered = copy.deepcopy(built)
        next(
            atom
            for atom in tampered["memories"]
            if atom["source"] != "synthetic_hard_a"
        )["text"] = "Changed grounded fact."
        errors = self.post.validate_record(tampered, source, plan)
        self.assertTrue(any(error.startswith("locked_real_atom_changed:") for error in errors))

    def test_domain_guardrail_uses_semantic_terms_not_substrings(self) -> None:
        atom = generated_atom("a1", "physical")
        atom["text"] = (
            "The user stores theater programs beside large-format earth-tone photographs "
            "after an archival project involving teak oil treatments."
        )
        errors: list[str] = []
        self.post.validate_generated_atom(
            atom, "a1", "atom", errors, domain="coding"
        )
        self.assertFalse(
            any(
                "text_coding_domain_leakage" in error
                or "text_response_or_workflow_preference" in error
                for error in errors
            )
        )

        atom["text"] = (
            "The user lined a seashell collection drawer with tissue to prevent shell abrasion."
        )
        errors = []
        self.post.validate_generated_atom(
            atom, "a1", "atom", errors, domain="coding"
        )
        self.assertNotIn("atom.text_coding_domain_leakage", errors)

        atom["text"] = "The user prefers running the command shell in an interactive session."
        errors = []
        self.post.validate_generated_atom(
            atom, "a1", "atom", errors, domain="coding"
        )
        self.assertIn("atom.text_coding_domain_leakage", errors)

        atom["text"] = (
            "The user prefers Python code responses in bullet-point format."
        )
        errors = []
        self.post.validate_generated_atom(
            atom, "a1", "atom", errors, domain="coding"
        )
        self.assertIn("atom.text_coding_domain_leakage", errors)
        self.assertIn("atom.text_response_or_workflow_preference", errors)

    def test_targeted_retry_preserves_identity_and_adds_audit_errors(self) -> None:
        request = {
            "request_id": "v22_longtail_augmentation:r1",
            "prompt": [{"role": "user", "content": "Return the planned JSON."}],
            "user_defined_params": {"record_id": "r1"},
        }
        retried = self.retry.retry_request(
            {
                "request_id": request["request_id"],
                "request": request,
                "errors": ["required_phrase_missing"],
            }
        )
        self.assertEqual(request["request_id"], retried["request_id"])
        self.assertEqual(
            request["user_defined_params"], retried["user_defined_params"]
        )
        self.assertIn("required_phrase_missing", retried["prompt"][0]["content"])
        self.assertNotEqual(request["prompt"][0]["content"], retried["prompt"][0]["content"])

    def test_retry_result_index_rejects_duplicate_ids(self) -> None:
        with self.assertRaises(ValueError):
            self.merge.index(
                [{"request_id": "r1"}, {"request_id": "r1"}],
                "retry",
            )

    def test_local_phrase_repair_is_narrow_and_audited(self) -> None:
        source = source_record()
        plan = self.prepare.build_plan(source, 5, seed=20260719)
        self.prepare.assign_scene_specs(
            {source["id"]: source}, {source["id"]: plan}, seed=20260719
        )
        payload = augmentation_for_plan(self.post, plan)
        block_index = next(
            index
            for index, block in enumerate(plan["synthetic_blocks"])
            if block["generated_atom_ids"]
        )
        payload["synthetic_blocks"][block_index]["generated_atoms"][0]["text"] = (
            "The user attached a handwritten inventory tag to an unrelated keepsake."
        )
        request_id = "v22_longtail_augmentation:record-1"
        result = {
            "request_id": request_id,
            "response": "{}",
            "raw_response": {
                "choices": [{"message": {"content": "{}"}}],
            },
            "user_defined_params": {
                "record_id": source["id"],
                "plan": plan,
            },
        }
        row = {
            "request_id": request_id,
            "record_id": source["id"],
            "request": {
                "request_id": request_id,
                "user_defined_params": result["user_defined_params"],
            },
            "result": result,
            "parsed_payload": payload,
            "errors": [
                f"synthetic_blocks[{block_index}].generated_atoms[0].required_phrase_missing"
            ],
        }
        repaired, audits = self.local_repair.repair_rejected_row(row)
        repaired_payload = json.loads(repaired["response"])
        repaired_atom = repaired_payload["synthetic_blocks"][block_index][
            "generated_atoms"
        ][0]
        required = plan["synthetic_blocks"][block_index]["generated_atom_specs"][0][
            "required_phrases"
        ]
        self.assertTrue(all(phrase in repaired_atom["text"] for phrase in required))
        self.assertEqual(request_id, repaired["request_id"])
        self.assertEqual(
            repaired["response"],
            repaired["raw_response"]["choices"][0]["message"]["content"],
        )
        self.assertEqual(1, len(audits))
        self.assertEqual(repaired_atom["atom_id"], audits[0]["atom_id"])
        self.assertNotEqual(
            audits[0]["before_text_sha256"], audits[0]["after_text_sha256"]
        )

    def test_local_phrase_repair_rejects_other_error_types(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported local repair error"):
            self.local_repair.repair_rejected_row(
                {
                    "errors": ["synthetic_blocks[0].generated_atoms[0].text_duplicate"],
                }
            )

    def test_direct_tail_repair_preserves_structure_and_labels(self) -> None:
        record = {
            "id": "r1",
            "memory_blocks": [
                {
                    "parent_memory_id": "noise",
                    "source": "synthetic_retrieval_noise",
                    "atom_ids": ["a1", "a2"],
                    "memory_text": "old",
                }
            ],
            "memories": [
                {
                    "atom_id": "a1",
                    "source": "synthetic_retrieval_noise",
                    "u_star": "A",
                    "memory_action": "ignore",
                    "text": "old one",
                },
                {
                    "atom_id": "a2",
                    "source": "synthetic_retrieval_noise",
                    "u_star": "A",
                    "memory_action": "ignore",
                    "text": "old two",
                },
            ],
        }
        repaired, audits = self.tail_repair.repair_record(
            record,
            {
                "noise": {
                    "scene_spec": {
                        "object_phrase": "marker",
                        "setting_phrase": "pool",
                        "time_phrase": "July 2008",
                    },
                    "joint_reason": "Both facts are coherent and irrelevant.",
                    "atoms": {"a1": "new one", "a2": "new two"},
                }
            },
        )
        self.assertEqual(1, len(repaired["memory_blocks"]))
        self.assertEqual(2, len(repaired["memories"]))
        self.assertEqual(["A", "A"], [atom["u_star"] for atom in repaired["memories"]])
        self.assertEqual(
            ["ignore", "ignore"],
            [atom["memory_action"] for atom in repaired["memories"]],
        )
        self.assertEqual(2, len(audits))
        self.assertIn("1. new one 2. new two", repaired["memory_blocks"][0]["memory_text"])


if __name__ == "__main__":
    unittest.main()
