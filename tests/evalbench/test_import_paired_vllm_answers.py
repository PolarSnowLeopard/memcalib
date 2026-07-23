#!/usr/bin/env python3
from __future__ import annotations

import unittest

from evaluation.common import request_fingerprint
from evaluation.scripts.import_paired_vllm_answers import validate_model_answers


def request(sample_id: str) -> dict:
    return {
        "request_id": f"answer:model:full_memory:{sample_id}",
        "prompt": [{"role": "user", "content": sample_id}],
        "user_defined_params": {"sample_id": sample_id},
    }


def answer(source: dict, *, model: str, response: str = "Answer") -> dict:
    return {
        "request_id": source["request_id"],
        "input_fingerprint": request_fingerprint(source),
        "response": response,
        "raw_response": {
            "model": model,
            "choices": [{"finish_reason": "stop", "message": {"content": response}}],
        },
        "user_defined_params": source["user_defined_params"],
    }


class ImportPairedVllmAnswersTest(unittest.TestCase):
    def test_accepts_complete_nonthinking_rows(self) -> None:
        requests = [request("s1"), request("s2")]
        answers = [answer(row, model="served") for row in requests]

        by_sample, summary = validate_model_answers(requests, answers, "served")

        self.assertEqual({"s1", "s2"}, set(by_sample))
        self.assertEqual(2, summary["answer_rows"])
        self.assertEqual(0, summary["reasoning_trace_rows"])

    def test_rejects_reasoning_or_stale_fingerprint(self) -> None:
        source = request("s1")
        result = answer(source, model="served", response="<think>hidden</think>Answer")
        result["input_fingerprint"] = "stale"

        with self.assertRaisesRegex(
            ValueError, "input_fingerprint_mismatch.*reasoning_trace_present"
        ):
            validate_model_answers([source], [result], "served")


if __name__ == "__main__":
    unittest.main()
