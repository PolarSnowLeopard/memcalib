# MemCalib v2.4.1 Non-Think sample-level metrics, DeepSeek-V4-Pro Judge, repeat 1

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
| Codex GPT-5.6 Sol | 49.9% | 28.8% | 27.5% | 71.9% | 41.5% | 41.7% | 58.4% | 31.6% |
| Kimi-K2.6 | 37.1% | 50.9% | 21.2% | 60.5% | 65.6% | 33.2% | 45.4% | 21.3% |
| GLM-5.2 | 34.9% | 48.6% | 24.7% | 61.1% | 63.0% | 38.1% | 46.4% | 17.6% |
| DeepSeek-V4-Flash | 33.1% | 52.0% | 26.2% | 58.1% | 69.0% | 41.1% | 40.6% | 15.2% |
| Qwen3-8B | 33.0% | 33.0% | 46.0% | 59.8% | 45.3% | 62.1% | 44.7% | 16.6% |
| Qwen3.7-Max | 32.3% | 51.8% | 29.4% | 57.3% | 68.4% | 43.7% | 40.5% | 16.4% |
| DeepSeek-V4-Pro | 29.6% | 60.3% | 22.8% | 52.5% | 75.7% | 35.8% | 35.2% | 14.4% |
| Qwen3.5-35B-A3B | 27.2% | 64.3% | 19.7% | 49.5% | 79.6% | 31.6% | 31.5% | 12.3% |
| Qwen3.6-Flash | 26.8% | 64.6% | 19.3% | 49.2% | 79.8% | 30.8% | 31.3% | 12.6% |

### nonthinking: sample-bootstrap 95% intervals

| Model | SCS | sOPB | sUPB | Any OPB | Any UPB |
| --- | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | [46.7%, 53.1%] | [25.8%, 31.8%] | [24.4%, 30.5%] | [37.2%, 45.7%] | [37.2%, 46.2%] |
| Kimi-K2.6 | [33.9%, 40.3%] | [47.3%, 54.3%] | [18.5%, 23.9%] | [61.3%, 69.6%] | [29.1%, 37.2%] |
| GLM-5.2 | [32.0%, 38.0%] | [45.2%, 52.0%] | [21.8%, 27.5%] | [58.7%, 67.2%] | [33.8%, 42.3%] |
| DeepSeek-V4-Flash | [30.3%, 36.0%] | [48.8%, 55.3%] | [23.3%, 29.1%] | [65.0%, 73.1%] | [36.8%, 45.3%] |
| Qwen3-8B | [30.1%, 36.0%] | [29.7%, 36.3%] | [42.5%, 49.3%] | [40.9%, 49.8%] | [57.9%, 66.4%] |
| Qwen3.7-Max | [29.5%, 35.2%] | [48.4%, 54.9%] | [26.4%, 32.5%] | [64.2%, 72.1%] | [39.5%, 48.2%] |
| DeepSeek-V4-Pro | [26.7%, 32.6%] | [56.9%, 63.3%] | [20.0%, 25.6%] | [71.7%, 79.4%] | [31.6%, 39.9%] |
| Qwen3.5-35B-A3B | [24.5%, 30.2%] | [60.9%, 67.5%] | [17.1%, 22.4%] | [75.7%, 83.0%] | [27.5%, 35.6%] |
| Qwen3.6-Flash | [24.1%, 29.6%] | [61.3%, 67.8%] | [16.7%, 21.9%] | [76.1%, 83.2%] | [26.7%, 34.8%] |

### nonthinking: total error-budget distribution

| Model | Mean | B=0 | B=1 | B=2 | B=3 | B=4 | B>=5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 1.623 | 31.6% | 20.9% | 23.5% | 12.1% | 5.5% | 6.5% |
| Kimi-K2.6 | 2.549 | 21.3% | 15.8% | 20.2% | 14.8% | 12.1% | 15.8% |
| GLM-5.2 | 2.524 | 17.6% | 16.8% | 23.3% | 17.2% | 11.1% | 14.0% |
| DeepSeek-V4-Flash | 2.599 | 15.2% | 18.4% | 22.5% | 16.4% | 11.5% | 16.0% |
| Qwen3-8B | 2.565 | 16.6% | 15.0% | 21.7% | 17.6% | 14.6% | 14.6% |
| Qwen3.7-Max | 2.719 | 16.4% | 14.2% | 22.9% | 15.0% | 14.6% | 17.0% |
| DeepSeek-V4-Pro | 3.000 | 14.4% | 14.4% | 19.4% | 15.2% | 14.4% | 22.3% |
| Qwen3.5-35B-A3B | 3.235 | 12.3% | 13.8% | 20.2% | 13.0% | 13.8% | 26.9% |
| Qwen3.6-Flash | 3.265 | 12.6% | 11.9% | 19.6% | 15.8% | 16.0% | 24.1% |

### nonthinking: rho sensitivity and within-model spread

| Model | SCS(0.25) | SCS(0.5) | SCS(0.75) | SCS(0.5) P10-P90 |
| --- | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 38.5% | 49.9% | 68.6% | [6.2%, 100.0%] |
| Kimi-K2.6 | 26.8% | 37.1% | 57.2% | [3.1%, 100.0%] |
| GLM-5.2 | 23.6% | 34.9% | 56.5% | [3.1%, 100.0%] |
| DeepSeek-V4-Flash | 21.5% | 33.1% | 55.1% | [3.1%, 100.0%] |
| Qwen3-8B | 22.0% | 33.0% | 55.0% | [3.1%, 100.0%] |
| Qwen3.7-Max | 21.7% | 32.3% | 53.8% | [3.1%, 100.0%] |
| DeepSeek-V4-Pro | 19.5% | 29.6% | 50.9% | [1.6%, 100.0%] |
| Qwen3.5-35B-A3B | 17.3% | 27.2% | 48.5% | [1.6%, 100.0%] |
| Qwen3.6-Flash | 17.1% | 26.8% | 48.2% | [1.6%, 100.0%] |

### nonthinking: SCS(0.5) by memory-load level

| Model | Level 1 | Level 2 | Level 3 |
| --- | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 52.2% | 47.7% | 52.2% |
| Kimi-K2.6 | 45.4% | 33.7% | 36.1% |
| GLM-5.2 | 43.4% | 31.2% | 34.4% |
| DeepSeek-V4-Flash | 35.5% | 30.8% | 35.5% |
| Qwen3-8B | 35.9% | 31.9% | 32.3% |
| Qwen3.7-Max | 35.7% | 32.0% | 29.6% |
| DeepSeek-V4-Pro | 35.1% | 26.7% | 30.3% |
| Qwen3.5-35B-A3B | 31.5% | 25.7% | 26.3% |
| Qwen3.6-Flash | 33.2% | 24.0% | 26.4% |

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
