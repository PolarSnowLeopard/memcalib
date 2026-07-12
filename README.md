# MemCalib

**Benchmarking when and how conversational language models should use memory.**

MemCalib evaluates whether a model can regulate the influence of retrieved or stored memories when answering a new query. The model receives realistic parent memory blocks. Hidden atomic annotations determine whether each fact should be suppressed, used only as bounded support, or treated as a controlling constraint.

## Current Release

MemCalib v0.1 is a private co-author review release built from two English medical QA sources. It validates the benchmark construction and evaluation representation; it does not yet support claims about general-domain dialogue.

| Statistic | Value |
|---|---:|
| Samples | 15,528 |
| Parent memory blocks | 56,044 |
| Atomic memories | 78,734 |
| Mixed-label parent blocks | 7,963 (14.2%) |
| A / irrelevant atoms | 22,722 |
| B / supporting atoms | 25,783 |
| C / controlling atoms | 30,229 |
| Source datasets | 2 |
| Medical topics | 12 |

## Capability Definition

- **A - suppress:** the memory must not leave an unsupported footprint in the response.
- **B - bound:** the memory may support the response, but must not control or overexpand it.
- **C - control:** the memory must materially constrain the answer or its main recommendation.

The model sees `memory_blocks`. Evaluation uses the hidden `memories` array, where each atomic memory has an A/B/C label, construction target, and observable judge rubric. This preserves realistic non-atomic memory input while supporting fine-grained diagnosis.

## Positioning

[StratMem-Bench](https://arxiv.org/abs/2604.26243) independently evaluates required, supportive, and irrelevant memories in 657 virtual-character scenarios. MemCalib does not claim the three-way relevance distinction as a new idea. Its intended contribution is the block-facing/atom-evaluated protocol, realistic non-atomic memories, atom-specific rubrics for under-use and over-use, and a substantially larger reproducible construction pipeline.

## Five-Minute Review

Use the designated non-Conda Python runtime in this workspace, or any Python 3.11+ interpreter with the standard library:

```bash
PY=/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3

$PY tools/verify_release.py --release-dir release/memcalib-v0.1
```

The verifier checks every release hash, reconstructs the two compressed shards in order, parses all records, verifies unique IDs, recomputes benchmark statistics, and requires the locked source SHA-256.

To reconstruct the uncompressed JSONL:

```bash
gzip -cd \
  release/memcalib-v0.1/data/memcalib-v0.1-00000-of-00002.jsonl.gz \
  release/memcalib-v0.1/data/memcalib-v0.1-00001-of-00002.jsonl.gz \
  > memcalib-v0.1.jsonl

shasum -a 256 memcalib-v0.1.jsonl
# 1cfd0334255266e6b8d4c234c615ade42b40c91bb86cb7c061a285261c363cb4
```

Review entry points:

- [Release guide](release/memcalib-v0.1/README.md)
- [100-sample audit page](release/memcalib-v0.1/review/memcalib-v0.1-audit-100.html)
- [Full statistical report](release/memcalib-v0.1/reports/memcalib-v0.1-statistics.html)
- [Data card](DATA_CARD.md)
- [Benchmark schema](docs/benchmark-schema.md)
- [Construction pipeline](docs/construction-pipeline.md)

## Repository Map

```text
pipeline/                 reproducible construction stages and prompts
release/memcalib-v0.1/   locked private-review data release
tools/                    deterministic release builder and verifier
tests/                    pipeline and release-tool tests
docs/                     schema, methods, sources, and archived designs
```

Large source downloads, API requests/responses, runtime logs, and construction intermediates remain local under `pipeline/data/` and are excluded from Git.

## Construction And Evaluation Status

The construction pipeline includes deterministic source filtering, deduplication, stratified candidate selection, semantic source QA, English memory construction, atomic decomposition, A/B/C annotation, per-atom rubric generation, and structural QC.

Response-level benchmark validation is the next phase. The planned first experiment uses a deterministic 500-sample calibration subset and representative models through the Bailian OpenAI-compatible API. No model leaderboard is included in v0.1.

## Release And Licensing Status

This repository is for private co-author research review. `OpenMed/MedDialog` declares Apache-2.0. The `lavita/ChatDoctor-HealthCareMagic-100k` dataset card does not specify a license. The data shards therefore are not cleared for public redistribution. Public release additionally requires a PII and sensitive-content review.

See [NOTICE.md](NOTICE.md) for attribution and rights status. No repository-wide code or data license is granted in this review release.
