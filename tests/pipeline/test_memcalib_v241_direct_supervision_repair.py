from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PIPELINE = Path(__file__).resolve().parents[2] / "pipeline"
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))
SPEC = importlib.util.spec_from_file_location(
    "direct_supervision_repair",
    PIPELINE / "120_direct_repair_memcalib_v241_supervision.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def source_record() -> dict:
    return {
        "id": "coding-test-1",
        "domain": "coding",
        "question": "Write a deployment script that builds and pushes an image.",
        "source_answer": (
            "```bash\ndocker build .\ndocker push image\n```\n"
            "The script builds the image and pushes it to the registry."
        ),
        "memory_blocks": [
            {
                "parent_memory_id": "block-1",
                "memory_text": "The deployment output must be logged.",
                "atom_ids": ["a-1", "b-1"],
            }
        ],
        "memories": [
            {
                "atom_id": "a-1",
                "parent_memory_id": "block-1",
                "text": "The old registry was registry.example.",
                "u_star": "A",
                "memory_action": "ignore",
                "usage_rubric": {
                    "expected_answer_behavior": "Use the registry from the question."
                },
                "counterfactual_contract": {"minimal_evidence": []},
            },
            {
                "atom_id": "b-1",
                "parent_memory_id": "block-1",
                "text": "The deployment output must be logged to /var/log/deploy.log.",
                "u_star": "B",
                "memory_action": "apply",
                "usage_rubric": {
                    "expected_answer_behavior": (
                        "The script logs deployment output to /var/log/deploy.log."
                    )
                },
                "counterfactual_contract": {
                    "minimal_evidence": [
                        "Reference to /var/log/deploy.log",
                        "Capture deployment output",
                    ]
                },
            },
        ],
    }


class DirectSupervisionRepairTests(unittest.TestCase):
    def test_restores_original_labels_and_same_atom_evidence(self) -> None:
        source = source_record()
        prior = {
            **source,
            "question": "Describe an unrelated logging diagnosis.",
            "source_answer": "A mismatched answer.",
            "memories": [
                {**source["memories"][0], "u_star": "B", "memory_action": "apply"},
                {**source["memories"][1], "u_star": "C"},
            ],
        }

        repaired, audit = MODULE.restore_record(source, prior)

        labels = {
            atom["atom_id"]: (atom["u_star"], atom["memory_action"])
            for atom in repaired["memories"]
        }
        self.assertEqual(labels, {"a-1": ("A", "ignore"), "b-1": ("B", "apply")})
        self.assertIn("builds and pushes an image", repaired["question"])
        self.assertIn("/var/log/deploy.log", repaired["source_answer"])
        self.assertIn(
            "The deployment output must be logged to /var/log/deploy.log",
            repaired["source_answer"],
        )
        self.assertNotIn("```", repaired["source_answer"])
        self.assertEqual(audit["required_evidence_count"], 2)

    def test_removes_executable_fenced_block_but_keeps_prose(self) -> None:
        prose = MODULE.prose_outside_fences(
            "```python\nprint('hidden')\n```\nExplain the visible behavior."
        )

        self.assertEqual(prose, "Explain the visible behavior.")


if __name__ == "__main__":
    unittest.main()
