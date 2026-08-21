# MemCalib v2.4.1 benchmark-1500 nine-model sample-level metrics, answer seed 44

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
| GPT-5.6-SOL | 46.6% | 38.4% | 22.7% | 68.6% | 52.9% | 35.6% | 54.4% | 29.0% |
| Claude Sonnet 4.6 | 36.9% | 48.0% | 25.2% | 61.3% | 64.4% | 38.5% | 45.1% | 19.5% |
| Kimi-K2.6 | 35.3% | 54.1% | 20.4% | 58.3% | 69.5% | 32.5% | 42.1% | 19.8% |
| Gemini 3.5 Flash | 34.2% | 52.3% | 24.9% | 58.4% | 68.8% | 38.0% | 41.5% | 17.1% |
| GLM-5.2 | 33.8% | 52.7% | 23.8% | 58.4% | 68.5% | 36.7% | 42.0% | 17.3% |
| Qwen3.8-Max | 33.5% | 50.6% | 27.9% | 58.6% | 66.8% | 41.3% | 42.4% | 17.1% |
| DeepSeek-V4-Flash-0731 | 33.0% | 57.1% | 20.1% | 55.8% | 74.7% | 31.7% | 36.9% | 16.4% |
| Qwen3-8B | 31.7% | 34.9% | 46.7% | 58.6% | 48.7% | 62.9% | 43.1% | 15.2% |
| Qwen3.5-35B-A3B | 24.4% | 68.4% | 18.2% | 45.6% | 83.9% | 29.1% | 26.3% | 10.0% |

### nonthinking: sample-bootstrap 95% intervals

| Model | SCS | sOPB | sUPB | Any OPB | Any UPB |
| --- | ---: | ---: | ---: | ---: | ---: |
| GPT-5.6-SOL | [44.7%, 48.4%] | [36.5%, 40.3%] | [21.0%, 24.3%] | [50.5%, 55.3%] | [33.2%, 38.1%] |
| Claude Sonnet 4.6 | [35.1%, 38.6%] | [46.2%, 50.1%] | [23.5%, 26.9%] | [62.0%, 66.8%] | [35.9%, 40.9%] |
| Kimi-K2.6 | [33.5%, 37.1%] | [52.1%, 56.0%] | [18.9%, 22.0%] | [67.2%, 71.9%] | [30.3%, 35.0%] |
| Gemini 3.5 Flash | [32.5%, 35.9%] | [50.4%, 54.2%] | [23.3%, 26.6%] | [66.5%, 71.1%] | [35.7%, 40.4%] |
| GLM-5.2 | [32.1%, 35.4%] | [50.7%, 54.6%] | [22.1%, 25.5%] | [66.1%, 70.9%] | [34.1%, 39.1%] |
| Qwen3.8-Max | [31.8%, 35.3%] | [48.7%, 52.5%] | [26.1%, 29.7%] | [64.5%, 69.1%] | [38.8%, 43.8%] |
| DeepSeek-V4-Flash-0731 | [31.4%, 34.6%] | [55.3%, 58.8%] | [18.5%, 21.7%] | [72.6%, 76.8%] | [29.3%, 34.2%] |
| Qwen3-8B | [30.1%, 33.4%] | [33.0%, 36.8%] | [44.8%, 48.7%] | [46.1%, 51.2%] | [60.5%, 65.4%] |
| Qwen3.5-35B-A3B | [22.9%, 25.8%] | [66.9%, 70.0%] | [16.7%, 19.7%] | [82.1%, 85.7%] | [26.9%, 31.4%] |

### nonthinking: total error-budget distribution

| Model | Mean | B=0 | B=1 | B=2 | B=3 | B=4 | B>=5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GPT-5.6-SOL | 1.824 | 29.0% | 19.7% | 21.0% | 13.9% | 8.7% | 7.6% |
| Claude Sonnet 4.6 | 2.337 | 19.5% | 17.9% | 20.7% | 17.7% | 12.1% | 12.1% |
| Kimi-K2.6 | 2.617 | 19.8% | 14.9% | 19.9% | 15.7% | 13.1% | 16.7% |
| Gemini 3.5 Flash | 2.425 | 17.1% | 14.4% | 26.9% | 17.3% | 12.2% | 12.1% |
| GLM-5.2 | 2.615 | 17.3% | 16.1% | 21.1% | 15.9% | 13.1% | 16.5% |
| Qwen3.8-Max | 2.554 | 17.1% | 14.9% | 22.9% | 16.7% | 12.3% | 16.1% |
| DeepSeek-V4-Flash-0731 | 2.551 | 16.4% | 15.2% | 22.5% | 17.5% | 14.3% | 14.1% |
| Qwen3-8B | 2.625 | 15.2% | 15.9% | 20.1% | 18.5% | 14.3% | 16.1% |
| Qwen3.5-35B-A3B | 3.321 | 10.0% | 12.3% | 18.1% | 17.6% | 17.1% | 24.9% |

### nonthinking: rho sensitivity and within-model spread

| Model | SCS(0.25) | SCS(0.5) | SCS(0.75) | SCS(0.5) P10-P90 |
| --- | ---: | ---: | ---: | ---: |
| GPT-5.6-SOL | 35.5% | 46.6% | 65.8% | [6.2%, 100.0%] |
| Claude Sonnet 4.6 | 25.6% | 36.9% | 58.2% | [3.1%, 100.0%] |
| Kimi-K2.6 | 25.1% | 35.3% | 55.8% | [3.1%, 100.0%] |
| Gemini 3.5 Flash | 22.7% | 34.2% | 56.5% | [3.1%, 100.0%] |
| GLM-5.2 | 23.0% | 33.8% | 55.1% | [3.1%, 100.0%] |
| Qwen3.8-Max | 22.6% | 33.5% | 55.2% | [3.1%, 100.0%] |
| DeepSeek-V4-Flash-0731 | 21.9% | 33.0% | 55.0% | [3.1%, 100.0%] |
| Qwen3-8B | 20.8% | 31.7% | 53.9% | [3.1%, 100.0%] |
| Qwen3.5-35B-A3B | 14.6% | 24.4% | 46.5% | [1.6%, 55.0%] |

### nonthinking: SCS(0.5) by memory-load level

| Model | Level 1 | Level 2 | Level 3 |
| --- | ---: | ---: | ---: |
| GPT-5.6-SOL | 50.1% | 44.9% | 46.3% |
| Claude Sonnet 4.6 | 40.9% | 36.3% | 34.1% |
| Kimi-K2.6 | 38.5% | 33.8% | 35.0% |
| Gemini 3.5 Flash | 38.3% | 32.7% | 33.1% |
| GLM-5.2 | 37.0% | 33.4% | 31.2% |
| Qwen3.8-Max | 36.8% | 33.0% | 31.1% |
| DeepSeek-V4-Flash-0731 | 37.1% | 32.5% | 30.0% |
| Qwen3-8B | 33.1% | 30.0% | 33.8% |
| Qwen3.5-35B-A3B | 28.1% | 24.5% | 20.6% |

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
