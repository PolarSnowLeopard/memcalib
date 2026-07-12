from __future__ import annotations

import gzip
import tempfile
import unittest
from pathlib import Path

from evaluation.scripts.release_full_benchmark import (
    canonicalize_parent_blocks,
    deduplicate_questions,
    validate_record,
    write_deterministic_gzip,
)


def atom(atom_id: str, parent_id: str, label: str = "B") -> dict:
    return {
        "atom_id": atom_id,
        "parent_memory_id": parent_id,
        "text": f"Atomic memory {atom_id}.",
        "u_star": label,
        "usage_rubric": {"correct_use": "Use it locally."},
        "memory_type": "case_fact",
        "hard_a_family": None,
    }


def record(sample_id: str, question: str, atoms: list[dict], blocks: list[dict]) -> dict:
    return {
        "id": sample_id,
        "source_dataset": "source",
        "source_topic": "topic",
        "question": question,
        "memory_blocks": blocks,
        "memories": atoms,
        "qc": {
            "atomicity_pass": True,
            "duplicate_pass": True,
            "question_memory_leakage_pass": True,
            "hard_a_target_consistency_pass": True,
            "rubric_objectivity_pass": True,
        },
    }


class FullReleaseTest(unittest.TestCase):
    def test_release_gzip_is_deterministic_and_reversible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "data.jsonl"
            first = Path(tmp) / "first.jsonl.gz"
            second = Path(tmp) / "second.jsonl.gz"
            payload = b'{"id":"s1"}\n{"id":"s2"}\n'
            source.write_bytes(payload)

            write_deterministic_gzip(source, first)
            write_deterministic_gzip(source, second)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            with gzip.open(first, "rb") as handle:
                self.assertEqual(payload, handle.read())

    def test_duplicate_parent_blocks_are_merged_without_losing_atoms(self) -> None:
        atoms = [atom("p1_a1", "p1", "B"), atom("p1_a2", "p1", "C")]
        row = record(
            "s1",
            "Question?",
            atoms,
            [
                {"parent_memory_id": "p1", "memory_text": "First fact.", "atom_ids": ["p1_a1"]},
                {"parent_memory_id": "p1", "memory_text": "Related fact.", "atom_ids": ["p1_a2"]},
            ],
        )

        repaired, count = canonicalize_parent_blocks(row)

        self.assertEqual(1, count)
        self.assertEqual(1, len(repaired["memory_blocks"]))
        self.assertEqual(["p1_a1", "p1_a2"], repaired["memory_blocks"][0]["atom_ids"])
        self.assertEqual(["B", "C"], repaired["memory_blocks"][0]["parent_label_set"])
        self.assertEqual([], validate_record(repaired))

    def test_exact_question_dedup_prefers_richer_atomic_coverage(self) -> None:
        first_atoms = [atom("p1_a1", "p1")]
        second_atoms = [atom("p1_a1", "p1"), atom("p1_a2", "p1")]
        first = record(
            "s1",
            "Same question?",
            first_atoms,
            [{"parent_memory_id": "p1", "memory_text": "Fact.", "atom_ids": ["p1_a1"]}],
        )
        second = record(
            "s2",
            "  same   QUESTION? ",
            second_atoms,
            [{"parent_memory_id": "p1", "memory_text": "Richer fact.", "atom_ids": ["p1_a1", "p1_a2"]}],
        )

        kept, excluded = deduplicate_questions([first, second])

        self.assertEqual(["s2"], [row["id"] for row in kept])
        self.assertEqual("s1", excluded[0]["excluded_id"])
        self.assertEqual("s2", excluded[0]["kept_id"])


if __name__ == "__main__":
    unittest.main()
