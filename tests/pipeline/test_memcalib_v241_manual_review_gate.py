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


def atom(atom_id: str, label: str, text: str) -> dict:
    return {
        "atom_id": atom_id,
        "parent_memory_id": atom_id,
        "text": text,
        "atomic_predicate": text,
        "u_star": label,
        "memory_action": "ignore" if label == "A" else "apply",
    }


class ManualReviewGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_script(
            PIPELINE_DIR / "126_apply_memcalib_v241_manual_review_gate.py",
            "apply_memcalib_v241_manual_review_gate_test",
        )

    def test_rebuild_block_text_removes_missing_atoms(self) -> None:
        blocks = [
            {
                "parent_memory_id": "block",
                "atom_ids": ["a", "b"],
                "memory_text": "stale",
            }
        ]
        rebuilt = self.module.rebuild_block_text(
            blocks,
            [atom("b", "A", "Retained sentence.")],
        )
        self.assertEqual(["b"], rebuilt[0]["atom_ids"])
        self.assertEqual("Retained sentence.", rebuilt[0]["memory_text"])

    def test_remove_conflicting_hard_a_updates_blocks(self) -> None:
        record = {
            "id": "sample",
            "memories": [
                atom("target", "B", "Target."),
                atom("v22_harda_01_a1", "A", "Conflict."),
            ],
            "memory_blocks": [
                {
                    "parent_memory_id": "target",
                    "atom_ids": ["target"],
                    "memory_text": "Target.",
                },
                {
                    "parent_memory_id": "hard",
                    "atom_ids": ["v22_harda_01_a1"],
                    "memory_text": "Conflict.",
                },
            ],
        }
        output = self.module.remove_conflicting_hard_a(record)
        self.assertEqual(["target"], [item["atom_id"] for item in output["memories"]])
        self.assertEqual(1, len(output["memory_blocks"]))

    def test_build_replacement_has_reviewed_core_and_noise(self) -> None:
        reserve = {
            "id": self.module.REPLACEMENT_RECORD_ID,
            "domain": "coding",
            "memories": [
                atom("p1_a1", "C", "Combined team fact."),
                atom("p1_a2", "A", "PHP fact."),
                atom("p3_a1", "A", "Physical machine fact."),
            ],
            "memory_blocks": [],
        }
        removed = {
            "id": self.module.REMOVED_RECORD_ID,
            "memories": [atom("noise", "A", "Unrelated noise.")],
            "memory_blocks": [
                {
                    "parent_memory_id": "noise",
                    "atom_ids": ["noise"],
                    "memory_text": "Unrelated noise.",
                }
            ],
        }
        output = self.module.build_replacement(reserve, removed)
        labels = {item["atom_id"]: item["u_star"] for item in output["memories"]}
        self.assertEqual("C", labels["p1_a1"])
        self.assertEqual("B", labels["p1_a2"])
        self.assertEqual("A", labels["p3_a1"])
        self.assertEqual("A", labels["noise"])
        self.assertEqual(self.module.REPLACEMENT_RECORD_ID, output["id"])
        self.assertIn("three-person", output["source_answer"])


if __name__ == "__main__":
    unittest.main()
