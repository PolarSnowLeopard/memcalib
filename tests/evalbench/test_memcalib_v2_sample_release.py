from __future__ import annotations

import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from evaluation.common import sha256_file
from evaluation.scripts.release_memcalib_v2_sample import build_release


def source_row(domain: str, index: int) -> dict:
    source = f"source/{domain}/{index % 2}"
    topic = f"topic-{index % 3}"
    return {
        "id": f"{domain}-{index}",
        "domain": domain,
        "source_dataset": source,
        "source_topic": topic,
        "question": f"Question {domain} {index}?",
        "source_answer": "Hidden reference answer.",
        "release_admission": {
            "decision": "admitted_nonblocking_review" if index % 17 == 0 else "admitted_strict"
        },
        "memory_blocks": [
            {
                "parent_memory_id": "p1",
                "memory_text": f"The user has constraint {index}.",
            }
        ],
        "memories": [
            {
                "atom_id": "p1_a1",
                "parent_memory_id": "p1",
                "text": f"The user has constraint {index}.",
                "u_star": "C",
                "usage_rubric": {"correct_use": "Respect it."},
            }
        ],
        "independent_qc": {"private": True},
    }


class MemCalibV2SampleReleaseTest(unittest.TestCase):
    def test_sample_is_reproducible_and_hides_private_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "benchmark.jsonl"
            output_dir = root / "release"
            config_path = root / "config.json"
            rows = [
                source_row(domain, index)
                for domain, size in (("health_seed", 60), ("general", 30), ("coding", 30))
                for index in range(size)
            ]
            input_path.write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                encoding="utf-8",
            )
            config_path.write_text(
                json.dumps(
                    {
                        "release": "test-v2-40",
                        "seed": 42,
                        "source_count": 120,
                        "sample_count": 40,
                        "domain_counts": {"health_seed": 20, "general": 10, "coding": 10},
                        "sampling": {"method": "test"},
                        "source_inputs": {"benchmark_sha256": sha256_file(input_path)},
                    }
                ),
                encoding="utf-8",
            )

            manifest = build_release(input_path, output_dir, config_path)
            first_ids = (output_dir / "sample-ids.txt").read_text(encoding="utf-8")
            manifest_again = build_release(input_path, output_dir, config_path)
            second_ids = (output_dir / "sample-ids.txt").read_text(encoding="utf-8")
            facing = [
                json.loads(line)
                for line in (output_dir / "model-facing.jsonl").read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(first_ids, second_ids)
        self.assertEqual(manifest["ordered_id_sha256"], manifest_again["ordered_id_sha256"])
        self.assertEqual(
            Counter({"health_seed": 20, "general": 10, "coding": 10}),
            Counter(row["domain"] for row in facing),
        )
        self.assertNotIn("source_answer", facing[0])
        self.assertNotIn("memories", facing[0])
        self.assertNotIn("release_admission", facing[0])
        self.assertEqual(facing[0]["domain"], facing[0]["panel"])


if __name__ == "__main__":
    unittest.main()
