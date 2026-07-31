# MemCalib v2.4.1 non-thinking sample-level three-layer metrics

This analysis reuses the completed primary-Judge outputs. It makes no new model or Judge calls.
The public evaluation uses three complementary layers at the answer-sample level:

1. **Overall primary:** `SCS_0.5(s) = 0.5 ** (over_budget(s) + under_budget(s))`.
2. **Directional primary:** `sOPB_0.5(s) = 1 - 0.5 ** over_budget(s)` and
   `sUPB_0.5(s) = 1 - 0.5 ** under_budget(s)`.
3. **Event guardrails:** `Any-OPB = 1[over_budget(s) > 0]` and
   `Any-UPB = 1[under_budget(s) > 0]`.

A one-step A/B/C error adds one budget unit; an A-to-C or C-to-A error adds two. All model-level
values are arithmetic means over samples, so each answer has equal weight. Directional primary
metrics preserve the number and severity of errors without growing unbounded; event guardrails
only answer whether a direction occurred at least once and therefore must not be used alone.

## nonthinking: three-layer full-memory results

| Model | SCS(0.5) up | sOPB(0.5) down | sUPB(0.5) down | Directional H up | Any OPB down | Any UPB down | Event H up | Exact up |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 40.4% | 33.8% | 36.0% | 65.1% | 46.0% | 53.6% | 49.9% | 21.5% |
| Kimi-K2.6 | 30.3% | 55.3% | 27.8% | 55.2% | 69.0% | 43.7% | 40.0% | 14.6% |
| GLM-5.2 | 30.1% | 53.7% | 29.5% | 55.9% | 67.4% | 43.9% | 41.2% | 15.0% |
| Qwen3-8B | 26.7% | 38.6% | 49.6% | 55.4% | 51.2% | 67.6% | 38.9% | 10.3% |
| Qwen3.7-Max | 26.6% | 54.2% | 35.6% | 53.5% | 68.4% | 54.0% | 37.4% | 10.5% |
| DeepSeek-V4-Flash | 24.9% | 63.0% | 28.2% | 48.8% | 77.1% | 44.9% | 32.3% | 10.5% |
| DeepSeek-V4-Pro | 24.1% | 64.2% | 28.0% | 47.8% | 78.7% | 44.3% | 30.8% | 10.5% |
| Qwen3.5-35B-A3B | 21.5% | 67.9% | 27.4% | 44.5% | 81.0% | 43.1% | 28.5% | 8.7% |
| Qwen3.6-Flash | 21.3% | 68.6% | 27.7% | 43.8% | 82.6% | 44.3% | 26.5% | 8.1% |

### nonthinking: sample-bootstrap 95% intervals

| Model | SCS | sOPB | sUPB | Any OPB | Any UPB |
| --- | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | [37.2%, 43.6%] | [30.3%, 37.2%] | [32.9%, 39.1%] | [41.5%, 50.6%] | [49.4%, 57.9%] |
| Kimi-K2.6 | [27.3%, 33.2%] | [51.8%, 58.8%] | [24.9%, 30.7%] | [65.0%, 73.1%] | [39.5%, 48.2%] |
| GLM-5.2 | [27.3%, 33.2%] | [50.1%, 57.3%] | [26.5%, 32.5%] | [63.0%, 71.5%] | [39.7%, 48.0%] |
| Qwen3-8B | [24.2%, 29.3%] | [35.1%, 42.1%] | [46.2%, 53.0%] | [46.8%, 55.7%] | [63.4%, 71.9%] |
| Qwen3.7-Max | [24.0%, 29.3%] | [50.6%, 57.6%] | [32.6%, 38.8%] | [64.2%, 72.3%] | [49.6%, 58.5%] |
| DeepSeek-V4-Flash | [22.3%, 27.5%] | [59.9%, 66.2%] | [25.4%, 31.0%] | [73.5%, 80.8%] | [40.5%, 49.2%] |
| DeepSeek-V4-Pro | [21.6%, 26.9%] | [60.9%, 67.3%] | [25.2%, 31.0%] | [75.1%, 82.2%] | [40.1%, 48.6%] |
| Qwen3.5-35B-A3B | [19.0%, 24.0%] | [64.8%, 71.1%] | [24.6%, 30.3%] | [77.3%, 84.2%] | [38.9%, 47.6%] |
| Qwen3.6-Flash | [18.9%, 23.8%] | [65.5%, 71.6%] | [24.7%, 30.6%] | [79.1%, 85.8%] | [39.7%, 48.8%] |

### nonthinking: total error-budget distribution

| Model | Mean | B=0 | B=1 | B=2 | B=3 | B=4 | B>=5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 2.115 | 21.5% | 21.9% | 20.4% | 17.0% | 8.3% | 10.9% |
| Kimi-K2.6 | 3.026 | 14.6% | 15.6% | 19.0% | 16.0% | 11.9% | 22.9% |
| GLM-5.2 | 3.083 | 15.0% | 14.0% | 19.8% | 15.2% | 14.4% | 21.7% |
| Qwen3-8B | 2.988 | 10.3% | 14.2% | 21.5% | 21.7% | 14.0% | 18.4% |
| Qwen3.7-Max | 3.055 | 10.5% | 14.8% | 20.0% | 18.6% | 14.2% | 21.9% |
| DeepSeek-V4-Flash | 3.334 | 10.5% | 12.1% | 18.0% | 19.8% | 14.6% | 24.9% |
| DeepSeek-V4-Pro | 3.464 | 10.5% | 11.1% | 16.6% | 19.4% | 16.0% | 26.3% |
| Qwen3.5-35B-A3B | 3.862 | 8.7% | 9.3% | 18.8% | 15.6% | 16.2% | 31.4% |
| Qwen3.6-Flash | 3.796 | 8.1% | 9.9% | 18.6% | 17.2% | 14.2% | 32.0% |

### nonthinking: rho sensitivity and within-model spread

| Model | SCS(0.25) | SCS(0.5) | SCS(0.75) | SCS(0.5) P10-P90 |
| --- | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 28.5% | 40.4% | 61.3% | [3.1%, 100.0%] |
| Kimi-K2.6 | 20.0% | 30.3% | 51.4% | [1.6%, 100.0%] |
| GLM-5.2 | 20.0% | 30.1% | 51.1% | [1.6%, 100.0%] |
| Qwen3-8B | 15.6% | 26.7% | 49.9% | [3.1%, 100.0%] |
| Qwen3.7-Max | 15.8% | 26.6% | 49.2% | [1.6%, 100.0%] |
| DeepSeek-V4-Flash | 15.1% | 24.9% | 46.9% | [1.6%, 100.0%] |
| DeepSeek-V4-Pro | 14.7% | 24.1% | 45.8% | [0.8%, 100.0%] |
| Qwen3.5-35B-A3B | 12.5% | 21.5% | 42.8% | [0.4%, 50.0%] |
| Qwen3.6-Flash | 12.1% | 21.3% | 42.9% | [0.8%, 50.0%] |

### nonthinking: SCS(0.5) by memory-load level

| Model | Level 1 | Level 2 | Level 3 |
| --- | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 45.8% | 39.7% | 36.3% |
| Kimi-K2.6 | 38.4% | 27.4% | 28.4% |
| GLM-5.2 | 38.2% | 29.0% | 24.3% |
| Qwen3-8B | 31.9% | 25.6% | 23.9% |
| Qwen3.7-Max | 30.1% | 23.9% | 28.8% |
| DeepSeek-V4-Flash | 26.8% | 25.6% | 21.6% |
| DeepSeek-V4-Pro | 28.4% | 24.1% | 20.0% |
| Qwen3.5-35B-A3B | 27.9% | 19.5% | 19.2% |
| Qwen3.6-Flash | 26.0% | 18.0% | 23.6% |

## Interpretation

- `SCS(0.5)` is the overall primary metric. It compounds over-use and under-use budgets within each
  answer, then gives each answer one equal model-level vote.
- `sOPB(0.5)` and `sUPB(0.5)` are the directional primary metrics. They distinguish one directional
  error from repeated or severe errors but asymptotically cap each sample at 1.
- `Any OPB` and `Any UPB` are event-rate guardrails. They reveal how widely errors are distributed
  across samples, but deliberately collapse one and many errors to the same event.
- `Directional H` and `Event H` summarize their paired resistance terms, but neither should replace
  the two directional columns in reporting.
- `Exact` is the share of answers with no scorable atom error and is the hardest event endpoint.
- `rho` is a policy parameter. It is fixed before interpretation, and the sensitivity table remains
  part of the release rather than selecting the value that creates the preferred ranking.

## Files

- `sample-level-metrics.json`: aggregate metrics and domain/difficulty breakdowns.
- `sample-level-scores.csv`: one row per mode/model/condition/sample.
- `sample-level-score-distributions.html`: visual error-budget distributions.
- `analysis-manifest.json`: source and output hashes.
