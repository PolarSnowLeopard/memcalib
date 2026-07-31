from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "merge_memcalib_v241_semantic_qc",
    ROOT / "pipeline" / "111_merge_memcalib_v241_semantic_qc.py",
)
assert SPEC and SPEC.loader
MERGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MERGE)


def judge(decision: str) -> dict:
    return {
        "decision": decision,
        "decision_reasons": [] if decision == "strict_pass" else ["not aligned"],
        "structural_errors": [],
        "judge_output": None,
    }


class MemCalibV241SemanticQcConsensusTest(unittest.TestCase):
    def test_only_dual_strict_without_hard_blocker_is_retained(self) -> None:
        benchmark = [
            {"id": "keep", "domain": "coding"},
            {"id": "judge-repair", "domain": "coding"},
            {"id": "hard-repair", "domain": "coding"},
            {"id": "advisory-only", "domain": "coding"},
        ]
        qwen = {row["id"]: judge("strict_pass") for row in benchmark}
        deepseek = {row["id"]: judge("strict_pass") for row in benchmark}
        deepseek["judge-repair"] = judge("review")
        deterministic = {
            "hard-repair": [
                {
                    "atom_id": "p1",
                    "u_star": "B",
                    "reasons": ["probable_cross_atom_rubric_swap"],
                }
            ],
            "advisory-only": [
                {
                    "atom_id": "p1",
                    "u_star": "B",
                    "reasons": ["very_low_atom_rubric_overlap"],
                }
            ],
        }
        strict, repair, audit = MERGE.build_consensus(
            benchmark,
            qwen,
            deepseek,
            deterministic,
        )
        self.assertEqual(
            ["keep", "advisory-only"],
            [row["id"] for row in strict],
        )
        self.assertEqual(
            ["judge-repair", "hard-repair"],
            [row["record_id"] for row in repair],
        )
        self.assertEqual(4, len(audit))

    def test_missing_judge_partition_forces_repair(self) -> None:
        benchmark = [{"id": "missing", "domain": "coding"}]
        strict, repair, _ = MERGE.build_consensus(
            benchmark,
            {},
            {"missing": judge("strict_pass")},
            {},
        )
        self.assertEqual([], strict)
        self.assertEqual(["missing"], [row["record_id"] for row in repair])
        self.assertIn("judge_partition_missing", " ".join(repair[0]["errors"]))

    def test_retry_partition_replaces_only_prior_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "original"
            retry = root / "retry"
            original.with_suffix(".strict.jsonl").write_text(
                json.dumps(
                    {
                        "id": "valid",
                        "v24_coding_independent_qc": {
                            "decision": "strict_pass",
                            "decision_reasons": [],
                        },
                    }
                )
                + "\n"
            )
            original.with_suffix(".review.jsonl").write_text("")
            original.with_suffix(".reject.jsonl").write_text("")
            original.with_suffix(".invalid.jsonl").write_text(
                json.dumps({"record_id": "retried", "errors": ["bad output"]})
                + "\n"
            )
            retry.with_suffix(".strict.jsonl").write_text(
                json.dumps(
                    {
                        "id": "retried",
                        "v24_coding_independent_qc": {
                            "decision": "strict_pass",
                            "decision_reasons": [],
                        },
                    }
                )
                + "\n"
            )
            retry.with_suffix(".review.jsonl").write_text("")
            retry.with_suffix(".reject.jsonl").write_text("")
            retry.with_suffix(".invalid.jsonl").write_text("")
            resolved = MERGE.load_resolved_judge_partitions([original, retry])
            self.assertEqual("strict_pass", resolved["valid"]["decision"])
            self.assertEqual("strict_pass", resolved["retried"]["decision"])


if __name__ == "__main__":
    unittest.main()
