# MemCalib v2.3 sample-level calibration metrics

This analysis reuses the completed primary-Judge outputs. It makes no new model or Judge calls.
Each answer first receives one sample-level over-use budget, under-use budget, and bounded score:

`SCS_rho(s) = rho ** (over_budget(s) + under_budget(s))`.

A one-step A/B/C error adds one budget unit; an A-to-C or C-to-A error adds two. The headline
sample score uses `rho=0.5`. Every sample has equal weight in the final model mean. Additional
atoms do not directly reduce a perfect score, but they create additional opportunities for error.

## sft-pilot: full-memory sample distribution

| Model | SCS(0.5) up | Any OPB down | Any UPB down | Exact up | Mean budget down | B=0 | B=1 | B=2 | B=3 | B=4 | B>=5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-35B-A3B SFT | 0.570 | 0.242 | 0.504 | 0.387 | 1.290 | 0.387 | 0.236 | 0.192 | 0.109 | 0.054 | 0.022 |
| Qwen3.5-35B-A3B Base | 0.235 | 0.833 | 0.371 | 0.107 | 3.540 | 0.107 | 0.079 | 0.208 | 0.183 | 0.143 | 0.280 |

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

- `Any OPB` and `Any UPB` are family-wise sample event rates: one directional atom error is enough.
- `Exact` is the share of answers with no scorable atom error and is the hard endpoint of this family.
- `SCS(0.5)` preserves partial credit while compounding every one-step error; a two-step error has the
  same penalty as two one-step errors.
- Rankings can differ from atom-macro H because this metric rewards clean whole answers and penalizes
  errors spread across many records. It should be reported beside directional atom metrics, not used
  to erase the OPB/UPB trade-off.
- `rho` is a policy parameter. It is fixed before interpretation, and the sensitivity table remains
  part of the release rather than selecting the value that creates the preferred ranking.

## Files

- `sample-level-metrics.json`: aggregate metrics and domain/difficulty breakdowns.
- `sample-level-scores.csv`: one row per mode/model/condition/sample.
- `sample-level-score-distributions.html`: visual error-budget distributions.
- `analysis-manifest.json`: source and output hashes.
