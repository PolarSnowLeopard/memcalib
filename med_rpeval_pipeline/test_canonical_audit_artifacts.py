#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
AUDIT_SCRIPT = SCRIPT_DIR / "12_build_canonical_audit_artifacts.py"


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CanonicalAuditArtifactsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.audit = load_script(AUDIT_SCRIPT, "canonical_audit")

    def sample(self) -> dict:
        return {
            "id": "crk2_raw1",
            "source_id": "raw1",
            "source_topic": "digestive",
            "source_dataset": "unit",
            "question": "去背景化问题",
            "memory_blocks": [
                {
                    "parent_memory_id": "p1",
                    "memory_text": "用户吃了自制辣椒后出现上腹痛，并伴有恶心。",
                    "raw_evidence": "I ate homemade chili and now have upper abdominal pain with nausea.",
                    "source": "from_question",
                    "u_star": "C",
                    "atom_count": 2,
                    "atom_ids": ["p1_a1", "p1_a2"],
                },
                {
                    "parent_memory_id": "p2",
                    "memory_text": "用户过去认为胃部不适通常只是压力导致。",
                    "raw_evidence": "synthetic hard A",
                    "source": "synthetic_hard_a",
                    "u_star": "A",
                    "atom_count": 1,
                    "atom_ids": ["p2_a1"],
                },
            ],
            "memories": [
                {
                    "parent_memory_id": "p1",
                    "atom_id": "p1_a1",
                    "text": "用户吃了自制辣椒。",
                    "evidence": "I ate homemade chili.",
                    "u_star": "C",
                    "subtype": "exposure",
                    "memory_type": "case_fact",
                    "hard_a_family": None,
                    "label_reason": "决定病因判断。",
                    "usage_rubric": {
                        "memory_usage_weight": "controlling",
                        "correct_use": "考虑食物刺激。",
                        "under_use": "忽略暴露。",
                        "over_use": "直接确诊。",
                    },
                },
                {
                    "parent_memory_id": "p1",
                    "atom_id": "p1_a2",
                    "text": "用户伴有恶心。",
                    "evidence": "with nausea.",
                    "u_star": "B",
                    "subtype": "symptom",
                    "memory_type": "case_fact",
                    "hard_a_family": None,
                    "label_reason": "局部支持解释。",
                    "usage_rubric": {
                        "memory_usage_weight": "supporting",
                        "correct_use": "局部提及。",
                        "under_use": "遗漏细节。",
                        "over_use": "主导结论。",
                    },
                },
                {
                    "parent_memory_id": "p2",
                    "atom_id": "p2_a1",
                    "text": "用户过去认为胃部不适通常只是压力导致。",
                    "evidence": "synthetic hard A",
                    "u_star": "A",
                    "subtype": "hard_a_evidence_conflict",
                    "memory_type": "profile_fact",
                    "hard_a_family": "evidence_conflict",
                    "label_reason": "当前证据优先。",
                    "usage_rubric": {
                        "memory_usage_weight": "none",
                        "correct_use": "完全不用。",
                        "under_use": "A 无 under-use。",
                        "over_use": "提及即过用。",
                    },
                },
            ],
        }

    def test_build_parent_audit_rows_marks_mixed_label_blocks(self) -> None:
        rows = self.audit.build_parent_audit_rows([self.sample()])

        self.assertEqual(2, len(rows))
        self.assertEqual("p1", rows[0]["parent_memory_id"])
        self.assertEqual("B+C", rows[0]["parent_label_set"])
        self.assertEqual("mixed", rows[0]["parent_label_mode"])
        self.assertIn("p1_a1:C:用户吃了自制辣椒。", rows[0]["atom_summary"])
        self.assertEqual("", rows[0]["review_status"])
        self.assertEqual("", rows[0]["memory_text_quality"])
        self.assertEqual("A", rows[1]["parent_label_set"])
        self.assertEqual("homogeneous", rows[1]["parent_label_mode"])
        self.assertEqual("evidence_conflict", rows[1]["hard_a_family_set"])

    def test_write_csv_and_html_include_reviewer_fields(self) -> None:
        rows = self.audit.build_parent_audit_rows([self.sample()])
        with tempfile.TemporaryDirectory() as td:
            csv_path = Path(td) / "audit.csv"
            html_path = Path(td) / "audit.html"
            self.audit.write_audit_csv(csv_path, rows)
            self.audit.write_audit_html(html_path, rows, {"total_samples": 1, "total_parent_rows": 2})

            with csv_path.open(encoding="utf-8") as f:
                csv_rows = list(csv.DictReader(f))
            csv_line_count = len(csv_path.read_text(encoding="utf-8").splitlines())
            html = html_path.read_text(encoding="utf-8")

        self.assertIn("memory_text_quality", csv_rows[0])
        self.assertEqual("", csv_rows[0]["memory_text_quality"])
        self.assertEqual(3, csv_line_count)
        self.assertIn("人工审查", html)
        self.assertIn("memory_text_quality", html)
        self.assertIn('class="audit-row mixed"', html)
        self.assertIn('class="review-panel"', html)
        self.assertIn('data-filter="mixed"', html)
        self.assertIn("B+C", html)
        self.assertIn("I ate homemade chili", html)


if __name__ == "__main__":
    unittest.main()
