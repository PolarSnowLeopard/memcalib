#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent / "08_build_memory_abc_coherent_seed.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("memory_abc_coherent_seed", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class MemoryAbcCoherentSeedTest(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = load_builder()

    def test_generate_sample_has_coherent_theme_and_mixed_atom_labels(self) -> None:
        sample = self.builder.generate_sample(0)

        self.assertEqual("coherent_mixed_block", sample["diagnostic_tags"][0])
        self.assertTrue(sample["memory_block_theme"])
        self.assertEqual({"A", "B", "C"}, {atom["label"] for atom in sample["atoms"]})
        self.assertTrue(all(atom["coherence_role"] for atom in sample["atoms"]))
        self.assertTrue(all(atom["theme"] == sample["memory_block_theme"] for atom in sample["atoms"]))

    def test_generate_samples_is_deterministic_and_balanced_across_templates(self) -> None:
        first = self.builder.generate_samples(limit=24)
        second = self.builder.generate_samples(limit=24)

        self.assertEqual(first, second)
        self.assertEqual(24, len(first))
        self.assertGreaterEqual(len({sample["memory_block_theme"] for sample in first}), 8)
        self.assertTrue(all(sample["block_composition"]["mixed_label"] for sample in first))

    def test_build_summary_counts_atom_level_labels(self) -> None:
        samples = self.builder.generate_samples(limit=3)
        summary = self.builder.summarize(samples)

        self.assertEqual(3, summary["total_samples"])
        self.assertEqual(sum(len(sample["atoms"]) for sample in samples), summary["total_atoms"])
        self.assertEqual(summary["label_counts"]["A"], 3)
        self.assertEqual(summary["label_counts"]["C"], 3)


if __name__ == "__main__":
    unittest.main()
