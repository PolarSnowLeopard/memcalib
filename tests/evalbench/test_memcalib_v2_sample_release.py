from __future__ import annotations

import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from evaluation.common import sha256_file
from evaluation.scripts.release_memcalib_v2_sample import admission_decision, build_release


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
        "composite_block_revision": {
            "difficulty_level": ("level_1", "level_2", "level_3")[index % 3]
        },
    }


class MemCalibV2SampleReleaseTest(unittest.TestCase):
    def test_revision_release_admission_takes_precedence(self) -> None:
        row = {
            "revision_release_admission": {"decision": "strict_pass"},
            "release_admission": {"decision": "admitted_nonblocking_review"},
        }
        self.assertEqual("strict_pass", admission_decision(row))
        self.assertEqual(
            "admitted_nonblocking_review",
            admission_decision({"release_admission": row["release_admission"]}),
        )
        self.assertEqual("unknown", admission_decision({}))

    def test_v23_independent_qc_takes_precedence(self) -> None:
        row = {
            "v23_independent_qc": {"decision": "review"},
            "revision_release_admission": {"decision": "strict_pass"},
        }
        self.assertEqual("review", admission_decision(row))

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
                        "status": "locked_release_candidate",
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
        self.assertEqual("locked_release_candidate", manifest["status"])
        self.assertEqual(manifest["ordered_id_sha256"], manifest_again["ordered_id_sha256"])
        self.assertEqual(
            Counter({"health_seed": 20, "general": 10, "coding": 10}),
            Counter(row["domain"] for row in facing),
        )
        self.assertNotIn("source_answer", facing[0])
        self.assertNotIn("memories", facing[0])
        self.assertNotIn("release_admission", facing[0])
        self.assertEqual(facing[0]["domain"], facing[0]["panel"])
        self.assertNotIn("preferred_sample_overlap", manifest)
        self.assertEqual(
            {
                "path": None,
                "preferred_query_ids": 0,
                "selected_query_ids": 0,
                "semantics": (
                    "shared query/source identity only; benchmark memory blocks and model-facing "
                    "rows may differ across versions"
                ),
            },
            manifest["preferred_query_id_overlap"],
        )

    def test_exact_domain_difficulty_matrix_is_enforced(self) -> None:
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
            matrix = {
                "health_seed": {"level_1": 6, "level_2": 8, "level_3": 6},
                "general": {"level_1": 3, "level_2": 4, "level_3": 3},
                "coding": {"level_1": 2, "level_2": 5, "level_3": 3},
            }
            config_path.write_text(
                json.dumps(
                    {
                        "release": "test-v23-40",
                        "seed": 42,
                        "source_count": 120,
                        "sample_count": 40,
                        "domain_counts": {"health_seed": 20, "general": 10, "coding": 10},
                        "domain_difficulty_counts": matrix,
                        "sampling": {"method": "test"},
                        "source_inputs": {"benchmark_sha256": sha256_file(input_path)},
                    }
                ),
                encoding="utf-8",
            )

            manifest = build_release(input_path, output_dir, config_path)
            hidden = [
                json.loads(line)
                for line in (output_dir / "hidden-evaluation.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]

        actual = Counter(
            (row["domain"], row["composite_block_revision"]["difficulty_level"])
            for row in hidden
        )
        expected = Counter(
            {
                (domain, level): count
                for domain, levels in matrix.items()
                for level, count in levels.items()
            }
        )
        self.assertEqual(expected, actual)
        self.assertEqual(
            Counter({"level_1": 11, "level_2": 17, "level_3": 12}),
            Counter(manifest["distribution"]["difficulty_levels"]),
        )


if __name__ == "__main__":
    unittest.main()
