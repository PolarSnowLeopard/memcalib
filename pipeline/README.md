# MemCalib Construction Pipeline

This directory contains the reproducible construction stages for MemCalib v0.1. The current source release uses:

- `OpenMed/MedDialog`
- `lavita/ChatDoctor-HealthCareMagic-100k`

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
DASHSCOPE_API_KEY="$(cat ~/.config/crk2/dashscope_api_key)" \
$PY pipeline/06_run_bailian_api.py \
  --input pipeline/data/requests.jsonl \
  --output pipeline/data/results.jsonl \
  --failed pipeline/data/failed.jsonl \
  --max-workers 16 \
  --rpm 60 \
  --timeout 300 \
  --progress-every 1
```

Do not commit credentials or API outputs.

## Formal Release Lineage

The completed v0.1 construction run admitted 15,577 strict-pass source records and accepted 15,528 final benchmark records. Prompt, configuration, implementation, input, output, and lineage hashes are stored in `release/memcalib-v0.1/provenance/`.

See [construction-pipeline.md](../docs/construction-pipeline.md) for the research-method summary and [the release guide](../release/memcalib-v0.1/README.md) for the review package.
