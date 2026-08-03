# MemCalib v2.4.1 Non-Think sample-level metrics, DeepSeek-V4-Pro Judge, repeat 3

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
| Codex GPT-5.6 Sol | 48.2% | 29.5% | 29.2% | 70.7% | 42.5% | 45.1% | 56.1% | 28.9% |
| Kimi-K2.6 | 39.1% | 50.1% | 19.3% | 61.6% | 64.8% | 30.2% | 46.8% | 23.1% |
| GLM-5.2 | 36.6% | 49.0% | 22.6% | 61.5% | 63.4% | 34.2% | 47.1% | 20.6% |
| DeepSeek-V4-Flash | 33.9% | 50.8% | 27.6% | 58.6% | 67.6% | 42.3% | 41.5% | 16.4% |
| Qwen3.7-Max | 33.9% | 49.2% | 28.8% | 59.3% | 64.6% | 43.7% | 43.5% | 16.8% |
| DeepSeek-V4-Pro | 32.9% | 58.7% | 19.0% | 54.7% | 75.5% | 30.8% | 36.2% | 16.8% |
| Qwen3-8B | 32.3% | 31.8% | 47.1% | 59.6% | 44.1% | 63.6% | 44.1% | 15.6% |
| Qwen3.5-35B-A3B | 27.0% | 65.2% | 18.4% | 48.8% | 80.4% | 29.6% | 30.7% | 12.3% |
| Qwen3.6-Flash | 26.7% | 65.1% | 19.0% | 48.8% | 80.2% | 30.6% | 30.9% | 13.0% |

### nonthinking: sample-bootstrap 95% intervals

| Model | SCS | sOPB | sUPB | Any OPB | Any UPB |
| --- | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | [44.9%, 51.5%] | [26.5%, 32.7%] | [26.2%, 32.3%] | [38.3%, 47.0%] | [40.9%, 49.8%] |
| Kimi-K2.6 | [35.9%, 42.5%] | [46.6%, 53.5%] | [16.8%, 22.0%] | [60.3%, 68.8%] | [26.3%, 34.4%] |
| GLM-5.2 | [33.6%, 39.8%] | [45.4%, 52.4%] | [19.9%, 25.4%] | [58.9%, 67.6%] | [30.2%, 38.3%] |
| DeepSeek-V4-Flash | [31.0%, 37.0%] | [47.6%, 54.1%] | [24.6%, 30.5%] | [63.6%, 71.7%] | [38.1%, 46.6%] |
| Qwen3.7-Max | [31.0%, 37.0%] | [45.7%, 52.5%] | [25.9%, 31.8%] | [60.1%, 68.6%] | [39.7%, 48.2%] |
| DeepSeek-V4-Pro | [29.9%, 36.1%] | [55.4%, 61.9%] | [16.4%, 21.6%] | [71.5%, 79.4%] | [26.7%, 34.8%] |
| Qwen3-8B | [29.6%, 35.3%] | [28.6%, 35.2%] | [43.6%, 50.3%] | [39.9%, 48.4%] | [59.1%, 67.8%] |
| Qwen3.5-35B-A3B | [24.2%, 30.0%] | [62.0%, 68.4%] | [15.9%, 21.0%] | [76.7%, 83.8%] | [25.5%, 33.8%] |
| Qwen3.6-Flash | [24.0%, 29.5%] | [61.9%, 68.1%] | [16.5%, 21.7%] | [76.7%, 83.4%] | [26.5%, 34.4%] |

### nonthinking: total error-budget distribution

| Model | Mean | B=0 | B=1 | B=2 | B=3 | B=4 | B>=5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 1.696 | 28.9% | 23.7% | 20.4% | 13.6% | 7.5% | 5.9% |
| Kimi-K2.6 | 2.443 | 23.1% | 18.0% | 16.8% | 14.6% | 10.1% | 17.4% |
| GLM-5.2 | 2.504 | 20.6% | 15.6% | 21.1% | 15.4% | 11.5% | 15.8% |
| DeepSeek-V4-Flash | 2.561 | 16.4% | 19.0% | 20.0% | 14.8% | 13.6% | 16.2% |
| Qwen3.7-Max | 2.540 | 16.8% | 17.4% | 21.1% | 15.8% | 13.4% | 15.6% |
| DeepSeek-V4-Pro | 2.713 | 16.8% | 15.0% | 22.5% | 14.6% | 12.3% | 18.8% |
| Qwen3-8B | 2.587 | 15.6% | 15.6% | 22.1% | 17.0% | 15.6% | 14.2% |
| Qwen3.5-35B-A3B | 3.263 | 12.3% | 13.6% | 18.6% | 15.2% | 14.2% | 26.1% |
| Qwen3.6-Flash | 3.245 | 13.0% | 9.9% | 21.7% | 15.8% | 14.6% | 25.1% |

### nonthinking: rho sensitivity and within-model spread

| Model | SCS(0.25) | SCS(0.5) | SCS(0.75) | SCS(0.5) P10-P90 |
| --- | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 36.4% | 48.2% | 67.5% | [6.2%, 100.0%] |
| Kimi-K2.6 | 28.9% | 39.1% | 58.5% | [3.1%, 100.0%] |
| GLM-5.2 | 26.2% | 36.6% | 57.2% | [3.1%, 100.0%] |
| DeepSeek-V4-Flash | 22.7% | 33.9% | 55.5% | [3.1%, 100.0%] |
| Qwen3.7-Max | 22.8% | 33.9% | 55.6% | [3.1%, 100.0%] |
| DeepSeek-V4-Pro | 22.2% | 32.9% | 54.1% | [1.6%, 100.0%] |
| Qwen3-8B | 21.2% | 32.3% | 54.7% | [3.1%, 100.0%] |
| Qwen3.5-35B-A3B | 17.2% | 27.0% | 48.3% | [1.6%, 100.0%] |
| Qwen3.6-Flash | 17.1% | 26.7% | 48.1% | [1.6%, 100.0%] |

### nonthinking: SCS(0.5) by memory-load level

| Model | Level 1 | Level 2 | Level 3 |
| --- | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 51.0% | 47.4% | 47.2% |
| Kimi-K2.6 | 45.3% | 35.5% | 40.6% |
| GLM-5.2 | 43.5% | 33.5% | 36.7% |
| DeepSeek-V4-Flash | 35.6% | 31.9% | 36.6% |
| Qwen3.7-Max | 37.6% | 31.8% | 34.6% |
| DeepSeek-V4-Pro | 36.4% | 31.3% | 32.6% |
| Qwen3-8B | 34.2% | 31.4% | 32.5% |
| Qwen3.5-35B-A3B | 31.2% | 24.4% | 28.5% |
| Qwen3.6-Flash | 31.7% | 24.3% | 26.7% |

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
