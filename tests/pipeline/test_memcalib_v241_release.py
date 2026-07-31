from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "pipeline") not in sys.path:
    sys.path.insert(0, str(ROOT / "pipeline"))
SPEC = importlib.util.spec_from_file_location(
    "build_memcalib_v241_release",
    ROOT / "pipeline" / "113_build_memcalib_v241_release.py",
)
assert SPEC and SPEC.loader
RELEASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RELEASE)


def coding(record_id: str) -> dict:
    return {
        "id": record_id,
        "domain": "coding",
        "schema_version": "crk-2-canonical-memory-v2.4",
        "question": f"question {record_id}",
        "memory_blocks": [
            {
                "parent_memory_id": "p1",
                "memory_text": "memory",
                "atom_ids": ["p1_a1"],
            }
        ],
        "memories": [
            {
                "atom_id": "p1_a1",
                "text": "memory",
                "u_star": "B",
                "memory_action": "apply",
                "parent_memory_id": "p1",
            }
        ],
    }


class MemCalibV241ReleaseTest(unittest.TestCase):
    def test_merge_preserves_order_and_locked_supervision(self) -> None:
        baseline = [coding("r1"), coding("r2")]
        retained = [copy.deepcopy(baseline[1])]
        repaired = [copy.deepcopy(baseline[0])]
        repaired[0]["question"] = "repaired question"
        merged = RELEASE.merge_coding_records(baseline, retained, repaired)
        self.assertEqual(["r1", "r2"], [row["id"] for row in merged])
        self.assertEqual("repaired question", merged[0]["question"])
        self.assertEqual(
            "targeted_rewrite_dual_strict",
            merged[0]["v241_alignment_remediation"]["channel"],
        )
        self.assertEqual(
            "retained_dual_strict",
            merged[1]["v241_alignment_remediation"]["channel"],
        )

    def test_merge_allows_audited_label_action_changes(self) -> None:
        baseline = [coding("r1")]
        repaired = [copy.deepcopy(baseline[0])]
        repaired[0]["memories"][0]["u_star"] = "C"
        merged = RELEASE.merge_coding_records(baseline, [], repaired)
        changes = merged[0]["v241_alignment_remediation"]["label_action_changes"]
        self.assertEqual(1, len(changes))
        self.assertEqual("B", changes[0]["old_u_star"])
        self.assertEqual("C", changes[0]["new_u_star"])

    def test_merge_rejects_changed_atom_text(self) -> None:
        baseline = [coding("r1")]
        repaired = [copy.deepcopy(baseline[0])]
        repaired[0]["memories"][0]["text"] = "changed memory"
        with self.assertRaisesRegex(ValueError, "identity or text changed"):
            RELEASE.merge_coding_records(baseline, [], repaired)


if __name__ == "__main__":
    unittest.main()
