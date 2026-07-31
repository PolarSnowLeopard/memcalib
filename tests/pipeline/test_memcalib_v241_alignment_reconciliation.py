from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PIPELINE_DIR = Path(__file__).resolve().parents[2] / "pipeline"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class AlignmentReconciliationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_script(
            PIPELINE_DIR / "124_reconcile_memcalib_v241_alignment.py",
            "reconcile_memcalib_v241_alignment_test",
        )

    def test_ensure_sentence_normalizes_proposition(self) -> None:
        self.assertEqual("A project fact.", self.module.ensure_sentence("A project fact"))

    def test_reconcile_uses_only_same_atom_evidence(self) -> None:
        record = {
            "id": "r1",
            "domain": "coding",
            "source_answer": "A practical answer.",
            "memories": [
                {
                    "atom_id": "p1_a1",
                    "u_star": "B",
                    "memory_action": "apply",
                    "text": "The project uses a remote service.",
                    "atomic_predicate": "The project uses a remote service.",
                    "usage_rubric": {
                        "expected_answer_behavior": "Call UnsupportedClient.do_work."
                    },
                }
            ],
            "memory_blocks": [],
        }
        finding = {
            "record_id": "r1",
            "findings": [
                {
                    "atom_id": "p1_a1",
                    "reasons": ["rubric_introduces_unsupported_identifier"],
                }
            ],
        }
        output, audit = self.module.reconcile_record(record, finding)
        expected = output["memories"][0]["usage_rubric"][
            "expected_answer_behavior"
        ]
        self.assertIn("The project uses a remote service.", expected)
        self.assertNotIn("UnsupportedClient", expected)
        self.assertEqual(["p1_a1"], audit["flagged_atom_ids"])


if __name__ == "__main__":
    unittest.main()
