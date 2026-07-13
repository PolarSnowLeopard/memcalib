# MemCalib v0.1 Construction Pipeline

## Overview

```text
public medical QA sources
  -> normalization
  -> deterministic eligibility and quality scoring
  -> exact and near deduplication
  -> source/topic/complexity stratified candidate pool
  -> grounded semantic source-QA gate
  -> strict-pass admission
  -> English memory-block and atomic-rubric construction
  -> schema and benchmark QC
  -> locked MemCalib v0.1 release
```

The pipeline distinguishes source admission from benchmark annotation. Deterministic source filtering does not assign A/B/C labels. Labels, atomic decomposition, construction targets, and rubrics are created only after a source record passes semantic QA.

## Stage Map

| Stage | Script | Purpose |
|---|---|---|
| Normalize | `pipeline/00_normalize_sources.py` | normalize locally downloaded sources |
| Raw quality | `pipeline/15_select_crk2_raw_seeds.py` | eligibility, score, dedup, stratification |
| Candidate pool | `pipeline/17_select_crk2_candidate_pool.py` | balanced 30k source pool |
| Semantic QA input | `pipeline/18_prepare_source_semantic_qc.py` | fixed six-dimension request construction |
| Semantic QA postprocess | `pipeline/19_post_source_semantic_qc.py` | evidence validation and decision parsing |
| Admission | `pipeline/21_select_source_semantic_admission.py` | strict-pass adaptive admission |
| Benchmark requests | `pipeline/10_prepare_crk2_generation.py` | locked English construction prompts |
| API execution | `pipeline/06_run_bailian_api.py` | resumable OpenAI-compatible runner |
| Benchmark postprocess | `pipeline/11_post_crk2_generation.py` | schema, language, and QC validation |
| Audit | `pipeline/12_build_canonical_audit_artifacts.py` | one-sample-per-page review materials |
| Statistics | `pipeline/24_analyze_crk2_formal_benchmark.py` | full release analysis |

Earlier numbered scripts are retained because they document prototype lineage. The formal v0.1 path begins with full normalization and uses stages 15 through 24.

## Fixed Source Selection

The source candidate pool contains 15,000 records from each source before semantic QA. Selection is deterministic under seed 42 and stratified by source, topic, and a source-observable construction-complexity proxy.

The 30,000-record semantic run produced a resolved set of 21,129 strict passes, 5,219 review records, 3,633 explicit rejects, and 19 residual invalid judgments. Construction admission selected 15,577 strict passes; no review record entered the formal construction run.

## Locked Construction

The formal English construction run uses:

- model: `qwen3.7-max` at the recorded run date;
- temperature: 0.2;
- target parent memory count: 3-6;
- output language: English;
- 15,577 admitted source records;
- prompt, config, implementation, request-order, and input hashes stored in the run lock.

After API and quality retries, 15,569 records were parseable and 15,528 passed final fixed-schema construction QC. The 41 final rejects used memory types outside the fixed enum.

## Reproducibility Boundary

Deterministic stages can be reproduced from the same source snapshots and configuration. LLM-dependent stages require the recorded prompt and a compatible model snapshot; exact regeneration may still vary if a mutable provider alias is used. The released JSONL and its SHA-256 are therefore the canonical benchmark artifact.

Full local intermediates remain excluded from Git. The private release contains the final data, summaries, audit pages, and sufficient provenance manifests to verify lineage without distributing API responses.

## Multi-domain Pilot Extension

The v0.2 internal pilot applies the same separation between source admission and benchmark annotation to OpenAssistant OASST1 and Magicoder OSS-Instruct. It adds the following reusable stages:

| Stage | Script | Purpose |
|---|---|---|
| Domain normalization | `pipeline/25_normalize_domain_sources.py` | normalize general-dialogue and coding sources while preserving license and source metadata |
| Semantic retry merge | `pipeline/26_merge_source_semantic_qc.py` | resolve evidence-grounding retries without admitting residual invalid rows |
| Construction repair | `pipeline/27_prepare_crk2_generation_repair.py` | repair only failed construction records while preserving successful API outputs |
| Pilot validation | `pipeline/28_validate_multidomain_benchmark.py` | verify row counts, IDs, domains, licenses, schema, rubric completeness, and evidence grounding |

The multi-domain construction prompt keeps the model-facing memory block non-atomic and applies A/B/C labels only to hidden atoms. Real memories must be grounded in source context or the current question. The reference answer is retained for task-coherence validation but is forbidden as a memory source. Every retained `raw_evidence` and atomic `evidence` value must be a contiguous source substring after whitespace normalization. Coding records whose question contains the reference solution at a near-complete level are rejected as trivialized tasks.

The pilot first selected 300 quality-controlled candidates per domain. After semantic-QC retry resolution, general dialogue contained 162 strict passes, 3 review records, and 135 rejects; coding contained 130 strict passes, 9 review records, 160 rejects, and 1 residual invalid record. Adaptive strict-only admission selected 122 records per domain to produce a final 100+100 review set. No review or invalid record entered construction.

The current pilot is an internal quality study rather than a locked benchmark expansion. Its release package records the generated artifacts and their hashes. A future large-scale run should freeze the source snapshots, prompt, model identifier, filter thresholds, and all implementation hashes before API execution.
