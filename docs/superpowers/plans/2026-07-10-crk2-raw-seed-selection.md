# CRK-2 Raw Seed Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, auditable raw-seed quality filtering and stratified selection stage that can be validated on 100 selected records and reused unchanged for 10,000 or more.

**Architecture:** Source normalization emits the full technically valid pool. A focused selector module extracts features, applies hard filters, scores candidates, deduplicates questions, allocates hierarchical strata, and writes audit/eligible/selected JSONL plus a versioned manifest. A separate renderer turns the selected JSONL into a keyboard-navigable one-sample audit page.

**Tech Stack:** Python 3 standard library, existing JSONL utilities, `unittest`, static HTML/CSS/JavaScript.

## Global Constraints

- Do not call an external LLM or API in raw-seed selection.
- Keep every threshold and weight in `med_rpeval_pipeline/config.json`.
- Preserve original source question and answer text in every downstream seed.
- Use fixed seeds and stable identifiers for all tie-breaking.
- Treat seed complexity as a construction proxy, not final benchmark difficulty.
- Write SHA-256 hashes and distribution summaries to the run manifest.

---

### Task 1: Portable Full-Pool Normalization

**Files:**
- Modify: `med_rpeval_pipeline/utils.py`
- Modify: `med_rpeval_pipeline/00_normalize_sources.py`
- Modify: `med_rpeval_pipeline/config.json`
- Modify: CRK-2 and legacy entry scripts that resolve `output_dir`
- Test: `med_rpeval_pipeline/test_raw_seed_selection.py`

**Interfaces:**
- Produces: `resolve_config_path(config_path: Path, value: str) -> Path`
- Produces: full normalized JSONL when source limits are zero

- [ ] Write a failing test for config-relative path resolution and zero source limits.
- [ ] Run the focused test and confirm the expected failure.
- [ ] Implement portable path resolution and full-pool defaults.
- [ ] Run the focused test and existing pipeline tests.

### Task 2: Candidate Quality Model and Deduplication

**Files:**
- Create: `med_rpeval_pipeline/15_select_crk2_raw_seeds.py`
- Test: `med_rpeval_pipeline/test_raw_seed_selection.py`

**Interfaces:**
- Produces: `assess_record(row, config) -> dict`
- Produces: `mark_duplicate_records(records, threshold) -> list[dict]`

- [ ] Write failing tests for signal extraction, hard rejection, component scores, and duplicate representatives.
- [ ] Run the focused tests and confirm failures are caused by missing behavior.
- [ ] Implement canonicalization, features, scoring, hard filters, and deterministic exact/near deduplication.
- [ ] Run the focused tests until green, then refactor without changing behavior.

### Task 3: Hierarchical Stratified Selection and Manifest

**Files:**
- Modify: `med_rpeval_pipeline/15_select_crk2_raw_seeds.py`
- Test: `med_rpeval_pipeline/test_raw_seed_selection.py`

**Interfaces:**
- Produces: `select_stratified(records, target, seed, config) -> list[dict]`
- Produces: quality audit, eligible pool, selected seeds, and manifest files

- [ ] Write failing tests for even source quotas, square-root topic smoothing, complexity proportions, deterministic output, and manifest hashes.
- [ ] Run the focused tests and confirm expected failures.
- [ ] Implement capacity-aware quota allocation, quality-first selection, deterministic fallback, summaries, and file hashing.
- [ ] Run focused and existing tests.

### Task 4: One-Sample Audit Page

**Files:**
- Create: `med_rpeval_pipeline/16_build_raw_seed_audit.py`
- Test: `med_rpeval_pipeline/test_raw_seed_selection.py`

**Interfaces:**
- Produces: `build_html(records, manifest) -> str`

- [ ] Write a failing test for one visible sample, complete quality fields, and ArrowLeft/ArrowRight navigation.
- [ ] Run the focused test and confirm the missing renderer failure.
- [ ] Implement the static audit page with readable score and signal explanations.
- [ ] Run the focused test and inspect generated HTML structure.

### Task 5: Full Local Pool and 100-Seed Validation Run

**Files:**
- Modify: `med_rpeval_pipeline/README.md`
- Generate, ignored: full normalized pool and quality intermediates under `med_rpeval_pipeline/data/`
- Generate: 100-seed manifest and audit HTML under `med_rpeval_pipeline/data/`

**Interfaces:**
- Consumes: local MedDialog and ChatDoctor source files
- Produces: an inspectable 100-seed preselection artifact ready for user review

- [ ] Normalize all locally available records with no source cap.
- [ ] Run the selector with target 100 and fixed seed 42.
- [ ] Build the one-sample audit HTML.
- [ ] Verify counts, uniqueness, hashes, rejection reasons, and source/topic/complexity distributions.
- [ ] Run all relevant tests and `git diff --check`.
