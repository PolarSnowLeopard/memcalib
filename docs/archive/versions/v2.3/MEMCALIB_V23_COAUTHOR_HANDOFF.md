# MemCalib v2.3 coauthor handoff

## Authoritative dataset

The authoritative v2.3 dataset contains 15,000 English records:

`data/memcalib-v2.3-multidomain-15000.jsonl.gz`

Compressed SHA-256:

`91a849d08dee6c7647f7a77c489da5efa877647fce107ed7423ec44c50d66f43`

After decompression:

- rows: 15,000;
- SHA-256: `e86d79545b44344b44337d8f9502dc69880daeb18c6513784344e33a06de8773`.

The dataset is intended for internal research review and controlled training.
It is not cleared for public redistribution.

## What changed from v2.2

v2.3 retains the same 15,000 questions, source lineage, visible-block count,
original atoms, A/B/C labels, actions, and canonical Hard A. It changes the
internal complexity and model-facing surface form:

- every visible block contains 1–20 hidden atoms;
- every record belongs to one of three atom-load difficulty strata;
- 115,402 added atoms are auxiliary A+ignore with zero answer footprint;
- there is no total-atom cap per record;
- every multi-atom set is rewritten as one natural paragraph;
- visible numbers and atom-boundary markers are forbidden;
- expansion, paragraph rewriting, and semantic QC are independent stages;
- rejected records are repaired and rejudged without rerunning accepted items.

## Locked statistics

| Quantity | Count |
|---|---:|
| Records | 15,000 |
| health / general / coding | 7,500 / 3,750 / 3,750 |
| Visible memory blocks | 74,800 |
| Multi-atom visible blocks | 59,800 |
| Blocks with at least three atoms | 48,548 |
| Hidden memory atoms | 234,221 |
| Atoms per record | 6–63; mean 15.6147; median 14 |
| A / B / C atoms | 197,573 / 19,032 / 17,616 |
| level 1 / 2 / 3 | 3,751 / 7,500 / 3,749 |
| strict / review / reject / invalid | 13,923 / 1,077 / 0 / 0 |
| Stack Exchange attribution complete | 805 / 805 |

The 1,077 review records contain no hard QC failure. They are retained as
audited boundary cases; reject and invalid records are absent.

The exact machine-readable distribution is stored in
`pipeline/data/multidomain/full-v2/revision-composite-blocks-v23/release/memcalib_v23_multidomain_benchmark_15000.statistics.json`.
The complete visual report is
`docs/reports/memcalib-v23-composite-block-revision.html`.

## Human-review sample

For quick inspection without opening the 1.9 GB release file, use the
deterministic 30-record sample under `docs/samples/`:

- `memcalib-v23-review-sample-30.model-facing.jsonl`: question and visible
  memory blocks exactly as presented to the answer model;
- `memcalib-v23-review-sample-30.full.jsonl`: complete hidden atoms, labels,
  actions, evidence, construction metadata, and QC records;
- `memcalib-v23-review-sample-30.manifest.json`: selection strata, sample IDs,
  distributions, and file hashes.

The sample balances all three domains and all five Hard A families, covers all
three difficulty levels, and includes audited `review` boundary cases. It is a
qualitative coverage sample, not an estimator of release prevalence.

## Model-facing versus hidden fields

For answer generation or supervised training, create an explicit projection
containing only:

- record ID;
- current question;
- ordered block IDs and `memory_text` paragraphs.

Do not expose `memories`, target labels, expected actions, counterfactual
contracts, usage rubrics, pairwise audits, or QC decisions to an answer model
being evaluated. The full rows intentionally contain both model-facing inputs
and hidden supervision. See `docs/benchmark-schema-v2.3.md`.

## Package contents

The coauthor ZIP contains:

- `data/memcalib-v2.3-multidomain-15000.jsonl.gz`: authoritative dataset;
- `metadata/release-manifest.json`: file hashes and release invariants;
- `metadata/statistics.json`: source, block, atom, label, difficulty, and QC counts;
- `review/record-review.html`: stratified record review interface;
- `docs/benchmark-schema-v2.3.md`: field and projection contract;
- `docs/reports/memcalib-v23-composite-block-revision.html`: complete build flow;
- v2.1 foundation and v2.2 block-tail reports for historical lineage;
- `DATA_CARD.md` and `NOTICE.md`: use, limitation, and attribution constraints;
- `package-manifest.json`: package-level hashes.

The local delivery filename is `MemCalib-v2.3-coauthor-20260721.zip`. Verify
the ZIP itself with the adjacent `MemCalib-v2.3-coauthor-20260721.zip.sha256`
file before sending or after receipt.

## Verification

```bash
shasum -a 256 data/memcalib-v2.3-multidomain-15000.jsonl.gz
gzip -dk data/memcalib-v2.3-multidomain-15000.jsonl.gz
wc -l data/memcalib-v2.3-multidomain-15000.jsonl
shasum -a 256 data/memcalib-v2.3-multidomain-15000.jsonl
```

The final command must print:

```text
e86d79545b44344b44337d8f9502dc69880daeb18c6513784344e33a06de8773
```

## Recommended training projection

Use only `question` and ordered `memory_blocks` as input. Hidden atom targets
may be used for auxiliary supervision only when benchmark evaluation records
are held out and leakage is explicitly controlled. Record the exact package
manifest and dataset digest in every experiment.

## Internal-use boundary

The package includes derivatives of eight upstream sources. The health subset
contains source data whose cards do not resolve redistribution permission in
the release metadata. Stack Exchange records retain complete CC-BY-SA
attribution. Rights, PII, medical-safety, and code-provenance review remains
required before public redistribution.
