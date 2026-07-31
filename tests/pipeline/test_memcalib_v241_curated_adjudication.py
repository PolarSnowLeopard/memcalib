from __future__ import annotations

import importlib
import unittest


mod = importlib.import_module("122_adjudicate_memcalib_v241_curated_residual")


class CuratedAdjudicationTest(unittest.TestCase):
    def test_choose_reference_prefers_original_when_semantic_equivalence_failed(self):
        original = (
            "Unix time does not encode leap seconds, so it is not a linear count "
            "of every SI second across civil time."
        )
        text, channel = mod.choose_reference(
            current=(
                "The project converts an unrelated workplace day counter with a "
                "fixed anchor and returns a calendar date."
            ),
            baseline="A migration plan uses a different date representation.",
            source=original,
            semantic_equivalence_failed=True,
        )
        self.assertEqual(channel, "original_reference_prose")
        self.assertIn("leap seconds", text)

    def test_remove_atom_footprint_removes_matching_sentence_only(self):
        sentences = [
            "Use bulk copy to transfer the data.",
            "Linked servers are prohibited by security policy.",
            "Validate the row count after transfer.",
        ]
        atom = {
            "text": "Linked servers are prohibited by security policy.",
            "atomic_predicate": "Linked servers are prohibited by security policy.",
        }
        retained, removed = mod.remove_atom_footprint(sentences, atom)
        self.assertEqual(removed, [sentences[1]])
        self.assertEqual(retained, [sentences[0], sentences[2]])

    def test_produce_is_an_implementation_task(self):
        self.assertEqual(
            mod.infer_repaired_family(
                "Produce the requested source-code artifact for this function."
            ),
            "implementation_plan",
        )


if __name__ == "__main__":
    unittest.main()
