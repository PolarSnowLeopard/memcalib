from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = (
    ROOT
    / "evaluation/current/v2.4.1/cluster/memcalib-v241-local-baselines-1500"
    / "validate_nonthinking.py"
)


def _run_validator(tmp_path: Path, message: dict[str, object]) -> tuple[int, dict[str, object]]:
    input_path = tmp_path / "answers.jsonl"
    report_path = tmp_path / "report.json"
    record = {
        "request_id": "answer:test",
        "raw_response": {"choices": [{"message": message}]},
    }
    input_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    completed = subprocess.run(
        [
            str(VALIDATOR),
            "--input",
            str(input_path),
            "--report",
            str(report_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode, json.loads(report_path.read_text(encoding="utf-8"))


class ValidateNonthinkingTest(unittest.TestCase):
    def test_null_reasoning_fields_are_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            returncode, report = _run_validator(
                Path(directory),
                {"content": "Direct answer.", "reasoning_content": None, "reasoning": None},
            )

        self.assertEqual(returncode, 0)
        self.assertIs(report["valid_nonthinking"], True)
        self.assertEqual(report["nonempty_reasoning_content"], 0)

    def test_nonempty_reasoning_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            returncode, report = _run_validator(
                Path(directory),
                {
                    "content": "Direct answer.",
                    "reasoning_content": None,
                    "reasoning": "hidden trace",
                },
            )

        self.assertEqual(returncode, 1)
        self.assertIs(report["valid_nonthinking"], False)
        self.assertEqual(report["nonempty_reasoning_content"], 1)

    def test_visible_nonempty_think_block_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            returncode, report = _run_validator(
                Path(directory),
                {"content": "<think>hidden trace</think>Direct answer.", "reasoning": None},
            )

        self.assertEqual(returncode, 1)
        self.assertIs(report["valid_nonthinking"], False)
        self.assertEqual(report["visible_nonempty_think_blocks"], 1)


if __name__ == "__main__":
    unittest.main()
