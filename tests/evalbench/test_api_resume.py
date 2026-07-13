from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evaluation.common import request_fingerprint
from evaluation.scripts.merge_api_results import merge_api_rows
from evaluation.scripts.prepare_missing_api_requests import missing_requests
from evaluation.scripts.resolve_api_results import resolve_rows


class ApiResumeTest(unittest.TestCase):
    def test_merge_api_rows_requires_disjoint_complete_results(self) -> None:
        rows = merge_api_rows([[{"request_id": "b"}], [{"request_id": "a"}]], expected=2)

        self.assertEqual(["a", "b"], [row["request_id"] for row in rows])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            merge_api_rows([[{"request_id": "a"}], [{"request_id": "a"}]], expected=1)
        with self.assertRaisesRegex(ValueError, "mismatch"):
            merge_api_rows([[{"request_id": "a"}]], expected=2)

    def test_resolve_rows_replaces_truncated_main_result_with_retry(self) -> None:
        request = {"request_id": "a", "prompt": [{"role": "user", "content": "hello"}]}
        fingerprint = request_fingerprint(request)
        truncated = {
            "request_id": "a",
            "input_fingerprint": fingerprint,
            "response": "partial",
            "raw_response": {"model": "model-a", "choices": [{"finish_reason": "length"}]},
        }
        retry = {
            "request_id": "a",
            "input_fingerprint": fingerprint,
            "response": "complete",
            "raw_response": {"model": "model-a", "choices": [{"finish_reason": "stop"}]},
        }

        rows, summary = resolve_rows([request], [[truncated], [retry]], expected_model="model-a")

        self.assertEqual("complete", rows[0]["response"])
        self.assertEqual({"1": 1}, summary["selected_result_group_counts"])
        self.assertEqual({"truncated": 1}, summary["discarded_invalid_counts"])

    def test_missing_requests_accepts_multiple_result_files(self) -> None:
        requests = [
            {"request_id": "a", "prompt": [{"role": "user", "content": "a"}]},
            {"request_id": "b", "prompt": [{"role": "user", "content": "b"}]},
        ]

        def result(request: dict) -> dict:
            return {
                "request_id": request["request_id"],
                "input_fingerprint": request_fingerprint(request),
                "response": "complete",
                "raw_response": {"choices": [{"finish_reason": "stop"}]},
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request_path = root / "requests.jsonl"
            first_path = root / "first.jsonl"
            second_path = root / "second.jsonl"
            request_path.write_text("".join(json.dumps(row) + "\n" for row in requests), encoding="utf-8")
            first_path.write_text(json.dumps(result(requests[0])) + "\n", encoding="utf-8")
            second_path.write_text(json.dumps(result(requests[1])) + "\n", encoding="utf-8")

            missing = missing_requests(request_path, [first_path, second_path])

        self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main()
