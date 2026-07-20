# MemCalib v2.2 coauthor handoff

## Authoritative dataset

The authoritative v2.2 dataset contains 15,000 English records:

`data/memcalib-v2.2-multidomain-15000.jsonl.gz`

After decompression:

- rows: 15,000;
- SHA-256: `04a3a3abf4d719e5e5ef72deecf979b40325068e6c137befc6649b3af52d2832`.

The dataset is intended for internal research review and training. It is not
cleared for public redistribution.

## What changed from v2.1

v2.1 used exactly two model-facing memory blocks per record. v2.2 retains the
same 15,000 questions, source lineage, grounded atoms, A/B/C labels, and
canonical Hard A atoms, but changes the model-facing memory interface:

- every record has 3–20 visible memory blocks;
- block counts follow a locked long-tail distribution;
- every record with K blocks has exactly `ceil(K/2)` multi-atom blocks;
- canonical Hard A remains a separate singleton block;
- auxiliary same-user retrieval-noise atoms provide realistic variable load;
- all 15,000 records underwent deterministic validation and independent
  semantic QC after reconstruction.

## Locked statistics

| Quantity | Count |
| --- | ---: |
| Records | 15,000 |
| health / general / coding | 7,500 / 3,750 / 3,750 |
| Visible memory blocks | 74,800 |
| Multi-atom visible blocks | 41,700 |
| Multi-atom block share | 55.7487% |
| Hidden memory atoms | 118,819 |
| A / B / C atoms | 82,171 / 19,032 / 17,616 |
| strict / review / reject / invalid | 14,973 / 27 / 0 / 0 |
| Canonical Hard A families | 3,000 each |
| Stack Exchange attribution complete | 805 / 805 |

The 27 review records are non-blocking same-user-plausibility boundary cases.
They still have absent query relation, no answer footprint, no correction
requirement, no failed block coherence, and no failed global check. Reject and
invalid records are not present.

## Visible-block distribution

```text
3:4200, 4:3600, 5:2700, 6:1800,
7:1052, 8:600, 9:376, 10:224,
11:148, 12:104, 13:76, 14:44,
15:32, 16:20, 17:12, 18:4, 19:4, 20:4
```

The same proportional distribution is used within every domain.

## Model-facing versus hidden fields

For answer generation or supervised training, create an explicit projection
containing at least:

- record ID;
- current question;
- ordered `memory_blocks`.

Do not expose hidden atom labels, expected actions, counterfactual contracts,
usage rubrics, pairwise audits, or independent-QC decisions to the answer
model unless the training objective explicitly requires those targets.

The full rows intentionally contain both model-facing inputs and hidden
evaluation supervision. See `docs/benchmark-schema-v2.2.md`.

## Package contents

The coauthor ZIP contains:

- `data/memcalib-v2.2-multidomain-15000.jsonl.gz`: authoritative dataset;
- `metadata/release-manifest.json`: file hashes and release invariants;
- `metadata/statistics.json`: source, topic, block, atom, label, and QC counts;
- `review/record-review.html`: domain and block-count-stratified record sample;
- `docs/benchmark-schema-v2.2.md`: field and projection contract;
- `docs/reports/memcalib-v22-longtail-revision.html`: v2.2 incremental flow;
- `docs/reports/memcalib-v21-dataset-construction-methodology.html`: foundation
  source and construction flow;
- `DATA_CARD.md` and `NOTICE.md`: use and attribution constraints;
- `package-manifest.json`: package-level checksums.

Existing eight-model evaluation results were produced on v2.1. They are not
included as v2.2 results and must not be reported as if the models had been
evaluated under the 3–20 block interface.

## Verification

```bash
shasum -a 256 data/memcalib-v2.2-multidomain-15000.jsonl.gz
gzip -dk data/memcalib-v2.2-multidomain-15000.jsonl.gz
wc -l data/memcalib-v2.2-multidomain-15000.jsonl
shasum -a 256 data/memcalib-v2.2-multidomain-15000.jsonl
```

The final command must print:

```text
04a3a3abf4d719e5e5ef72deecf979b40325068e6c137befc6649b3af52d2832
```

## Internal-use boundary

The package includes records derived from eight upstream sources. The health
subset includes source data whose cards do not state a license. Stack
Exchange records retain completed CC-BY-SA attribution metadata. A separate
rights, PII, and sensitive-content review is required before any public
redistribution.
