# MemCalib v2.4.1 benchmark-1500 nine-model sample-level metrics, answer seed 42

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
| GPT-5.6-SOL | 45.4% | 38.7% | 23.5% | 68.1% | 53.9% | 36.5% | 53.4% | 27.2% |
| Claude Sonnet 4.6 | 36.0% | 49.1% | 24.8% | 60.7% | 65.5% | 37.6% | 44.4% | 19.0% |
| Kimi-K2.6 | 35.7% | 53.8% | 19.1% | 58.8% | 68.6% | 30.2% | 43.3% | 19.8% |
| Gemini 3.5 Flash | 35.3% | 51.2% | 24.7% | 59.2% | 68.1% | 37.4% | 42.3% | 18.4% |
| GLM-5.2 | 34.8% | 52.0% | 23.1% | 59.1% | 67.7% | 35.1% | 43.2% | 18.6% |
| DeepSeek-V4-Flash-0731 | 34.8% | 54.5% | 21.0% | 57.7% | 72.6% | 32.6% | 39.0% | 18.3% |
| Qwen3.8-Max | 34.5% | 49.9% | 27.2% | 59.3% | 65.9% | 40.9% | 43.3% | 18.0% |
| Qwen3-8B | 32.0% | 34.9% | 46.4% | 58.8% | 48.7% | 62.2% | 43.5% | 15.9% |
| Qwen3.5-35B-A3B | 25.4% | 66.8% | 19.8% | 46.9% | 82.3% | 31.5% | 28.1% | 11.1% |

### nonthinking: sample-bootstrap 95% intervals

| Model | SCS | sOPB | sUPB | Any OPB | Any UPB |
| --- | ---: | ---: | ---: | ---: | ---: |
| GPT-5.6-SOL | [43.6%, 47.3%] | [36.8%, 40.5%] | [21.8%, 25.2%] | [51.5%, 56.5%] | [34.1%, 39.0%] |
| Claude Sonnet 4.6 | [34.3%, 37.8%] | [47.2%, 51.0%] | [23.1%, 26.5%] | [63.1%, 67.9%] | [35.2%, 40.1%] |
| Kimi-K2.6 | [33.9%, 37.4%] | [51.9%, 55.8%] | [17.6%, 20.7%] | [66.2%, 71.0%] | [28.0%, 32.5%] |
| Gemini 3.5 Flash | [33.6%, 37.1%] | [49.4%, 53.2%] | [23.0%, 26.4%] | [65.7%, 70.5%] | [35.0%, 39.8%] |
| GLM-5.2 | [33.1%, 36.5%] | [50.1%, 54.0%] | [21.5%, 24.7%] | [65.3%, 70.0%] | [32.7%, 37.5%] |
| DeepSeek-V4-Flash-0731 | [33.0%, 36.5%] | [52.6%, 56.4%] | [19.4%, 22.6%] | [70.3%, 74.9%] | [30.1%, 34.8%] |
| Qwen3.8-Max | [32.9%, 36.3%] | [48.0%, 51.8%] | [25.5%, 29.0%] | [63.5%, 68.3%] | [38.4%, 43.3%] |
| Qwen3-8B | [30.3%, 33.6%] | [33.0%, 36.7%] | [44.4%, 48.5%] | [46.2%, 51.1%] | [59.5%, 64.7%] |
| Qwen3.5-35B-A3B | [23.9%, 26.8%] | [65.2%, 68.5%] | [18.3%, 21.3%] | [80.4%, 84.2%] | [29.3%, 33.8%] |

### nonthinking: total error-budget distribution

| Model | Mean | B=0 | B=1 | B=2 | B=3 | B=4 | B>=5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GPT-5.6-SOL | 1.844 | 27.2% | 20.1% | 22.7% | 14.3% | 8.7% | 7.0% |
| Claude Sonnet 4.6 | 2.370 | 19.0% | 16.4% | 22.5% | 17.7% | 12.3% | 12.1% |
| Kimi-K2.6 | 2.561 | 19.8% | 16.0% | 20.0% | 14.0% | 13.2% | 17.0% |
| Gemini 3.5 Flash | 2.367 | 18.4% | 14.4% | 27.3% | 15.3% | 11.9% | 12.7% |
| GLM-5.2 | 2.561 | 18.6% | 15.8% | 21.2% | 15.1% | 12.4% | 16.9% |
| DeepSeek-V4-Flash-0731 | 2.465 | 18.3% | 15.7% | 20.9% | 18.6% | 13.3% | 13.2% |
| Qwen3.8-Max | 2.512 | 18.0% | 16.0% | 21.8% | 15.3% | 14.2% | 14.7% |
| Qwen3-8B | 2.634 | 15.9% | 14.5% | 20.8% | 18.1% | 15.6% | 15.1% |
| Qwen3.5-35B-A3B | 3.283 | 11.1% | 12.5% | 17.7% | 16.9% | 16.0% | 25.9% |

### nonthinking: rho sensitivity and within-model spread

| Model | SCS(0.25) | SCS(0.5) | SCS(0.75) | SCS(0.5) P10-P90 |
| --- | ---: | ---: | ---: | ---: |
| GPT-5.6-SOL | 33.9% | 45.4% | 65.2% | [6.2%, 100.0%] |
| Claude Sonnet 4.6 | 24.8% | 36.0% | 57.6% | [3.1%, 100.0%] |
| Kimi-K2.6 | 25.3% | 35.7% | 56.2% | [3.1%, 100.0%] |
| Gemini 3.5 Flash | 24.0% | 35.3% | 57.2% | [3.1%, 100.0%] |
| GLM-5.2 | 24.2% | 34.8% | 55.8% | [3.1%, 100.0%] |
| DeepSeek-V4-Flash-0731 | 23.9% | 34.8% | 56.3% | [3.1%, 100.0%] |
| Qwen3.8-Max | 23.7% | 34.5% | 56.0% | [3.1%, 100.0%] |
| Qwen3-8B | 21.2% | 32.0% | 54.0% | [3.1%, 100.0%] |
| Qwen3.5-35B-A3B | 15.7% | 25.4% | 47.2% | [1.6%, 100.0%] |

### nonthinking: SCS(0.5) by memory-load level

| Model | Level 1 | Level 2 | Level 3 |
| --- | ---: | ---: | ---: |
| GPT-5.6-SOL | 47.3% | 44.7% | 44.9% |
| Claude Sonnet 4.6 | 41.5% | 33.7% | 35.4% |
| Kimi-K2.6 | 38.9% | 33.7% | 36.5% |
| Gemini 3.5 Flash | 38.7% | 33.9% | 35.0% |
| GLM-5.2 | 37.5% | 34.1% | 33.6% |
| DeepSeek-V4-Flash-0731 | 37.6% | 32.6% | 36.2% |
| Qwen3.8-Max | 37.5% | 32.7% | 35.3% |
| Qwen3-8B | 33.2% | 30.5% | 33.7% |
| Qwen3.5-35B-A3B | 30.3% | 23.4% | 24.3% |

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
