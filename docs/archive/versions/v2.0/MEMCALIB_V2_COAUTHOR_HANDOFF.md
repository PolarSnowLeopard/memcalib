# MemCalib v2.1 coauthor handoff

## What to use

The authoritative training dataset in the handoff archive is:

`data/memcalib-v2.1-multidomain-15000.jsonl.gz`

After decompression it contains 15,000 JSON Lines records, one record per line:

- `health_seed`: 7,500
- `general`: 3,750
- `coding`: 3,750

All 15,000 records are strict pass. Review, reject, and invalid records are excluded.

The SHA-256 digest of the compressed file is:

`6e581e813c9a172a9fd71383a5002de50dd6e75597c554eca2415b142248f8ce`

The SHA-256 digest of the decompressed JSONL is:

`bd45f77534351cd096476080096ce9ba6250a375941a171ab561ad78704bed44`

The package-internal `package-manifest.json` records the compressed dataset and
all included file hashes. Because a ZIP cannot contain its own digest without a
circular dependency, the ZIP-level digest is stored beside the archive in:

- `MemCalib-v2.1-coauthor-20260719.zip.sha256`;
- `MemCalib-v2.1-coauthor-20260719.zip.manifest.json`.

The package is deterministic and can be rebuilt with:

```bash
PY=/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3

$PY tools/package_memcalib_v21_handoff.py --require-evaluation
```

## What changed from v2.0

v2.1 directly addresses two design issues found during coauthor review:

1. every record now contains exactly one model-visible multi-atom grounded block and one single-atom Hard A block;
2. Hard A follows five explicit mechanisms and is exactly balanced.

Consequently:

- visible blocks: 30,000;
- multi-atom visible blocks: 15,000;
- multi-atom visible-block share: 50%;
- records with at least one multi-atom block: 100%;
- five Hard A families: 3,000 records each.

The old v2.0 dataset and model-evaluation results remain audit artifacts and must not be mixed with v2.1 training or evaluation.

## Memory semantics

- `A`: the memory must leave no observable footprint in the answer.
- `B`: the memory is relevant but provides only bounded support.
- `C`: the memory must materially control or constrain the answer.

These labels encode usage strength, not truthfulness. The per-atom `memory_action` separately specifies `ignore`, `apply`, or `correct`.

Wrong, stale, or unsafe but relevant memories are therefore `B+correct` or `C+correct`. `A` is always paired with `ignore`; `A+correct` is forbidden. The `usage_rubric` field defines observable expected behavior and over-use/under-use criteria.

## Record layout

For answer-model training or inference:

- use `question`;
- use `memory_blocks`;
- do not expose hidden atom labels, actions, evidence, rubrics, QC, or source answers unless they are intentional supervision targets.

Each record has exactly two model-facing memory blocks:

1. `composite_grounded`: a realistic block containing all source-grounded real atoms in a numbered, recoverable form;
2. `synthetic_hard_a`: a single A+ignore atom that is superficially relevant but has no legitimate answer influence.

For supervised label/action, judge, reward-model, or preference research, the hidden `memories` array contains the atomic contracts. Keep any benchmark evaluation split disjoint from training.

## Quality status

The v2.1 reconstruction processed all 15,000 foundation records:

- 14,923 passed the first deterministic reconstruction gate;
- the remaining 77 passed one targeted structural repair;
- full independent QC initially produced 14,140 strict, 296 review, and 564 reject after structural invalid retries;
- targeted semantic repair and a second model-family review raised the pool to 14,907 strict;
- the remaining 93 were directly repaired with source-grounded, same-family, auditable edits;
- fresh dual-family QC produced 79 dual-strict consensus cases and 14 explicit deterministic tiebreaks;
- no tail record had both judges non-strict;
- the final release is 15,000 strict, 0 review, 0 reject, and 0 invalid.

Every released record also passes exact domain quotas, exact Hard A family balance, evidence grounding, label-action compatibility, two-block structure, unique record/source IDs, and Stack Exchange attribution checks.

## Included files

- `data/memcalib-v2.1-multidomain-15000.jsonl.gz`: authoritative dataset.
- `metadata/release-manifest.json`: release inputs, hashes, and invariant checks.
- `metadata/statistics.json`: complete source, domain, label, action, type, and Hard A distributions.
- `review/record-review.html`: 30-record review interface.
- `docs/reports/memcalib-v21-dataset-construction-methodology.html`: readable end-to-end methodology with diagrams, formulas, pseudocode, counts, and repair loops.
- `docs/construction-pipeline.md`: concise pipeline specification.
- `DATA_CARD.md`: intended uses, composition, limitations, and rights boundary.
- `docs/benchmark-schema.md`: model-facing and hidden-supervision field contract.
- `docs/evaluation_protocol_v2.1.md`: ordered-usage Judge protocol and metric definitions.
- `evaluation/README.md`: model, Judge, intermediate-artifact, and reproducibility notes.
- `NOTICE.md`: source attribution and redistribution boundary.
- `evaluation/releases/memcalib-v21-multidomain-500-eight-models/report.html`: paired full-memory/no-memory eight-model report for the locked v2.1 500-record sample.
- `evaluation/releases/memcalib-v21-multidomain-500-eight-models/metrics.json`: machine-readable evaluation metrics, including macro and supplemental micro OPB/UPB/H.
- `evaluation/releases/memcalib-v21-multidomain-500-eight-models/README.md`: sample, model, Judge, completeness, comparability, and result summary.
- `evaluation/releases/memcalib-v21-multidomain-500-eight-models/release-manifest.json`: exact locked sample, model coverage, artifact hashes, and completeness checks.
- `evaluation/releases/memcalib-v21-multidomain-500-codex/`: Codex GPT-5.6 Sol answer-only controls, manifests, metrics, and report.
- `package-manifest.json`: per-file sizes and SHA-256 digests.

The two sibling ZIP verification files are not inside the archive and should be
transferred together with it.

## Basic verification

```bash
shasum -a 256 data/memcalib-v2.1-multidomain-15000.jsonl.gz
gzip -dk data/memcalib-v2.1-multidomain-15000.jsonl.gz
wc -l data/memcalib-v2.1-multidomain-15000.jsonl
shasum -a 256 data/memcalib-v2.1-multidomain-15000.jsonl
```

Expected results:

- compressed SHA-256: `6e581e813c9a172a9fd71383a5002de50dd6e75597c554eca2415b142248f8ce`;
- line count: `15000`;
- decompressed SHA-256: `bd45f77534351cd096476080096ce9ba6250a375941a171ab561ad78704bed44`.

## Sharing and rights boundary

The archive intentionally omits credentials, raw API responses, intermediate rejects, retries, and provider logs. Those remain in the builder's local audit tree.

This package is for private coauthor research review and controlled internal training. It is not cleared for public redistribution. The health subset remains conservatively marked as license unknown, and public release requires a separate rights, attribution, privacy, PII, and sensitive-content review.
