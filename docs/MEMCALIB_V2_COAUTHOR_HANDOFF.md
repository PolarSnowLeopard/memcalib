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
- `B`: the memory is relevant but should provide only bounded support.
- `C`: the memory should materially control or constrain the answer.

These labels encode usage strength, not truthfulness. The per-atom
`memory_action` field separately specifies `ignore`, `apply`, or `correct`.
Wrong, stale, or unsafe but relevant memories can therefore be `B+correct`
or `C+correct`; `A` is always paired with `ignore`. The `usage_rubric` field
defines the observable expected behavior.

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
- `memcalib-v2-six-model-evaluation.html`: 500-record, six-model paired
  diagnostic evaluation report.
- `memcalib-v2-six-model-metrics.json`: machine-readable evaluation
  metrics.

The handoff archive also retains the superseded five-model snapshot for
comparison. The six-model files are authoritative: they add Qwen3.5-35B-A3B
without changing the locked 500-record sample or the five previously evaluated
model outputs.

## Basic verification

```bash
shasum -a 256 memcalib_v02_multidomain_benchmark_15000.jsonl.gz
gzip -dk memcalib_v02_multidomain_benchmark_15000.jsonl.gz
wc -l memcalib_v02_multidomain_benchmark_15000.jsonl
```

The expected line count is 15,000. The package intentionally omits raw API
responses, intermediate rejected records, retry logs, and credentials.
