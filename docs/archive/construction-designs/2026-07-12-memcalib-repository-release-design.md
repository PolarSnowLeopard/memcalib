# MemCalib Repository And Private Review Release Design

**Date:** 2026-07-12  
**Status:** Approved concept; implementation pending  
**Benchmark name:** MemCalib  
**Paper-facing title:** *MemCalib: Benchmarking When and How Conversational LLMs Should Use Memory*  
**Target GitHub repository:** `memcalib`

## 1. Objective

Prepare the current CRK-2 research workspace as a coherent private GitHub repository that a co-author can clone, inspect, validate, and use without distinguishing among dozens of historical prototype artifacts. The repository will expose the locked 15,528-sample benchmark as MemCalib v0.1, preserve reproducible construction code and provenance, and keep large local intermediates and secrets out of version control.

This phase ends after the reorganized repository and the private GitHub remote have been created and verified. Model evaluation is intentionally deferred to a separate design and implementation phase; the repository will document that planned phase without shipping an uncalibrated leaderboard.

## 2. Benchmark Identity And Positioning

MemCalib evaluates **calibrated memory use** in conversational language models. Given a query and realistic non-atomic memory blocks, a model must regulate each memory's effect according to its contextual role:

- **A:** leave no unsupported footprint from irrelevant or unsafe-to-use memory;
- **B:** use supporting memory only within its allowed scope;
- **C:** incorporate controlling memory strongly enough to change the answer when required.

The model receives parent memory blocks, while evaluation uses hidden atomic annotations and atom-specific judge rubrics. This block-facing, atom-evaluated design distinguishes MemCalib from benchmarks that expose already atomic memory items or evaluate selection only.

The repository and documentation will not claim that v0.1 represents general-domain dialogue. Its current 15,528 samples come from two medical QA sources. MemCalib is the domain-independent framework and benchmark name; v0.1 is the medical-source release used to validate the framework before additional sources are added.

An April 2026 benchmark, StratMem-Bench, also uses required, supportive, and irrelevant memories in 657 virtual-character scenarios. MemCalib documentation must cite this work and avoid claiming that the three-way relevance distinction is itself novel. The paper-facing contribution should instead emphasize scale, realistic non-atomic blocks, atomic decomposition, per-atom rubrics, and explicit under-use/over-use diagnostics.

## 3. Repository Structure

The repository will use the following top-level layout:

```text
memcalib/
├── README.md
├── DATA_CARD.md
├── NOTICE.md
├── .gitignore
├── docs/
│   ├── benchmark-schema.md
│   ├── construction-pipeline.md
│   ├── repository-layout.md
│   ├── sources/
│   │   ├── chatdoctor-healthcaremagic.md
│   │   └── meddialog.md
│   └── archive/
│       └── construction-designs/
├── pipeline/
│   ├── README.md
│   ├── requirements.txt
│   ├── config.json
│   ├── 00_normalize_sources.py
│   ├── ...
│   ├── 24_analyze_crk2_formal_benchmark.py
│   ├── utils.py
│   ├── prompts/
│   └── data/
├── release/
│   └── memcalib-v0.1/
│       ├── README.md
│       ├── manifest.json
│       ├── data/
│       │   ├── memcalib-v0.1-00000-of-00002.jsonl.gz
│       │   └── memcalib-v0.1-00001-of-00002.jsonl.gz
│       ├── samples/
│       │   └── memcalib-v0.1-sample-100.jsonl
│       ├── review/
│       │   └── memcalib-v0.1-audit-100.html
│       ├── reports/
│       │   └── memcalib-v0.1-statistics.html
│       ├── statistics/
│       │   ├── benchmark-summary.json
│       │   └── analysis-snapshot.json
│       └── provenance/
│           ├── generation-run.lock.json
│           ├── generation-input.manifest.json
│           ├── source-admission.manifest.json
│           └── source-candidate-pool.manifest.json
├── tests/
│   └── pipeline/
└── tools/
    ├── build_release.py
    └── verify_release.py
```

### 3.1 Construction code

`med_rpeval_pipeline/` will be renamed to `pipeline/`. The numbered stage scripts remain in one directory because their order is a meaningful representation of the construction DAG and because moving each stage into nested packages would add import churn without improving the research interface. Tests move to `tests/pipeline/`, and their script paths are updated explicitly.

`pipeline/data/` remains the local working directory for ignored source downloads, API inputs, API outputs, and full intermediate JSONL files. It will no longer contain tracked prototype reports or ambiguous candidate releases.

### 3.2 Release material

Only the locked MemCalib v0.1 artifacts are placed in `release/memcalib-v0.1/`. Historical 100-sample prototypes, stale API outputs, superseded Chinese review datasets, and duplicate HTML files are removed from the current tree. They remain recoverable from Git history.

The two original source directories at repository root are replaced by source documentation under `docs/sources/`. Raw source data remains excluded from Git and must be obtained from the upstream datasets.

## 4. Deterministic Release Packaging

`tools/build_release.py` will stream the locked formal JSONL and create two deterministic gzip shards. It must not load the 275 MB dataset into memory. Gzip headers use a fixed modification time, shard boundaries are row based, and records retain their original order.

The release manifest will contain:

- benchmark name and release version;
- schema version and release status;
- sample, parent-memory, and atomic-memory counts;
- source and topic distributions;
- A/B/C counts and mixed-parent count;
- paths, byte sizes, row counts, and SHA-256 hashes for every release file;
- SHA-256 of the reconstructed uncompressed JSONL;
- lineage hashes from the construction run lock;
- packaging script hash and packaging parameters;
- explicit license and privacy review state.

`tools/verify_release.py` will validate every file hash, decompress both shards in manifest order, parse every JSON line, enforce unique sample IDs, recompute benchmark counts, and require the reconstructed stream hash to equal the locked benchmark hash. Verification returns a nonzero exit code on any mismatch.

The 100-sample JSONL review subset will be selected deterministically and stratified across source, topic, seed complexity, A/B/C composition, mixed-parent status, and Hard-A family coverage. Its HTML companion remains one sample per page with keyboard navigation.

## 5. Documentation

### 5.1 Root README

The root README provides the benchmark definition, current release statistics, repository map, five-minute verification path, data reconstruction command, audit-report links, construction entry points, evaluation status, and interim citation guidance. It states clearly that v0.1 is medical-source data and that the benchmark framework is intended to expand beyond medicine.

### 5.2 Data card

`DATA_CARD.md` documents sources, selection, transformation, fields, distributions, intended uses, prohibited interpretations, medical-domain limitations, LLM-generated annotations, quality checks, known residual risks, and the absence of response-level human validation.

### 5.3 Schema and construction documentation

`docs/benchmark-schema.md` defines model-facing parent blocks, hidden atoms, A/B/C semantics, construction targets, usage rubrics, and QC fields. `docs/construction-pipeline.md` gives the reproducible stage graph and identifies which stages require external APIs.

### 5.4 Source and licensing notice

`NOTICE.md` and source cards preserve upstream attribution and state the license facts without inventing permissions. `OpenMed/MedDialog` declares Apache-2.0. The `lavita/ChatDoctor-HealthCareMagic-100k` dataset card does not specify a license. Consequently:

- the GitHub repository is private and limited to co-author research review;
- the repository does not assign a public license to the data shards;
- public data redistribution is blocked until source rights are resolved;
- a separate PII and sensitive-content review is required before public release.

The code also remains without a new repository-wide open-source license in this phase. A code license can be selected independently before public release.

## 6. GitHub Publication

The target repository is created as a **private** repository named `memcalib` under the currently authenticated GitHub account. The local branch history is preserved; no destructive history rewrite is performed. After all local release verification and tests pass, the implementation branch is fast-forwarded into local `main`, and `main` is pushed as the remote default branch.

The remote publication checklist is:

1. confirm no API keys, credentials, local absolute secret paths, or raw source downloads are tracked;
2. require the complete Python test suite to pass with the designated non-Conda runtime;
3. require release verification to reproduce 15,528 unique samples, 56,044 parent memories, and 78,734 atomic memories;
4. confirm each tracked file is below GitHub's ordinary 100 MB single-file limit;
5. fast-forward local `main`, create the private repository, and push `main`;
6. inspect the remote file tree and default branch;
7. report the repository URL and the exact commit reviewed.

## 7. Testing And Acceptance Criteria

The reorganization is complete only when all conditions below hold:

- repository root contains only current project entry points and documentation;
- no tracked file is an obsolete or ambiguous benchmark candidate;
- two compressed data shards reconstruct the locked formal benchmark byte for byte;
- release manifest hashes, counts, distributions, and lineage all validate;
- 15,528 sample IDs are unique;
- all 77 existing tests pass after path migration;
- new packaging and release-verification tests pass;
- the statistical HTML and audit HTML remain self-contained and readable;
- secret scanning finds no credential material;
- Git working tree is clean after commit;
- private GitHub repository creation and push succeed.

## 8. Deferred Evaluation Phase

The next phase will specify and implement a 500-sample deterministic calibration evaluation using the Bailian OpenAI-compatible API. Candidate answer models are a fixed Qwen flagship snapshot, a Qwen efficiency baseline, DeepSeek, Kimi, and GLM. Judge calibration, atom-level scoring, disagreement analysis, and the decision to scale to all 15,528 samples will be handled in a separate design so repository publication is not coupled to an unvalidated evaluation protocol.
