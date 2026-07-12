#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[2] / "pipeline"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
SELECTOR_SCRIPT = SCRIPT_DIR / "15_select_crk2_raw_seeds.py"
AUDIT_SCRIPT = SCRIPT_DIR / "16_build_raw_seed_audit.py"
UTILS_SCRIPT = SCRIPT_DIR / "utils.py"
CONFIG_PATH = SCRIPT_DIR / "config.json"


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def selection_config() -> dict:
    return {
        "schema_version": "crk2-raw-selection-v1",
        "scoring_version": "crk2-seed-quality-v1",
        "min_question_chars": 40,
        "max_question_chars": 2500,
        "min_answer_chars": 50,
        "max_answer_chars": 6000,
        "min_question_tokens": 8,
        "min_answer_tokens": 8,
        "min_english_letter_ratio": 0.75,
        "max_boilerplate_ratio": 0.65,
        "min_quality_score": 65,
        "near_duplicate_jaccard": 0.88,
        "topic_alpha": 0.5,
        "quality_weight_beta": 2.0,
        "complexity_targets": {"simple": 0.25, "medium": 0.5, "complex": 0.25},
    }


def rich_row(row_id: str = "rich-1", source: str = "source-a", topic: str = "digestive") -> dict:
    return {
        "id": row_id,
        "source_dataset": source,
        "source_split": "train",
        "source_index": 1,
        "topic": topic,
        "raw_question": (
            "I was diagnosed with diabetes five years ago and have taken metformin since then. "
            "My fasting glucose has recently risen to 9.2 mmol/L, and I prefer to avoid injections "
            "if another safe treatment is available. What should I discuss with my doctor?"
        ),
        "doctor_answer": (
            "Persistent fasting glucose at this level suggests that current control is inadequate. "
            "The clinician should review adherence, diet, kidney function, HbA1c, and the current dose, "
            "then discuss additional medication options and the circumstances in which insulin is needed."
        ),
    }


def eligible_stub(
    row_id: str,
    source: str,
    topic: str,
    complexity: str,
    score: int,
) -> dict:
    row = rich_row(row_id=row_id, source=source, topic=topic)
    row["raw_selection"] = {
        "hard_filter_pass": True,
        "hard_rejection_reasons": [],
        "score_pass": True,
        "eligible": True,
        "quality_score": score,
        "quality_components": {
            "question_informativeness": 20,
            "answer_substance": 20,
            "memory_suitability": 30,
            "cleanliness_coherence": 10,
        },
        "memory_signal_families": ["personal_entity", "temporal_history"],
        "seed_complexity": complexity,
        "dedup_status": "unique",
        "duplicate_cluster_id": None,
        "duplicate_of": None,
        "selection_status": "eligible",
    }
    return row


class RawSeedSelectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.selector = load_script(SELECTOR_SCRIPT, "raw_seed_selector")
        cls.audit = load_script(AUDIT_SCRIPT, "raw_seed_audit")
        cls.utils = load_script(UTILS_SCRIPT, "raw_seed_utils")

    def test_resolve_config_path_is_relative_to_config_file(self) -> None:
        config_path = Path("/tmp/project/med_rpeval_pipeline/config.json")

        resolved = self.utils.resolve_config_path(config_path, "../sources")

        self.assertEqual(Path("/tmp/project/sources").resolve(), resolved)
        self.assertEqual(Path("/absolute/data"), self.utils.resolve_config_path(config_path, "/absolute/data"))

    def test_config_defaults_to_portable_full_pool_selection(self) -> None:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

        self.assertEqual("..", config["source_root"])
        self.assertEqual("data", config["output_dir"])
        self.assertTrue(all(limit == 0 for limit in config["sampling"]["source_limits"].values()))
        self.assertEqual("crk2-raw-selection-v1", config["raw_selection"]["schema_version"])
        self.assertEqual(65, config["raw_selection"]["min_quality_score"])

    def test_assess_record_accepts_memory_rich_substantive_qa(self) -> None:
        assessed = self.selector.assess_record(rich_row(), selection_config())
        selection = assessed["raw_selection"]

        self.assertTrue(selection["hard_filter_pass"])
        self.assertTrue(selection["score_pass"])
        self.assertTrue(selection["eligible"])
        self.assertGreaterEqual(selection["quality_score"], 65)
        self.assertEqual(
            {
                "answer_substance",
                "cleanliness_coherence",
                "memory_suitability",
                "question_informativeness",
            },
            set(selection["quality_components"]),
        )
        self.assertTrue(
            {"personal_entity", "temporal_history", "treatment", "measurement", "preference_constraint"}
            <= set(selection["memory_signal_families"])
        )
        self.assertIn(selection["seed_complexity"], {"medium", "complex"})

    def test_high_quality_simple_record_is_not_penalized_for_one_signal_family(self) -> None:
        row = rich_row("simple-quality")
        row["raw_question"] = (
            "My forearm has a red patch that feels itchy and dry. It becomes more noticeable because the skin "
            "is irritated by washing, and if it spreads I would seek an examination. What could explain the "
            "patch, and which warning signs should prompt an in-person evaluation?"
        )
        row["doctor_answer"] = (
            "The description can fit dermatitis, although a clinician should inspect the area before confirming "
            "the cause. Use a gentle cleanser and moisturizer, avoid scratching, and arrange prompt assessment "
            "if the redness spreads, becomes painful, drains fluid, or is accompanied by fever."
        )

        assessed = self.selector.assess_record(row, selection_config())
        selection = assessed["raw_selection"]

        self.assertEqual(["personal_entity"], selection["memory_signal_families"])
        self.assertEqual("simple", selection["seed_complexity"])
        self.assertTrue(selection["eligible"])
        self.assertGreaterEqual(selection["quality_score"], 65)

    def test_assess_record_rejects_generic_question_without_memory_signal(self) -> None:
        row = rich_row("generic")
        row["raw_question"] = (
            "Please explain how diabetes is generally treated in adults and what complications it may cause."
        )

        assessed = self.selector.assess_record(row, selection_config())

        self.assertFalse(assessed["raw_selection"]["hard_filter_pass"])
        self.assertIn("no_memory_signal", assessed["raw_selection"]["hard_rejection_reasons"])

    def test_assess_record_rejects_narrative_without_question_intent(self) -> None:
        row = rich_row("unfinished")
        row["raw_question"] = (
            "I am 35 years old and underwent bilateral varicocele surgery four months ago. "
            "For the following three months I was taking the medication listed below."
        )

        assessed = self.selector.assess_record(row, selection_config())

        self.assertFalse(assessed["raw_selection"]["hard_filter_pass"])
        self.assertIn("missing_question_intent", assessed["raw_selection"]["hard_rejection_reasons"])

    def test_assess_record_rejects_boilerplate_dominated_answer(self) -> None:
        row = rich_row("boilerplate")
        row["doctor_answer"] = (
            "Hello and welcome. Thank you for your query. Hope this helps. Please contact us again "
            "if you have another query. Thanks for choosing our service. Regards and take care."
        )

        assessed = self.selector.assess_record(row, selection_config())

        self.assertFalse(assessed["raw_selection"]["hard_filter_pass"])
        self.assertIn("answer_boilerplate_dominated", assessed["raw_selection"]["hard_rejection_reasons"])

    def test_mark_duplicate_records_keeps_highest_quality_exact_match(self) -> None:
        lower = self.selector.assess_record(rich_row("lower"), selection_config())
        higher_input = rich_row("higher")
        higher_input["doctor_answer"] += " Urgent symptoms such as vomiting or confusion require prompt review."
        higher = self.selector.assess_record(higher_input, selection_config())
        lower["raw_selection"]["quality_score"] = 70
        higher["raw_selection"]["quality_score"] = 85

        deduplicated = self.selector.mark_duplicate_records(
            [lower, higher], threshold=selection_config()["near_duplicate_jaccard"]
        )
        by_id = {row["id"]: row for row in deduplicated}

        self.assertEqual("representative", by_id["higher"]["raw_selection"]["dedup_status"])
        self.assertTrue(by_id["higher"]["raw_selection"]["eligible"])
        self.assertEqual("duplicate", by_id["lower"]["raw_selection"]["dedup_status"])
        self.assertEqual("higher", by_id["lower"]["raw_selection"]["duplicate_of"])
        self.assertFalse(by_id["lower"]["raw_selection"]["eligible"])

    def test_mark_duplicate_records_detects_minor_near_duplicate(self) -> None:
        first = self.selector.assess_record(rich_row("near-a"), selection_config())
        second_input = rich_row("near-b")
        second_input["raw_question"] = second_input["raw_question"].replace("recently risen", "lately risen")
        second = self.selector.assess_record(second_input, selection_config())

        deduplicated = self.selector.mark_duplicate_records(
            [first, second], threshold=selection_config()["near_duplicate_jaccard"]
        )

        self.assertEqual(1, sum(row["raw_selection"]["eligible"] for row in deduplicated))
        self.assertEqual(
            {"duplicate", "representative"},
            {row["raw_selection"]["dedup_status"] for row in deduplicated},
        )

    def test_near_duplicate_matching_does_not_merge_similarity_chain(self) -> None:
        common = "alpha bravo charlie delta echo foxtrot golf hotel"
        first = eligible_stub("chain-a", "source-a", "general_other", "medium", 100)
        middle = eligible_stub("chain-b", "source-a", "general_other", "medium", 90)
        last = eligible_stub("chain-c", "source-a", "general_other", "medium", 80)
        first["raw_question"] = f"{common} india juliet"
        middle["raw_question"] = f"{common} india kilo"
        last["raw_question"] = f"{common} lima kilo"

        deduplicated = self.selector.mark_duplicate_records([first, middle, last], threshold=0.8)
        by_id = {row["id"]: row for row in deduplicated}

        self.assertEqual("chain-a", by_id["chain-b"]["raw_selection"]["duplicate_of"])
        self.assertTrue(by_id["chain-c"]["raw_selection"]["eligible"])
        self.assertNotEqual(
            by_id["chain-a"]["raw_selection"]["duplicate_cluster_id"],
            by_id["chain-c"]["raw_selection"]["duplicate_cluster_id"],
        )

    def test_select_stratified_is_source_balanced_and_deterministic(self) -> None:
        rows = []
        for source in ("source-a", "source-b"):
            for index in range(8):
                topic = "rare" if index == 0 else "common"
                complexity = ("simple", "medium", "complex")[index % 3]
                rows.append(eligible_stub(f"{source}-{index}", source, topic, complexity, 90 - index))

        first = self.selector.select_stratified(rows, target=8, seed=42, config=selection_config())
        second = self.selector.select_stratified(rows, target=8, seed=42, config=selection_config())

        self.assertEqual([row["id"] for row in first], [row["id"] for row in second])
        self.assertEqual(4, sum(row["source_dataset"] == "source-a" for row in first))
        self.assertEqual(4, sum(row["source_dataset"] == "source-b" for row in first))
        self.assertEqual({"source-a", "source-b"}, {row["source_dataset"] for row in first if row["topic"] == "rare"})
        self.assertEqual(list(range(1, 9)), [row["raw_selection"]["selection_rank"] for row in first])

    def test_selection_uses_seeded_quality_weighting_instead_of_top_score_cutoff(self) -> None:
        rows = [
            eligible_stub(f"weighted-{index}", "source-a", "digestive", "medium", 65 + index)
            for index in range(36)
        ]

        selected = self.selector.select_stratified(rows, target=10, seed=42, config=selection_config())
        selected_scores = {row["raw_selection"]["quality_score"] for row in selected}

        self.assertNotEqual(set(range(91, 101)), selected_scores)
        self.assertTrue(all(score >= 65 for score in selected_scores))
        self.assertTrue(all("quality_sampling_weight" in row["raw_selection"] for row in selected))

    def test_duplicate_progress_callback_reports_completion(self) -> None:
        events = []
        rows = [eligible_stub("progress-a", "source-a", "digestive", "medium", 80)]

        self.selector.mark_duplicate_records(rows, threshold=0.88, progress_every=1, progress_callback=events.append)

        self.assertEqual("deduplicate", events[-1]["stage"])
        self.assertEqual(1, events[-1]["done"])
        self.assertEqual(1, events[-1]["total"])

    def test_manifest_records_hashes_counts_and_distributions(self) -> None:
        rows = [eligible_stub("one", "source-a", "digestive", "medium", 80)]
        selected = self.selector.select_stratified(rows, target=1, seed=42, config=selection_config())
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.jsonl"
            input_path.write_text(json.dumps(rich_row(), ensure_ascii=False) + "\n", encoding="utf-8")
            manifest = self.selector.build_manifest(
                assessed_rows=rows,
                eligible_rows=rows,
                selected_rows=selected,
                input_path=input_path,
                target=1,
                seed=42,
                config=selection_config(),
                config_path=CONFIG_PATH,
            )

        self.assertEqual(64, len(manifest["input"]["sha256"]))
        self.assertEqual(64, len(manifest["implementation"]["config_sha256"]))
        self.assertEqual(1, manifest["counts"]["selected"])
        self.assertEqual({"source-a": 1}, manifest["distributions"]["selected"]["source_dataset"])
        self.assertEqual("crk2-raw-selection-v1", manifest["schema_version"])
        self.assertEqual(0, manifest["duplicates"]["clusters"])
        self.assertEqual("seeded_exponential_quality_weighting", manifest["selection_algorithm"]["within_stratum"])

    def test_audit_html_has_one_active_page_and_keyboard_navigation(self) -> None:
        rows = [
            eligible_stub("one", "source-a", "digestive", "medium", 80),
            eligible_stub("two", "source-b", "cardio", "complex", 85),
        ]
        rows = self.selector.select_stratified(rows, target=2, seed=42, config=selection_config())
        manifest = {
            "schema_version": "crk2-raw-selection-v1",
            "counts": {"selected": 2},
            "parameters": {"seed": 42, "target": 2, "min_quality_score": 65},
        }

        html = self.audit.build_html(rows, manifest)

        self.assertEqual(1, html.count('class="sample-page active"'))
        self.assertEqual(1, html.count('class="sample-page"'))
        self.assertIn("Model-facing source question", html)
        self.assertIn("Quality components", html)
        self.assertIn("Memory-signal families", html)
        self.assertIn("event.key === 'ArrowRight'", html)
        self.assertIn("event.key === 'ArrowLeft'", html)


if __name__ == "__main__":
    unittest.main()
