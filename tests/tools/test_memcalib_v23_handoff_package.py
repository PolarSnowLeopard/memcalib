from __future__ import annotations

import gzip
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_SCRIPT = REPO_ROOT / "tools" / "package_memcalib_v23_handoff.py"


def load_script():
    spec = importlib.util.spec_from_file_location(
        "memcalib_v23_handoff_package", PACKAGE_SCRIPT
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {PACKAGE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MemCalibV23HandoffPackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.release = self.root / "release"
        self.release.mkdir()
        self.dataset = self.release / "memcalib_v23_multidomain_benchmark_15000.jsonl"
        with self.dataset.open("w", encoding="utf-8") as stream:
            for index in range(15000):
                stream.write(json.dumps({"id": f"record-{index}"}) + "\n")

        for name in (
            "memcalib_v23_multidomain_benchmark_15000.manifest.json",
            "memcalib_v23_multidomain_benchmark_15000.statistics.json",
        ):
            (self.release / name).write_text("{}\n", encoding="utf-8")
        (self.release / "memcalib_v23_multidomain_benchmark_review.html").write_text(
            "<!doctype html><title>review</title>\n", encoding="utf-8"
        )

        docs = self.root / "docs" / "archive" / "versions"
        v21_reports = docs / "v2.1" / "reports"
        v22_reports = docs / "v2.2" / "reports"
        v23 = docs / "v2.3"
        v23_reports = v23 / "reports"
        for reports in (v21_reports, v22_reports, v23_reports):
            reports.mkdir(parents=True)
        (self.root / "DATA_CARD.md").write_text("# data card\n", encoding="utf-8")
        (self.root / "NOTICE.md").write_text("# notice\n", encoding="utf-8")
        (v23 / "MEMCALIB_V23_COAUTHOR_HANDOFF.md").write_text(
            "# handoff\n", encoding="utf-8"
        )
        (v23 / "benchmark-schema-v2.3.md").write_text(
            "# schema\n", encoding="utf-8"
        )
        report_paths = (
            v23_reports / "memcalib-v23-composite-block-revision.html",
            v22_reports / "memcalib-v22-longtail-revision.html",
            v21_reports / "memcalib-v21-dataset-construction-methodology.html",
        )
        for path in report_paths:
            path.write_text(
                f"<!doctype html><title>{path.name}</title>\n", encoding="utf-8"
            )

        self.module = load_script()
        self.module.ROOT = self.root
        self.module.RELEASE_DIR = self.release
        self.module.EXPECTED_SHA256 = self.module.sha256_file(self.dataset)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_package_is_deterministic_and_reconstructs_dataset(self) -> None:
        first = self.module.build_package(self.dataset, self.root / "first")
        second = self.module.build_package(self.dataset, self.root / "second")

        first_zip = self.root / "first" / first["zip"]["path"]
        second_zip = self.root / "second" / second["zip"]["path"]
        self.assertEqual(first_zip.read_bytes(), second_zip.read_bytes())
        self.assertEqual("dataset_complete_v23", first["status"])
        self.assertEqual(15000, first["source_dataset"]["rows"])

        compressed = (
            self.root
            / "first"
            / self.module.PACKAGE_NAME
            / "data"
            / "memcalib-v2.3-multidomain-15000.jsonl.gz"
        )
        with gzip.open(compressed, "rb") as stream:
            self.assertEqual(self.dataset.read_bytes(), stream.read())

        with zipfile.ZipFile(first_zip) as archive:
            names = archive.namelist()
            self.assertEqual(sorted(names), names)
            self.assertTrue(
                all(
                    item.date_time == self.module.FIXED_ZIP_TIME
                    for item in archive.infolist()
                )
            )
            prefix = f"{self.module.PACKAGE_NAME}/"
            self.assertIn(f"{prefix}README.md", names)
            self.assertIn(f"{prefix}DATA_CARD.md", names)
            self.assertIn(f"{prefix}NOTICE.md", names)
            self.assertIn(f"{prefix}docs/benchmark-schema-v2.3.md", names)
            self.assertIn(
                f"{prefix}docs/reports/memcalib-v23-composite-block-revision.html",
                names,
            )
            self.assertIn(f"{prefix}review/record-review.html", names)

    def test_rejects_wrong_dataset_row_count(self) -> None:
        short = self.release / "short.jsonl"
        short.write_text('{"id":"only-one"}\n', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "expected 15000 rows"):
            self.module.build_package(short, self.root / "wrong-size")

    def test_rejects_wrong_dataset_hash(self) -> None:
        self.module.EXPECTED_SHA256 = "0" * 64
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            self.module.build_package(self.dataset, self.root / "wrong-hash")


if __name__ == "__main__":
    unittest.main()
