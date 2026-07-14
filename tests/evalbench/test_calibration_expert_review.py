from __future__ import annotations

import json
import unittest

from evaluation.common import iter_jsonl
from evaluation.scripts.finalize_calibration_expert_review import (
    DEFAULT_ANNOTATIONS,
    DEFAULT_BASE_HTML,
    DEFAULT_HIDDEN,
    DEFAULT_RECORDS,
    load_sources,
    render_reviewed_html,
    summarize,
    validate_annotations,
)


class CalibrationExpertReviewTest(unittest.TestCase):
    def test_locked_review_is_complete_and_matches_release_records(self) -> None:
        records = list(iter_jsonl(DEFAULT_RECORDS))
        payload = json.loads(DEFAULT_ANNOTATIONS.read_text(encoding="utf-8"))

        annotations = validate_annotations(records, payload)
        summary = summarize(records, payload, annotations, load_sources(DEFAULT_HIDDEN))

        self.assertEqual(30, len(annotations))
        self.assertEqual(25, summary["unique_samples"])
        self.assertEqual(161, summary["atoms"])
        self.assertEqual({"reject": 20, "revise": 10}, summary["decisions"])
        self.assertEqual({"invalid": 89, "revise": 6, "valid": 66}, summary["gold_quality"])
        self.assertEqual(
            {"OpenMed/MedDialog": 16, "lavita/ChatDoctor-HealthCareMagic-100k": 14},
            summary["source_answer_counts"],
        )

    def test_reviewed_html_preloads_annotations_without_overwriting_user_edits(self) -> None:
        records = list(iter_jsonl(DEFAULT_RECORDS))
        payload = json.loads(DEFAULT_ANNOTATIONS.read_text(encoding="utf-8"))
        annotations = validate_annotations(records, payload)
        summary = summarize(records, payload, annotations, load_sources(DEFAULT_HIDDEN))

        html = render_reviewed_html(DEFAULT_BASE_HTML.read_text(encoding="utf-8"), annotations, summary)

        self.assertIn("原两数据源专家预审结果", html)
        self.assertIn("AI 辅助专家预审，不可替代论文人工标注", html)
        self.assertIn("const preloadedSaved =", html)
        self.assertIn("memcalib-calibration-expert-review-v1", html)
        self.assertIn("...preloadedSaved, ...JSON.parse", html)


if __name__ == "__main__":
    unittest.main()
