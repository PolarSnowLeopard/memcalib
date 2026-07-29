# MemCalib v2.4 Coauthor Handoff

## Authoritative Dataset

The v2.4 dataset contains 15,000 English records:

```text
data/memcalib-v2.4-multidomain-15000.jsonl.gz
```

Domain counts are health_seed/general/coding = 7,500/3,750/3,750.

v2.4 revises all 3,750 coding records from executable-code generation into
natural-language implementation planning, behavior prediction, or debugging
diagnosis. Health and general records remain semantically unchanged from v2.3.

## Why Coding Changed

The previous coding tasks often required executable code, while the Judge only
read the output text. Runtime behavior could therefore be underdetermined. v2.4
requires natural-language answers and rebuilds every coding atom rubric so that
correct use, under-use, and over-use can be judged directly from answer text.

## Coverage

| Statistic | Count |
|---|---:|
| Coding records processed | 3,750 |
| Questions changed | 3,750 |
| Natural-language contracts present | 3,750 |
| Coding questions with code fences | 0 |
| Coding reference answers with code fences | 0 |
| Independent-QC strict | 3,735 |
| Manual adjudication with separate audit | 15 |

The 15 manually adjudicated residual records are explicitly marked. They were
not relabeled as independent Judge results. Their memory atoms, labels, actions,
and visible blocks remain locked.

## Integrity

The local DingTalk-ready package is:

```text
pipeline/data/multidomain/full-v2/revision-coding-text-observable-v24/handoff/
  MemCalib-v2.4-coauthor-20260729.zip
```

Verify the ZIP with the adjacent `.zip.sha256` file before transfer. The
package is approximately 254 MiB and contains the compressed dataset,
machine-readable manifests, statistics, full merge audit, manual-adjudication
audit, review HTML, and 30-record JSONL sample.

The uncompressed dataset SHA-256 is:

```text
377770f0048114db4cf40e95783f05789f1a024d1e6c90ff77881e170c0e111b
```

After decompression:

```bash
gzip -dk data/memcalib-v2.4-multidomain-15000.jsonl.gz
wc -l data/memcalib-v2.4-multidomain-15000.jsonl
shasum -a 256 data/memcalib-v2.4-multidomain-15000.jsonl
```

Expected line count: `15000`.

## Review Entry Points

- `docs/current/v2.4/benchmark-schema-v2.4.md`: schema and invariants;
- `docs/current/v2.4/reports/memcalib-v24-coding-text-observability.md`: complete revision
  and QC process;
- `metadata/statistics.json`: machine-readable full-release statistics;
- `review/record-review.html`: 30-record coding review interface;
- `samples/memcalib-v24-coding-review-sample-30.model-facing.jsonl`: what the
  evaluated model sees;
- `samples/memcalib-v24-coding-review-sample-30.full.jsonl`: hidden supervision
  and audit fields.

## Usage Boundary

This package is for private coauthor review and controlled research use. It does
not by itself clear upstream licensing, attribution, privacy, PII, or
sensitive-content requirements for public redistribution. Existing v2.3 model
scores must not be reported as v2.4 results; coding questions and rubrics have
changed and require a new locked evaluation run.
