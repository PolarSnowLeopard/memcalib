# MemCalib Construction Pipeline

This directory contains the reproducible construction stages for MemCalib v0.1. The current source release uses:

- `OpenMed/MedDialog`
- `lavita/ChatDoctor-HealthCareMagic-100k`

The v0.2 multi-domain construction line additionally uses:

- `OpenAssistant/oasst1`
- `OpenAssistant/oasst2`
- `HuggingFaceH4/ultrachat_200k`
- `ise-uiuc/Magicoder-OSS-Instruct-75K`
- `codeparrot/apps`

Raw source files, API requests and responses, logs, and large intermediates stay under `pipeline/data/` and are excluded from Git. The locked review release is under `release/memcalib-v0.1/`.

## Environment

Normalization requires pandas and a Parquet engine. The remaining pipeline is primarily standard-library Python.

```bash
PY=/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
$PY -m pip install -r pipeline/requirements.txt
```

All configured paths are resolved relative to `pipeline/config.json`.

## Formal Data Flow

```text
00 normalize full sources
15 deterministic source eligibility, scoring, deduplication, and pilot selection
17 source/topic/complexity stratified 30k candidate pool
18 prepare grounded semantic-QA requests
19 validate semantic decisions and evidence
21 select strict-pass construction admission
10 prepare locked English construction requests
06 execute resumable OpenAI-compatible API calls
11 validate, normalize, and write benchmark records
12 build manual audit materials
24 compute full-release statistics
25 normalize general-dialogue and coding sources
26 merge grounded semantic-QC retries
27 prepare targeted construction repairs
28 validate the grounded multi-domain pilot
29 prepare a source-balanced CRK-2 construction-v2 pilot
30 apply deterministic v2 construction gates
31 prepare independent semantic-QC requests
32 recompute and merge independent QC decisions
33 prepare targeted v2 construction repairs
34 merge deterministic-pass primary and repair records
35 build the one-sample-per-page v2 human-review artifact
36 build the practical expert-audit artifact
37 cross-source deduplication and quota-locked General/Coding candidate pool
38 strict per-domain source-QA admission for construction
39 merge locked medical and new-domain construction seeds
40 strict-first, review-fallback final 15k release admission
```

Scripts 01-09 and 13-14 are retained as prototype and calibration lineage. They are not the final v0.1 construction path.

## Reproduce Deterministic Source Selection

```bash
$PY pipeline/00_normalize_sources.py

$PY pipeline/15_select_crk2_raw_seeds.py \
  --target 100 \
  --seed 42 \
  --progress-every 25000

$PY pipeline/17_select_crk2_candidate_pool.py \
  --per-source 15000 \
  --seed 42 \
  --progress-every 50000
```

## API Execution

The generic runner supports concurrency, RPM limits, retries, timeouts, live progress, fingerprints, and safe resume. Credentials are read only from environment variables.

```bash
DASHSCOPE_API_KEY="$(cat ~/.config/crk2/dashscope_fast_api_key)" \
DASHSCOPE_API_KEY_FALLBACK="$(cat ~/.config/crk2/dashscope_broad_api_key)" \
$PY pipeline/06_run_bailian_api.py \
  --input pipeline/data/requests.jsonl \
  --output pipeline/data/results.jsonl \
  --failed pipeline/data/failed.jsonl \
  --max-workers 16 \
  --rpm 60 \
  --timeout 300 \
  --progress-every 1
```

`DASHSCOPE_API_KEY` is always preferred. If the provider explicitly returns
`Model.AccessDenied` for that key and `DASHSCOPE_API_KEY_FALLBACK` is set, the
runner switches the whole invocation to the fallback key. Rate limits,
timeouts, connection failures, content inspection failures, and other errors
do not trigger credential switching. The output records only the role
`preferred` or `fallback`; it never writes either key.

Do not commit credentials or API outputs.

## Formal Release Lineage

The completed v0.1 construction run admitted 15,577 strict-pass source records and accepted 15,528 final benchmark records. Prompt, configuration, implementation, input, output, and lineage hashes are stored in `release/memcalib-v0.1/provenance/`.

See [construction-pipeline.md](../docs/construction-pipeline.md) for the research-method summary and [the release guide](../release/memcalib-v0.1/README.md) for the review package.

The multi-domain pilot and its one-sample-per-page review interfaces are under [`release/memcalib-multidomain-pilot-v0.2/`](../release/memcalib-multidomain-pilot-v0.2/README.md).

## Construction Protocol V2 Repair Pilot

Scripts 29-32 implement the pre-release repair protocol motivated by the expert calibration audit. This protocol does not overwrite the reproducible v0.1 release.

The v2 annotation separates influence magnitude (`A/B/C`) from memory action (`ignore/apply/correct`). Explicitly correcting an unsafe or false memory is observable memory use and must therefore be labeled B or C. Every B/C atom also carries a counterfactual contract with a concrete observable answer delta.

The following construction constraints are enforced as hard gates:

- the final question cannot state or entail a scored memory atom;
- duplicated scoring across parent memories and incompatible labels/actions is forbidden;
- B/C requires an observable with-memory versus without-memory difference.

Localized atomicity concerns, a coherent same-event grouping within one parent memory, and defensible adjacent-label boundaries are review-level observations. They do not block admission unless they make scoring ambiguous or change the required answer behavior.

The first repair pilot is locked to 100 English construction requests: 50 records from each v0.1 source, stratified across topic and source complexity. Run the offline preparation step with:

```bash
$PY pipeline/29_prepare_crk2_v2_generation.py
```

API construction, deterministic postprocessing, and independent QC are separate stages. Only records that pass script 30 and receive `strict_pass` from the recomputed script-32 decision are eligible for benchmark admission.

The completed 100-record pilot required one targeted construction-repair round: 74 records passed initially and all 26 deterministic rejects passed after repair. Independent QC produced 91 strict passes and 9 rejects after one structural-output retry. The complete review interface and locked result summary are under [`evaluation/releases/memcalib-v0.2-construction-pilot-100/`](../evaluation/releases/memcalib-v0.2-construction-pilot-100/README.md).

## Multi-domain Full Construction

`config.multidomain-v2.json` locks the first full multi-domain target. Source semantic QC uses 24,000 candidates: 12,000 General and 12,000 Coding. Construction oversamples 18,000 records (8,500 Health, 4,750 General, and 4,750 Coding) before independent QC. Final admission targets 15,000 records with a 7,500/3,750/3,750 domain split.

The General/Coding source pool is built with script 37. It performs cross-source near-duplicate removal before quota sampling, preserves source-level provenance and licenses, and allows a source shortfall to be filled only within the same domain. Strict-pass records are admitted first; non-blocking review records are eligible only when a domain target cannot otherwise be met.
