from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


PIPELINE = Path(__file__).resolve().parents[2] / "pipeline"
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))
SPEC = importlib.util.spec_from_file_location(
    "post_relabel_aware",
    PIPELINE / "117_post_memcalib_v241_relabel_aware_repair.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def source_record() -> dict:
    return {
        "id": "coding-test-1",
        "domain": "coding",
        "question": "How should this service handle a failed operation?",
        "source_answer": "Describe a reliable failure-handling design.",
        "memory_blocks": [
            {
                "parent_memory_id": "block-1",
                "memory_text": "Combined memory text.",
                "atom_ids": ["a-1", "b-1", "c-1"],
            }
        ],
        "memories": [
            {
                "atom_id": "a-1",
                "parent_memory_id": "block-1",
                "text": "The team previously standardized on Django.",
                "u_star": "A",
                "memory_action": "ignore",
            },
            {
                "atom_id": "b-1",
                "parent_memory_id": "block-1",
                "text": "The service must retry exactly three times.",
                "u_star": "B",
                "memory_action": "apply",
            },
            {
                "atom_id": "c-1",
                "parent_memory_id": "block-1",
                "text": "Exhausted failures must return status RETRY_EXHAUSTED.",
                "u_star": "C",
                "memory_action": "apply",
            },
        ],
    }


def params(source: dict) -> dict:
    return {
        "record_id": source["id"],
        "task_family": "implementation_plan",
        "expected_atom_ids": ["a-1", "b-1", "c-1"],
    }


def valid_payload() -> dict:
    return {
        "schema_version": MODULE.PAYLOAD_SCHEMA,
        "record_id": "coding-test-1",
        "task_family": "implementation_plan",
        "task_stem": (
            "Describe a natural-language implementation plan for handling a failed "
            "service operation, including its retry and terminal response behavior."
        ),
        "reference_answer": (
            "The service must retry exactly three times. "
            "Exhausted failures must return status RETRY_EXHAUSTED."
        ),
        "applicable_atom_footprints": [
            {
                "atom_id": "b-1",
                "u_star": "C",
                "memory_action": "apply",
                "required_answer_elements": [
                    "The service must retry exactly three times."
                ],
                "overuse_signals": ["Retrying more than three times"],
                "label_justification": (
                    "The retry count now controls whether the central failure path "
                    "can be implemented completely."
                ),
            },
            {
                "atom_id": "c-1",
                "u_star": "C",
                "memory_action": "apply",
                "required_answer_elements": [
                    "Exhausted failures must return status RETRY_EXHAUSTED."
                ],
                "overuse_signals": ["Returning an unsupported status"],
                "label_justification": (
                    "The terminal status controls the externally visible result of "
                    "the central failure path."
                ),
            },
        ],
        "label_revision_audit": [
            {
                "atom_id": "b-1",
                "old_u_star": "B",
                "new_u_star": "C",
                "reason": (
                    "Without the retry count the requested central control flow is "
                    "materially unresolved, so the final task makes it controlling."
                ),
            }
        ],
        "ignored_a_audit": [
            {
                "atom_id": "a-1",
                "question_has_footprint": False,
                "reference_has_footprint": False,
                "reason": "The framework preference is unrelated and fully excluded.",
            }
        ],
        "query_isolation_audit": [
            {
                "atom_id": "b-1",
                "query_supplies_atom_value": False,
                "reason": "The question asks for retry behavior without giving a count.",
            },
            {
                "atom_id": "c-1",
                "query_supplies_atom_value": False,
                "reason": "The question asks for a terminal response without naming it.",
            },
        ],
        "self_check": {key: True for key in MODULE.SELF_CHECK_KEYS},
    }


class RelabelAwareRepairTests(unittest.TestCase):
    def test_accepts_audited_bc_magnitude_change(self) -> None:
        source = source_record()
        errors, corrected, audit = MODULE.validate_custom_payload(
            valid_payload(), source, params(source)
        )
        self.assertEqual(errors, [])
        labels = {atom["atom_id"]: atom["u_star"] for atom in corrected["memories"]}
        self.assertEqual(labels, {"a-1": "A", "b-1": "C", "c-1": "C"})
        self.assertEqual(len(audit), 1)

    def test_rejects_unaudited_label_change(self) -> None:
        source = source_record()
        payload = valid_payload()
        payload["label_revision_audit"] = []
        errors, _, _ = MODULE.validate_custom_payload(
            payload, source, params(source)
        )
        self.assertIn("label_revision_audit_mismatch", errors)

    def test_rejects_a_footprint_in_reference(self) -> None:
        source = source_record()
        payload = copy.deepcopy(valid_payload())
        payload["reference_answer"] += (
            " The team previously standardized on Django."
        )
        errors, _, _ = MODULE.validate_custom_payload(
            payload, source, params(source)
        )
        self.assertTrue(
            any(
                error.startswith("a-1_a_atom_exact_text_in_reference")
                for error in errors
            )
        )


if __name__ == "__main__":
    unittest.main()
