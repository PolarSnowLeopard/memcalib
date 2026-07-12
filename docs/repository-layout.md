# Repository Layout

## `pipeline/`

Executable benchmark-construction stages, prompts, configuration, utilities, and a local `data/` workspace. The `data/` directory is ignored because it can contain raw public datasets, API requests and responses, logs, and multi-gigabyte intermediates.

## `release/memcalib-v0.1/`

The only current benchmark release. It contains deterministic compressed data shards, a release manifest, a 100-sample review subset, self-contained HTML reports, summary statistics, and provenance manifests.

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

