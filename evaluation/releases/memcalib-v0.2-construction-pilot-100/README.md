# MemCalib construction-v2 pilot (100 records)

This directory contains the protocol, provenance, result summary, and human-review interface for the completed 100-record repair pilot. API responses remain local and the pilot does not modify the MemCalib v0.1 release.

- [`protocol.html`](protocol.html): Chinese visual review of the revised labels, hard gates, and staged admission flow.
- [`review.html`](review.html): one-sample-per-page review interface with full atoms, counterfactual contracts, rubrics, independent-QC reasons, and local annotations.
- [`result-summary.json`](result-summary.json): final counts and output lineage hashes.
- [`qc-reject-preaudit.md`](qc-reject-preaudit.md): preliminary consistency audit of the nine independent-QC rejects.
- `benchmark-resolved.jsonl.gz`: all 100 records after deterministic validation and targeted repair.
- `strict-pass.jsonl.gz`: the 91 records admitted by independent QC.
- `qc-reject.jsonl.gz`: the 9 records retained for human adjudication.
- [`generation-input.manifest.json`](generation-input.manifest.json): selected source IDs, distributions, parameters, and SHA-256 lineage.
- [`../../../docs/crk2-v2-construction-protocol.md`](../../../docs/crk2-v2-construction-protocol.md): formal Chinese protocol.

The generated request file remains under `pipeline/data/` and is excluded from Git. Recreate it with the non-Conda Python runtime:

```bash
PY=/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
$PY pipeline/29_prepare_crk2_v2_generation.py \
  --manifest evaluation/releases/memcalib-v0.2-construction-pilot-100/generation-input.manifest.json
```

The locked pilot contains 50 records from each existing medical source. Construction produced 74 deterministic passes and 26 repair candidates; all 26 passed one targeted repair. Independent Kimi QC produced 91 strict passes and 9 rejects after one structural retry. The 9 rejects are intentionally retained at the front of the review interface for human adjudication.
