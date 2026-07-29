from __future__ import annotations

import importlib.util
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


def atom(atom_id: str, label: str, action: str, text: str) -> dict:
    return {
        "memory_id": atom_id,
        "parent_memory_id": atom_id.split("_")[0],
        "atom_id": atom_id,
        "atom_index": 1,
        "atom_count": 1,
        "text": text,
        "evidence": text,
        "atomic_predicate": text,
        "derivation": "explicit",
        "source": "from_context" if label != "A" else "synthetic_hard_a",
        "memory_type": "task_constraint",
        "u_star": label,
        "memory_action": action,
        "query_relation": "absent",
        "subtype": "test",
        "hard_a_family": "scope_overreach" if label == "A" else None,
        "label_reason": "Old code-oriented reason.",
        "construction_target": {
            "task_goal": "Old goal.",
            "memory_role": "Old role.",
            "usage_boundary": "Old boundary.",
            "failure_direction": "Old failure.",
        },
        "counterfactual_contract": {
            "without_memory_behavior": "Old behavior.",
            "with_memory_behavior": "Old behavior.",
            "observable_delta": "none" if label == "A" else "Old code delta.",
            "minimal_evidence": [] if label == "A" else ["Old code evidence."],
        },
        "usage_rubric": {
            "expected_answer_behavior": "Old code behavior.",
            "memory_usage_weight": {"A": "none", "B": "supporting", "C": "controlling"}[
                label
            ],
            "validity_scope": "Old code.",
            "correct_use": "Old code.",
            "under_use": "Old code.",
            "over_use": "Old code.",
            "forbidden_memory_role": "Old code.",
            "failure_direction": "Old code.",
            "observable_checks": ["Inspect the code.", "Run the tests."],
        },
    }


def source_record() -> dict:
    atoms = [
        atom(
            "p1_a1",
            "C",
            "apply",
            "Missing configuration must produce the literal message '.env not found'.",
        ),
        atom(
            "p2_a1",
            "B",
            "correct",
            "An old memory incorrectly recommends silently creating the missing file.",
        ),
        atom(
            "hard_a1",
            "A",
            "ignore",
            "The user previously preferred tabs in an unrelated editor.",
        ),
    ]
    return {
        "id": "coding-record-1",
        "source_id": "source-coding-record-1",
        "schema_version": "crk-2-canonical-memory-v2.3",
        "domain": "coding",
        "question": "Write a Python function that loads the configuration.",
        "source_answer": "```python\nload_config()\n```",
        "memory_blocks": [
            {
                "parent_memory_id": item["parent_memory_id"],
                "memory_text": item["text"],
                "source": item["source"],
                "atom_ids": [item["atom_id"]],
            }
            for item in atoms
        ],
        "memories": atoms,
    }


def valid_payload(common) -> dict:
    return {
        "schema_version": common.PAYLOAD_SCHEMA,
        "record_id": "coding-record-1",
        "task_family": "implementation_plan",
        "task_stem": (
            "A service must load its configuration before startup. Explain the "
            "implementation behavior and failure path."
        ),
        "reference_answer": (
            "The plan checks for the configuration before initialization. If it is "
            "missing, the answer must specify the literal message '.env not found'. "
            "The plan must reject the old suggestion to create the missing file "
            "silently and should stop startup instead."
        ),
        "applicable_atom_footprints": [
            {
                "atom_id": "p1_a1",
                "u_star": "C",
                "memory_action": "apply",
                "required_answer_elements": [
                    "the literal message '.env not found'"
                ],
                "overuse_signals": ["create an unrelated default configuration"],
                "label_justification": (
                    "The exact failure message controls an externally visible failure path."
                ),
            },
            {
                "atom_id": "p2_a1",
                "u_star": "B",
                "memory_action": "correct",
                "required_answer_elements": [
                    "reject the old suggestion to create the missing file silently"
                ],
                "overuse_signals": ["delete existing configuration files"],
                "label_justification": (
                    "The correction changes one bounded part of the failure explanation."
                ),
            },
        ],
        "query_isolation_audit": [
            {
                "atom_id": "p1_a1",
                "query_supplies_atom_value": False,
                "reason": "The task asks for the failure behavior without stating the literal.",
            },
            {
                "atom_id": "p2_a1",
                "query_supplies_atom_value": False,
                "reason": "The task asks for a failure path without supplying the correction.",
            },
        ],
        "self_check": {key: True for key in common.SELF_CHECK_KEYS},
    }


class MemCalibV24CodingObservabilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.common = load_script(
            PIPELINE_DIR / "memcalib_v24_coding_common.py",
            "memcalib_v24_coding_common_test",
        )
        cls.prepare = load_script(
            PIPELINE_DIR / "102_prepare_memcalib_v24_coding_rewrite.py",
            "prepare_memcalib_v24_coding_rewrite_test",
        )
        cls.post = load_script(
            PIPELINE_DIR / "103_post_memcalib_v24_coding_rewrite.py",
            "post_memcalib_v24_coding_rewrite_test",
        )
        cls.prepare_qc = load_script(
            PIPELINE_DIR / "104_prepare_memcalib_v24_coding_independent_qc.py",
            "prepare_memcalib_v24_coding_independent_qc_test",
        )
        cls.post_qc = load_script(
            PIPELINE_DIR / "105_post_memcalib_v24_coding_independent_qc.py",
            "post_memcalib_v24_coding_independent_qc_test",
        )

    def test_request_covers_only_locked_applicable_atoms(self) -> None:
        record = source_record()
        record["memories"] = [
            record["memories"][2],
            record["memories"][1],
            record["memories"][0],
        ]
        request = self.prepare.build_request(
            record,
            "{record_id}\n{task_family}\n{blocks_json}",
            task_family="implementation_plan",
        )
        params = request["user_defined_params"]
        self.assertEqual(
            ["p1_a1", "p2_a1"],
            [item["atom_id"] for item in params["expected_applicable_atoms"]],
        )
        self.assertEqual(
            self.common.locked_supervision_fingerprint(record),
            params["locked_supervision_fingerprint"],
        )

    def test_payload_requires_verbatim_answer_evidence(self) -> None:
        record = source_record()
        request = self.prepare.build_request(
            record, "{record_id}", task_family="implementation_plan"
        )
        payload = valid_payload(self.common)
        self.assertEqual(
            [],
            self.common.validate_revision_payload(
                payload, record, request["user_defined_params"]
            ),
        )
        payload["applicable_atom_footprints"][0]["required_answer_elements"] = [
            "a phrase absent from the reference"
        ]
        errors = self.common.validate_revision_payload(
            payload, record, request["user_defined_params"]
        )
        self.assertIn(
            "footprint_0_required_element_0_not_verbatim_in_reference", errors
        )
        repaired, additions = self.post.repair_missing_verbatim_evidence(payload)
        self.assertEqual(["a phrase absent from the reference"], additions)
        self.assertNotIn(
            "footprint_0_required_element_0_not_verbatim_in_reference",
            self.common.validate_revision_payload(
                repaired, record, request["user_defined_params"]
            ),
        )

    def test_build_replaces_code_rubrics_with_answer_text_rubrics(self) -> None:
        record = source_record()
        request = self.prepare.build_request(
            record, "{record_id}", task_family="implementation_plan"
        )
        params = request["user_defined_params"]
        revised, audit = self.post.build_record(
            record,
            valid_payload(self.common),
            params,
            request["request_id"],
        )
        self.assertNotIn("```", revised["question"])
        self.assertNotIn("```", revised["source_answer"])
        self.assertIn("Do not provide executable code", revised["question"])
        self.assertEqual(
            [atom["atom_id"] for atom in record["memories"]],
            [atom["atom_id"] for atom in revised["memories"]],
        )
        self.assertEqual(
            [],
            self.post.validate_built_record(revised, record, params),
        )
        hard_a = revised["memories"][2]
        self.assertEqual(
            "none", hard_a["counterfactual_contract"]["observable_delta"]
        )
        self.assertEqual([], hard_a["counterfactual_contract"]["minimal_evidence"])
        for item in revised["memories"]:
            self.assertTrue(
                all(
                    "answer" in check.casefold()
                    for check in item["usage_rubric"]["observable_checks"]
                )
            )
        self.assertEqual(
            self.common.canonical_sha256(revised),
            audit["output_record_fingerprint"],
        )

    def test_local_residual_repair_removes_flagged_atom_value(self) -> None:
        local = load_script(
            PIPELINE_DIR / "107_repair_memcalib_v24_coding_residual.py",
            "memcalib_v24_local_repair_test",
        )
        record = source_record()
        record["question"] = (
            "Write a function for the user's Python 3.11 environment that returns "
            "the requested result."
        )
        record["memories"][0]["text"] = (
            "The user works in a Python 3.11 environment."
        )
        stem, removals = local.local_task_stem(
            record,
            "implementation_plan",
            {"p1_a1"},
        )
        self.assertNotIn("Python 3.11", stem)
        self.assertIn("natural-language implementation plan", stem)
        self.assertTrue(removals)

    def test_family_assignment_is_stable_and_supported(self) -> None:
        first = self.common.stable_task_family("record-123")
        second = self.common.stable_task_family("record-123")
        self.assertEqual(first, second)
        self.assertIn(first, self.common.TASK_FAMILIES)

    def test_manual_adjudication_override_set_is_exactly_fifteen(self) -> None:
        manual = load_script(
            PIPELINE_DIR
            / "108_finalize_memcalib_v24_coding_manual_adjudication.py",
            "memcalib_v24_manual_adjudication_test",
        )
        self.assertEqual(15, len(manual.OVERRIDES))
        for override in manual.OVERRIDES.values():
            self.assertIn(override["family"], self.common.TASK_FAMILIES)
            self.assertGreaterEqual(len(override["task_stem"]), 40)
            self.assertGreaterEqual(len(override["reference"]), 80)

    def test_independent_qc_covers_every_atom_and_rejects_query_leakage(self) -> None:
        source = source_record()
        rewrite_request = self.prepare.build_request(
            source, "{record_id}", task_family="implementation_plan"
        )
        revised, _ = self.post.build_record(
            source,
            valid_payload(self.common),
            rewrite_request["user_defined_params"],
            rewrite_request["request_id"],
        )
        qc_request = self.prepare_qc.build_request(revised, "{record_json}")
        params = qc_request["user_defined_params"]
        qc = {
            "schema_version": self.post_qc.QC_SCHEMA,
            "record_id": revised["id"],
            "record_checks": [
                {
                    "check": name,
                    "verdict": "pass",
                    "reason": "The requested property is directly satisfied.",
                }
                for name in self.post_qc.RECORD_CHECKS
            ],
            "atom_checks": [
                {
                    "atom_id": atom["atom_id"],
                    "label_action_validity": "pass",
                    "answer_text_observability": "pass",
                    "rubric_objectivity": "pass",
                    "query_value_status": "not_supplied",
                    "reason": "The atom has the correct role and answer-text evidence.",
                }
                for atom in revised["memories"]
            ],
            "declared_decision": "strict_pass",
            "decision_reasons": ["All checks pass."],
            "self_check": {
                key: True for key in self.post_qc.SELF_CHECK_KEYS
            },
        }
        errors, decision, reasons = self.post_qc.validate_qc(qc, revised, params)
        self.assertEqual([], errors)
        self.assertEqual("strict_pass", decision)
        self.assertEqual([], reasons)
        qc["atom_checks"][0]["query_value_status"] = "partially_supplied"
        errors, decision, reasons = self.post_qc.validate_qc(qc, revised, params)
        self.assertEqual([], errors)
        self.assertEqual("reject", decision)
        self.assertIn(
            "p1_a1:query_value_status:partially_supplied", reasons
        )


if __name__ == "__main__":
    unittest.main()
