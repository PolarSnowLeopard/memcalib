#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evaluation.common import request_fingerprint, write_jsonl
from evaluation.scripts.build_vllm_runtime_config import build_runtime_config
from evaluation.scripts.finalize_answer_run import summarize_result_rows, validation_model
from evaluation.scripts.prepare_answer_requests import (
    build_answer_messages,
    build_answer_request,
    config_for_single_model,
    prepare_answer_requests,
)
from evaluation.scripts.validate_api_results import validate_results


SYSTEM = "Use relevant memory and answer in English."


def sample() -> dict:
    return {
        "id": "sample-1",
        "panel": "representative",
        "question": "What should I do?",
        "memory_blocks": [
            {"parent_memory_id": "p1", "memory_text": "First memory."},
            {"parent_memory_id": "p2", "memory_text": "Second memory."},
        ],
        "memories": [{"atom_id": "hidden"}],
        "doctor_answer": "hidden answer",
    }


class AnswerRequestTest(unittest.TestCase):
    def test_runtime_config_discovers_custom_model_metadata(self) -> None:
        config = {
            "answer_models": [{"key": "default", "model": "default"}],
            "answer_generation": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            answers = Path(tmp) / "answers"
            model_dir = answers / "qwen3-8b-grpo"
            model_dir.mkdir(parents=True)
            (model_dir / "served-model-name.txt").write_text("med_chat\n", encoding="utf-8")
            (model_dir / "model-metadata.json").write_text(
                json.dumps(
                    {
                        "key": "qwen3-8b-grpo",
                        "model": "Qwen/Qwen3-8B-GRPO",
                        "display_name": "Qwen3-8B GRPO",
                        "answer_mode": "nonthinking",
                        "checkpoint_role": "grpo",
                    }
                ),
                encoding="utf-8",
            )

            runtime = build_runtime_config(config, answers)

        self.assertEqual(1, len(runtime["answer_models"]))
        self.assertEqual("qwen3-8b-grpo", runtime["answer_models"][0]["key"])
        self.assertEqual("med_chat", runtime["answer_models"][0]["served_model_name"])
        self.assertEqual("grpo", runtime["answer_models"][0]["checkpoint_role"])

    def test_runtime_config_keeps_legacy_unregistered_result_key(self) -> None:
        config = {
            "answer_models": [{"key": "qwen3-8b-official", "model": "official"}],
            "answer_generation": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            answers = Path(tmp) / "answers"
            model_dir = answers / "qwen3-8b-base-vllm"
            model_dir.mkdir(parents=True)
            (model_dir / "served-model-name.txt").write_text("med_chat\n", encoding="utf-8")

            runtime = build_runtime_config(config, answers)

        self.assertEqual("qwen3-8b-base-vllm", runtime["answer_models"][0]["key"])
        self.assertEqual("legacy_or_custom", runtime["answer_models"][0]["checkpoint_role"])

    def test_custom_model_key_replaces_hard_coded_model_list(self) -> None:
        config = {
            "answer_models": [{"key": "old", "model": "old"}],
            "answer_generation": {},
        }

        selected = config_for_single_model(
            config,
            model_key="qwen3-8b-grpo",
            display_name="Qwen3-8B GRPO",
            checkpoint_role="grpo",
        )

        self.assertEqual("old", config["answer_models"][0]["key"])
        self.assertEqual(
            [
                {
                    "key": "qwen3-8b-grpo",
                    "model": "qwen3-8b-grpo",
                    "display_name": "Qwen3-8B GRPO",
                    "answer_mode": "nonthinking",
                    "checkpoint_role": "grpo",
                }
            ],
            selected["answer_models"],
        )

    def test_custom_model_key_rejects_path_components(self) -> None:
        with self.assertRaises(ValueError):
            config_for_single_model(
                {"answer_models": [], "answer_generation": {}},
                model_key="../outside",
            )

    def test_leaderboard_mode_can_prepare_full_memory_only(self) -> None:
        samples = []
        for index in range(500):
            row = sample()
            row["id"] = f"sample-{index}"
            row["panel"] = "diagnostic" if index == 499 else "representative"
            samples.append(row)
        config = {"answer_models": [{"key": "m1", "model": "model-1"}], "answer_generation": {}}
        with tempfile.TemporaryDirectory() as tmp:
            manifest = prepare_answer_requests(
                samples,
                config,
                SYSTEM,
                Path(tmp),
                conditions=("full_memory",),
            )

            self.assertTrue((Path(tmp) / "m1" / "full_memory.jsonl").exists())
            self.assertFalse((Path(tmp) / "m1" / "no_memory.jsonl").exists())

        self.assertEqual(500, manifest["formal_requests"])
        self.assertEqual(["full_memory"], manifest["conditions"])

    def test_full_release_scale_is_not_hard_coded_to_500_samples(self) -> None:
        samples = []
        for index in range(3):
            row = sample()
            row["id"] = f"formal-{index}"
            row["panel"] = "formal"
            samples.append(row)
        config = {"answer_models": [{"key": "m1", "model": "model-1"}], "answer_generation": {}}
        with tempfile.TemporaryDirectory() as tmp:
            manifest = prepare_answer_requests(
                samples,
                config,
                SYSTEM,
                Path(tmp),
                conditions=("full_memory",),
            )

        self.assertEqual(3, manifest["samples"])
        self.assertEqual(3, manifest["formal_requests"])

    def test_result_summary_aggregates_models_finish_reasons_and_usage(self) -> None:
        rows = [
            {
                "response": "Answer",
                "raw_response": {
                    "model": "model-a",
                    "choices": [{"finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                },
            }
        ]

        summary = summarize_result_rows(rows)

        self.assertEqual({"model-a": 1}, summary["returned_models"])
        self.assertEqual({"stop": 1}, summary["finish_reasons"])
        self.assertEqual({"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}, summary["usage"])

    def test_runtime_served_name_does_not_replace_logical_model_name(self) -> None:
        model = {
            "key": "qwen3-8b-method",
            "model": "qwen3-8b-method",
            "served_model_name": "med_chat",
        }

        self.assertEqual("med_chat", validation_model(model))
        self.assertEqual("qwen3-8b-method", model["model"])

    def test_full_memory_preserves_parent_order(self) -> None:
        messages = build_answer_messages(sample(), "full_memory", SYSTEM)

        self.assertEqual("system", messages[0]["role"])
        user = messages[1]["content"]
        self.assertLess(user.index("[1] First memory."), user.index("[2] Second memory."))
        self.assertIn("CURRENT QUERY\nWhat should I do?", user)

    def test_no_memory_contains_no_memory_text_or_heading(self) -> None:
        messages = build_answer_messages(sample(), "no_memory", SYSTEM)
        serialized = json.dumps(messages)

        self.assertNotIn("First memory", serialized)
        self.assertNotIn("Second memory", serialized)
        self.assertNotIn("MEMORY", serialized)
        self.assertIn("What should I do?", serialized)

    def test_request_metadata_is_stable_and_prompt_has_no_hidden_fields(self) -> None:
        first = build_answer_request(sample(), "full_memory", "qwen-max", "qwen-model", SYSTEM)
        second = build_answer_request(sample(), "full_memory", "qwen-max", "qwen-model", SYSTEM)
        serialized = json.dumps(first)

        self.assertEqual(first, second)
        self.assertEqual("answer:qwen-max:full_memory:sample-1", first["request_id"])
        self.assertNotIn("hidden answer", serialized)
        self.assertNotIn("atom_id", serialized)

    def test_validator_accepts_complete_fingerprinted_results(self) -> None:
        request = build_answer_request(sample(), "full_memory", "qwen-max", "qwen-model", SYSTEM)
        result = {
            "request_id": request["request_id"],
            "input_fingerprint": request_fingerprint(request),
            "response": "A useful answer.",
            "raw_response": {
                "model": "qwen-model",
                "choices": [{"finish_reason": "stop"}],
            },
            "user_defined_params": request["user_defined_params"],
        }
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.jsonl"
            output_path = Path(tmp) / "output.jsonl"
            write_jsonl(input_path, [request])
            write_jsonl(output_path, [result])

            report = validate_results(input_path, output_path, "qwen-model")

        self.assertTrue(report["valid"])
        self.assertEqual(1, report["counts"]["valid"])

    def test_validator_rejects_duplicate_truncated_and_stale_results(self) -> None:
        request = build_answer_request(sample(), "full_memory", "qwen-max", "qwen-model", SYSTEM)
        bad = {
            "request_id": request["request_id"],
            "input_fingerprint": "stale",
            "response": "Partial",
            "raw_response": {
                "model": "wrong-model",
                "choices": [{"finish_reason": "length"}],
            },
            "user_defined_params": request["user_defined_params"],
        }
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.jsonl"
            output_path = Path(tmp) / "output.jsonl"
            write_jsonl(input_path, [request])
            write_jsonl(output_path, [bad, bad])

            report = validate_results(input_path, output_path, "qwen-model")

        self.assertFalse(report["valid"])
        self.assertEqual(1, report["counts"]["duplicate_ids"])
        self.assertIn("input_fingerprint_mismatch", report["errors"])
        self.assertIn("finish_reason_length", report["errors"])
        self.assertIn("model_mismatch", report["errors"])


if __name__ == "__main__":
    unittest.main()
