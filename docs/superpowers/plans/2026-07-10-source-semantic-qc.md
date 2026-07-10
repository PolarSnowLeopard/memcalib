# Source QA Semantic QC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and calibrate a grounded semantic quality gate for source question-answer pairs before CRK-2 construction.

**Architecture:** A preparation script selects a stratified calibration subset and emits fixed-schema Bailian requests. A postprocessor validates grounded evidence and maps model judgments to `strict_pass`, `review`, `reject`, or `invalid`. A static audit renderer shows one source record at a time, and a calibration summary estimates pass rates and adaptive capacity for a 15,000-record final benchmark.

**Tech Stack:** Python 3 standard library, existing JSONL utilities, existing Bailian runner, `unittest`, static HTML/CSS/JavaScript.

## Global Constraints

- Schema version is `crk2-source-semantic-qc-v1`.
- Every dimension uses `pass`, `reject`, or `uncertain` and includes grounded evidence.
- Explicit rejects are never automatically rescued.
- Uncertain records are reviewed only when strict-pass capacity is insufficient.
- Final benchmark target is 15,000 usable records.
- The 30,000-record API run is blocked until the 100-record calibration is reviewed.

---

### Task 1: Calibration Request Preparation

**Files:**
- Create: `med_rpeval_pipeline/prompts/verify_source_qa_semantic_quality.txt`
- Create: `med_rpeval_pipeline/18_prepare_source_semantic_qc.py`
- Create: `med_rpeval_pipeline/test_source_semantic_qc.py`

**Interfaces:**
- Produces: `select_calibration_rows(rows, limit, seed) -> list[dict]`
- Produces: `build_request(row, index, prompt_template) -> dict`

- [ ] Write failing tests that require 50/50 source coverage, all available topic/complexity strata, exact schema instructions, and preserved source fields.
- [ ] Run `python -m unittest med_rpeval_pipeline/test_source_semantic_qc.py -v` and confirm missing-module failure.
- [ ] Implement deterministic calibration selection and request construction.
- [ ] Re-run the focused tests and require all request-preparation tests to pass.

### Task 2: Grounded Result Validation and Adaptive State

**Files:**
- Create: `med_rpeval_pipeline/19_post_source_semantic_qc.py`
- Modify: `med_rpeval_pipeline/test_source_semantic_qc.py`

**Interfaces:**
- Produces: `validate_judgment(judgment, params) -> list[str]`
- Produces: `classify_judgment(judgment) -> str`
- Produces: `wilson_lower_bound(successes, total, z=1.959963984540054) -> float`

- [ ] Write failing tests for strict pass, uncertain review, explicit reject, ungrounded evidence, invalid schema, and Wilson lower bounds.
- [ ] Run focused tests and confirm each failure is caused by missing behavior.
- [ ] Implement schema validation, evidence grounding, classification, retry output, and summary rates.
- [ ] Re-run focused and existing pipeline tests.

### Task 3: One-Sample Calibration Audit

**Files:**
- Create: `med_rpeval_pipeline/20_build_source_semantic_qc_audit.py`
- Modify: `med_rpeval_pipeline/test_source_semantic_qc.py`

**Interfaces:**
- Produces: `build_html(records, summary) -> str`

- [ ] Write a failing test requiring one active sample, all six dimensions, exact evidence, final state, and ArrowLeft/ArrowRight navigation.
- [ ] Run the focused test and confirm the renderer is missing.
- [ ] Implement the keyboard audit renderer and summary header.
- [ ] Re-run focused tests and structural HTML checks.

### Task 4: 100-Record Bailian Calibration

**Files:**
- Generate: `med_rpeval_pipeline/data/crk2_source_semantic_qc_input_100.jsonl`
- Generate: `med_rpeval_pipeline/data/crk2_source_semantic_qc_result_100.jsonl`
- Generate: `med_rpeval_pipeline/data/crk2_source_semantic_qc_100.*`

**Interfaces:**
- Consumes: fixed 30k candidate pool and local DashScope key
- Produces: calibrated pass/review/reject rates and an inspectable HTML artifact

- [ ] Prepare 100 stratified requests with seed 42.
- [ ] Run the existing Bailian runner with 16 workers, 60 RPM, 300-second timeout, and live progress.
- [ ] Parse results, retry only invalid API/model outputs, and build the audit page.
- [ ] Verify manifests, counts, source/topic/complexity coverage, grounded evidence rates, all tests, and `git diff --check`.
