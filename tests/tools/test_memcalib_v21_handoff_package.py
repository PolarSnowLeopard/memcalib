from __future__ import annotations

import gzip
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_SCRIPT = REPO_ROOT / "tools" / "package_memcalib_v21_handoff.py"


def load_script():
    spec = importlib.util.spec_from_file_location("memcalib_v21_handoff_package", PACKAGE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {PACKAGE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MemCalibV21HandoffPackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.release = self.root / "release"
        self.release.mkdir()
        self.dataset = self.release / "memcalib_v21_multidomain_benchmark_15000.jsonl"
        with self.dataset.open("w", encoding="utf-8") as stream:
            for index in range(15000):
                stream.write(json.dumps({"id": f"record-{index}"}) + "\n")

        for name in (
            "memcalib_v21_multidomain_benchmark_15000.manifest.json",
            "memcalib_v21_multidomain_benchmark_15000.statistics.json",
        ):
            (self.release / name).write_text("{}\n", encoding="utf-8")
        (self.release / "memcalib_v21_multidomain_benchmark_review.html").write_text(
            "<!doctype html><title>review</title>\n", encoding="utf-8"
        )

        docs = self.root / "docs"
        reports = docs / "reports"
        reports.mkdir(parents=True)
        (self.root / "README.md").write_text("# repository\n", encoding="utf-8")
        (self.root / "DATA_CARD.md").write_text("# data card\n", encoding="utf-8")
        (self.root / "NOTICE.md").write_text("# notice\n", encoding="utf-8")
        (docs / "benchmark-schema.md").write_text("# schema\n", encoding="utf-8")
        (docs / "construction-pipeline.md").write_text("# pipeline\n", encoding="utf-8")
        (docs / "evaluation_protocol_v2.1.md").write_text("# protocol\n", encoding="utf-8")
        (docs / "MEMCALIB_V2_COAUTHOR_HANDOFF.md").write_text("# handoff\n", encoding="utf-8")
        (reports / "memcalib-v21-dataset-construction-methodology.html").write_text(
            "<!doctype html><title>method</title>\n", encoding="utf-8"
        )

        self.evaluation = self.root / "evaluation"
        self.evaluation.mkdir()
        (self.evaluation / "README.md").write_text("# evaluation\n", encoding="utf-8")
        self.module = load_script()
        self.module.ROOT = self.root
        self.module.EVALUATION_DIR = self.evaluation

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def add_evaluation_files(self) -> None:
        for name in (
            "README.md",
            "answer-request.manifest.json",
            "answer-run.manifest.json",
            "judge-request.manifest.json",
            "judge-run.manifest.json",
            "metrics.json",
            "report.html",
            "release-manifest.json",
            "sample-ids.txt",
        ):
            (self.evaluation / name).write_text(f"{name}\n", encoding="utf-8")

    def test_complete_package_is_deterministic_and_reconstructs_dataset(self) -> None:
        self.add_evaluation_files()
        first = self.module.build_package(
            self.dataset, self.root / "first", require_evaluation=True
        )
        second = self.module.build_package(
            self.dataset, self.root / "second", require_evaluation=True
        )

        first_zip = self.root / "first" / first["zip"]["path"]
        second_zip = self.root / "second" / second["zip"]["path"]
        self.assertEqual(first_zip.read_bytes(), second_zip.read_bytes())
        self.assertEqual("complete", first["status"])
        self.assertEqual(15000, first["source_dataset"]["rows"])
        self.assertEqual(
            (self.root / "first" / first["external_manifest"]).read_bytes(),
            (self.root / "second" / second["external_manifest"]).read_bytes(),
        )
        expected_sha_line = f"{first['zip']['sha256']}  {first_zip.name}\n"
        self.assertEqual(
            expected_sha_line,
            (self.root / "first" / first["zip_sha256_file"]).read_text(encoding="ascii"),
        )

        compressed = (
            self.root
            / "first"
            / self.module.PACKAGE_NAME
            / "data"
            / "memcalib-v2.1-multidomain-15000.jsonl.gz"
        )
        with gzip.open(compressed, "rb") as stream:
            self.assertEqual(self.dataset.read_bytes(), stream.read())

        with zipfile.ZipFile(first_zip) as archive:
            names = archive.namelist()
            self.assertEqual(sorted(names), names)
            self.assertTrue(all(item.date_time == self.module.FIXED_ZIP_TIME for item in archive.infolist()))
            prefix = f"{self.module.PACKAGE_NAME}/"
            self.assertIn(f"{prefix}DATA_CARD.md", names)
            self.assertIn(f"{prefix}NOTICE.md", names)
            self.assertIn(f"{prefix}docs/benchmark-schema.md", names)
            self.assertIn(f"{prefix}evaluation/README.md", names)
            self.assertIn(
                f"{prefix}evaluation/releases/memcalib-v21-multidomain-500-seven-models/README.md",
                names,
            )

    def test_required_evaluation_gate_reports_missing_files(self) -> None:
        with self.assertRaisesRegex(FileNotFoundError, "evaluation release is incomplete"):
            self.module.build_package(
                self.dataset, self.root / "incomplete", require_evaluation=True
            )

    def test_rejects_wrong_dataset_row_count(self) -> None:
        short = self.release / "short.jsonl"
        short.write_text('{"id":"only-one"}\n', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "expected 15000 dataset rows"):
            self.module.build_package(
                short, self.root / "wrong-size", require_evaluation=False
            )


if __name__ == "__main__":
    unittest.main()
