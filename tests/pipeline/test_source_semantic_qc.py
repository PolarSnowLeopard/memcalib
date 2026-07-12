#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from collections import Counter
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[2] / "pipeline"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

PREPARE_SCRIPT = SCRIPT_DIR / "18_prepare_source_semantic_qc.py"
POST_SCRIPT = SCRIPT_DIR / "19_post_source_semantic_qc.py"
AUDIT_SCRIPT = SCRIPT_DIR / "20_build_source_semantic_qc_audit.py"
ADMISSION_SCRIPT = SCRIPT_DIR / "21_select_source_semantic_admission.py"
RETRY_SCRIPT = SCRIPT_DIR / "22_prepare_source_semantic_qc_retry.py"


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def source_row(row_id: str, source: str, topic: str, complexity: str, score: int = 85) -> dict:
    return {
        "id": row_id,
        "source_dataset": source,
        "source_split": "train",
        "source_index": row_id,
        "topic": topic,
        "raw_question": (
            "I have taken metformin for five years, and my fasting glucose is now 9.2 mmol/L. "
            "What should I discuss with my doctor?"
        ),
        "doctor_answer": (
            "The glucose level suggests that current control may be inadequate. Your clinician should review "
            "adherence, HbA1c, kidney function, and options for adjusting treatment."
        ),
        "raw_selection": {
            "hard_filter_pass": True,
            "score_pass": True,
            "eligible": True,
            "quality_score": score,
            "quality_components": {
                "question_informativeness": 20,
                "answer_substance": 20,
                "memory_suitability": 30,
                "cleanliness_coherence": 10,
            },
            "memory_signal_families": ["personal_entity", "temporal_history", "treatment", "measurement"],
            "seed_complexity": complexity,
            "dedup_status": "unique",
            "selection_status": "selected",
        },
    }


def selection_config() -> dict:
    return {
        "min_quality_score": 65,
        "topic_alpha": 0.5,
        "quality_weight_beta": 2.0,
        "complexity_targets": {"simple": 0.25, "medium": 0.5, "complex": 0.25},
    }


def dimension(label: str, evidence: str, reason: str = "The quoted evidence supports this decision.") -> dict:
    return {"label": label, "evidence": evidence, "reason": reason}


def strict_pass_judgment() -> dict:
    return {
        "schema_version": "crk2-source-semantic-qc-v1",
        "dimensions": {
            "question_completeness": dimension("pass", "What should I discuss with my doctor?"),
            "answer_relevance": dimension("pass", "current control may be inadequate"),
            "answer_substantiveness": dimension("pass", "review adherence, HbA1c, kidney function"),
            "memory_extractability": dimension("pass", "I have taken metformin for five years"),
            "text_integrity": dimension("pass", "my fasting glucose is now 9.2 mmol/L"),
            "safety_plausibility": dimension("pass", "options for adjusting treatment"),
        },
        "overall_verdict": "pass",
        "reject_reasons": [],
        "confidence": "high",
        "summary": "The question is complete, the answer is relevant, and explicit memory evidence is available.",
    }


class SourceSemanticQcTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prepare = load_script(PREPARE_SCRIPT, "prepare_source_semantic_qc")
        cls.post = load_script(POST_SCRIPT, "post_source_semantic_qc")
        cls.audit = load_script(AUDIT_SCRIPT, "audit_source_semantic_qc")
        cls.admission = load_script(ADMISSION_SCRIPT, "select_source_semantic_admission")
        cls.retry = load_script(RETRY_SCRIPT, "prepare_source_semantic_qc_retry")

    def test_select_calibration_rows_balances_sources_and_preserves_strata(self) -> None:
        rows = []
        for source in ("source-a", "source-b"):
            for index in range(9):
                rows.append(
                    source_row(
                        f"{source}-{index}",
                        source,
                        ("cardio", "digestive", "pediatrics")[index % 3],
                        ("simple", "medium", "complex")[index % 3],
                        90 - index,
                    )
                )

        selected = self.prepare.select_calibration_rows(rows, limit=12, seed=42, config=selection_config())

        self.assertEqual({"source-a": 6, "source-b": 6}, dict(Counter(row["source_dataset"] for row in selected)))
        self.assertEqual({"simple", "medium", "complex"}, {row["raw_selection"]["seed_complexity"] for row in selected})
        self.assertEqual({"cardio", "digestive", "pediatrics"}, {row["topic"] for row in selected})

    def test_build_request_contains_fixed_schema_and_preserves_source_fields(self) -> None:
        row = source_row("raw-1", "source-a", "cardio", "medium")
        template = "Schema={schema_version}\nQuestion={raw_question}\nAnswer={doctor_answer}\nDimensions={dimension_names}"

        request = self.prepare.build_request(row, request_index=1, prompt_template=template)

        self.assertEqual("sourceqc_raw-1", request["request_id"])
        self.assertEqual("raw-1", request["user_defined_params"]["id"])
        self.assertEqual("crk2-source-semantic-qc-v1", request["user_defined_params"]["semantic_qc_schema_version"])
        content = request["prompt"][0]["content"]
        self.assertIn("question_completeness", content)
        self.assertIn("safety_plausibility", content)
        self.assertIn(row["raw_question"], content)
        self.assertIn(row["doctor_answer"], content)

    def test_strict_pass_requires_all_dimensions_to_pass(self) -> None:
        params = source_row("raw-1", "source-a", "cardio", "medium")
        judgment = strict_pass_judgment()

        self.assertEqual([], self.post.validate_judgment(judgment, params))
        self.assertEqual("strict_pass", self.post.classify_judgment(judgment))

    def test_uncertain_without_reject_routes_to_review(self) -> None:
        judgment = strict_pass_judgment()
        judgment["dimensions"]["safety_plausibility"] = dimension(
            "uncertain", "options for adjusting treatment", "Medical correctness cannot be confirmed from the source alone."
        )
        judgment["overall_verdict"] = "review"
        judgment["confidence"] = "medium"

        self.assertEqual("review", self.post.classify_judgment(judgment))

    def test_explicit_dimension_reject_is_not_rescued(self) -> None:
        judgment = strict_pass_judgment()
        judgment["dimensions"]["answer_relevance"] = dimension(
            "reject", "The glucose level", "The answer addresses an unrelated issue."
        )
        judgment["overall_verdict"] = "reject"
        judgment["reject_reasons"] = ["answer_irrelevant"]

        self.assertEqual("reject", self.post.classify_judgment(judgment))

    def test_validation_rejects_ungrounded_evidence(self) -> None:
        params = source_row("raw-1", "source-a", "cardio", "medium")
        judgment = strict_pass_judgment()
        judgment["dimensions"]["answer_relevance"]["evidence"] = "This sentence does not occur in the source answer."

        errors = self.post.validate_judgment(judgment, params)

        self.assertIn("ungrounded_evidence_answer_relevance", errors)

    def test_grounding_accepts_ordered_source_fragments_joined_by_ellipsis(self) -> None:
        source = (
            "No need to get scared, its not the age to worry about the lesions in the breast."
            " An ultrasound scan will help to evaluate what it contains."
        )
        evidence = (
            "No need to get scared, its not the age to worry about the lesions in the breast... "
            "An ultrasound scan will help to evaluate what it contains."
        )

        self.assertTrue(self.post.grounded(evidence, source))

    def test_grounding_requires_ellipsis_fragments_to_follow_source_order(self) -> None:
        source = "First the clinician reviews adherence. Later the clinician reviews kidney function."
        evidence = "kidney function... reviews adherence"

        self.assertFalse(self.post.grounded(evidence, source))

    def test_grounding_accepts_json_escaped_quotes_and_unicode_spaces(self) -> None:
        quoted_source = 'MRI showed \\\"mild chronic small vessel ischemic changes\\\" yesterday.'
        spaced_source = "Paracetamol in the dose of 15\\u00a0mg/kg/dose."

        self.assertTrue(
            self.post.grounded('MRI showed "mild chronic small vessel ischemic changes" yesterday.', quoted_source)
        )
        self.assertTrue(self.post.grounded("Paracetamol in the dose of 15 mg/kg/dose.", spaced_source))

    def test_wilson_lower_bound_produces_conservative_admission_target(self) -> None:
        lower = self.post.wilson_lower_bound(100, 100)
        target = self.post.compute_admission_target(final_target=15000, generation_successes=100, generation_total=100)

        self.assertGreater(lower, 0.95)
        self.assertLess(lower, 1.0)
        self.assertGreater(target, 15000)
        self.assertLess(target, 16000)

    def test_admission_uses_only_strict_passes_when_capacity_is_sufficient(self) -> None:
        rows = []
        for index in range(10):
            row = source_row(f"strict-{index}", "source-a", "cardio", "medium")
            row["semantic_qc"] = {"state": "strict_pass"}
            rows.append(row)
        for state in ("review", "reject"):
            row = source_row(state, "source-a", "cardio", "medium")
            row["semantic_qc"] = {"state": state}
            rows.append(row)

        plan = self.admission.plan_admission(
            rows,
            final_target=5,
            generation_successes=100,
            generation_total=100,
            seed=42,
            config=selection_config(),
        )

        self.assertEqual("strict_sufficient", plan["status"])
        self.assertEqual(plan["admission_target"], len(plan["admitted"]))
        self.assertEqual([], plan["review_candidates"])
        self.assertEqual({"strict_pass"}, {row["semantic_qc"]["state"] for row in plan["admitted"]})

    def test_admission_routes_uncertain_records_only_when_strict_capacity_is_short(self) -> None:
        rows = []
        for index, state in enumerate(("strict_pass", "strict_pass", "review", "review", "reject")):
            row = source_row(f"row-{index}", "source-a", "cardio", "medium")
            row["semantic_qc"] = {"state": state}
            rows.append(row)

        plan = self.admission.plan_admission(
            rows,
            final_target=3,
            generation_successes=100,
            generation_total=100,
            seed=42,
            config=selection_config(),
        )

        self.assertEqual("review_required", plan["status"])
        self.assertEqual(2, len(plan["admitted"]))
        self.assertEqual(2, len(plan["review_candidates"]))
        self.assertNotIn("reject", {row["semantic_qc"]["state"] for row in plan["review_candidates"]})

    def test_summary_reports_semantic_states_by_sampling_stratum(self) -> None:
        first = source_row("raw-1", "source-a", "cardio", "simple")
        first["semantic_qc"] = {"state": "strict_pass", "judgment": strict_pass_judgment()}
        second = source_row("raw-2", "source-b", "neuro", "complex")
        second_judgment = strict_pass_judgment()
        second_judgment["dimensions"]["safety_plausibility"]["label"] = "uncertain"
        second_judgment["overall_verdict"] = "review"
        second["semantic_qc"] = {"state": "review", "judgment": second_judgment}

        summary = self.post.build_summary([first, second], invalid_count=0)

        self.assertEqual({"strict_pass": 1}, summary["state_by_source"]["source-a"])
        self.assertEqual({"review": 1}, summary["state_by_source"]["source-b"])
        self.assertEqual({"strict_pass": 1}, summary["state_by_topic"]["cardio"])
        self.assertEqual({"review": 1}, summary["state_by_seed_complexity"]["complex"])

    def test_retry_requests_target_only_invalid_ids_and_reinforce_exact_evidence(self) -> None:
        requests = [
            {
                "request_id": "sourceqc_raw-1",
                "prompt": [{"role": "user", "content": "Evaluate this source."}],
                "user_defined_params": {"id": "raw-1"},
            },
            {
                "request_id": "sourceqc_raw-2",
                "prompt": [{"role": "user", "content": "Evaluate another source."}],
                "user_defined_params": {"id": "raw-2"},
            },
        ]
        invalid_rows = [{"source": {"request_id": "sourceqc_raw-2"}}]

        retry_requests = self.retry.build_retry_requests(requests, invalid_rows, retry_round=1)

        self.assertEqual(1, len(retry_requests))
        self.assertEqual("sourceqc_raw-2", retry_requests[0]["request_id"])
        self.assertEqual(1, retry_requests[0]["user_defined_params"]["semantic_qc_retry_round"])
        self.assertIn("contiguous exact substring", retry_requests[0]["prompt"][0]["content"])

    def test_audit_html_has_one_active_sample_all_dimensions_and_keyboard_navigation(self) -> None:
        row = source_row("raw-1", "source-a", "cardio", "medium")
        row["semantic_qc"] = {
            "state": "strict_pass",
            "judgment": strict_pass_judgment(),
            "validation_errors": [],
        }
        summary = {"total": 2, "strict_pass": 1, "review": 1, "reject": 0, "invalid": 0}

        html = self.audit.build_html([row, dict(row, id="raw-2")], summary)

        self.assertEqual(1, html.count('class="sample-page active"'))
        self.assertEqual(1, html.count('class="sample-page"'))
        for name in self.post.DIMENSION_NAMES:
            self.assertIn(name, html)
        self.assertIn("Exact evidence", html)
        self.assertIn("event.key === 'ArrowRight'", html)
        self.assertIn("event.key === 'ArrowLeft'", html)


if __name__ == "__main__":
    unittest.main()
