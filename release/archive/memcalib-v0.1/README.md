# MemCalib v0.1 Private Review Release

## Status

This release is intended for private co-author research review. It is not cleared for public redistribution because one source has no stated license and a PII review remains pending.

## Contents

- `data/`: two deterministic gzip-compressed JSONL shards;
- `manifest.json`: hashes, counts, distributions, packaging settings, and review state;
- `samples/`: deterministic 100-sample review subset;
- `review/`: self-contained one-sample-per-page audit HTML;
- `reports/`: full statistical analysis HTML;
- `statistics/`: benchmark and analysis summaries;
- `provenance/`: locked construction and admission manifests.

## Verify

From the repository root:

```bash
python3 tools/verify_release.py --release-dir release/archive/memcalib-v0.1
```

Expected core result:

```text
status: passed
samples: 15528
parent_memories: 56044
atomic_memories: 78734
source_sha256: 1cfd0334255266e6b8d4c234c615ade42b40c91bb86cb7c061a285261c363cb4
```

## Reconstruct

```bash
gzip -cd data/memcalib-v0.1-00000-of-00002.jsonl.gz \
  data/memcalib-v0.1-00001-of-00002.jsonl.gz \
  > memcalib-v0.1.jsonl
```

When running this command from the repository root, prefix each shard with `release/archive/memcalib-v0.1/`.

## Review Order

1. Read the root `DATA_CARD.md` and `docs/benchmark-schema.md`.
2. Open `review/memcalib-v0.1-audit-100.html` and use Left/Right Arrow to navigate.
3. Open `reports/memcalib-v0.1-statistics.html` for full-distribution analysis.
4. Run the release verifier before using the shards.
