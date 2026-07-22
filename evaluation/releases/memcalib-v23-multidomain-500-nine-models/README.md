# MemCalib v2.3 500-record nine-model evaluation

This internal diagnostic evaluates nine models on one locked 500-record sample
from the 15,000-record MemCalib v2.3 release. Eight Bailian models use
answer-side thinking; Codex GPT-5.6 Sol uses `reasoning_effort=none` and is
reported as a separate answer-only configuration. All Judges run with thinking
disabled.

## Locked sample

- 500 records: health/general/coding = 250/125/125.
- Difficulty levels 1/2/3 = 125/250/125.
- Source benchmark SHA-256:
  `e86d79545b44344b44337d8f9502dc69880daeb18c6513784344e33a06de8773`.
- Model-facing SHA-256:
  `84ae94bba9c01a2edaa91a1c5e25a1a5c7e5449306ff39530df474b1b7fea28d`.
- Ordered sample-ID SHA-256:
  `0f167e665807f1ed4bbbb0ab9f9ef11f28fd7cd388edd4be1d67660b8aaba0bf`.

The sampler preferentially retained 388 query/source IDs from the older v2.1
diagnostic sample. This is query-ID overlap only: all 388 corresponding v2.3
rows have rebuilt memory blocks, and there are zero identical `memory_blocks`
or complete model-facing rows between the v2.1 and v2.3 samples.

## Headline results

| Model | Full OPB down | Full UPB down | Full H up | No-memory H |
|---|---:|---:|---:|---:|
| GLM-5.2 | 0.078 | 0.173 | 0.872 | 0.209 |
| Qwen3.7-Max | 0.092 | 0.165 | 0.870 | 0.211 |
| DeepSeek-V4-Pro | 0.092 | 0.184 | 0.859 | 0.218 |
| Qwen3.5-35B-A3B | 0.087 | 0.200 | 0.853 | 0.184 |
| DeepSeek-V4-Flash | 0.070 | 0.216 | 0.850 | 0.195 |
| Qwen3.6-Flash | 0.078 | 0.234 | 0.837 | 0.208 |
| Kimi-K2.6 | 0.063 | 0.258 | 0.828 | 0.201 |
| Codex GPT-5.6 Sol | 0.046 | 0.310 | 0.801 | 0.172 |
| Qwen3-8B | 0.057 | 0.364 | 0.760 | 0.153 |

The full-memory table uses the formal directional OPB/UPB definition and its
resistance harmonic mean H. The candidate study additionally reports
MinCalib, MCC, Kappa, ordinal severity, CVaR90/95, PMU, Rasch, pairwise, and
Pareto diagnostics. No single composite score should be treated as sufficient.

## Completeness and audit

- Answers: 9,000/9,000 across nine models and two conditions.
- Primary Judge: 9,000/9,000 normalized rows.
- Secondary Judges: 450/450 normalized rows.
- Structural retries: primary 24 then 2; secondary Kimi 4; residual invalid 0.
- Judge exact agreement: 0.9736; Cohen kappa: 0.9210.
- Ordered-usage exact agreement: 0.9629; linear weighted kappa: 0.8670.

API requests, raw answers, raw Judge outputs, failures, and retry records are
retained under the local ignored `evaluation/runs/` directory. This Git-tracked
release contains the locked sample, manifests, aggregate metrics, and report.

## Files

- [Visual report](report.html)
- [Machine-readable metrics](metrics.json)
- [Sample and privacy manifest](release-manifest.json)
- [Answer run manifest](answer-run.manifest.json)
- [Judge run manifest](judge-run.manifest.json)
- [Candidate metric study](../../analyses/memcalib-v23-multidomain-500-nine-models-candidate-metrics/README.md)
- [Thinking versus non-thinking comparison](../../analyses/memcalib-v23-thinking-vs-nonthinking/README.md)
