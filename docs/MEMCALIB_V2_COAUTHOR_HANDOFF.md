# MemCalib v2 coauthor handoff

## Primary training data

The authoritative dataset is:

`memcalib_v02_multidomain_benchmark_15000.jsonl.gz`

After decompression it contains 15,000 JSON Lines records, one record per
line. The released domain allocation is:

- `health_seed`: 7,500
- `general`: 3,750
- `coding`: 3,750

Each record contains the current question, memory blocks, atomic memory
labels and actions, source provenance, deterministic validation results,
independent quality-control results, and release-admission metadata.

The SHA-256 digest of the compressed file is:

`d73d7304f95ce47d679ee629be3eae56749b96b8a779f11f35f0472b04c164e5`

The SHA-256 digest of the decompressed JSONL is:

`41139c0f8cc54c2d2b2606c9edf2028de69b630cad7078eb1c3348625cb257b7`

## Memory semantics

- `A`: the memory should not be used to answer the current question.
- `B`: the memory is relevant but wrong, unsafe, stale, or otherwise needs
  explicit correction.
- `C`: the memory is relevant and usable.

The per-atom `memory_action` and `usage_rubric` fields provide the
corresponding expected behavior. In particular, memories that need
correction are not represented as ordinary usable memories.

## Included review materials

- `memcalib_v02_multidomain_benchmark_15000.manifest.json`: release
  selection and distribution manifest.
- `memcalib_v02_multidomain_benchmark_15000.stats.json`: compact aggregate
  statistics.
- `memcalib_v02_multidomain_benchmark_15000.package.json`: artifact sizes,
  validation status, and hashes.
- `memcalib_v02_multidomain_benchmark_15000.review.html`: record-level
  review interface.
- `memcalib-v2-dataset-construction-methodology.html`: end-to-end
  construction and quality-control methodology.
- `memcalib-v2-five-model-evaluation.html`: 500-record, five-model
  diagnostic evaluation report.
- `memcalib-v2-five-model-metrics.json`: machine-readable evaluation
  metrics.

## Basic verification

```bash
shasum -a 256 memcalib_v02_multidomain_benchmark_15000.jsonl.gz
gzip -dk memcalib_v02_multidomain_benchmark_15000.jsonl.gz
wc -l memcalib_v02_multidomain_benchmark_15000.jsonl
```

The expected line count is 15,000. The package intentionally omits raw API
responses, intermediate rejected records, retry logs, and credentials.
