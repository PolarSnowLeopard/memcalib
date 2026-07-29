# MemCalib v2.4 complete-case three-layer sample-level metrics

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

## thinking: three-layer full-memory results

| Model | SCS(0.5) up | sOPB(0.5) down | sUPB(0.5) down | Directional H up | Any OPB down | Any UPB down | Event H up | Exact up |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 39.8% | 38.5% | 33.7% | 63.8% | 52.6% | 51.4% | 48.0% | 21.9% |
| Kimi-K2.6 | 32.3% | 53.3% | 28.9% | 56.3% | 67.0% | 44.1% | 41.5% | 18.0% |
| Qwen3-8B | 30.4% | 47.0% | 39.6% | 56.4% | 59.9% | 59.3% | 40.4% | 15.0% |
| DeepSeek-V4-Flash | 28.6% | 60.9% | 24.9% | 51.4% | 75.9% | 39.9% | 34.4% | 14.2% |
| Qwen3.6-Flash | 27.9% | 60.9% | 27.0% | 51.0% | 74.5% | 42.3% | 35.4% | 15.4% |
| GLM-5.2 | 25.9% | 64.7% | 22.2% | 48.6% | 78.1% | 36.4% | 32.5% | 11.7% |
| DeepSeek-V4-Pro | 24.4% | 67.8% | 20.9% | 45.8% | 81.4% | 33.4% | 29.1% | 11.7% |
| Qwen3.5-35B-A3B | 21.0% | 70.0% | 26.1% | 42.7% | 84.4% | 41.1% | 24.7% | 8.5% |
| Qwen3.7-Max | 20.7% | 71.8% | 19.9% | 41.7% | 86.0% | 32.4% | 23.2% | 6.7% |

### thinking: sample-bootstrap 95% intervals

| Model | SCS | sOPB | sUPB | Any OPB | Any UPB |
| --- | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | [36.5%, 42.8%] | [35.1%, 42.0%] | [30.7%, 36.8%] | [48.4%, 57.1%] | [46.8%, 55.7%] |
| Kimi-K2.6 | [29.1%, 35.3%] | [50.0%, 56.8%] | [25.8%, 32.0%] | [63.0%, 71.3%] | [39.7%, 48.4%] |
| Qwen3-8B | [27.7%, 33.4%] | [43.2%, 50.5%] | [36.5%, 42.7%] | [55.5%, 64.4%] | [55.1%, 63.8%] |
| DeepSeek-V4-Flash | [25.7%, 31.5%] | [57.8%, 64.1%] | [22.2%, 27.6%] | [72.3%, 79.8%] | [35.6%, 44.1%] |
| Qwen3.6-Flash | [25.1%, 30.7%] | [57.6%, 64.1%] | [24.0%, 29.9%] | [70.9%, 78.1%] | [37.9%, 46.8%] |
| GLM-5.2 | [23.3%, 28.7%] | [61.4%, 67.9%] | [19.3%, 25.0%] | [74.3%, 81.8%] | [31.8%, 40.7%] |
| DeepSeek-V4-Pro | [21.8%, 27.3%] | [64.6%, 70.8%] | [18.2%, 23.7%] | [77.7%, 84.8%] | [29.4%, 37.7%] |
| Qwen3.5-35B-A3B | [18.6%, 23.7%] | [66.8%, 72.8%] | [23.2%, 28.9%] | [81.2%, 87.7%] | [36.6%, 45.5%] |
| Qwen3.7-Max | [18.3%, 23.1%] | [68.9%, 74.5%] | [17.4%, 22.7%] | [83.0%, 89.1%] | [28.3%, 36.6%] |

### thinking: total error-budget distribution

| Model | Mean | B=0 | B=1 | B=2 | B=3 | B=4 | B>=5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 2.158 | 21.9% | 19.2% | 20.6% | 17.8% | 11.1% | 9.3% |
| Kimi-K2.6 | 2.903 | 18.0% | 12.3% | 21.1% | 11.5% | 16.4% | 20.6% |
| Qwen3-8B | 2.844 | 15.0% | 12.8% | 22.1% | 18.0% | 14.0% | 18.2% |
| DeepSeek-V4-Flash | 3.113 | 14.2% | 11.7% | 21.5% | 15.2% | 14.6% | 22.9% |
| Qwen3.6-Flash | 3.350 | 15.4% | 8.7% | 18.2% | 17.8% | 14.4% | 25.5% |
| GLM-5.2 | 3.366 | 11.7% | 10.9% | 22.1% | 15.8% | 11.3% | 28.1% |
| DeepSeek-V4-Pro | 3.615 | 11.7% | 7.5% | 23.5% | 14.2% | 13.6% | 29.6% |
| Qwen3.5-35B-A3B | 3.881 | 8.5% | 8.1% | 20.2% | 16.0% | 15.6% | 31.6% |
| Qwen3.7-Max | 3.660 | 6.7% | 9.7% | 22.7% | 15.4% | 17.4% | 28.1% |

### thinking: rho sensitivity and within-model spread

| Model | SCS(0.25) | SCS(0.5) | SCS(0.75) | SCS(0.5) P10-P90 |
| --- | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 28.3% | 39.8% | 60.7% | [6.2%, 100.0%] |
| Kimi-K2.6 | 22.7% | 32.3% | 52.7% | [1.6%, 100.0%] |
| Qwen3-8B | 19.9% | 30.4% | 52.3% | [3.1%, 100.0%] |
| DeepSeek-V4-Flash | 18.8% | 28.6% | 49.9% | [1.6%, 100.0%] |
| Qwen3.6-Flash | 19.0% | 27.9% | 48.5% | [1.6%, 100.0%] |
| GLM-5.2 | 16.2% | 25.9% | 47.3% | [0.8%, 100.0%] |
| DeepSeek-V4-Pro | 15.4% | 24.4% | 45.5% | [0.8%, 100.0%] |
| Qwen3.5-35B-A3B | 12.1% | 21.0% | 42.4% | [0.8%, 50.0%] |
| Qwen3.7-Max | 10.8% | 20.7% | 43.2% | [0.8%, 50.0%] |

### thinking: SCS(0.5) by memory-load level

| Model | Level 1 | Level 2 | Level 3 |
| --- | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 42.3% | 38.2% | 40.2% |
| Kimi-K2.6 | 39.0% | 30.1% | 29.9% |
| Qwen3-8B | 32.2% | 29.0% | 31.3% |
| DeepSeek-V4-Flash | 29.0% | 27.3% | 30.8% |
| Qwen3.6-Flash | 33.8% | 25.9% | 25.8% |
| GLM-5.2 | 31.5% | 23.8% | 24.4% |
| DeepSeek-V4-Pro | 29.6% | 23.3% | 21.5% |
| Qwen3.5-35B-A3B | 24.9% | 20.5% | 18.2% |
| Qwen3.7-Max | 24.2% | 20.5% | 17.3% |

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
