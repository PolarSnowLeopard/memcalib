# MemCalib v2.4.1 Qwen3-8B training-view comparison

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

## primary: three-layer full-memory results

| Model | SCS(0.5) up | sOPB(0.5) down | sUPB(0.5) down | Directional H up | Any OPB down | Any UPB down | Event H up | Exact up |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen3-8b-v241-sft-fluent-12k | 65.6% | 11.0% | 26.0% | 80.8% | 17.1% | 42.1% | 68.2% | 47.8% |
| qwen3-8b-v241-sft-atomic-12k | 63.5% | 13.6% | 26.7% | 79.3% | 21.4% | 42.7% | 66.3% | 46.4% |
| qwen3-8b-v241-coldstart-4k | 50.8% | 18.5% | 37.7% | 70.6% | 27.4% | 56.7% | 54.2% | 32.4% |

### primary: sample-bootstrap 95% intervals

| Model | SCS | sOPB | sUPB | Any OPB | Any UPB |
| --- | ---: | ---: | ---: | ---: | ---: |
| qwen3-8b-v241-sft-fluent-12k | [62.4%, 68.6%] | [8.9%, 13.3%] | [23.2%, 29.0%] | [13.8%, 20.6%] | [37.7%, 46.6%] |
| qwen3-8b-v241-sft-atomic-12k | [60.3%, 66.7%] | [11.3%, 16.1%] | [23.8%, 29.7%] | [17.9%, 25.2%] | [38.4%, 47.0%] |
| qwen3-8b-v241-coldstart-4k | [47.3%, 54.1%] | [15.8%, 21.5%] | [34.6%, 40.8%] | [23.5%, 31.3%] | [52.2%, 61.0%] |

### primary: total error-budget distribution

| Model | Mean | B=0 | B=1 | B=2 | B=3 | B=4 | B>=5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen3-8b-v241-sft-fluent-12k | 0.957 | 47.8% | 25.4% | 15.7% | 7.8% | 2.1% | 1.2% |
| qwen3-8b-v241-sft-atomic-12k | 1.035 | 46.4% | 22.3% | 18.4% | 9.1% | 3.1% | 0.8% |
| qwen3-8b-v241-coldstart-4k | 1.579 | 32.4% | 22.9% | 17.9% | 14.8% | 8.7% | 3.3% |

### primary: rho sensitivity and within-model spread

| Model | SCS(0.25) | SCS(0.5) | SCS(0.75) | SCS(0.5) P10-P90 |
| --- | ---: | ---: | ---: | ---: |
| qwen3-8b-v241-sft-fluent-12k | 55.3% | 65.6% | 79.9% | [12.5%, 100.0%] |
| qwen3-8b-v241-sft-atomic-12k | 53.3% | 63.5% | 78.4% | [12.5%, 100.0%] |
| qwen3-8b-v241-coldstart-4k | 39.5% | 50.8% | 69.3% | [6.2%, 100.0%] |

### primary: SCS(0.5) by memory-load level

| Model | Level 1 | Level 2 | Level 3 |
| --- | ---: | ---: | ---: |
| qwen3-8b-v241-sft-fluent-12k | 63.2% | 67.3% | 64.2% |
| qwen3-8b-v241-sft-atomic-12k | 61.8% | 62.3% | 67.4% |
| qwen3-8b-v241-coldstart-4k | 49.3% | 51.3% | 51.2% |

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
