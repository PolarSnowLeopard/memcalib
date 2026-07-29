# MemCalib construction-v2 pilot (100 records)

This directory contains the protocol, provenance, result summary, and human-review interface for the completed 100-record repair pilot. API responses remain local and the pilot does not modify the MemCalib v0.1 release.

- [`protocol.html`](protocol.html): Chinese visual review of the revised labels, hard gates, and staged admission flow.
- [`review.html`](review.html): one-sample-per-page review interface with full atoms, counterfactual contracts, rubrics, independent-QC reasons, and local annotations.
- [`result-summary.json`](result-summary.json): final counts and output lineage hashes.
- [`qc-reject-preaudit.md`](qc-reject-preaudit.md): preliminary consistency audit of the nine independent-QC rejects.
- [`expert-audit-30.html`](expert-audit-30.html): one-sample-per-page practical acceptance audit covering all QC rejects, all correct-action records, and all strict-pass records with multi-atom parents.
- [`expert-audit-30.annotations.json`](expert-audit-30.annotations.json): machine-readable accept/revise/reject decisions and atom-level revision instructions.
- [`expert-audit-30.summary.json`](expert-audit-30.summary.json): reproducible audit counts, coverage, observed versus blocking dimensions, and explicitly qualified rates.
- [`expert-audit-30.md`](expert-audit-30.md): compact findings table for code review.
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

The subsequent 30-record audit is risk-enriched rather than a random quality estimate. The final adjudication uses a practical acceptance threshold: unsupported facts, core query leakage, metric-changing label errors, unsafe rubrics, and clearly relevant hard-A memories are blocking; defensible atom grouping, adjacent label boundaries, and wording refinements are advisory. Under this threshold, 19 records are directly usable, 11 require targeted repair, and none require irreversible source rejection. Among the 21 audited strict-pass records, 6 contain blocking issues. The pilot can proceed after those 11 records are repaired and lightly spot-checked; full regeneration and repeated perfection-driven review are not required.

Rebuild the expert-audit artifacts from the annotations and resolved QC files with:

```bash
$PY pipeline/36_build_crk2_v2_expert_audit.py
```
