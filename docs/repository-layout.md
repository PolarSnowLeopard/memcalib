# Repository Layout

## `pipeline/`

Executable benchmark-construction stages, prompts, configuration, utilities, and a local `data/` workspace. The `data/` directory is ignored because it can contain raw public datasets, API requests and responses, logs, and multi-gigabyte intermediates.

## Current v2.4 Local Release

The current 15,000-record v2.4 dataset and large construction artifacts remain
under ignored `pipeline/data/multidomain/full-v2/revision-coding-text-observable-v24/`.
The DingTalk-ready coauthor ZIP is built there by
`tools/package_memcalib_v24_handoff.py`. Reproducible code, prompts, tests,
schemas, reports, and small review samples are tracked in Git.

## `release/memcalib-v0.1/`

This is the historical repository-tracked medical-only release. It contains
deterministic compressed data shards, a release manifest, a 100-sample review
subset, self-contained HTML reports, summary statistics, and provenance
manifests.

## `tools/`

- `build_release.py`: builds deterministic gzip shards and release metadata from the locked formal JSONL.
- `verify_release.py`: independently validates hashes, JSON structure, IDs, counts, and reconstructed source bytes.

## `tests/`

- `tests/pipeline/`: construction-stage unit tests.
- `tests/tools/`: release packaging and tamper-detection tests.

## `docs/`

Current benchmark documentation and archived construction-design records. Implementation plans used during development are retained in Git history rather than the reviewer-facing tree.

## Local Data

Raw source snapshots should be placed according to `pipeline/config.json`. The repository never searches user home directories for API keys. API credentials are read only from environment variables at execution time.
