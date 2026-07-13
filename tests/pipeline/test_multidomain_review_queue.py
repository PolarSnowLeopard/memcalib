#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = ROOT / "tools"


def load_script(name: str, filename: str):
    path = TOOLS_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sample(
    sample_id: str,
    *,
    repair_round: int = 0,
    atom_count: int = 1,
    overlap: bool = False,
    topic: str = "planning",
    complexity: str = "medium",
) -> dict:
    answer_phrase = "alpha beta gamma delta epsilon zeta"
    memory_text = answer_phrase if overlap else f"The user has constraint {sample_id}."
    atom_ids = [f"p1_a{index}" for index in range(1, atom_count + 1)]
    memories = []
    for index, atom_id in enumerate(atom_ids, start=1):
        memories.append(
            {
                "memory_id": f"m{index}",
                "parent_memory_id": "p1",
                "atom_id": atom_id,
                "text": memory_text if index == 1 else f"The user also has constraint {sample_id}-{index}.",
                "atomic_predicate": memory_text if index == 1 else f"constraint {index}",
                "evidence": f"constraint {sample_id}",
                "source": "from_question",
                "u_star": "C" if index == 1 else "B",
                "usage_rubric": {"correct_use": "Respect the constraint."},
            }
        )
    return {
        "id": sample_id,
        "domain": "general",
        "source_id": f"source-{sample_id}",
        "source_dataset": "test/source",
        "source_topic": topic,
        "question": f"How should I handle constraint {sample_id}?",
        "raw_query": f"I have constraint {sample_id}. What should I do next?",
        "source_context": "",
        "source_answer": f"A useful answer includes {answer_phrase}." if overlap else "Provide a grounded response.",
        "memory_blocks": [
            {
                "parent_memory_id": "p1",
                "memory_text": f"The user has one or more constraints for {sample_id}.",
                "raw_evidence": f"constraint {sample_id}",
                "source": "from_question",
                "atom_count": atom_count,
                "atom_ids": atom_ids,
                "parent_label_set": sorted({memory["u_star"] for memory in memories}),
                "parent_label_mode": "mixed" if atom_count > 1 else "homogeneous",
            }
        ],
        "memories": memories,
        "lineage": {
            "generation_repair_round": repair_round,
            "raw_selection": {"seed_complexity": complexity},
        },
    }


class MultidomainReviewQueueTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.queue = load_script("multidomain_review_queue", "build_multidomain_review_queue.py")

    def test_general_queue_includes_all_repair_and_overlap_samples(self) -> None:
        rows = [sample(f"g{index}", topic=f"topic-{index % 3}") for index in range(10)]
        rows[1] = sample("g1", repair_round=1)
        rows[3] = sample("g3", overlap=True)

        first = self.queue.select_review_rows(rows, domain="general", target=5, seed=17)
        second = self.queue.select_review_rows(rows, domain="general", target=5, seed=17)
        selected_ids = {row["id"] for row in first}

        self.assertEqual([row["id"] for row in first], [row["id"] for row in second])
        self.assertEqual(5, len(first))
        self.assertTrue({"g1", "g3"}.issubset(selected_ids))
        self.assertIn("generation_repair", next(row for row in first if row["id"] == "g1")["audit_selection"]["selection_reasons"])
        self.assertIn("reference_answer_overlap", next(row for row in first if row["id"] == "g3")["audit_selection"]["selection_reasons"])

    def test_coding_queue_includes_all_non_atomic_and_overlap_samples(self) -> None:
        rows = [sample(f"c{index}", topic=f"topic-{index % 4}") for index in range(12)]
        rows[2] = sample("c2", atom_count=2)
        rows[4] = sample("c4", overlap=True)

        selected = self.queue.select_review_rows(rows, domain="coding", target=6, seed=23)
        selected_ids = {row["id"] for row in selected}

        self.assertTrue({"c2", "c4"}.issubset(selected_ids))
        self.assertIn("non_atomic_parent", next(row for row in selected if row["id"] == "c2")["audit_selection"]["selection_reasons"])
        self.assertEqual(6, len(selected))

    def test_audit_html_persists_and_exports_parent_annotations(self) -> None:
        rows = [sample("g1", repair_round=1), sample("g2", atom_count=2)]
        selected = self.queue.select_review_rows(rows, domain="general", target=2, seed=31)
        audit_rows = self.queue.AUDIT.build_parent_audit_rows(selected)
        summary = self.queue.AUDIT.summarize_rows(audit_rows, selected)
        summary.update(
            {
                "audit_title": "Test review queue",
                "storage_key": "test-review-storage",
                "export_filename": "test-review.json",
            }
        )

        with tempfile.TemporaryDirectory() as tmp:
            html_path = Path(tmp) / "review.html"
            self.queue.AUDIT.write_audit_html(html_path, audit_rows, summary)
            content = html_path.read_text(encoding="utf-8")

        self.assertEqual(2, content.count('class="sample-page'))
        self.assertIn("localStorage.getItem(storageKey)", content)
        self.assertIn('id="export-annotations"', content)
        self.assertIn('data-audit-field="review_status"', content)
        self.assertIn("构建修复", content)


if __name__ == "__main__":
    unittest.main()
