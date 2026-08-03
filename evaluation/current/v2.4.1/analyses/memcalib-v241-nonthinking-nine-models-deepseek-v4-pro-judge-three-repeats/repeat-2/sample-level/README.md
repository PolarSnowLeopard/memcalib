# MemCalib v2.4.1 Non-Think sample-level metrics, DeepSeek-V4-Pro Judge, repeat 2

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
| Codex GPT-5.6 Sol | 48.3% | 30.2% | 28.7% | 70.6% | 42.5% | 44.7% | 56.4% | 29.8% |
| GLM-5.2 | 37.3% | 47.6% | 23.5% | 62.2% | 62.1% | 35.6% | 47.7% | 21.3% |
| Kimi-K2.6 | 37.0% | 51.2% | 21.2% | 60.3% | 66.0% | 33.6% | 45.0% | 21.1% |
| Qwen3.7-Max | 34.1% | 50.1% | 28.0% | 59.0% | 66.6% | 42.3% | 42.3% | 17.6% |
| DeepSeek-V4-Flash | 33.8% | 49.7% | 27.2% | 59.5% | 65.4% | 42.3% | 43.3% | 16.2% |
| Qwen3-8B | 31.9% | 33.9% | 46.6% | 59.1% | 48.2% | 62.8% | 43.3% | 14.6% |
| DeepSeek-V4-Pro | 31.2% | 59.2% | 20.8% | 53.9% | 75.7% | 33.2% | 35.6% | 14.8% |
| Qwen3.6-Flash | 27.3% | 64.9% | 17.7% | 49.2% | 80.0% | 28.5% | 31.3% | 13.2% |
| Qwen3.5-35B-A3B | 26.1% | 65.2% | 20.4% | 48.5% | 80.8% | 33.8% | 29.8% | 10.7% |

### nonthinking: sample-bootstrap 95% intervals

| Model | SCS | sOPB | sUPB | Any OPB | Any UPB |
| --- | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | [45.1%, 51.5%] | [26.9%, 33.7%] | [25.7%, 31.7%] | [38.1%, 47.2%] | [40.3%, 49.2%] |
| GLM-5.2 | [34.1%, 40.6%] | [44.2%, 51.2%] | [20.6%, 26.3%] | [57.9%, 66.4%] | [31.6%, 39.9%] |
| Kimi-K2.6 | [33.8%, 40.2%] | [47.9%, 54.7%] | [18.4%, 23.9%] | [61.9%, 70.2%] | [29.6%, 37.9%] |
| Qwen3.7-Max | [31.0%, 37.0%] | [46.7%, 53.3%] | [25.0%, 31.1%] | [62.1%, 70.6%] | [38.1%, 46.8%] |
| DeepSeek-V4-Flash | [30.8%, 36.7%] | [46.3%, 53.1%] | [24.3%, 30.1%] | [61.3%, 69.8%] | [37.9%, 46.6%] |
| Qwen3-8B | [29.1%, 34.8%] | [30.8%, 37.2%] | [43.1%, 49.9%] | [43.9%, 52.4%] | [58.5%, 67.0%] |
| DeepSeek-V4-Pro | [28.3%, 34.1%] | [56.0%, 62.3%] | [18.2%, 23.7%] | [71.9%, 79.4%] | [29.1%, 37.7%] |
| Qwen3.6-Flash | [24.5%, 30.1%] | [61.7%, 68.0%] | [15.1%, 20.2%] | [76.3%, 83.4%] | [24.7%, 32.6%] |
| Qwen3.5-35B-A3B | [23.5%, 28.8%] | [61.9%, 68.2%] | [17.7%, 23.2%] | [77.1%, 84.0%] | [29.8%, 38.1%] |

### nonthinking: total error-budget distribution

| Model | Mean | B=0 | B=1 | B=2 | B=3 | B=4 | B>=5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 1.725 | 29.8% | 22.7% | 19.2% | 14.6% | 6.7% | 7.1% |
| GLM-5.2 | 2.449 | 21.3% | 16.2% | 19.8% | 15.8% | 12.1% | 14.8% |
| Kimi-K2.6 | 2.468 | 21.1% | 16.0% | 19.6% | 15.8% | 11.9% | 15.6% |
| Qwen3.7-Max | 2.567 | 17.6% | 16.4% | 19.6% | 17.8% | 13.2% | 15.4% |
| DeepSeek-V4-Flash | 2.528 | 16.2% | 18.0% | 21.5% | 16.6% | 12.6% | 15.2% |
| Qwen3-8B | 2.547 | 14.6% | 16.0% | 23.3% | 18.8% | 13.6% | 13.8% |
| DeepSeek-V4-Pro | 2.846 | 14.8% | 16.8% | 21.1% | 11.9% | 14.2% | 21.3% |
| Qwen3.6-Flash | 3.190 | 13.2% | 12.1% | 18.2% | 16.6% | 16.8% | 23.1% |
| Qwen3.5-35B-A3B | 3.245 | 10.7% | 14.6% | 19.2% | 14.8% | 15.2% | 25.5% |

### nonthinking: rho sensitivity and within-model spread

| Model | SCS(0.25) | SCS(0.5) | SCS(0.75) | SCS(0.5) P10-P90 |
| --- | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 36.9% | 48.3% | 67.3% | [6.2%, 100.0%] |
| GLM-5.2 | 26.8% | 37.3% | 57.8% | [3.1%, 100.0%] |
| Kimi-K2.6 | 26.6% | 37.0% | 57.4% | [3.1%, 100.0%] |
| Qwen3.7-Max | 23.3% | 34.1% | 55.5% | [3.1%, 100.0%] |
| DeepSeek-V4-Flash | 22.4% | 33.8% | 55.7% | [3.1%, 100.0%] |
| Qwen3-8B | 20.4% | 31.9% | 54.6% | [3.1%, 100.0%] |
| DeepSeek-V4-Pro | 20.5% | 31.2% | 52.6% | [1.6%, 100.0%] |
| Qwen3.6-Flash | 17.7% | 27.3% | 48.7% | [1.6%, 100.0%] |
| Qwen3.5-35B-A3B | 15.9% | 26.1% | 47.9% | [1.6%, 100.0%] |

### nonthinking: SCS(0.5) by memory-load level

| Model | Level 1 | Level 2 | Level 3 |
| --- | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 52.2% | 46.2% | 48.8% |
| GLM-5.2 | 41.3% | 35.7% | 36.9% |
| Kimi-K2.6 | 40.3% | 35.8% | 36.2% |
| Qwen3.7-Max | 36.7% | 32.3% | 35.4% |
| DeepSeek-V4-Flash | 35.1% | 31.1% | 38.1% |
| Qwen3-8B | 32.2% | 31.2% | 33.1% |
| DeepSeek-V4-Pro | 37.7% | 30.0% | 27.4% |
| Qwen3.6-Flash | 31.7% | 25.0% | 27.8% |
| Qwen3.5-35B-A3B | 31.4% | 24.2% | 24.7% |

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
