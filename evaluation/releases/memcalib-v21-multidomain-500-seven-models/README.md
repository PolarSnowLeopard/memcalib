# MemCalib v2.1 seven-model diagnostic

This directory locks the 500-record MemCalib v2.1 diagnostic used to compare
seven answer models under paired full-memory and no-memory conditions.

## Locked sample

- source dataset: MemCalib v2.1, 15,000 strict records;
- source SHA-256:
  `bd45f77534351cd096476080096ce9ba6250a375941a171ab561ad78704bed44`;
- sample: 500 records, with 250 health, 125 general, and 125 coding;
- seed: `20260719`;
- ordered sample-ID SHA-256:
  `92292219c596e790720456754376354be30c5954bf7875085594fbce40c52d29`;
- sampling: proportional stratification by domain, source, topic, and atom-count
  bucket, followed by stable seeded ordering.

The sample contains 556 A, 635 B, and 570 C hidden atoms. Model-facing files
contain only the question and the two non-atomic memory blocks; labels, actions,
rubrics, source answers, and QC remain hidden.

## Models and completeness

The answer models are Qwen3.7-Max, Qwen3.6-Flash, DeepSeek-V4-Pro,
DeepSeek-V4-Flash, Kimi-K2.6, Qwen3.5-35B-A3B, and Qwen3-8B.

Every model has 500 valid full-memory answers and 500 valid no-memory answers:
7,000 unique answers in total. Missing or failed API rows were retried by
request ID, and completed cells were not rerun.

The primary Judge is Qwen3.7-Plus and covers all 7,000 answers. DeepSeek-V4-Pro
reviews 250 stratified answers and Kimi-K2.6 reviews 100. Structural Judge
failures were retried only for the malformed rows; the normalized result has
7,000 primary and 350 secondary judgments with no residual invalid rows.

## Results

### Full-memory

| Model | OPB error | UPB error | H |
|---|---:|---:|---:|
| Kimi-K2.6 | 0.311 | 0.196 | 0.742 |
| DeepSeek-V4-Pro | 0.383 | 0.193 | 0.699 |
| Qwen3.7-Max | 0.384 | 0.201 | 0.696 |
| DeepSeek-V4-Flash | 0.393 | 0.199 | 0.691 |
| Qwen3.6-Flash | 0.394 | 0.201 | 0.689 |
| Qwen3.5-35B-A3B | 0.414 | 0.176 | 0.685 |
| Qwen3-8B | 0.251 | 0.452 | 0.633 |

### No-memory counterfactual

| Model | OPB error | UPB error | H |
|---|---:|---:|---:|
| DeepSeek-V4-Flash | 0.047 | 0.902 | 0.177 |
| DeepSeek-V4-Pro | 0.052 | 0.907 | 0.170 |
| Qwen3.7-Max | 0.057 | 0.910 | 0.164 |
| Kimi-K2.6 | 0.048 | 0.913 | 0.160 |
| Qwen3.5-35B-A3B | 0.055 | 0.913 | 0.159 |
| Qwen3.6-Flash | 0.065 | 0.915 | 0.155 |
| Qwen3-8B | 0.024 | 0.944 | 0.105 |

No-memory is a paired counterfactual baseline, not a separate leaderboard.

Across 1,309 double-judged atoms, overall exact agreement is 0.898 and Cohen
kappa is 0.864. Ordered usage-level agreement is 0.861 with linearly weighted
kappa 0.804. Human expert validation remains pending, so these results are an
internal diagnostic rather than a public leaderboard.

## Files

- `release-manifest.json`: source digest, sample IDs, distributions, and
  artifact hashes;
- `model-facing.jsonl(.gz)`: exact answer-model input;
- `hidden-evaluation.jsonl(.gz)`: atom-level evaluation supervision;
- `answer-request.manifest.json` and `answer-run.manifest.json`: answer
  completeness and generation settings;
- `judge-request.manifest.json` and `judge-run.manifest.json`: Judge sampling,
  completeness, retries, warnings, and hashes;
- `metrics.json`: complete machine-readable metrics, bootstrap intervals,
  confusion matrices, pair effects, and agreement statistics;
- `report.html`: self-contained visual report.

Raw answer text, raw Judge responses, retry rows, and logs remain under the
gitignored local `evaluation/runs/memcalib-v21-multidomain-500-seven-models/`
audit directory. Credentials are not stored in this release.
