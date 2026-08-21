# MemCalib v2.4.1 benchmark-1500 nine-model sample-level metrics, answer seed 43

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
| GPT-5.6-SOL | 46.8% | 38.3% | 22.6% | 68.6% | 53.2% | 35.3% | 54.3% | 29.0% |
| Claude Sonnet 4.6 | 36.4% | 49.5% | 24.3% | 60.6% | 66.3% | 37.7% | 43.8% | 18.7% |
| Kimi-K2.6 | 35.6% | 53.6% | 20.3% | 58.7% | 67.9% | 32.0% | 43.6% | 20.4% |
| Gemini 3.5 Flash | 35.3% | 51.4% | 24.6% | 59.1% | 67.9% | 37.7% | 42.3% | 18.3% |
| Qwen3.8-Max | 34.6% | 49.8% | 27.2% | 59.4% | 65.6% | 41.3% | 43.4% | 18.3% |
| GLM-5.2 | 34.6% | 51.7% | 23.3% | 59.3% | 66.4% | 35.3% | 44.2% | 18.7% |
| DeepSeek-V4-Flash-0731 | 33.4% | 55.3% | 21.5% | 57.0% | 72.6% | 33.6% | 38.8% | 16.2% |
| Qwen3-8B | 31.8% | 34.2% | 46.6% | 58.9% | 47.3% | 62.3% | 43.9% | 15.5% |
| Qwen3.5-35B-A3B | 24.6% | 67.4% | 19.1% | 46.4% | 83.0% | 30.7% | 27.3% | 10.3% |

### nonthinking: sample-bootstrap 95% intervals

| Model | SCS | sOPB | sUPB | Any OPB | Any UPB |
| --- | ---: | ---: | ---: | ---: | ---: |
| GPT-5.6-SOL | [45.0%, 48.6%] | [36.5%, 40.2%] | [21.0%, 24.3%] | [50.9%, 55.7%] | [33.0%, 37.7%] |
| Claude Sonnet 4.6 | [34.7%, 38.1%] | [47.7%, 51.5%] | [22.6%, 26.0%] | [63.9%, 68.6%] | [35.3%, 40.2%] |
| Kimi-K2.6 | [33.8%, 37.4%] | [51.7%, 55.6%] | [18.8%, 21.9%] | [65.6%, 70.3%] | [29.7%, 34.5%] |
| Gemini 3.5 Flash | [33.6%, 37.1%] | [49.5%, 53.3%] | [22.9%, 26.3%] | [65.6%, 70.2%] | [35.3%, 40.2%] |
| Qwen3.8-Max | [32.9%, 36.4%] | [47.9%, 51.8%] | [25.5%, 29.0%] | [63.3%, 68.1%] | [38.7%, 43.7%] |
| GLM-5.2 | [32.9%, 36.4%] | [49.7%, 53.7%] | [21.7%, 25.0%] | [64.0%, 68.8%] | [32.9%, 37.7%] |
| DeepSeek-V4-Flash-0731 | [31.8%, 35.1%] | [53.5%, 57.1%] | [19.9%, 23.0%] | [70.3%, 74.7%] | [31.2%, 36.0%] |
| Qwen3-8B | [30.1%, 33.5%] | [32.3%, 36.1%] | [44.6%, 48.6%] | [44.7%, 49.7%] | [59.8%, 64.9%] |
| Qwen3.5-35B-A3B | [23.1%, 26.0%] | [65.8%, 69.1%] | [17.6%, 20.6%] | [81.1%, 84.9%] | [28.5%, 33.0%] |

### nonthinking: total error-budget distribution

| Model | Mean | B=0 | B=1 | B=2 | B=3 | B=4 | B>=5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GPT-5.6-SOL | 1.807 | 29.0% | 19.9% | 21.7% | 13.4% | 9.1% | 6.9% |
| Claude Sonnet 4.6 | 2.366 | 18.7% | 18.8% | 20.3% | 17.5% | 12.0% | 12.7% |
| Kimi-K2.6 | 2.631 | 20.4% | 14.9% | 19.1% | 15.3% | 12.3% | 18.1% |
| Gemini 3.5 Flash | 2.369 | 18.3% | 15.3% | 23.9% | 19.1% | 11.7% | 11.7% |
| Qwen3.8-Max | 2.491 | 18.3% | 15.7% | 21.1% | 16.3% | 13.7% | 14.9% |
| GLM-5.2 | 2.597 | 18.7% | 14.9% | 22.0% | 15.5% | 12.3% | 16.7% |
| DeepSeek-V4-Flash-0731 | 2.533 | 16.2% | 16.8% | 22.1% | 17.5% | 12.3% | 15.1% |
| Qwen3-8B | 2.645 | 15.5% | 15.9% | 18.7% | 19.5% | 15.1% | 15.3% |
| Qwen3.5-35B-A3B | 3.296 | 10.3% | 12.2% | 17.9% | 18.7% | 14.9% | 26.1% |

### nonthinking: rho sensitivity and within-model spread

| Model | SCS(0.25) | SCS(0.5) | SCS(0.75) | SCS(0.5) P10-P90 |
| --- | ---: | ---: | ---: | ---: |
| GPT-5.6-SOL | 35.6% | 46.8% | 66.0% | [6.2%, 100.0%] |
| Claude Sonnet 4.6 | 25.0% | 36.4% | 57.8% | [3.1%, 100.0%] |
| Kimi-K2.6 | 25.6% | 35.6% | 55.8% | [3.1%, 100.0%] |
| Gemini 3.5 Flash | 24.0% | 35.3% | 57.2% | [3.1%, 100.0%] |
| Qwen3.8-Max | 23.8% | 34.6% | 56.1% | [3.1%, 100.0%] |
| GLM-5.2 | 24.1% | 34.6% | 55.6% | [3.1%, 100.0%] |
| DeepSeek-V4-Flash-0731 | 22.1% | 33.4% | 55.4% | [3.1%, 100.0%] |
| Qwen3-8B | 21.0% | 31.8% | 53.9% | [3.1%, 100.0%] |
| Qwen3.5-35B-A3B | 14.8% | 24.6% | 46.7% | [1.6%, 100.0%] |

### nonthinking: SCS(0.5) by memory-load level

| Model | Level 1 | Level 2 | Level 3 |
| --- | ---: | ---: | ---: |
| GPT-5.6-SOL | 49.8% | 45.9% | 45.5% |
| Claude Sonnet 4.6 | 40.5% | 35.3% | 34.4% |
| Kimi-K2.6 | 39.6% | 33.5% | 35.8% |
| Gemini 3.5 Flash | 38.3% | 33.1% | 36.7% |
| Qwen3.8-Max | 38.7% | 33.7% | 32.5% |
| GLM-5.2 | 38.8% | 33.3% | 33.0% |
| DeepSeek-V4-Flash-0731 | 34.8% | 32.8% | 33.2% |
| Qwen3-8B | 32.5% | 30.9% | 33.1% |
| Qwen3.5-35B-A3B | 28.0% | 23.2% | 23.9% |

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
