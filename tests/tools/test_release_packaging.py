from __future__ import annotations

import gzip
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = REPO_ROOT / "tools" / "build_release.py"
VERIFY_SCRIPT = REPO_ROOT / "tools" / "verify_release.py"


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_record(index: int, *, mixed: bool = False) -> dict:
    labels = ["A", "C"] if mixed else (["B"] if index % 2 else ["C"])
    parent_id = f"p{index}"
    memories = []
    for atom_index, label in enumerate(labels, start=1):
        memories.append(
            {
                "atom_id": f"{parent_id}_a{atom_index}",
                "parent_memory_id": parent_id,
                "u_star": label,
                "hard_a_family": "scope_overreach" if label == "A" else None,
                "text": f"Atomic memory {index}-{atom_index}",
                "usage_rubric": {"memory_usage_weight": {"A": "none", "B": "supporting", "C": "controlling"}[label]},
            }
        )
    return {
        "id": f"sample-{index}",
        "source_dataset": "source-a" if index % 2 else "source-b",
        "source_topic": "topic-a" if index < 3 else "topic-b",
        "question": f"Question {index}?",
        "memory_blocks": [
            {
                "parent_memory_id": parent_id,
                "memory_text": f"Parent memory {index}",
                "parent_label_mode": "mixed" if mixed else "homogeneous",
                "parent_label_set": labels,
            }
        ],
        "memories": memories,
        "construction_audit": {"seed_complexity": "complex" if index % 2 else "simple"},
    }


class ReleasePackagingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.work = Path(self.tempdir.name)
        self.source = self.work / "benchmark.jsonl"
        rows = [fixture_record(index, mixed=index == 3) for index in range(1, 6)]
        self.source.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    @staticmethod
    def shard_bytes(release_dir: Path, manifest: dict) -> list[bytes]:
        return [
            (release_dir / item["path"]).read_bytes()
            for item in manifest["files"]["data_shards"]
        ]

    @staticmethod
    def reconstructed(release_dir: Path, manifest: dict) -> bytes:
        chunks = []
        for item in manifest["files"]["data_shards"]:
            with gzip.open(release_dir / item["path"], "rb") as handle:
                chunks.append(handle.read())
        return b"".join(chunks)

    def test_release_shards_are_deterministic_and_reconstruct_source(self) -> None:
        builder = load_script(BUILD_SCRIPT, "release_builder_determinism")
        first_dir = self.work / "first"
        second_dir = self.work / "second"

        first = builder.build_release(self.source, first_dir, shard_count=2, sample_size=2)
        second = builder.build_release(self.source, second_dir, shard_count=2, sample_size=2)

        self.assertEqual(first["source_sha256"], second["source_sha256"])
        self.assertEqual(self.shard_bytes(first_dir, first), self.shard_bytes(second_dir, second))
        self.assertEqual(self.source.read_bytes(), self.reconstructed(first_dir, first))
        self.assertEqual([3, 2], [item["rows"] for item in first["files"]["data_shards"]])

    def test_manifest_records_counts_and_bounded_review_sample(self) -> None:
        builder = load_script(BUILD_SCRIPT, "release_builder_counts")
        release_dir = self.work / "release"

        manifest = builder.build_release(self.source, release_dir, shard_count=2, sample_size=3)

        self.assertEqual(5, manifest["counts"]["samples"])
        self.assertEqual(5, manifest["counts"]["parent_memories"])
        self.assertEqual(6, manifest["counts"]["atomic_memories"])
        self.assertEqual({"A": 1, "B": 2, "C": 3}, manifest["counts"]["labels"])
        sample_path = release_dir / manifest["files"]["review_sample"]["path"]
        self.assertEqual(3, len(sample_path.read_text(encoding="utf-8").splitlines()))

    def test_verify_release_rejects_modified_shard(self) -> None:
        builder = load_script(BUILD_SCRIPT, "release_builder_tamper")
        verifier = load_script(VERIFY_SCRIPT, "release_verifier_tamper")
        release_dir = self.work / "release"
        manifest = builder.build_release(self.source, release_dir, shard_count=2, sample_size=2)
        shard = release_dir / manifest["files"]["data_shards"][0]["path"]
        tampered = bytearray(shard.read_bytes())
        tampered[-1] ^= 1
        shard.write_bytes(tampered)

        with self.assertRaisesRegex(ValueError, "sha256"):
            verifier.verify_release(release_dir, expected=None)

    def test_rebuild_preserves_in_place_release_artifact(self) -> None:
        builder = load_script(BUILD_SCRIPT, "release_builder_in_place")
        release_dir = self.work / "release"
        release_dir.mkdir()
        readme = release_dir / "README.md"
        readme.write_text("# Review release\n", encoding="utf-8")

        manifest = builder.build_release(
            self.source,
            release_dir,
            shard_count=2,
            sample_size=2,
            artifacts={"README.md": readme},
        )

        self.assertEqual("# Review release\n", readme.read_text(encoding="utf-8"))
        self.assertEqual("README.md", manifest["files"]["artifacts"]["README.md"]["path"])


if __name__ == "__main__":
    unittest.main()
