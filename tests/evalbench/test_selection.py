#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

from evaluation.common import load_release_records
from evaluation.scripts import select_eval_subset as selector
from evaluation.scripts.select_eval_subset import (
    build_selection_artifacts,
    largest_remainder_quotas,
    select_diagnostic,
    select_representative,
)


SOURCES = ("source-a", "source-b")
TOPICS = ("topic-a", "topic-b")
COMPLEXITIES = ("simple", "medium", "complex")


def make_record(index: int, source: str, topic: str, complexity: str) -> dict:
    rare = ("evidence_conflict", "profile_style_near_neighbor", "scope_overreach")[index % 3]
    mixed = index % 2 == 0
    safety = index % 3 == 0
    atom_count = 7 if index % 4 == 0 else 3
    labels = ["A", "B", "C"]
    memories = []
    for atom_index in range(atom_count):
        label = labels[atom_index % len(labels)]
        memories.append(
            {
                "atom_id": f"p1_a{atom_index + 1}",
                "parent_memory_id": "p1",
                "u_star": label,
                "memory_type": "safety_sensitive" if safety and atom_index == 0 else "case_fact",
                "hard_a_family": rare if label == "A" and atom_index == 0 else None,
            }
        )
    return {
        "id": f"sample-{index:04d}",
        "source_dataset": source,
        "source_topic": topic,
        "question": f"Question {index}",
        "memory_blocks": [
            {
                "parent_memory_id": "p1",
                "memory_text": f"Memory {index}",
                "parent_label_mode": "mixed" if mixed else "homogeneous",
                "parent_label_set": ["A", "B"] if mixed else ["A"],
            }
        ],
        "memories": memories,
        "doctor_answer": "hidden",
        "construction_audit": {"hidden": True},
        "_seed_complexity": complexity,
    }


def synthetic_records() -> list[dict]:
    records = []
    index = 0
    for source in SOURCES:
        for topic in TOPICS:
            for complexity in COMPLEXITIES:
                for _ in range(20):
                    records.append(make_record(index, source, topic, complexity))
                    index += 1
    return records


class SelectionTest(unittest.TestCase):
    def test_load_release_records_supports_locked_manifest(self) -> None:
        release_dir = Path(__file__).resolve().parents[2] / "release" / "memcalib-v0.1"

        records, source_sha = load_release_records(release_dir)

        self.assertEqual(15_528, len(records))
        self.assertEqual("1cfd0334255266e6b8d4c234c615ade42b40c91bb86cb7c061a285261c363cb4", source_sha)

    def test_largest_remainder_quotas_are_exact_and_deterministic(self) -> None:
        counts = {"a": 5, "b": 3, "c": 2}

        self.assertEqual({"a": 4, "b": 2, "c": 1}, largest_remainder_quotas(counts, 7))

    def test_representative_selection_meets_hard_margins(self) -> None:
        config = {
            "seed": 20260712,
            "representative": {
                "size": 12,
                "source_quotas": {"source-a": 6, "source-b": 6},
                "complexity_quotas": {"simple": 3, "medium": 6, "complex": 3},
            },
        }

        first = select_representative(synthetic_records(), config)
        second = select_representative(synthetic_records(), config)

        self.assertEqual([row["id"] for row in first], [row["id"] for row in second])
        self.assertEqual(12, len(first))
        self.assertEqual({"source-a": 6, "source-b": 6}, Counter(row["source_dataset"] for row in first))
        self.assertEqual({"topic-a": 6, "topic-b": 6}, Counter(row["source_topic"] for row in first))
        self.assertEqual(
            {"simple": 3, "medium": 6, "complex": 3},
            Counter(row["_seed_complexity"] for row in first),
        )

    def test_representative_selection_precomputes_record_features(self) -> None:
        records = synthetic_records()
        config = {
            "seed": 20260712,
            "representative": {
                "size": 12,
                "source_quotas": {"source-a": 6, "source-b": 6},
                "complexity_quotas": {"simple": 3, "medium": 6, "complex": 3},
            },
        }

        with mock.patch.object(selector, "record_features", wraps=selector.record_features) as wrapped:
            select_representative(records, config)

        self.assertLessEqual(wrapped.call_count, len(records) * 2)

    def test_diagnostic_selection_meets_minimum_coverage(self) -> None:
        config = {
            "seed": 20260712,
            "diagnostic": {
                "size": 12,
                "source_quotas": {"source-a": 6, "source-b": 6},
                "topic_minimum": 2,
                "mixed_parent_minimum": 6,
                "rare_hard_a_families": [
                    "evidence_conflict",
                    "profile_style_near_neighbor",
                    "scope_overreach",
                ],
                "rare_hard_a_each_minimum": 2,
                "rare_hard_a_union_minimum": 6,
                "safety_sensitive_minimum": 3,
                "high_atom_minimum": 3,
                "high_atom_threshold": 7,
            },
        }

        selected = select_diagnostic(synthetic_records(), set(), config)
        source_counts = Counter(row["source_dataset"] for row in selected)
        topic_counts = Counter(row["source_topic"] for row in selected)
        rare_counts = Counter(
            memory["hard_a_family"]
            for row in selected
            for memory in row["memories"]
            if memory.get("hard_a_family")
        )

        self.assertEqual(12, len(selected))
        self.assertEqual({"source-a": 6, "source-b": 6}, source_counts)
        self.assertGreaterEqual(min(topic_counts.values()), 2)
        self.assertGreaterEqual(
            sum(any(block["parent_label_mode"] == "mixed" for block in row["memory_blocks"]) for row in selected),
            6,
        )
        for family in config["diagnostic"]["rare_hard_a_families"]:
            self.assertGreaterEqual(rare_counts[family], 2)

    def test_diagnostic_selection_precomputes_record_features(self) -> None:
        records = synthetic_records()
        config = {
            "seed": 20260712,
            "diagnostic": {
                "size": 12,
                "source_quotas": {"source-a": 6, "source-b": 6},
                "topic_minimum": 2,
                "mixed_parent_minimum": 6,
                "rare_hard_a_families": [
                    "evidence_conflict",
                    "profile_style_near_neighbor",
                    "scope_overreach",
                ],
                "rare_hard_a_each_minimum": 2,
                "rare_hard_a_union_minimum": 6,
                "safety_sensitive_minimum": 3,
                "high_atom_minimum": 3,
                "high_atom_threshold": 7,
            },
        }

        with mock.patch.object(selector, "record_features", wraps=selector.record_features) as wrapped:
            select_diagnostic(records, set(), config)

        self.assertLessEqual(wrapped.call_count, len(records) * 2)

    def test_artifacts_separate_hidden_and_model_facing_fields(self) -> None:
        records = synthetic_records()[:4]
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            manifest = build_selection_artifacts(records[:2], records[2:], output_dir, {"seed": 20260712})
            model_rows = [
                json.loads(line)
                for line in (output_dir / "model-facing.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            hidden_rows = [
                json.loads(line)
                for line in (output_dir / "hidden-evaluation.jsonl").read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(4, manifest["counts"]["total"])
        self.assertNotIn("memories", model_rows[0])
        self.assertNotIn("doctor_answer", model_rows[0])
        self.assertNotIn("construction_audit", model_rows[0])
        self.assertIn("memories", hidden_rows[0])
        self.assertEqual(["representative", "representative", "diagnostic", "diagnostic"], [r["panel"] for r in hidden_rows])


if __name__ == "__main__":
    unittest.main()
