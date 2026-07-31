from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "audit_memcalib_v24_atom_alignment",
    ROOT / "pipeline" / "110_audit_memcalib_v24_atom_alignment.py",
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def atom(atom_id: str, text: str, expected: str, label: str = "B") -> dict:
    return {
        "atom_id": atom_id,
        "text": text,
        "atomic_predicate": text,
        "evidence": text,
        "u_star": label,
        "memory_action": "apply",
        "usage_rubric": {"expected_answer_behavior": expected},
    }


class AtomAlignmentAuditTest(unittest.TestCase):
    def test_aligned_atoms_are_not_flagged(self) -> None:
        record = {
            "id": "aligned",
            "domain": "coding",
            "question": "Explain the project-approved database choice.",
            "source_dataset": "test",
            "memories": [
                atom(
                    "p1",
                    "The user requires MySQL as the database engine.",
                    "Select MySQL as the database engine.",
                    "C",
                )
            ],
        }
        self.assertIsNone(AUDIT.audit_record(record))

    def test_cross_atom_swap_is_flagged(self) -> None:
        record = {
            "id": "swap",
            "domain": "coding",
            "question": "Describe the application architecture.",
            "source_dataset": "test",
            "memories": [
                atom(
                    "p1",
                    "The user develops applications with Django.",
                    "Describe the browser strategy game and historical records.",
                ),
                atom(
                    "p2",
                    "The user is building a browser strategy game with historical records.",
                    "Use Django as the web framework.",
                ),
            ],
        }
        finding = AUDIT.audit_record(record)
        self.assertIsNotNone(finding)
        reasons = {
            reason
            for item in finding["findings"]
            for reason in item["reasons"]
        }
        self.assertIn("probable_cross_atom_rubric_swap", reasons)

    def test_unsupported_named_identifiers_are_flagged(self) -> None:
        record = {
            "id": "unsupported",
            "domain": "coding",
            "question": "Recommend a managed DNS service.",
            "source_dataset": "test",
            "memories": [
                atom(
                    "p1",
                    "The user primarily works with the LAMP stack.",
                    "Recommend Route53, Linode, and Dynadot.",
                )
            ],
        }
        finding = AUDIT.audit_record(record)
        self.assertIsNotNone(finding)
        self.assertIn(
            "rubric_introduces_unsupported_identifier",
            finding["findings"][0]["reasons"],
        )

    def test_unsupplied_numeric_value_is_not_treated_as_query_leakage(self) -> None:
        target = atom(
            "p1",
            "The user's node ports must start at 9600.",
            "The starting port number is 9600.",
            "C",
        )
        result = AUDIT.analyze_atom_alignment(
            target,
            target["usage_rubric"]["expected_answer_behavior"],
            [target],
            "Explain how the function determines the starting port number.",
        )
        self.assertNotIn(
            "probable_query_rubric_value_leakage",
            result["reasons"],
        )

    def test_identifier_matching_is_case_insensitive(self) -> None:
        target = atom(
            "p1",
            "The user invokes the service with lowercase cfinvoke.",
            "The answer should use CFInvoke.",
            "B",
        )
        result = AUDIT.analyze_atom_alignment(
            target,
            target["usage_rubric"]["expected_answer_behavior"],
            [target],
            "Explain the integration plan.",
        )
        self.assertNotIn(
            "rubric_introduces_unsupported_identifier",
            result["reasons"],
        )

    def test_generic_query_words_do_not_leak_an_absent_exact_identifier(
        self,
    ) -> None:
        target = atom(
            "p1",
            "The output must use [PageSize-Generate]: %d/%d.",
            (
                "Use the mandated string [PageSize-Generate]: %d/%d for "
                "download progress reporting."
            ),
            "C",
        )
        result = AUDIT.analyze_atom_alignment(
            target,
            target["usage_rubric"]["expected_answer_behavior"],
            [target],
            (
                "Explain the mandated output format for download progress "
                "reporting without naming the exact format."
            ),
        )
        self.assertNotIn(
            "probable_query_rubric_value_leakage",
            result["reasons"],
        )


if __name__ == "__main__":
    unittest.main()
