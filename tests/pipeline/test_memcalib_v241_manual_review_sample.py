from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PIPELINE_DIR = Path(__file__).resolve().parents[2] / "pipeline"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ManualReviewSampleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_script(
            PIPELINE_DIR / "125_build_memcalib_v241_manual_review_sample.py",
            "build_memcalib_v241_manual_review_sample_test",
        )

    def test_targets_total_thirty(self) -> None:
        self.assertEqual(30, sum(self.module.TARGETS.values()))
        self.assertEqual(9, self.module.TARGETS["manual_finalization"])

    def test_diverse_select_prefers_channel_coverage(self) -> None:
        rows = [
            {"id": "a1", "repair_channel": "a"},
            {"id": "a2", "repair_channel": "a"},
            {"id": "b1", "repair_channel": "b"},
        ]
        selected = self.module.diverse_select(rows, 2)
        self.assertEqual({"a", "b"}, {row["repair_channel"] for row in selected})


if __name__ == "__main__":
    unittest.main()
