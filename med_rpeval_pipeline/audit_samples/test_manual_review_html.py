#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


AUDIT_DIR = Path(__file__).resolve().parent
SAMPLES_JSONL = AUDIT_DIR / "manual_quality_review_samples.jsonl"
BUILDER = AUDIT_DIR / "build_manual_review_html.py"


class ManualReviewHtmlTest(unittest.TestCase):
    def test_builder_creates_self_contained_review_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "review.html"
            subprocess.run(
                [
                    sys.executable,
                    str(BUILDER),
                    "--input",
                    str(SAMPLES_JSONL),
                    "--output",
                    str(output),
                ],
                check=True,
                cwd=AUDIT_DIR,
            )

            html = output.read_text(encoding="utf-8")
            expected_count = sum(1 for line in SAMPLES_JSONL.read_text(encoding="utf-8").splitlines() if line.strip())

            self.assertIn("<title>Medical RPEval Manual Review</title>", html)
            self.assertIn("window.REVIEW_SAMPLES =", html)
            self.assertIn("localStorage", html)
            self.assertIn("exportJson", html)
            self.assertIn("exportCsv", html)
            self.assertIn('data-review-value="pass"', html)
            self.assertIn('data-review-value="minor_fix"', html)
            self.assertIn('data-review-value="major_fix"', html)
            self.assertIn('data-review-value="drop"', html)
            self.assertIn("Generated question / 构造后问题", html)
            self.assertIn("Original raw question / 原始问题", html)
            self.assertIn("Metadata", html)
            self.assertIn("Full verifier audit", html)
            self.assertIn("source_raw_id", html)
            self.assertIn("source_split", html)
            self.assertIn("source_index", html)
            self.assertIn("corrected_u_star", html)
            self.assertIn("audit_reason", html)

            match = re.search(r"window\.REVIEW_SAMPLES = (\[.*?\]);\n", html, re.S)
            self.assertIsNotNone(match)
            embedded = json.loads(match.group(1))
            self.assertEqual(expected_count, len(embedded))
            self.assertEqual("QR-0001", embedded[0]["review_id"])


if __name__ == "__main__":
    unittest.main()
