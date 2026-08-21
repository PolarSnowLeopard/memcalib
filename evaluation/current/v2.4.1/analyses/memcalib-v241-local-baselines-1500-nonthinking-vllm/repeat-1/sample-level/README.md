# MemCalib v2.4.1 local vLLM baseline sample-level metrics, seed 42

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
| ministral3-8b-instruct-2512-bf16-local-vllm | 30.6% | 59.1% | 24.4% | 53.1% | 75.6% | 37.2% | 35.1% | 15.1% |
| qwen35-35b-a3b-local-vllm | 24.7% | 67.5% | 18.8% | 46.4% | 83.1% | 30.4% | 27.2% | 9.9% |

### nonthinking: sample-bootstrap 95% intervals

| Model | SCS | sOPB | sUPB | Any OPB | Any UPB |
| --- | ---: | ---: | ---: | ---: | ---: |
| ministral3-8b-instruct-2512-bf16-local-vllm | [28.9%, 32.3%] | [57.2%, 60.9%] | [22.7%, 26.1%] | [73.5%, 77.7%] | [34.8%, 39.7%] |
| qwen35-35b-a3b-local-vllm | [23.2%, 26.2%] | [65.7%, 69.3%] | [17.4%, 20.3%] | [81.2%, 85.0%] | [28.1%, 32.6%] |

### nonthinking: total error-budget distribution

| Model | Mean | B=0 | B=1 | B=2 | B=3 | B=4 | B>=5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ministral3-8b-instruct-2512-bf16-local-vllm | 2.919 | 15.1% | 14.1% | 20.7% | 15.9% | 13.7% | 20.3% |
| qwen35-35b-a3b-local-vllm | 3.285 | 9.9% | 13.1% | 18.5% | 15.9% | 16.9% | 25.6% |

### nonthinking: rho sensitivity and within-model spread

| Model | SCS(0.25) | SCS(0.5) | SCS(0.75) | SCS(0.5) P10-P90 |
| --- | ---: | ---: | ---: | ---: |
| ministral3-8b-instruct-2512-bf16-local-vllm | 20.3% | 30.6% | 52.0% | [1.6%, 100.0%] |
| qwen35-35b-a3b-local-vllm | 14.7% | 24.7% | 46.8% | [1.6%, 50.0%] |

### nonthinking: SCS(0.5) by memory-load level

| Model | Level 1 | Level 2 | Level 3 |
| --- | ---: | ---: | ---: |
| ministral3-8b-instruct-2512-bf16-local-vllm | 34.0% | 28.9% | 30.6% |
| qwen35-35b-a3b-local-vllm | 29.0% | 21.7% | 26.1% |

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
