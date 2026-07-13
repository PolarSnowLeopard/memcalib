from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evaluation.scripts.release_multidomain_pilot import build_release


def source_row(domain: str, index: int) -> dict:
    return {
        "id": f"{domain}-{index}",
        "domain": domain,
        "source_dataset": f"source/{domain}",
        "source_topic": "topic",
        "question": f"Question {index}?",
        "source_answer": "Hidden reference answer.",
        "memory_blocks": [
            {
                "parent_memory_id": "p1",
                "memory_text": f"The user has constraint {index}.",
            }
        ],
        "memories": [
            {
                "atom_id": "p1_a1",
                "parent_memory_id": "p1",
                "text": f"The user has constraint {index}.",
                "u_star": "C",
                "usage_rubric": {"correct_use": "Respect it."},
            }
        ],
        "lineage": {"private": True},
    }


class MultidomainPilotReleaseTest(unittest.TestCase):
    def test_release_keeps_answers_and_atoms_out_of_model_facing_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            general_path = root / "general.jsonl"
            coding_path = root / "coding.jsonl"
            output_dir = root / "release"
            general_path.write_text(
                "".join(json.dumps(source_row("general", index)) + "\n" for index in range(100)),
                encoding="utf-8",
            )
            coding_path.write_text(
                "".join(json.dumps(source_row("coding", index)) + "\n" for index in range(100)),
                encoding="utf-8",
            )

            manifest = build_release(general_path, coding_path, output_dir)
            facing = [
                json.loads(line)
                for line in (output_dir / "model-facing.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            hidden = [
                json.loads(line)
                for line in (output_dir / "hidden-evaluation.jsonl").read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(200, manifest["samples"])
        self.assertEqual({"coding": 100, "general": 100}, manifest["domains"])
        self.assertEqual("general", facing[0]["panel"])
        self.assertNotIn("source_answer", facing[0])
        self.assertNotIn("memories", facing[0])
        self.assertIn("source_answer", hidden[0])
        self.assertIn("memories", hidden[0])


if __name__ == "__main__":
    unittest.main()
