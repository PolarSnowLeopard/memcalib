# CRK-2 Memory Benchmark Construction Pipeline

This directory converts public dialogue/QA sources into CRK-2 memory-use benchmark records. The current source release uses:

- `OpenMed/MedDialog`
- `lavita/ChatDoctor-HealthCareMagic-100k`

The source files remain local and are excluded from Git.

## Current Data Flow

```text
full source normalization
  -> deterministic raw eligibility and feature extraction
  -> exact/near deduplication
  -> source/topic/seed-complexity stratified preselection
  -> semantic source-QA quality gate
  -> CRK-2 LLM construction in English
  -> schema and rule validation
  -> benchmark-level QC and manual audit
  -> final split
```

The deterministic selector does not assign memory A/B/C labels. It only decides whether a source record is a suitable input candidate. Memory blocks, atomic memories, labels, construction targets, and judge rubrics are created in the CRK-2 construction stage.

## Environment

The normalization step reads the ChatDoctor parquet source and therefore requires both pandas and a parquet engine.

```bash
PY=/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
$PY -m pip install -r pipeline/requirements.txt
```

All paths in `config.json` are resolved relative to that configuration file. No user-specific absolute path is required.

## Raw Seed Selection

Normalize every locally available record that passes broad schema and length checks. Source limits are zero by default, so this step does not randomly cap either source.

```bash
$PY pipeline/00_normalize_sources.py
```

This writes the ignored full pool to `data/normalized_raw_full.jsonl` and a tracked statistical summary to `data/normalized_raw_full.stats.json`.

Run deterministic quality filtering, scoring, representative-based deduplication, and stratified selection:

```bash
$PY pipeline/15_select_crk2_raw_seeds.py \
  --target 100 \
  --seed 42 \
  --progress-every 25000
```

Outputs:

- `data/crk2_raw_quality_audit.jsonl`: all normalized rows with features, score components, rejection reasons, and duplicate status; ignored by Git.
- `data/crk2_raw_eligible_pool.jsonl`: rows that pass hard rules, score threshold, and deduplication; ignored by Git.
- `data/crk2_selected_raw_seeds_100.jsonl`: source/topic/seed-complexity stratified preselection.
- `data/crk2_raw_selection_100.manifest.json`: input and output hashes, versions, parameters, rejection counts, duplicate statistics, score summaries, and distributions.

Build the one-sample-per-page review artifact:

```bash
$PY pipeline/16_build_raw_seed_audit.py \
  --input pipeline/data/crk2_selected_raw_seeds_100.jsonl \
  --manifest pipeline/data/crk2_raw_selection_100.manifest.json \
  --output pipeline/data/crk2_raw_seed_audit_100.html
```

Use Left/Right Arrow to switch samples. `seed_complexity` is a construction-complexity proxy based on observable source context; it is not the final benchmark difficulty label.

Once the eligible-pool version has been reviewed and fixed, create the large source candidate pool without rerunning deterministic filtering:

```bash
$PY pipeline/17_select_crk2_candidate_pool.py \
  --per-source 15000 \
  --seed 42 \
  --progress-every 50000
```

This verifies the eligible-pool hash and the parent selector/config lineage before sampling. It writes the ignored 30k pool to `data/crk2_source_candidate_pool_30000.jsonl` and its tracked lineage and distribution report to `data/crk2_source_candidate_pool_30000.manifest.json`. The pool contains exactly 15,000 records from each current source; source equality is a benchmark coverage choice rather than an estimate of the sources' natural frequency.

## Source Semantic QC

Prepare a stratified 100-record calibration set, run the fixed six-dimension rubric, validate grounded evidence, and build the one-record-per-page audit:

```bash
$PY pipeline/18_prepare_source_semantic_qc.py --limit 100 --seed 42

DASHSCOPE_API_KEY="$(cat ~/.config/crk2/dashscope_api_key)" \
$PY pipeline/06_run_bailian_api.py \
  --input pipeline/data/crk2_source_semantic_qc_input_100.jsonl \
  --output pipeline/data/crk2_source_semantic_qc_result_100.jsonl \
  --failed pipeline/data/crk2_source_semantic_qc_failed_100.jsonl \
  --max-workers 16 --rpm 60 --timeout 300 --progress-every 1
```

The calibrated result contains 68 `strict_pass`, 22 `review`, 10 `reject`, and 0 invalid outputs. The audit page is `data/crk2_source_semantic_qc_audit_100.html`; use Left/Right Arrow to switch records. The full 30k request file is reproducibly prepared with `--limit 30000`, but the API run should start only after the calibration audit is accepted.

After the full semantic run, apply the adaptive admission rule:

```bash
$PY pipeline/21_select_source_semantic_admission.py \
  --input pipeline/data/crk2_source_semantic_qc_30000.jsonl \
  --final-target 15000 \
  --generation-successes 100 \
  --generation-total 100
```

With a 100/100 construction-and-post-QC pilot, the conservative admission target is 15,577. If enough strict passes remain, review records are excluded and retained only as a reserve. If strict capacity is insufficient, review records are routed to secondary adjudication; explicit rejects are never recovered.

The completed 30k run produced 29,477 valid judgments and 523 evidence-grounding invalids. One targeted retry recovered 504 judgments; 19 residual invalids were retained for audit and excluded. The resolved pool contains 21,129 strict passes, 5,219 review records, and 3,633 explicit rejects. Adaptive admission selected 15,577 strict passes with 7,789 MedDialog and 7,788 ChatDoctor records, so no review record was used.

## CRK-2 Construction

Prepare generation requests only from the selected seed file. The 100-sample review run uses Chinese generated fields for manual inspection; the final benchmark uses English.

```bash
$PY pipeline/10_prepare_crk2_generation.py \
  --input pipeline/data/crk2_selected_raw_seeds_100.jsonl \
  --output pipeline/data/crk2_canonical_generation_input_100.jsonl \
  --limit 100 \
  --output-language zh
```

For the final release, use the selected full-scale seed file and `--output-language en`. API execution is handled by `06_run_bailian_api.py`, which supports request fingerprints, resume, retries, worker concurrency, rate limits, and live progress.

The locked English construction release uses the 15,577-record strict-pass admission file:

```bash
$PY pipeline/10_prepare_crk2_generation.py \
  --input pipeline/data/crk2_source_semantic_admitted_15577.jsonl \
  --input-manifest pipeline/data/crk2_source_semantic_admission_15577.manifest.json \
  --output pipeline/data/crk2_canonical_generation_input_en_15577.jsonl \
  --manifest pipeline/data/crk2_canonical_generation_input_en_15577.manifest.json \
  --limit 15577 --seed 42 --target-memory-count 3-6 --output-language en
```

`data/crk2_canonical_generation_run_en_15577.lock.json` freezes the request, lineage, prompt, implementation, model, and planned execution hashes before API submission.

## Quality Boundary

Deterministic source filtering can verify structure, language, noise, observable memory signals, score thresholds, duplicates, and sampling distributions. It cannot reliably establish semantic answer relevance from lexical overlap alone. Source-QA relevance must therefore be checked by a fixed semantic rubric before a preselected source record is admitted to large-scale CRK-2 construction.

The formal selector design is recorded in `docs/superpowers/specs/2026-07-10-crk2-raw-seed-selection-design.md`.
