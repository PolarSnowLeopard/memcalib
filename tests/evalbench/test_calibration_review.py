from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evaluation.scripts.build_calibration_review import (
    DEFAULT_TEMPLATE,
    attach_translations,
    render_calibration_review_html,
)
from evaluation.scripts.calibration_review_translation import collect_translation_items, chunk_items


class CalibrationReviewTest(unittest.TestCase):
    def test_translation_inventory_covers_rubric_lists_and_both_judges(self) -> None:
        record = {
            "question": "Question",
            "memory_blocks": [{"memory_text": "Memory"}],
            "model_response": "Response",
            "atomic_memories": [
                {
                    "text": "Atom",
                    "usage_rubric": {"correct_use": "Use it", "observable_checks": ["Check one", "Check two"]},
                }
            ],
            "primary_judgment": {"atom_judgments": [{"evidence_quote": "Quote", "reason": "Primary reason"}]},
            "secondary_judgment": {"atom_judgments": [{"evidence_quote": "", "reason": "Secondary reason"}]},
        }

        items = {item["field_id"]: item["english"] for item in collect_translation_items(record)}

        self.assertEqual("Question", items["question"])
        self.assertEqual("Check two", items["atomic_memories.0.usage_rubric.observable_checks.1"])
        self.assertEqual("Primary reason", items["primary_judgment.atom_judgments.0.reason"])
        self.assertEqual("Secondary reason", items["secondary_judgment.atom_judgments.0.reason"])
        self.assertNotIn("secondary_judgment.atom_judgments.0.evidence_quote", items)

    def test_translation_chunks_preserve_every_field_once(self) -> None:
        items = [
            {"field_id": "a", "english": "1234"},
            {"field_id": "b", "english": "5678"},
            {"field_id": "c", "english": "90"},
        ]

        chunks = chunk_items(items, max_source_chars=6)

        self.assertEqual([["a"], ["b", "c"]], [[item["field_id"] for item in chunk] for chunk in chunks])

    def test_bilingual_renderer_embeds_atom_level_controls(self) -> None:
        records = [
            {
                "answer_request_id": "answer-1",
                "translations_zh": {"question": "问题"},
                "question": "Question",
                "memory_blocks": [],
                "model_response": "Response",
                "atomic_memories": [],
            }
        ]

        html = render_calibration_review_html(records, DEFAULT_TEMPLATE)

        self.assertIn('class="atom-level"', html)
        self.assertIn("English · 正式原文", html)
        self.assertIn("Gold u* 表示应该如何使用", html)
        self.assertIn("完成“实际使用强度”后显示 Gold", html)
        self.assertIn("行动或建议违反记忆约束", html)
        self.assertIn('if (event.key === \'ArrowLeft\') go(-1)', html)
        self.assertIn(json.dumps(records, ensure_ascii=False), html)

    def test_attach_translations_matches_answer_id(self) -> None:
        records = [{"answer_request_id": "answer-1"}, {"answer_request_id": "answer-2"}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "translations.jsonl"
            path.write_text(
                json.dumps({"answer_request_id": "answer-2", "translations_zh": {"question": "问题"}}, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )

            localized = attach_translations(records, path)

        self.assertEqual(1, localized)
        self.assertNotIn("translations_zh", records[0])
        self.assertEqual({"question": "问题"}, records[1]["translations_zh"])


if __name__ == "__main__":
    unittest.main()
