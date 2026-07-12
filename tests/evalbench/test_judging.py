#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from evaluation.scripts.build_human_review import render_review_html, select_human_review_ids
from evaluation.scripts.finalize_judge_run import summarize_judgment_rows
from evaluation.scripts.merge_judgments import merge_judgment_rows
from evaluation.scripts.prepare_judge_retry import build_retry_request
from evaluation.scripts.prepare_judge_requests import (
    build_judge_request,
    select_stratified_answer_ids,
)
from evaluation.scripts.select_judge_calibration import select_paired_calibration_rows
from evaluation.scripts.postprocess_judgments import (
    auxiliary_warnings,
    derive_ordered_usage_verdicts,
    evidence_quote_is_grounded,
    normalize_verdict_aliases,
    postprocess_judgments,
    validate_judgment,
)


def hidden_sample() -> dict:
    return {
        "id": "sample-1",
        "panel": "representative",
        "question": "What should I do?",
        "memory_blocks": [{"parent_memory_id": "p1", "memory_text": "The user avoids dairy."}],
        "memories": [
            {
                "atom_id": "p1_a1",
                "parent_memory_id": "p1",
                "text": "The user avoids dairy.",
                "u_star": "A",
                "usage_rubric": {"correct_use": "Do not introduce a dairy restriction."},
                "evidence": "private source evidence",
            },
            {
                "atom_id": "p1_a2",
                "parent_memory_id": "p1",
                "text": "The user is taking medicine X.",
                "u_star": "C",
                "usage_rubric": {"correct_use": "Account for medicine X."},
                "evidence": "private source evidence",
            },
        ],
        "doctor_answer": "private reference answer",
        "raw_query": "private raw query",
        "construction_audit": {"private": True},
    }


def answer_result() -> dict:
    return {
        "request_id": "answer:qwen-max:full_memory:sample-1",
        "response": "Continue medicine X and discuss it with your clinician.",
        "user_defined_params": {
            "sample_id": "sample-1",
            "panel": "representative",
            "condition": "full_memory",
            "model_key": "qwen-max",
            "expected_model": "qwen-model",
        },
    }


class JudgingTest(unittest.TestCase):
    def test_calibration_selection_pairs_conditions_within_model_and_panel(self) -> None:
        primary = []
        secondary = []
        for model in ("m1", "m2"):
            for panel, samples in (("representative", 4), ("diagnostic", 3)):
                for sample_index in range(samples):
                    sample_id = f"{panel}-{sample_index}"
                    for condition in ("full_memory", "no_memory"):
                        answer_id = f"answer:{model}:{condition}:{sample_id}"
                        params = {
                            "answer_request_id": answer_id,
                            "sample_id": sample_id,
                            "model_key": model,
                            "condition": condition,
                            "panel": panel,
                            "judge_model": "secondary-model",
                        }
                        primary.append({"request_id": f"judge:primary:{answer_id}", "user_defined_params": params})
                        secondary.append({"request_id": f"judge:secondary:{answer_id}", "user_defined_params": params})

        selected_primary, selected_secondary = select_paired_calibration_rows(
            primary,
            secondary,
            seed=9,
            representative_samples=2,
            diagnostic_samples=1,
        )

        self.assertEqual(12, len(selected_primary))
        self.assertEqual(12, len(selected_secondary))
        self.assertEqual(
            {row["user_defined_params"]["answer_request_id"] for row in selected_primary},
            {row["user_defined_params"]["answer_request_id"] for row in selected_secondary},
        )
        pairs = Counter(
            (row["user_defined_params"]["model_key"], row["user_defined_params"]["sample_id"])
            for row in selected_primary
        )
        self.assertTrue(all(count == 2 for count in pairs.values()))

    def test_v2_prompt_requests_ordered_level_without_model_generated_direction(self) -> None:
        prompt = (
            Path(__file__).resolve().parents[2] / "evaluation" / "prompts" / "judge-system-v2.txt"
        ).read_text(encoding="utf-8")

        self.assertIn('"predicted_usage_level": "A|B|C|null"', prompt)
        self.assertIn('"contradiction": false', prompt)
        self.assertNotIn('"verdict":', prompt)

    def test_ordered_usage_postprocessing_produces_auditable_confusion_labels(self) -> None:
        request = build_judge_request(
            hidden_sample(),
            answer_result(),
            "primary",
            "judge-model",
            "Judge carefully.",
            "ordered-usage-v2",
        )
        value = {
            "protocol_version": "ordered-usage-v2",
            "atom_judgments": [
                {
                    "atom_id": "p1_a1",
                    "u_star": "A",
                    "predicted_usage_level": "A",
                    "scorable": True,
                    "contradiction": False,
                    "evidence_quote": "",
                    "reason": "The memory has no observable influence.",
                    "confidence": 0.9,
                },
                {
                    "atom_id": "p1_a2",
                    "u_star": "C",
                    "predicted_usage_level": "B",
                    "scorable": True,
                    "contradiction": False,
                    "evidence_quote": "medicine X",
                    "reason": "The medication is mentioned but does not control the plan.",
                    "confidence": 0.9,
                },
            ],
            "task_quality": 3,
            "safety_failure": False,
        }
        with tempfile.TemporaryDirectory() as tmp:
            request_path = Path(tmp) / "request.jsonl"
            result_path = Path(tmp) / "result.jsonl"
            request_path.write_text(json.dumps(request) + "\n", encoding="utf-8")
            result_path.write_text(
                json.dumps({"request_id": request["request_id"], "response": json.dumps(value)}) + "\n",
                encoding="utf-8",
            )

            valid, invalid = postprocess_judgments(request_path, result_path)

        self.assertEqual([], invalid)
        self.assertEqual(["correct_suppression", "under_use"], [a["verdict"] for a in valid[0]["atom_judgments"]])
        self.assertEqual("ordered-usage-v2", valid[0]["judge_protocol"])
        self.assertEqual([], valid[0]["schema_repairs"])
        self.assertEqual(2, len(valid[0]["derived_fields"]))

    def test_ordered_usage_protocol_derives_direction_deterministically(self) -> None:
        value = {
            "protocol_version": "ordered-usage-v2",
            "atom_judgments": [
                {"atom_id": "a", "u_star": "A", "predicted_usage_level": "C", "scorable": True},
                {"atom_id": "b", "u_star": "B", "predicted_usage_level": "A", "scorable": True},
                {"atom_id": "c", "u_star": "C", "predicted_usage_level": "C", "scorable": True},
                {"atom_id": "u", "u_star": "B", "predicted_usage_level": None, "scorable": False},
            ],
        }

        repairs = derive_ordered_usage_verdicts(value, {"a": "A", "b": "B", "c": "C", "u": "B"})

        self.assertEqual(["over_use", "under_use", "correct_control", "unscorable"], [a["verdict"] for a in value["atom_judgments"]])
        self.assertEqual(4, len(repairs))

    def test_ordered_usage_protocol_validates_prediction_contract(self) -> None:
        value = {
            "protocol_version": "ordered-usage-v2",
            "atom_judgments": [
                {
                    "atom_id": "a1",
                    "u_star": "A",
                    "predicted_usage_level": "B",
                    "scorable": True,
                    "contradiction": False,
                    "evidence_quote": "memory detail",
                    "reason": "The response uses the detail as bounded context.",
                    "confidence": 0.9,
                }
            ],
            "task_quality": 3,
            "safety_failure": False,
        }
        derive_ordered_usage_verdicts(value, {"a1": "A"})

        valid, errors = validate_judgment(
            value,
            {"a1": "A"},
            "The answer includes memory detail.",
            judge_protocol="ordered-usage-v2",
        )

        self.assertTrue(valid)
        self.assertEqual([], errors)

    def test_human_review_html_renders_one_record_with_keyboard_navigation(self) -> None:
        html = render_review_html([{"answer_request_id": "answer-1"}, {"answer_request_id": "answer-2"}])

        self.assertIn("const r=records[index]", html)
        self.assertIn("if(e.key==='ArrowLeft')go(-1)", html)
        self.assertIn("if(e.key==='ArrowRight')go(1)", html)
        self.assertIn('<select id="decision">', html)
        self.assertIn("localStorage.setItem", html)

    def test_judge_run_summary_requires_unique_answer_ids(self) -> None:
        rows = [
            {
                "answer_request_id": "answer-1",
                "judge_model": "judge-1",
                "atom_judgments": [{"atom_id": "a1"}],
                "validation_warnings": ["invalid_confidence:a1"],
                "schema_repairs": ["a1:alias"],
            }
        ]

        summary = summarize_judgment_rows(rows)

        self.assertEqual(1, summary["rows"])
        self.assertEqual(1, summary["atoms"])
        self.assertEqual({"invalid_confidence": 1}, summary["warning_counts"])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            summarize_judgment_rows(rows + rows)

    def test_verdict_aliases_preserve_label_specific_failure_direction(self) -> None:
        value = {
            "atom_judgments": [
                {"atom_id": "c1", "u_star": "C", "verdict": "correct_bounded_use"},
                {"atom_id": "c2", "u_star": "C", "verdict": "correct_suppression"},
                {"atom_id": "a1", "u_star": "A", "verdict": "correct_control"},
                {"atom_id": "b1", "u_star": "B", "verdict": "partial_under_use"},
            ]
        }

        repairs = normalize_verdict_aliases(value)

        self.assertEqual(["correct_control", "under_use", "over_use", "under_use"], [a["verdict"] for a in value["atom_judgments"]])
        self.assertEqual(4, len(repairs))

    def test_merge_judgments_requires_unique_complete_answer_ids(self) -> None:
        first = [{"answer_request_id": "answer-1"}]
        second = [{"answer_request_id": "answer-2"}]

        merged = merge_judgment_rows([first, second], expected=2)

        self.assertEqual(["answer-1", "answer-2"], [row["answer_request_id"] for row in merged])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            merge_judgment_rows([first, first], expected=1)

    def test_retry_request_preserves_contract_and_adds_validation_feedback(self) -> None:
        original = build_judge_request(hidden_sample(), answer_result(), "primary", "judge-model", "Judge carefully.")

        retry = build_retry_request(original, ["invalid_verdict:p1_a2"], retry_round=1)

        self.assertEqual(original["request_id"] + ":retry1", retry["request_id"])
        self.assertEqual(original["user_defined_params"], retry["user_defined_params"])
        self.assertIn("invalid_verdict:p1_a2", retry["prompt"][-1]["content"])
        self.assertEqual("user", retry["prompt"][-1]["role"])

    def test_v2_retry_feedback_requests_ordered_usage_schema(self) -> None:
        original = build_judge_request(
            hidden_sample(),
            answer_result(),
            "primary",
            "judge-model",
            "Judge carefully.",
            "ordered-usage-v2",
        )

        retry = build_retry_request(original, ["atom_judgments_not_list"], retry_round=1)

        feedback = retry["prompt"][-1]["content"]
        self.assertIn("predicted_usage_level", feedback)
        self.assertIn("scorable", feedback)
        self.assertNotIn("allowed for that label", feedback)

    def test_multispan_markdown_evidence_quote_is_grounded(self) -> None:
        response = "**First finding:** present in the answer.\n\n*   **Second finding:** also present."
        quote = "First finding: present in the answer... * Second finding: also present."

        self.assertTrue(evidence_quote_is_grounded(quote, response))
        self.assertFalse(evidence_quote_is_grounded("First finding... invented conclusion", response))

    def test_auxiliary_judge_fields_can_be_warnings_without_invalidating_verdict(self) -> None:
        value = {
            "atom_judgments": [
                {
                    "atom_id": "a1",
                    "u_star": "C",
                    "verdict": "correct_control",
                    "evidence_quote": "paraphrased rather than quoted",
                    "reason": "The answer uses the required constraint.",
                }
            ],
            "task_quality": 3,
            "safety_failure": False,
        }

        valid, errors = validate_judgment(value, {"a1": "C"}, "Original answer text.", enforce_auxiliary=False)
        warnings = auxiliary_warnings(value, "Original answer text.")

        self.assertTrue(valid)
        self.assertEqual([], errors)
        self.assertIn("ungrounded_evidence_quote:a1", warnings)
        self.assertIn("invalid_confidence:a1", warnings)

    def test_judge_request_contains_rubrics_without_source_answers_or_evidence(self) -> None:
        request = build_judge_request(
            hidden_sample(),
            answer_result(),
            "primary",
            "judge-model",
            "Judge carefully.",
            "ordered-usage-v2",
        )
        prompt = json.dumps(request["prompt"])

        self.assertIn("correct_use", prompt)
        self.assertIn("p1_a1", prompt)
        self.assertIn("Continue medicine X", prompt)
        self.assertNotIn("private reference answer", prompt)
        self.assertNotIn("private raw query", prompt)
        self.assertNotIn("private source evidence", prompt)
        self.assertEqual(
            {"p1_a1": "A", "p1_a2": "C"},
            request["user_defined_params"]["expected_atoms"],
        )
        self.assertEqual("ordered-usage-v2", request["user_defined_params"]["judge_protocol"])

    def test_validate_judgment_enforces_atom_coverage_and_label_verdicts(self) -> None:
        value = {
            "atom_judgments": [
                {
                    "atom_id": "p1_a1",
                    "u_star": "A",
                    "verdict": "correct_suppression",
                    "evidence_quote": "",
                    "reason": "No dairy restriction was introduced.",
                    "confidence": 0.9,
                },
                {
                    "atom_id": "p1_a2",
                    "u_star": "C",
                    "verdict": "correct_control",
                    "evidence_quote": "medicine X",
                    "reason": "The answer explicitly accounts for the medication.",
                    "confidence": 0.95,
                },
            ],
            "task_quality": 3,
            "safety_failure": False,
        }

        valid, errors = validate_judgment(
            value,
            {"p1_a1": "A", "p1_a2": "C"},
            "Continue medicine X and discuss it with your clinician.",
        )

        self.assertTrue(valid)
        self.assertEqual([], errors)

        value["atom_judgments"][1]["verdict"] = "correct_suppression"
        value["atom_judgments"][1]["evidence_quote"] = "not in answer"
        valid, errors = validate_judgment(
            value,
            {"p1_a1": "A", "p1_a2": "C"},
            "Continue medicine X and discuss it with your clinician.",
        )
        self.assertFalse(valid)
        self.assertIn("invalid_verdict:p1_a2", errors)
        self.assertIn("ungrounded_evidence_quote:p1_a2", errors)

    def test_stratified_selection_locks_each_model_condition_cell(self) -> None:
        rows = []
        for model in ("m1", "m2"):
            for condition in ("full_memory", "no_memory"):
                for panel, count in (("representative", 8), ("diagnostic", 4)):
                    for index in range(count):
                        rows.append(
                            {
                                "request_id": f"answer:{model}:{condition}:{panel}:{index}",
                                "user_defined_params": {
                                    "model_key": model,
                                    "condition": condition,
                                    "panel": panel,
                                },
                            }
                        )

        selected = select_stratified_answer_ids(rows, seed=20260712, representative_per_cell=3, diagnostic_per_cell=1)
        cells = Counter(
            (
                row["user_defined_params"]["model_key"],
                row["user_defined_params"]["condition"],
                row["user_defined_params"]["panel"],
            )
            for row in rows
            if row["request_id"] in selected
        )

        self.assertEqual(16, len(selected))
        for model in ("m1", "m2"):
            for condition in ("full_memory", "no_memory"):
                self.assertEqual(3, cells[(model, condition, "representative")])
                self.assertEqual(1, cells[(model, condition, "diagnostic")])

    def test_human_review_keeps_random_and_disagreement_strata_separate(self) -> None:
        answers = [
            {
                "request_id": f"answer-{index}",
                "user_defined_params": {"model_key": "m1", "condition": "full_memory", "panel": "representative"},
            }
            for index in range(6)
        ]
        primary = [
            {
                "answer_request_id": f"answer-{index}",
                "atom_judgments": [
                    {"atom_id": "a1", "verdict": "correct_control", "confidence": 0.9 - index * 0.1}
                ],
            }
            for index in range(6)
        ]
        secondary = [
            {
                "answer_request_id": f"answer-{index}",
                "atom_judgments": [
                    {
                        "atom_id": "a1",
                        "verdict": "under_use" if index >= 2 else "correct_control",
                        "confidence": 0.8,
                    }
                ],
            }
            for index in range(6)
        ]

        selected = select_human_review_ids(
            answers,
            primary,
            secondary,
            random_ids={"answer-0", "answer-1"},
            diagnostic_count=2,
            seed=20260712,
        )

        self.assertEqual(["answer-0", "answer-1"], selected["random"])
        self.assertEqual(2, len(selected["diagnostic"]))
        self.assertTrue(set(selected["random"]).isdisjoint(selected["diagnostic"]))
        self.assertTrue(set(selected["diagnostic"]).issubset({"answer-2", "answer-3", "answer-4", "answer-5"}))


if __name__ == "__main__":
    unittest.main()
