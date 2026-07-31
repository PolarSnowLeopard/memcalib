from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location(
    "prefill_matching_results",
    ROOT / "evaluation" / "scripts" / "prefill_matching_results.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PrefillMatchingResultsTest(unittest.TestCase):
    def test_reuses_only_exact_request_fingerprint(self) -> None:
        request = {
            "request_id": "r1",
            "prompt": [{"role": "user", "content": "new"}],
        }
        result = {
            "request_id": "r1",
            "input_fingerprint": "wrong",
            "response": "answer",
            "raw_response": {
                "model": "model-a",
                "choices": [{"finish_reason": "stop"}],
            },
        }
        selected, summary = MODULE.select_matching(
            [request], [result], expected_model="model-a"
        )
        self.assertEqual([], selected)
        self.assertEqual(1, summary["pending"])


if __name__ == "__main__":
    unittest.main()
