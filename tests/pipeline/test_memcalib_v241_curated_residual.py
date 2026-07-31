from __future__ import annotations

import copy
import importlib
import unittest


mod = importlib.import_module("121_build_memcalib_v241_curated_residual")


def atom(atom_id: str, label: str, text: str) -> dict:
    return {
        "atom_id": atom_id,
        "u_star": label,
        "memory_action": "apply" if label != "A" else "ignore",
        "text": text,
        "atomic_predicate": text,
        "counterfactual_contract": {
            "minimal_evidence": [text],
        },
        "usage_rubric": {
            "expected_answer_behavior": text,
        },
    }


class CuratedResidualTest(unittest.TestCase):
    def test_response_family_does_not_force_every_question_to_implementation(self):
        self.assertEqual(
            mod.infer_response_family(
                "Is it a good idea to use migrations for a Java project?"
            ),
            "recommendation_or_evaluation",
        )
        question = mod.response_form_question(
            "Is it a good idea to use migrations for a Java project?",
            "recommendation_or_evaluation",
        )
        self.assertIn("recommendation or evaluation", question)
        self.assertNotIn("step-by-step implementation plan", question)

    def test_same_atom_supervision_uses_only_own_fact(self):
        source = atom(
            "p1_a1",
            "B",
            "The project stores its base URL in SERVICE_URL.",
        )
        updated, reference = mod.same_atom_supervision(
            source,
            "The plan validates its input and constructs the request URL.",
        )
        expected = updated["usage_rubric"]["expected_answer_behavior"]
        self.assertIn("SERVICE_URL", expected)
        self.assertNotIn("OTHER_URL", expected)
        self.assertIn("SERVICE_URL", reference)
        self.assertEqual(
            updated["counterfactual_contract"]["minimal_evidence"],
            ["The project stores its base URL in SERVICE_URL."],
        )

    def test_query_supplied_scored_atom_is_demoted_but_other_score_remains(self):
        source = {
            "id": "r1",
            "question": (
                "The project uses Django. Explain how to structure the browser "
                "strategy game."
            ),
            "source_answer": "Use Django to implement the service behavior.",
            "memory_blocks": [],
            "memories": [
                atom(
                    "p1",
                    "B",
                    "The project uses Django.",
                ),
                atom(
                    "p2",
                    "C",
                    "The service must emit status READY.",
                ),
            ],
        }
        candidate = copy.deepcopy(source)
        candidate["domain"] = "coding"
        candidate["source_answer"] = (
            "Use Django for the web layer. The service must emit status READY "
            "after initialization completes."
        )
        record, audit = mod.curate_record(source, candidate, "test")
        by_id = {item["atom_id"]: item for item in record["memories"]}
        self.assertEqual(by_id["p1"]["u_star"], "A")
        self.assertEqual(by_id["p1"]["memory_action"], "ignore")
        self.assertEqual(by_id["p2"]["u_star"], "C")
        self.assertEqual(len(audit["query_supplied_atom_demotions"]), 1)


if __name__ == "__main__":
    unittest.main()
