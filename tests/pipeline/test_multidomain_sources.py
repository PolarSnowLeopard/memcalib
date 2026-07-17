#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


PIPELINE_DIR = Path(__file__).resolve().parents[2] / "pipeline"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))


def load_script(name: str, filename: str):
    path = PIPELINE_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class MultidomainSourcesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.normalizer = load_script("normalize_domain_sources", "25_normalize_domain_sources.py")
        cls.selector = load_script("multidomain_raw_selector", "15_select_crk2_raw_seeds.py")
        cls.semantic = load_script("multidomain_semantic_prepare", "18_prepare_source_semantic_qc.py")
        cls.semantic_retry = load_script("multidomain_semantic_retry", "22_prepare_source_semantic_qc_retry.py")
        cls.semantic_merge = load_script("multidomain_semantic_merge", "26_merge_source_semantic_qc.py")
        cls.generation = load_script("multidomain_generation_prepare", "10_prepare_crk2_generation.py")
        cls.generation_post = load_script("multidomain_generation_post", "11_post_crk2_generation.py")
        cls.generation_repair = load_script("multidomain_generation_repair", "27_prepare_crk2_generation_repair.py")
        cls.attribution = load_script(
            "stack_exchange_attribution",
            "42_enrich_stack_exchange_attribution.py",
        )

    @staticmethod
    def selection_config() -> dict:
        return {
            "schema_version": "test",
            "scoring_version": "test",
            "min_question_chars": 20,
            "max_question_chars": 6000,
            "min_answer_chars": 30,
            "max_answer_chars": 10000,
            "min_question_tokens": 5,
            "min_answer_tokens": 5,
            "min_english_letter_ratio": 0.75,
            "max_boilerplate_ratio": 0.65,
            "min_quality_score": 60,
            "near_duplicate_jaccard": 0.88,
            "topic_alpha": 0.5,
            "quality_weight_beta": 2.0,
            "complexity_targets": {"simple": 0.25, "medium": 0.5, "complex": 0.25},
        }

    def test_normalize_oasst1_builds_general_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "train.parquet"
            pd.DataFrame(
                [
                    {
                        "message_id": "u1",
                        "parent_id": None,
                        "message_tree_id": "tree1",
                        "text": "I am planning a low-cost weekend trip and prefer quiet places. Can you suggest an itinerary?",
                        "role": "prompter",
                        "lang": "en",
                        "deleted": False,
                        "review_result": True,
                    },
                    {
                        "message_id": "a1",
                        "parent_id": "u1",
                        "message_tree_id": "tree1",
                        "text": "Choose a nearby destination and divide the weekend into travel, walking, and rest periods.",
                        "role": "assistant",
                        "lang": "en",
                        "deleted": False,
                        "review_result": True,
                    },
                ]
            ).to_parquet(path, index=False)

            records = list(self.normalizer.normalize_oasst1(path))

        self.assertEqual(1, len(records))
        self.assertEqual("general", records[0]["domain"])
        self.assertEqual("OpenAssistant/oasst1", records[0]["source_dataset"])
        self.assertEqual("Apache-2.0", records[0]["source_license"])
        self.assertEqual(records[0]["source_answer"], records[0]["doctor_answer"])

    def test_normalize_oasst2_uses_distinct_source_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "train.parquet"
            pd.DataFrame(
                [
                    {
                        "message_id": "u1",
                        "parent_id": None,
                        "message_tree_id": "tree1",
                        "text": "I work nights and prefer quiet exercise. Can you suggest a weekly routine?",
                        "role": "prompter",
                        "lang": "en",
                        "deleted": False,
                        "review_result": True,
                    },
                    {
                        "message_id": "a1",
                        "parent_id": "u1",
                        "message_tree_id": "tree1",
                        "text": "Use short sessions after waking and reserve longer low-noise workouts for days off.",
                        "role": "assistant",
                        "lang": "en",
                        "deleted": False,
                        "review_result": True,
                    },
                ]
            ).to_parquet(path, index=False)

            records = list(self.normalizer.normalize_oasst2(path))

        self.assertEqual(1, len(records))
        self.assertEqual("OpenAssistant/oasst2", records[0]["source_dataset"])
        self.assertEqual("Apache-2.0", records[0]["source_license"])

    def test_normalize_ultrachat_emits_each_assistant_turn_with_prior_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "train_sft.parquet"
            pd.DataFrame(
                [
                    {
                        "prompt_id": "p1",
                        "prompt": "I prefer quiet trips. Can you suggest a destination?",
                        "messages": [
                            {"role": "user", "content": "I prefer quiet trips. Can you suggest a destination?"},
                            {"role": "assistant", "content": "Consider a small coastal town outside peak season."},
                            {"role": "user", "content": "Please turn that into a two-day plan with a low budget."},
                            {"role": "assistant", "content": "Use public transit, free walking routes, and one inexpensive local meal."},
                        ],
                    }
                ]
            ).to_parquet(path, index=False)

            records = list(self.normalizer.normalize_ultrachat(path))

        self.assertEqual(2, len(records))
        self.assertEqual("HuggingFaceH4/ultrachat_200k", records[0]["source_dataset"])
        self.assertEqual("MIT", records[0]["source_license"])
        self.assertEqual("", records[0]["source_context"])
        self.assertIn("User: I prefer quiet trips", records[1]["source_context"])
        self.assertIn("Assistant: Consider a small coastal town", records[1]["source_context"])
        self.assertTrue(records[1]["source_metadata"]["synthetic_dialogue"])

    def test_normalize_magicoder_preserves_code_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "magicoder.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "lang": "python",
                        "index": 7,
                        "raw_index": 11,
                        "seed": "def old():\n    pass",
                        "problem": "Implement a Python 3.10 function named parse_rows.\nDo not use pandas.",
                        "solution": "```python\ndef parse_rows(text):\n    return text.splitlines()\n```",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            records = list(self.normalizer.normalize_magicoder(path))

        self.assertEqual(1, len(records))
        self.assertEqual("coding", records[0]["domain"])
        self.assertIn("\n", records[0]["raw_question"])
        self.assertEqual("MIT", records[0]["source_license"])

    def test_normalize_apps_preserves_task_metadata_and_uses_reference_solution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "apps.parquet"
            pd.DataFrame(
                [
                    {
                        "problem_id": 42,
                        "question": "Implement a parser that returns each non-empty row while preserving input order.",
                        "solutions": json.dumps(["def parse_rows(text):\n    return [x for x in text.splitlines() if x]"]),
                        "input_output": json.dumps({"fn_name": "parse_rows", "inputs": [], "outputs": []}),
                        "difficulty": "interview",
                        "url": "https://example.com/problem/42",
                        "starter_code": "def parse_rows(text):\n    pass",
                    }
                ]
            ).to_parquet(path, index=False)

            records = list(self.normalizer.normalize_apps(path))

        self.assertEqual(1, len(records))
        self.assertEqual("codeparrot/apps", records[0]["source_dataset"])
        self.assertEqual("coding", records[0]["domain"])
        self.assertIn("Starter code:", records[0]["source_context"])
        self.assertIn("return [x", records[0]["source_answer"])
        self.assertEqual("interview", records[0]["source_metadata"]["difficulty"])
        self.assertTrue(records[0]["source_metadata"]["has_function_name"])

    def test_normalize_stack_exchange_preserves_attribution_and_selects_accepted_answer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "train-00000-of-00335.parquet"
            pd.DataFrame(
                [
                    {
                        "qid": 42,
                        "question": "<p>How can I fix this <code>ValueError</code> in Python?</p>",
                        "answers": [
                            {
                                "answer_id": 10,
                                "author": "High Score",
                                "author_id": 100,
                                "author_profile": "https://stackoverflow.com/users/100",
                                "pm_score": 12,
                                "selected": False,
                                "text": "<p>Use a broad fallback.</p>",
                            },
                            {
                                "answer_id": 11,
                                "author": "Accepted Author",
                                "author_id": 101,
                                "author_profile": "https://stackoverflow.com/users/101",
                                "pm_score": 8,
                                "selected": True,
                                "text": "<p>Validate the input first.</p><pre><code>int(value)</code></pre>",
                            },
                        ],
                        "date": "2020/01/02",
                        "metadata": [
                            "https://stackoverflow.com/questions/42",
                            "https://stackoverflow.com",
                            "https://stackoverflow.com/users/99",
                        ],
                    }
                ]
            ).to_parquet(path, index=False)

            records = list(self.normalizer.normalize_stack_exchange(path))

        self.assertEqual(1, len(records))
        record = records[0]
        self.assertEqual("coding", record["domain"])
        self.assertEqual("CC-BY-SA-4.0", record["source_license"])
        self.assertEqual("Accepted Author", record["source_metadata"]["answer_author"])
        self.assertEqual("https://stackoverflow.com/questions/42", record["source_metadata"]["question_url"])
        self.assertEqual("https://stackoverflow.com/users/99", record["source_metadata"]["question_author_profile"])
        self.assertIn("`ValueError`", record["raw_question"])
        self.assertIn("```\nint(value)\n```", record["source_answer"])
        self.assertFalse(record["source_metadata"]["attribution_complete"])

    def test_stack_exchange_attribution_enrichment_resolves_question_author(self) -> None:
        row = {
            "id": "stack-1",
            "source_dataset": "HuggingFaceH4/stack-exchange-preferences",
            "source_metadata": {
                "question_url": "https://stackoverflow.com/questions/42",
                "question_author_profile": "https://stackoverflow.com/users/99/",
                "question_author_name": "",
                "answer_author": "Accepted Author",
                "answer_author_profile": "https://stackoverflow.com/users/101",
                "attribution_complete": False,
            },
        }

        enriched, audit = self.attribution.enrich_rows(
            [row],
            {99: {"display_name": "Question Author", "link": "https://stackoverflow.com/users/99/name"}},
        )

        metadata = enriched[0]["source_metadata"]
        self.assertEqual("Question Author", metadata["question_author_name"])
        self.assertTrue(metadata["attribution_complete"])
        self.assertEqual(1, audit["question_authors_resolved"])
        self.assertEqual([99], self.attribution.required_user_ids([row]))

    def test_domain_selector_detects_general_and_coding_memory_signals(self) -> None:
        general = {
            "id": "g1",
            "domain": "general",
            "source_dataset": "OpenAssistant/oasst1",
            "raw_question": "I am planning a low-cost weekend trip and my schedule only allows two days. What itinerary would work?",
            "source_answer": "Choose a nearby destination, compare transport costs, and leave enough time for rest on both days.",
            "topic": "planning_advice",
        }
        coding = {
            "id": "c1",
            "domain": "coding",
            "source_dataset": "Magicoder",
            "raw_question": "Implement this function in Python 3.10 without using pandas. It must return a list and handle empty input.",
            "source_answer": "Define the function, split valid input rows, return a list, and explicitly handle the empty string case.",
            "topic": "implementation",
        }

        general_result = self.selector.assess_record(general, self.selection_config())["raw_selection"]
        coding_result = self.selector.assess_record(coding, self.selection_config())["raw_selection"]

        self.assertTrue(general_result["eligible"])
        self.assertIn("goal_plan", general_result["memory_signal_families"])
        self.assertTrue(coding_result["eligible"])
        self.assertIn("language_version", coding_result["memory_signal_families"])
        self.assertIn("implementation_constraint", coding_result["memory_signal_families"])

    def test_coding_noise_check_allows_normal_code_punctuation(self) -> None:
        coding = {
            "id": "c2",
            "domain": "coding",
            "source_dataset": "Magicoder",
            "raw_question": "Implement solve(items: list[int]) -> dict[str, int] in Python 3.10 without third-party libraries.",
            "source_answer": "def solve(items):\n    return {str(value): value * 2 for value in items if value >= 0}",
            "topic": "implementation",
        }

        result = self.selector.assess_record(coding, self.selection_config())["raw_selection"]

        self.assertNotIn("text_noise", result["hard_rejection_reasons"])

    def test_coding_selector_accepts_tasked_with_instruction(self) -> None:
        coding = {
            "id": "c-tasked",
            "domain": "coding",
            "source_dataset": "Magicoder",
            "raw_question": (
                "You are tasked with implementing a Python function for this project. "
                "The function must return a list and handle empty input without pandas."
            ),
            "source_answer": (
                "Define the function, return an empty list for empty input, and otherwise parse each row "
                "using only the standard library."
            ),
            "topic": "implementation",
        }

        result = self.selector.assess_record(coding, self.selection_config())["raw_selection"]

        self.assertTrue(result["features"]["question_intent"])
        self.assertNotIn("missing_question_intent", result["hard_rejection_reasons"])

    def test_coding_selector_rejects_question_that_contains_reference_solution(self) -> None:
        solution = "def solve(values):\n    total = sum(values)\n    return total if total > 0 else 0"
        coding = {
            "id": "c3",
            "domain": "coding",
            "source_dataset": "Magicoder",
            "raw_question": "Implement solve in Python and use this implementation:\n" + solution,
            "source_answer": solution,
            "topic": "implementation",
        }

        result = self.selector.assess_record(coding, self.selection_config())["raw_selection"]

        self.assertIn("reference_answer_in_question", result["hard_rejection_reasons"])

    def test_generic_requests_include_domain_context_and_reference_answer(self) -> None:
        row = {
            "id": "c1",
            "domain": "coding",
            "source_dataset": "Magicoder",
            "topic": "implementation",
            "source_context": "The project uses Python 3.10.",
            "raw_question": "Implement parse_rows without pandas.",
            "source_answer": "Use the csv module and return a list.",
        }
        semantic_template = (
            "Domain={domain}\nGuide={domain_guidance}\nContext={source_context}\n"
            "Question={raw_question}\nAnswer={source_answer}\nSchema={schema_version}\nDimensions={dimension_names}"
        )
        generation_template = (
            "Domain={domain}\nGuide={domain_guidance}\nContext={source_context}\n"
            "Question={raw_question}\nAnswer={source_answer}\n{language_policy}"
        )

        semantic = self.semantic.build_request(row, 1, semantic_template)["prompt"][0]["content"]
        generation = self.generation.build_request(
            row,
            1,
            "3-6",
            generation_template,
            output_language="en",
        )["prompt"][0]["content"]

        self.assertIn("project environment", semantic)
        self.assertIn("The project uses Python 3.10.", semantic)
        self.assertIn("Do not turn the reference solution into memory", generation)
        self.assertIn("Use the csv module", generation)

    def test_semantic_retry_allows_context_grounding(self) -> None:
        self.assertIn("SOURCE CONTEXT", self.semantic_retry.RETRY_INSTRUCTION)
        self.assertIn("REFERENCE ANSWER", self.semantic_retry.RETRY_INSTRUCTION)

    def test_semantic_resolution_replaces_only_original_invalid_rows(self) -> None:
        strict = {"id": "one", "semantic_qc": {"state": "strict_pass"}}
        invalid = {"source": {"request_id": "sourceqc_two", "user_defined_params": {"id": "two"}}}
        retried = {"id": "two", "semantic_qc": {"state": "reject"}}

        resolved, residual = self.semantic_merge.merge_resolution([strict], [invalid], [retried], [])

        self.assertEqual(["one", "two"], [row["id"] for row in resolved])
        self.assertEqual([], residual)

    def test_generation_grounding_rejects_composed_evidence(self) -> None:
        record = {
            "memory_blocks": [
                {
                    "parent_memory_id": "p1",
                    "source": "from_question",
                    "raw_evidence": "Python 3.10 and no pandas",
                }
            ],
            "memories": [
                {
                    "parent_memory_id": "p1",
                    "source": "from_question",
                    "evidence": "Python 3.10 and no pandas",
                    "u_star": "C",
                    "derivation": "explicit",
                }
            ],
        }
        params = {
            "domain": "coding",
            "raw_question": "Use Python 3.10. Do not use pandas.",
            "source_context": "",
        }

        errors = self.generation_post.validate_evidence_grounding(record, params)

        self.assertIn("block_0_ungrounded_raw_evidence", errors)
        self.assertIn("memory_0_ungrounded_evidence", errors)

    def test_generation_repair_prompt_forbids_reference_answer_memory(self) -> None:
        request = self.generation_repair.build_repair_request(
            {
                "errors": ["memory_0_ungrounded_evidence"],
                "params": {
                    "id": "raw_coding_1",
                    "domain": "coding",
                    "raw_question": "Use Python 3.10.",
                    "source_answer": "print('solution')",
                },
                "raw": {"accepted": True},
            },
            1,
            {
                "prompt": [{"role": "user", "content": "Construct the complete benchmark record."}],
                "user_defined_params": {"id": "raw_coding_1"},
            },
        )

        content = request["prompt"][0]["content"]
        self.assertIn("Never use REFERENCE ANSWER", content)
        self.assertEqual("crk2_repair1_raw_coding_1", request["request_id"])


if __name__ == "__main__":
    unittest.main()
