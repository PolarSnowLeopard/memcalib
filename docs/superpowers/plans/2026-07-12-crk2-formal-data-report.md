# CRK-2 Formal Dataset Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible statistical analysis and a polished self-contained HTML report for the complete 15,528-sample formal CRK-2 benchmark.

**Architecture:** A Python script streams the formal JSONL, computes bounded aggregate datasets, reconciles them against the locked summary, and writes a canonical Data Analytics report artifact. The local Data Analytics portable packager validates the artifact, embeds the reader and chart runtime, and performs browser QA before publishing the single HTML file.

**Tech Stack:** Python 3 from the Codex runtime, standard-library JSON/statistics collections, Data Analytics canonical artifact schema, Node.js portable report packager.

## Global Constraints

- Do not invoke Conda or a Conda-managed Python executable.
- Use `/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`.
- Recompute all claims from `med_rpeval_pipeline/data/crk2_canonical_memory_benchmark_en_15528.jsonl`.
- Keep the artifact snapshot below 2,000 rows per dataset and 3 MB total.
- Deliver one self-contained HTML without CDN, server, or sibling runtime files.
- Use descriptive claims only; do not present causal or inferential conclusions.

---

### Task 1: Streaming Aggregate Engine

**Files:**
- Create: `med_rpeval_pipeline/24_analyze_crk2_formal_benchmark.py`
- Create: `med_rpeval_pipeline/test_formal_benchmark_analysis.py`

**Interfaces:**
- Consumes: benchmark JSONL, rejected JSONL, final summary, run lock.
- Produces: `analyze_benchmark(paths: AnalysisPaths) -> dict[str, Any]` and JSON-safe aggregate datasets.

- [ ] **Step 1: Write failing tests for quantiles and sample-level aggregation**

```python
def test_quantile_uses_linear_interpolation():
    assert quantile([1, 2, 3, 4], 0.5) == 2.5

def test_analyze_sample_counts_mixed_parent_and_labels():
    state = new_state()
    update_state(state, FIXTURE_SAMPLE)
    result = finalize_state(state)
    assert result["headline"]["samples"] == 1
    assert result["headline"]["mixed_parents"] == 1
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
PYTHONPATH=med_rpeval_pipeline /Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest med_rpeval_pipeline/test_formal_benchmark_analysis.py
```

Expected: failure because the analysis functions do not exist.

- [ ] **Step 3: Implement streaming counters, distributions, and reconciliation**

Implement `AnalysisPaths`, `new_state`, `update_state`, `quantile`, `distribution_summary`, `finalize_state`, and `analyze_benchmark`. Track sample/source/topic counts, parent and atom structure, A/B/C crosses, memory types, Hard-A families, text/rubric lengths, subtype cardinality, construction funnel, and QC checks.

- [ ] **Step 4: Run focused and full tests**

Expected: focused tests and the existing test suite pass.

### Task 2: Canonical Report Artifact

**Files:**
- Modify: `med_rpeval_pipeline/24_analyze_crk2_formal_benchmark.py`
- Modify: `med_rpeval_pipeline/test_formal_benchmark_analysis.py`
- Create: `med_rpeval_pipeline/data/crk2_formal_benchmark_analysis.snapshot.json`
- Create: `med_rpeval_pipeline/data/crk2_formal_benchmark_analysis.artifact.json`

**Interfaces:**
- Consumes: aggregate analysis dictionary.
- Produces: `build_artifact(analysis, generated_at) -> dict[str, Any]` with report manifest, bounded snapshot datasets, canonical sources, metric cards, charts, tables, and ordered narrative blocks.

- [ ] **Step 1: Write failing tests for artifact shape**

```python
def test_artifact_has_matching_title_and_chart():
    artifact = build_artifact(FIXTURE_ANALYSIS, "2026-07-12T00:00:00+08:00")
    assert artifact["manifest"]["blocks"][0]["body"].startswith("# " + artifact["manifest"]["title"])
    assert any(block["type"] == "chart" for block in artifact["manifest"]["blocks"])
```

- [ ] **Step 2: Verify RED, then implement the report reading path**

Include technical summary, construction funnel, source/topic coverage, atomization, labels and cross-distributions, Hard-A, text/rubric complexity, paper-ready tables, limitations, next steps, and reproducibility metadata.

- [ ] **Step 3: Generate the full aggregate and artifact files**

Run:

```bash
/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 med_rpeval_pipeline/24_analyze_crk2_formal_benchmark.py
```

Expected: reconciliation succeeds and both JSON outputs are written.

- [ ] **Step 4: Validate the complete artifact**

Call Data Analytics `validate_artifact` with the generated `manifest`, `snapshot`, and `sources`. Correct schema errors only through the validator until it passes.

### Task 3: Portable HTML Packaging And QA

**Files:**
- Create: `med_rpeval_pipeline/data/crk2_formal_benchmark_analysis_report.html`

**Interfaces:**
- Consumes: canonical artifact JSON.
- Produces: one portable HTML report.

- [ ] **Step 1: Package with the canonical local builder**

```bash
node /Users/zhaofanyu/.codex/plugins/cache/openai-curated-remote/data-analytics/0.2.8-13ceeea1f599/skills/build-report/scripts/deliver_portable_artifact.mjs \
  --input med_rpeval_pipeline/data/crk2_formal_benchmark_analysis.artifact.json \
  --output med_rpeval_pipeline/data/crk2_formal_benchmark_analysis_report.html
```

- [ ] **Step 2: Require a successful delivery receipt**

Expected: artifact validation passes, output is self-contained, and browser verification is `passed` or explicitly reported as `structural_only` if no compatible browser exists.

- [ ] **Step 3: Reconcile final file hashes and sizes**

Verify the artifact payload embedded in the HTML equals the canonical JSON and record SHA-256 values in the analysis snapshot.

### Task 4: Final Verification And Commit

**Files:**
- Modify: `.gitignore` only if large generated intermediates require exclusion.
- Commit: script, tests, bounded snapshot, artifact JSON, and report HTML.

**Interfaces:**
- Consumes: all prior outputs.
- Produces: reproducible repository state and user-facing report.

- [ ] **Step 1: Run the full repository test suite**

```bash
PYTHONPATH=med_rpeval_pipeline /Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover -s med_rpeval_pipeline -p 'test_*.py'
```

- [ ] **Step 2: Run data reconciliation checks**

Require 15,528 unique samples, 78,734 atomic memories, zero generated-language CJK violations, and exact agreement with the locked summary.

- [ ] **Step 3: Commit the report implementation and artifacts**

```bash
git add med_rpeval_pipeline/24_analyze_crk2_formal_benchmark.py med_rpeval_pipeline/test_formal_benchmark_analysis.py med_rpeval_pipeline/data/crk2_formal_benchmark_analysis.snapshot.json med_rpeval_pipeline/data/crk2_formal_benchmark_analysis.artifact.json med_rpeval_pipeline/data/crk2_formal_benchmark_analysis_report.html
git commit -m "Add CRK-2 formal dataset analysis report"
```
