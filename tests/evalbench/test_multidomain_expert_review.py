from __future__ import annotations

import json
import unittest

from evaluation.common import iter_jsonl
from evaluation.scripts.finalize_multidomain_expert_review import (
    DEFAULT_ANNOTATIONS,
    DEFAULT_BASE_HTML,
    DEFAULT_RECORDS,
    render_reviewed_html,
    summarize,
    validate_annotations,
)


class MultidomainExpertReviewTest(unittest.TestCase):
    def test_locked_review_is_complete_and_matches_release_records(self) -> None:
        records = list(iter_jsonl(DEFAULT_RECORDS))
        payload = json.loads(DEFAULT_ANNOTATIONS.read_text(encoding="utf-8"))

        annotations = validate_annotations(records, payload)
        summary = summarize(records, payload, annotations)

        self.assertEqual(30, len(annotations))
        self.assertEqual(128, summary["atoms"])
        self.assertEqual({"accept": 4, "reject": 15, "revise": 11}, summary["decisions"])
        self.assertEqual({"invalid": 50, "revise": 2, "valid": 76}, summary["gold_quality"])

    def test_reviewed_html_preloads_annotations_without_overwriting_user_edits(self) -> None:
        records = list(iter_jsonl(DEFAULT_RECORDS))
        payload = json.loads(DEFAULT_ANNOTATIONS.read_text(encoding="utf-8"))
        annotations = validate_annotations(records, payload)
        summary = summarize(records, payload, annotations)

        html = render_reviewed_html(DEFAULT_BASE_HTML.read_text(encoding="utf-8"), annotations, summary)

        self.assertIn("多领域专家预审结果", html)
        self.assertIn("AI 辅助专家预审，不可替代论文人工标注", html)
        self.assertIn("const preloadedSaved =", html)
        self.assertIn("memcalib-multidomain-expert-review-v1", html)
        self.assertIn("...preloadedSaved, ...JSON.parse", html)


if __name__ == "__main__":
    unittest.main()
