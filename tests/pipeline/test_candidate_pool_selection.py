#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[2] / "pipeline"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

CANDIDATE_SCRIPT = SCRIPT_DIR / "17_select_crk2_candidate_pool.py"


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def eligible_row(row_id: str, source: str, topic: str, complexity: str, score: int) -> dict:
    return {
        "id": row_id,
        "source_dataset": source,
        "source_split": "train",
        "source_index": row_id,
        "topic": topic,
        "raw_question": f"What should I discuss about symptom {row_id}? My symptoms have changed recently.",
        "doctor_answer": "A clinician should review the history, examination findings, and relevant tests.",
        "raw_selection": {
            "hard_filter_pass": True,
            "hard_rejection_reasons": [],
            "score_pass": True,
            "eligible": True,
            "quality_score": score,
            "quality_components": {
                "question_informativeness": 20,
                "answer_substance": 20,
                "memory_suitability": 30,
                "cleanliness_coherence": 10,
            },
            "memory_signal_families": ["personal_entity", "temporal_history"],
            "seed_complexity": complexity,
            "dedup_status": "unique",
            "duplicate_cluster_id": None,
            "duplicate_of": None,
            "selection_status": "eligible",
        },
    }


def selection_config() -> dict:
    return {
        "min_quality_score": 65,
        "topic_alpha": 0.5,
        "quality_weight_beta": 2.0,
        "complexity_targets": {"simple": 0.25, "medium": 0.5, "complex": 0.25},
    }


class CandidatePoolSelectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_script(CANDIDATE_SCRIPT, "candidate_pool_selector")

    def test_select_candidate_pool_enforces_equal_per_source_quota(self) -> None:
        rows = []
        for source in ("source-a", "source-b"):
            for index in range(6):
                rows.append(
                    eligible_row(
                        f"{source}-{index}",
                        source,
                        "rare" if index == 0 else "common",
                        ("simple", "medium", "complex")[index % 3],
                        90 - index,
                    )
                )

        selected = self.module.select_candidate_pool(
            rows,
            per_source=4,
            seed=42,
            config=selection_config(),
        )

        self.assertEqual(8, len(selected))
        self.assertEqual({"source-a": 4, "source-b": 4}, dict(Counter(row["source_dataset"] for row in selected)))
        self.assertEqual(list(range(1, 9)), [row["raw_selection"]["selection_rank"] for row in selected])

    def test_select_candidate_pool_rejects_insufficient_source_capacity(self) -> None:
        rows = [eligible_row("a-1", "source-a", "common", "medium", 80)]

        with self.assertRaisesRegex(ValueError, "source-a has 1 eligible rows; requires 2"):
            self.module.select_candidate_pool(rows, per_source=2, seed=42, config=selection_config())

    def test_verify_parent_manifest_rejects_stale_eligible_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            eligible_path = Path(tmp) / "eligible.jsonl"
            eligible_path.write_text(json.dumps(eligible_row("a-1", "source-a", "common", "medium", 80)) + "\n")
            manifest_path = Path(tmp) / "parent.json"
            manifest_path.write_text(
                json.dumps({"outputs": {"eligible_pool": {"sha256": "0" * 64}}}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "eligible pool hash does not match parent manifest"):
                self.module.verify_parent_manifest(eligible_path, manifest_path)

    def test_candidate_manifest_records_parent_lineage_and_source_quota(self) -> None:
        rows = [
            eligible_row("a-1", "source-a", "common", "simple", 80),
            eligible_row("b-1", "source-b", "rare", "complex", 90),
        ]
        for rank, row in enumerate(rows, start=1):
            row["raw_selection"]["selection_status"] = "selected"
            row["raw_selection"]["selection_rank"] = rank
        with tempfile.TemporaryDirectory() as tmp:
            eligible_path = Path(tmp) / "eligible.jsonl"
            eligible_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
            parent_path = Path(tmp) / "parent.json"
            parent_path.write_text(json.dumps({"schema_version": "crk2-raw-selection-v1"}), encoding="utf-8")
            output_path = Path(tmp) / "selected.jsonl"
            output_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

            manifest = self.module.build_candidate_manifest(
                eligible_rows=rows,
                selected_rows=rows,
                eligible_path=eligible_path,
                parent_manifest_path=parent_path,
                output_path=output_path,
                per_source=1,
                seed=42,
                config=selection_config(),
            )

        self.assertEqual("crk2-source-candidate-pool-v1", manifest["schema_version"])
        self.assertEqual(64, len(manifest["parent"]["manifest_sha256"]))
        self.assertEqual({"source-a": 1, "source-b": 1}, manifest["distributions"]["source_dataset"])
        self.assertEqual(1, manifest["parameters"]["per_source"])
        self.assertEqual(2, manifest["counts"]["selected"])


if __name__ == "__main__":
    unittest.main()
