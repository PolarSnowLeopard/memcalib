#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from http.client import RemoteDisconnected
from pathlib import Path
from types import SimpleNamespace


SCRIPT = Path(__file__).resolve().parents[2] / "pipeline" / "06_run_bailian_api.py"
CONFIG = Path(__file__).resolve().parents[2] / "pipeline" / "config.json"


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

    def test_project_config_defaults_to_300_second_timeout(self) -> None:
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))

        self.assertEqual(300, cfg["api"]["timeout"])

    def test_parse_extra_body_requires_json_object(self) -> None:
        self.assertEqual(
            {"enable_thinking": False},
            self.runner.parse_extra_body('{"enable_thinking": false}'),
        )
        self.assertEqual({}, self.runner.parse_extra_body(""))

        with self.assertRaisesRegex(ValueError, "JSON object"):
            self.runner.parse_extra_body("[]")

    def test_extra_body_cannot_override_core_request_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "reserved fields"):
            self.runner.validate_extra_body({"model": "other-model"})

    def test_resume_rejects_output_when_input_fingerprint_changes(self) -> None:
        current_input = {
            "request_id": "r1",
            "prompt": [{"role": "user", "content": "new prompt"}],
            "user_defined_params": {"id": "raw1"},
        }

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out.jsonl"
            invalid = Path(tmp) / "invalid.jsonl"
            output.write_text(
                json.dumps(
                    {
                        "request_id": "r1",
                        "input_fingerprint": "old-fingerprint",
                        "response": "{}",
                        "raw_response": {"choices": [{"finish_reason": "stop"}]},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            expected = {"r1": self.runner.request_fingerprint(current_input)}
            report = self.runner.repair_output_for_resume(output, invalid, expected_fingerprints=expected)

            self.assertEqual({"valid": 0, "invalid": 1, "invalid_reasons": {"input_fingerprint_mismatch": 1}}, report)
            self.assertEqual(set(), self.runner.load_done_ids(output, expected_fingerprints=expected))
            invalid_row = json.loads(invalid.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual("input_fingerprint_mismatch", invalid_row["_invalid_reason"])

    def test_run_one_records_input_fingerprint(self) -> None:
        row = {
            "request_id": "r1",
            "prompt": [{"role": "user", "content": "hello"}],
            "user_defined_params": {"id": "raw1"},
        }
        args = SimpleNamespace(
            base_url="https://example.invalid",
            model="test-model",
            temperature=0.0,
            max_tokens=32,
            timeout=1,
            max_retries=0,
            retry_base_sleep=0.0,
            retry_max_sleep=0.0,
        )

        original_call = self.runner.call_chat_completions
        self.runner.call_chat_completions = lambda **_: {
            "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]
        }
        try:
            result = self.runner.run_one(row, args, "fake-key", self.runner.RateLimiter(0))
        finally:
            self.runner.call_chat_completions = original_call

        self.assertTrue(result["ok"])
        self.assertEqual(self.runner.request_fingerprint(row), result["input_fingerprint"])

    def test_run_one_retries_remote_disconnect(self) -> None:
        row = {
            "request_id": "r1",
            "prompt": [{"role": "user", "content": "hello"}],
            "user_defined_params": {"id": "raw1"},
        }
        args = SimpleNamespace(
            base_url="https://example.invalid",
            model="test-model",
            temperature=0.0,
            max_tokens=32,
            timeout=1,
            max_retries=1,
            retry_base_sleep=0.0,
            retry_max_sleep=0.0,
        )
        calls = 0

        def disconnect_once(**_):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RemoteDisconnected("remote closed connection")
            return {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}

        original_call = self.runner.call_chat_completions
        self.runner.call_chat_completions = disconnect_once
        try:
            result = self.runner.run_one(row, args, "fake-key", self.runner.RateLimiter(0))
        finally:
            self.runner.call_chat_completions = original_call

        self.assertTrue(result["ok"])
        self.assertEqual(2, calls)

    def test_hard_timeout_is_reported_as_retryable(self) -> None:
        original_run = self.runner.subprocess.run

        def raise_timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

        self.runner.subprocess.run = raise_timeout
        try:
            with self.assertRaises(self.runner.ProviderCallError) as raised:
                self.runner.call_chat_completions_with_hard_timeout(
                    base_url="https://example.invalid",
                    api_key="fake-key",
                    model="test-model",
                    messages=[{"role": "user", "content": "hello"}],
                    temperature=0.0,
                    max_tokens=32,
                    timeout=300,
                    hard_timeout=1,
                )
        finally:
            self.runner.subprocess.run = original_run

        self.assertTrue(raised.exception.retryable)
        self.assertIn("exceeded 1s", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
