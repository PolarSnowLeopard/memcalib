#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent / "06_run_bailian_api.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("bailian_runner", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BailianRunnerProgressTest(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = load_runner()

    def test_should_report_progress_respects_interval_and_final_row(self) -> None:
        self.assertFalse(self.runner.should_report_progress(1, 10, 5))
        self.assertTrue(self.runner.should_report_progress(5, 10, 5))
        self.assertTrue(self.runner.should_report_progress(10, 10, 5))
        self.assertTrue(self.runner.should_report_progress(3, 3, 50))
        self.assertFalse(self.runner.should_report_progress(1, 10, 0))

    def test_progress_payload_includes_live_counts(self) -> None:
        payload = self.runner.progress_payload(
            done=7,
            total=20,
            ok_count=5,
            fail_count=2,
            started=100.0,
            now=130.0,
        )

        self.assertEqual(7, payload["done"])
        self.assertEqual(20, payload["total"])
        self.assertEqual(5, payload["ok"])
        self.assertEqual(2, payload["failed"])
        self.assertEqual(13, payload["remaining"])
        self.assertEqual(30, payload["elapsed_s"])
        self.assertEqual(14.0, payload["rpm_actual"])


if __name__ == "__main__":
    unittest.main()
