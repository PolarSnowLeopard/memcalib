from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "prepare_memcalib_v241_qc_retry",
    ROOT / "pipeline" / "112_prepare_memcalib_v241_qc_retry.py",
)
assert SPEC and SPEC.loader
RETRY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RETRY)


class MemCalibV241QcRetryTest(unittest.TestCase):
    def test_retry_preserves_request_and_requires_exact_atom_coverage(self) -> None:
        original = {
            "request_id": "original:r1",
            "prompt": [{"role": "user", "content": "Audit this record."}],
            "user_defined_params": {
                "record_id": "r1",
                "expected_atom_ids": ["a1", "a2"],
                "record_fingerprint": "record-fingerprint",
            },
        }
        invalid = {
            "request_id": "original:r1",
            "record_id": "r1",
            "errors": ["atom_checks_coverage_mismatch"],
        }
        retry = RETRY.build_retry_request(original, invalid, 1)
        self.assertEqual("v241_semantic_qc_retry1:r1", retry["request_id"])
        self.assertIn(
            '["a1", "a2"]',
            retry["prompt"][0]["content"],
        )
        self.assertIn(
            "Do not split one atom into separate objects",
            retry["prompt"][0]["content"],
        )
        self.assertEqual(
            "record-fingerprint",
            retry["user_defined_params"]["record_fingerprint"],
        )
        self.assertEqual(
            "original:r1",
            retry["user_defined_params"]["qc_retry"]["prior_request_id"],
        )


if __name__ == "__main__":
    unittest.main()
