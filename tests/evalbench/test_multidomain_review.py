from __future__ import annotations

import unittest
from collections import Counter
from pathlib import Path

from evaluation.scripts.build_multidomain_review import render_review_html, select_review_answers


def judgment(answer_id: str, gold: str, predicted: str, *, secondary: bool = False) -> dict:
    return {
        "answer_request_id": answer_id,
        "judge_model": "secondary" if secondary else "primary",
        "atom_judgments": [
            {
                "atom_id": "a1",
                "u_star": gold,
                "predicted_usage_level": predicted,
                "verdict": "over_use" if predicted > gold else "under_use",
            }
        ],
    }


class MultidomainReviewTest(unittest.TestCase):
    def test_selection_is_balanced_and_contains_expected_strata(self) -> None:
        samples = []
        answers = []
        primary = []
        secondary = []
        models = ["m1", "m2", "m3", "m4", "m5"]
        for domain in ("general", "coding"):
            for index in range(40):
                sample_id = f"{domain}-{index}"
                samples.append({"id": sample_id, "domain": domain})
                for model_index, model in enumerate(models):
                    for condition in ("full_memory", "no_memory"):
                        answer_id = f"answer:{model}:{condition}:{sample_id}"
                        answers.append(
                            {
                                "request_id": answer_id,
                                "response": "short response",
                                "user_defined_params": {
                                    "sample_id": sample_id,
                                    "model_key": model,
                                    "condition": condition,
                                },
                            }
                        )
                        gold = ("A", "B", "C")[index % 3]
                        if condition == "full_memory":
                            predicted = ("C", "C", "A")[index % 3]
                        else:
                            predicted = ("A", "A", "B")[index % 3]
                        primary.append(judgment(answer_id, gold, predicted))
                        secondary_predicted = predicted
                        if (index + model_index) % 4 == 0:
                            secondary_predicted = "B" if predicted != "B" else "C"
                        secondary.append(judgment(answer_id, gold, secondary_predicted, secondary=True))

        selected = select_review_answers(samples, answers, primary, secondary, seed=19)

        self.assertEqual(30, len(selected))
        self.assertEqual({"general": 15, "coding": 15}, dict(Counter(row["domain"] for row in selected)))
        self.assertEqual(
            {
                "representative_random": 10,
                "judge_disagreement": 6,
                "opb": 6,
                "upb": 4,
                "paired_contrast": 4,
            },
            dict(Counter(row["selection_category"] for row in selected)),
        )
        self.assertEqual(28, len({row["sample_id"] for row in selected}))

    def test_render_customizes_review_and_keeps_gold_quality_control(self) -> None:
        template = Path(__file__).resolve().parents[2] / "evaluation" / "templates" / "calibration-review-bilingual.html"
        record = {
            "answer_request_id": "answer:m:full_memory:s1",
            "selection_label": "双 Judge 分歧",
            "selection_category": "judge_disagreement",
            "selection_reason": "a1:primary A/secondary C",
            "domain": "general",
            "panel": "general",
            "model_key": "m",
            "condition": "full_memory",
            "question": "Question",
            "memory_blocks": [],
            "model_response": "Response",
            "atomic_memories": [],
            "primary_judgment": {},
            "secondary_judgment": {},
        }

        page = render_review_html([record], template)

        self.assertIn("多领域有效性审查", page)
        self.assertIn("memcalib-multidomain-human-review-v1", page)
        self.assertIn("atom-gold-quality", page)
        self.assertIn("抽样理由", page)


if __name__ == "__main__":
    unittest.main()
