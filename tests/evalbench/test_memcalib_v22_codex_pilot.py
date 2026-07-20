from __future__ import annotations

import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from evaluation.common import sha256_file
from evaluation.scripts.release_memcalib_v22_codex_pilot import (
    block_count_bucket,
    build_release,
)
from evaluation.scripts.run_codex_answers import (
    parse_events,
    render_prompt,
    tool_event_types,
    usage_from_events,
)


def source_row(domain: str, index: int, block_count: int) -> dict:
    blocks = [
        {
            "parent_memory_id": f"p{block_index}",
            "memory_text": f"Visible memory {domain} {index} {block_index}.",
        }
        for block_index in range(block_count)
    ]
    memories = [
        {
            "atom_id": f"p{block_index}_a1",
            "parent_memory_id": f"p{block_index}",
            "text": f"Visible memory {domain} {index} {block_index}.",
            "u_star": ("A", "B", "C")[block_index % 3],
            "hard_a_family": (
                "scope_overreach" if block_index == 0 else None
            ),
            "usage_rubric": {"correct_use": "Follow the atomic contract."},
        }
        for block_index in range(block_count)
    ]
    return {
        "id": f"{domain}-{index}-{block_count}",
        "domain": domain,
        "source_dataset": f"source/{domain}/{index % 2}",
        "source_topic": f"topic-{index % 3}",
        "question": f"Question {domain} {index}?",
        "source_answer": "Hidden.",
        "revision_release_admission": {"decision": "admitted_strict"},
        "memory_blocks": blocks,
        "memories": memories,
    }


class MemCalibV22CodexPilotTest(unittest.TestCase):
    def test_block_bucket_boundaries(self) -> None:
        for count, expected in ((3, "3-4"), (4, "3-4"), (5, "5-6"), (6, "5-6"), (7, "7-10"), (10, "7-10"), (11, "11-20"), (20, "11-20")):
            self.assertEqual(expected, block_count_bucket({"id": "x", "memory_blocks": [{}] * count}))
        with self.assertRaises(ValueError):
            block_count_bucket({"id": "x", "memory_blocks": [{}] * 2})

    def test_release_is_reproducible_and_hides_private_fields(self) -> None:
        block_counts = (3, 5, 8, 12)
        rows = [
            source_row(domain, index, block_count)
            for domain in ("health_seed", "general", "coding")
            for block_count in block_counts
            for index in range(10)
        ]
        targets = {
            "health_seed": {"3-4": 2, "5-6": 2, "7-10": 1, "11-20": 1},
            "general": {"3-4": 1, "5-6": 1, "7-10": 1, "11-20": 1},
            "coding": {"3-4": 1, "5-6": 1, "7-10": 1, "11-20": 1},
        }
        source_targets = {
            domain: {f"source/{domain}/0": total // 2, f"source/{domain}/1": total - total // 2}
            for domain, total in (("health_seed", 6), ("general", 4), ("coding", 4))
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "benchmark.jsonl"
            config_path = root / "config.json"
            output_dir = root / "release"
            input_path.write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                encoding="utf-8",
            )
            config_path.write_text(
                json.dumps(
                    {
                        "release": "test-codex-pilot",
                        "seed": 7,
                        "source_count": len(rows),
                        "sample_count": 14,
                        "source_inputs": {"benchmark_sha256": sha256_file(input_path)},
                        "block_bucket_counts": targets,
                        "source_counts": source_targets,
                        "sampling": {"method": "test"},
                    }
                ),
                encoding="utf-8",
            )
            first = build_release(input_path, output_dir, config_path)
            first_ids = (output_dir / "sample-ids.txt").read_text(encoding="utf-8")
            second = build_release(input_path, output_dir, config_path)
            second_ids = (output_dir / "sample-ids.txt").read_text(encoding="utf-8")
            facing = list(
                json.loads(line)
                for line in (output_dir / "model-facing.jsonl").read_text(encoding="utf-8").splitlines()
            )

        self.assertEqual(first["ordered_id_sha256"], second["ordered_id_sha256"])
        self.assertEqual(first_ids, second_ids)
        self.assertEqual(
            Counter({("health_seed", "3-4"): 2, ("health_seed", "5-6"): 2, ("health_seed", "7-10"): 1, ("health_seed", "11-20"): 1, ("general", "3-4"): 1, ("general", "5-6"): 1, ("general", "7-10"): 1, ("general", "11-20"): 1, ("coding", "3-4"): 1, ("coding", "5-6"): 1, ("coding", "7-10"): 1, ("coding", "11-20"): 1}),
            Counter((row["domain"], block_count_bucket(row)) for row in facing),
        )
        self.assertNotIn("source_answer", facing[0])
        self.assertNotIn("memories", facing[0])

    def test_codex_prompt_and_event_audit(self) -> None:
        request = {
            "request_id": "answer:codex:full_memory:x",
            "prompt": [
                {"role": "system", "content": "Answer directly."},
                {"role": "user", "content": "MEMORY\n[1] Visible.\n\nCURRENT QUERY\nQuestion?"},
            ],
        }
        prompt = render_prompt(request)
        self.assertIn("Do not use shell commands", prompt)
        self.assertIn("Answer directly.", prompt)
        self.assertIn("CURRENT QUERY\nQuestion?", prompt)
        events = parse_events(
            "\n".join(
                [
                    '{"type":"item.completed","item":{"type":"agent_message","text":"{\\"answer\\":\\"ok\\"}"}}',
                    '{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":3}}',
                ]
            )
        )
        self.assertEqual([], tool_event_types(events))
        self.assertEqual(13, usage_from_events(events)["total_tokens"])
        tool_events = parse_events(
            '{"type":"item.completed","item":{"type":"command_execution","command":"pwd"}}'
        )
        self.assertEqual(["command_execution"], tool_event_types(tool_events))


if __name__ == "__main__":
    unittest.main()
