# MemCalib v2.3 three-layer sample-level metrics

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

## sft-pilot: three-layer full-memory results

| Model | SCS(0.5) up | sOPB(0.5) down | sUPB(0.5) down | Directional H up | Any OPB down | Any UPB down | Event H up | Exact up |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-35B-A3B SFT | 0.570 | 0.159 | 0.324 | 0.750 | 0.242 | 0.504 | 0.600 | 0.387 |
| Qwen3.5-35B-A3B Base | 0.235 | 0.687 | 0.229 | 0.445 | 0.833 | 0.371 | 0.264 | 0.107 |

### sft-pilot: sample-bootstrap 95% intervals

| Model | SCS | sOPB | sUPB | Any OPB | Any UPB |
| --- | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-35B-A3B SFT | [0.538, 0.604] | [0.134, 0.186] | [0.295, 0.355] | [0.206, 0.282] | [0.462, 0.548] |
| Qwen3.5-35B-A3B Base | [0.209, 0.262] | [0.656, 0.717] | [0.201, 0.257] | [0.798, 0.865] | [0.329, 0.415] |

### sft-pilot: total error-budget distribution

| Model | Mean | B=0 | B=1 | B=2 | B=3 | B=4 | B>=5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-35B-A3B SFT | 1.290 | 0.387 | 0.236 | 0.192 | 0.109 | 0.054 | 0.022 |
| Qwen3.5-35B-A3B Base | 3.540 | 0.107 | 0.079 | 0.208 | 0.183 | 0.143 | 0.280 |

### sft-pilot: rho sensitivity and within-model spread

| Model | SCS(0.25) | SCS(0.5) | SCS(0.75) | SCS(0.5) P10-P90 |
| --- | ---: | ---: | ---: | ---: |
| Qwen3.5-35B-A3B SFT | 0.460 | 0.570 | 0.739 | [0.125, 1.000] |
| Qwen3.5-35B-A3B Base | 0.143 | 0.235 | 0.452 | [0.008, 1.000] |

### sft-pilot: SCS(0.5) by memory-load level

| Model | Level 1 | Level 2 | Level 3 |
| --- | ---: | ---: | ---: |
| Qwen3.5-35B-A3B SFT | 0.596 | 0.554 | 0.577 |
| Qwen3.5-35B-A3B Base | 0.256 | 0.220 | 0.243 |

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
