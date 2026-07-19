from __future__ import annotations

import importlib.util
import json
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


class MemCalibV22LongtailQcTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.post = load_script(
            PIPELINE_DIR / "70_post_memcalib_v22_longtail_independent_qc.py",
            "post_memcalib_v22_longtail_independent_qc",
        )
        cls.retry = load_script(
            PIPELINE_DIR / "75_prepare_memcalib_v22_longtail_qc_retry.py",
            "prepare_memcalib_v22_longtail_qc_retry",
        )
        cls.id_repair = load_script(
            PIPELINE_DIR / "76_repair_memcalib_v22_qc_record_id.py",
            "repair_memcalib_v22_qc_record_id",
        )
        cls.merge = load_script(
            PIPELINE_DIR / "78_merge_memcalib_v22_longtail_tail_qc.py",
            "merge_memcalib_v22_longtail_tail_qc",
        )

    def record(self) -> dict:
        return {"id": "r1", "domain": "coding", "memories": []}

    def params(self) -> dict:
        return {
            "schema_version": self.post.REQUEST_SCHEMA,
            "record_id": "r1",
            "record_fingerprint": self.post.canonical_sha256(self.record()),
            "domain": "coding",
            "auxiliary_atom_ids": ["a1"],
            "auxiliary_block_atom_ids": {"p1": ["a1"]},
        }

    def qc(self) -> dict:
        return {
            "schema_version": self.post.QC_SCHEMA,
            "record_id": "r1",
            "atom_checks": [
                {
                    "atom_id": "a1",
                    "query_relation": "absent",
                    "answer_footprint": "none",
                    "explicit_correction_required": False,
                    "atomicity": "pass",
                    "same_user_plausibility": "pass",
                    "decision": "pass",
                    "reason": "The unrelated memory cannot change any valid implementation.",
                }
            ],
            "block_checks": [
                {
                    "parent_memory_id": "p1",
                    "joint_answer_footprint": "none",
                    "coherence": "pass",
                    "decision": "pass",
                    "reason": "The one-atom block is coherent and has no answer footprint.",
                }
            ],
            "global_check": {
                "all_auxiliary_zero_footprint": True,
                "no_collective_persona_influence": True,
                "all_locked_memories_unchanged": True,
                "reason": "The complete auxiliary set is inert for the current task.",
            },
            "recommended_decision": "strict_pass",
            "decision_reason": "All auxiliary checks pass.",
        }

    def test_all_pass_computes_strict(self) -> None:
        errors, decision, reasons = self.post.validate_qc(
            self.qc(), self.record(), self.params()
        )
        self.assertEqual([], errors)
        self.assertEqual("strict_pass", decision)
        self.assertEqual([], reasons)

    def test_footprint_forces_reject_despite_declared_pass(self) -> None:
        qc = self.qc()
        qc["atom_checks"][0]["answer_footprint"] = "implementation"
        errors, decision, reasons = self.post.validate_qc(
            qc, self.record(), self.params()
        )
        self.assertEqual([], errors)
        self.assertEqual("reject", decision)
        self.assertIn("a1:answer_footprint_implementation", reasons)

    def test_missing_atom_is_invalid(self) -> None:
        qc = self.qc()
        qc["atom_checks"] = []
        errors, decision, _ = self.post.validate_qc(
            qc, self.record(), self.params()
        )
        self.assertIn("atom_checks_order_or_coverage_mismatch", errors)
        self.assertEqual("invalid", decision)

    def test_check_order_does_not_change_coverage(self) -> None:
        params = self.params()
        params["auxiliary_atom_ids"] = ["a1", "a2"]
        params["auxiliary_block_atom_ids"] = {"p2": ["a2"], "p1": ["a1"]}
        qc = self.qc()
        second_atom = dict(qc["atom_checks"][0])
        second_atom["atom_id"] = "a2"
        second_block = dict(qc["block_checks"][0])
        second_block["parent_memory_id"] = "p2"
        qc["atom_checks"] = [second_atom, qc["atom_checks"][0]]
        qc["block_checks"] = [qc["block_checks"][0], second_block]

        errors, decision, reasons = self.post.validate_qc(
            qc, self.record(), params
        )
        self.assertEqual([], errors)
        self.assertEqual("strict_pass", decision)
        self.assertEqual([], reasons)

    def test_invalid_qc_retry_preserves_request_identity(self) -> None:
        request = {
            "request_id": "v22_longtail_qc:r1",
            "prompt": [{"role": "user", "content": "Verify this record."}],
            "user_defined_params": self.params(),
        }
        retried = self.retry.build_retry_request(
            request,
            {
                "request_id": request["request_id"],
                "validation_errors": ["record_id_mismatch"],
            },
        )
        self.assertEqual(request["request_id"], retried["request_id"])
        self.assertEqual(
            request["user_defined_params"], retried["user_defined_params"]
        )
        self.assertIn("record_id_mismatch", retried["prompt"][0]["content"])
        self.assertEqual("Verify this record.", request["prompt"][0]["content"])

    def test_qc_record_id_repair_changes_only_judge_id(self) -> None:
        judge = self.qc()
        judge["record_id"] = "r-typo"
        result = {
            "request_id": "v22_longtail_qc:r1",
            "response": "{}",
            "raw_response": {"choices": [{"message": {"content": "{}"}}]},
        }
        repaired, audit = self.id_repair.repair_invalid_row(
            {
                "request_id": result["request_id"],
                "record_id": "r1",
                "validation_errors": ["record_id_mismatch"],
                "judge_output": judge,
                "raw_result": result,
            }
        )
        repaired_judge = json.loads(repaired["response"])
        self.assertEqual("r1", repaired_judge["record_id"])
        self.assertEqual(
            repaired["response"],
            repaired["raw_response"]["choices"][0]["message"]["content"],
        )
        self.assertEqual(["record_id"], audit["changed_fields"])

    def test_qc_record_id_repair_rejects_other_errors(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported QC repair errors"):
            self.id_repair.repair_invalid_row(
                {"validation_errors": ["block_checks_order_or_coverage_mismatch"]}
            )

    def test_tail_qc_merge_replaces_in_original_order(self) -> None:
        base = [
            {"id": "r1", "value": "old"},
            {"id": "r2", "value": "keep"},
        ]
        repaired = [
            {
                "id": "r1",
                "value": "new",
                "longtail_independent_qc": {"computed_decision": "strict_pass"},
            }
        ]
        merged = self.merge.merge_rows(base, repaired)
        self.assertEqual(["r1", "r2"], [row["id"] for row in merged])
        self.assertEqual("new", merged[0]["value"])
        self.assertEqual("keep", merged[1]["value"])

    def test_tail_qc_merge_rejects_failed_repair(self) -> None:
        with self.assertRaisesRegex(ValueError, "forbidden QC decision"):
            self.merge.merge_rows(
                [{"id": "r1"}],
                [
                    {
                        "id": "r1",
                        "longtail_independent_qc": {
                            "computed_decision": "reject"
                        },
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()
