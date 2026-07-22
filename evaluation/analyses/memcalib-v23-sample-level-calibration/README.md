# MemCalib v2.3 sample-level calibration metrics

This analysis reuses the completed primary-Judge outputs. It makes no new model or Judge calls.
Each answer first receives one sample-level over-use budget, under-use budget, and bounded score:

`SCS_rho(s) = rho ** (over_budget(s) + under_budget(s))`.

A one-step A/B/C error adds one budget unit; an A-to-C or C-to-A error adds two. The headline
sample score uses `rho=0.5`. Every sample has equal weight in the final model mean. Additional
atoms do not directly reduce a perfect score, but they create additional opportunities for error.

## thinking: full-memory sample distribution

| Model | SCS(0.5) up | Any OPB down | Any UPB down | Exact up | Mean budget down | B=0 | B=1 | B=2 | B=3 | B=4 | B>=5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 0.427 | 0.490 | 0.508 | 0.246 | 1.984 | 0.246 | 0.194 | 0.228 | 0.148 | 0.102 | 0.082 |
| Kimi-K2.6 | 0.349 | 0.638 | 0.424 | 0.182 | 2.522 | 0.182 | 0.158 | 0.232 | 0.156 | 0.124 | 0.148 |
| DeepSeek-V4-Flash | 0.326 | 0.716 | 0.382 | 0.178 | 2.740 | 0.178 | 0.112 | 0.232 | 0.180 | 0.130 | 0.168 |
| Qwen3.6-Flash | 0.313 | 0.716 | 0.398 | 0.164 | 2.816 | 0.164 | 0.114 | 0.234 | 0.176 | 0.124 | 0.188 |
| GLM-5.2 | 0.307 | 0.760 | 0.328 | 0.148 | 2.764 | 0.148 | 0.130 | 0.250 | 0.164 | 0.128 | 0.180 |
| Qwen3-8B | 0.304 | 0.622 | 0.580 | 0.142 | 2.754 | 0.142 | 0.140 | 0.220 | 0.202 | 0.134 | 0.162 |
| DeepSeek-V4-Pro | 0.276 | 0.802 | 0.320 | 0.136 | 3.222 | 0.136 | 0.104 | 0.210 | 0.182 | 0.136 | 0.232 |
| Qwen3.5-35B-A3B | 0.271 | 0.794 | 0.380 | 0.128 | 3.102 | 0.128 | 0.102 | 0.232 | 0.162 | 0.148 | 0.228 |
| Qwen3.7-Max | 0.257 | 0.818 | 0.308 | 0.108 | 3.172 | 0.108 | 0.112 | 0.232 | 0.178 | 0.136 | 0.234 |

### thinking: rho sensitivity and within-model spread

| Model | SCS(0.25) | SCS(0.5) | SCS(0.75) | SCS(0.5) P10-P90 |
| --- | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 0.312 | 0.427 | 0.631 | [0.062, 1.000] |
| Kimi-K2.6 | 0.239 | 0.349 | 0.563 | [0.031, 1.000] |
| DeepSeek-V4-Flash | 0.224 | 0.326 | 0.539 | [0.031, 1.000] |
| Qwen3.6-Flash | 0.210 | 0.313 | 0.528 | [0.030, 1.000] |
| GLM-5.2 | 0.199 | 0.307 | 0.528 | [0.016, 1.000] |
| Qwen3-8B | 0.195 | 0.304 | 0.529 | [0.031, 1.000] |
| DeepSeek-V4-Pro | 0.179 | 0.276 | 0.490 | [0.016, 1.000] |
| Qwen3.5-35B-A3B | 0.171 | 0.271 | 0.490 | [0.016, 1.000] |
| Qwen3.7-Max | 0.154 | 0.257 | 0.481 | [0.016, 1.000] |

### thinking: SCS(0.5) by memory-load level

| Model | Level 1 | Level 2 | Level 3 |
| --- | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 0.441 | 0.414 | 0.439 |
| Kimi-K2.6 | 0.385 | 0.333 | 0.344 |
| DeepSeek-V4-Flash | 0.324 | 0.320 | 0.339 |
| Qwen3.6-Flash | 0.365 | 0.289 | 0.309 |
| GLM-5.2 | 0.354 | 0.294 | 0.288 |
| Qwen3-8B | 0.311 | 0.278 | 0.348 |
| DeepSeek-V4-Pro | 0.318 | 0.260 | 0.264 |
| Qwen3.5-35B-A3B | 0.297 | 0.265 | 0.256 |
| Qwen3.7-Max | 0.283 | 0.263 | 0.218 |

## nonthinking: full-memory sample distribution

| Model | SCS(0.5) up | Any OPB down | Any UPB down | Exact up | Mean budget down | B=0 | B=1 | B=2 | B=3 | B=4 | B>=5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 0.417 | 0.506 | 0.512 | 0.230 | 2.002 | 0.230 | 0.196 | 0.246 | 0.158 | 0.092 | 0.078 |
| Kimi-K2.6 | 0.359 | 0.636 | 0.410 | 0.198 | 2.556 | 0.198 | 0.148 | 0.228 | 0.158 | 0.120 | 0.148 |
| GLM-5.2 | 0.309 | 0.704 | 0.398 | 0.150 | 2.720 | 0.150 | 0.124 | 0.272 | 0.136 | 0.146 | 0.172 |
| Qwen3-8B | 0.301 | 0.444 | 0.704 | 0.132 | 2.640 | 0.132 | 0.138 | 0.250 | 0.202 | 0.144 | 0.134 |
| DeepSeek-V4-Flash | 0.294 | 0.740 | 0.430 | 0.136 | 2.820 | 0.136 | 0.122 | 0.242 | 0.212 | 0.118 | 0.170 |
| DeepSeek-V4-Pro | 0.292 | 0.760 | 0.398 | 0.136 | 3.052 | 0.136 | 0.138 | 0.224 | 0.154 | 0.132 | 0.216 |
| Qwen3.7-Max | 0.285 | 0.742 | 0.404 | 0.130 | 2.898 | 0.130 | 0.122 | 0.234 | 0.186 | 0.142 | 0.186 |
| Qwen3.6-Flash | 0.268 | 0.794 | 0.406 | 0.126 | 3.168 | 0.126 | 0.112 | 0.210 | 0.162 | 0.140 | 0.250 |
| Qwen3.5-35B-A3B | 0.256 | 0.820 | 0.380 | 0.110 | 3.318 | 0.110 | 0.120 | 0.216 | 0.154 | 0.138 | 0.262 |

### nonthinking: rho sensitivity and within-model spread

| Model | SCS(0.25) | SCS(0.5) | SCS(0.75) | SCS(0.5) P10-P90 |
| --- | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 0.297 | 0.417 | 0.626 | [0.062, 1.000] |
| Kimi-K2.6 | 0.252 | 0.359 | 0.568 | [0.031, 1.000] |
| GLM-5.2 | 0.201 | 0.309 | 0.531 | [0.031, 1.000] |
| Qwen3-8B | 0.186 | 0.301 | 0.532 | [0.031, 1.000] |
| DeepSeek-V4-Flash | 0.185 | 0.294 | 0.520 | [0.016, 1.000] |
| DeepSeek-V4-Pro | 0.188 | 0.292 | 0.509 | [0.016, 1.000] |
| Qwen3.7-Max | 0.179 | 0.285 | 0.509 | [0.016, 1.000] |
| Qwen3.6-Flash | 0.170 | 0.268 | 0.485 | [0.016, 1.000] |
| Qwen3.5-35B-A3B | 0.157 | 0.256 | 0.473 | [0.016, 1.000] |

### nonthinking: SCS(0.5) by memory-load level

| Model | Level 1 | Level 2 | Level 3 |
| --- | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 0.427 | 0.406 | 0.427 |
| Kimi-K2.6 | 0.366 | 0.357 | 0.356 |
| GLM-5.2 | 0.362 | 0.312 | 0.251 |
| Qwen3-8B | 0.273 | 0.297 | 0.336 |
| DeepSeek-V4-Flash | 0.317 | 0.291 | 0.278 |
| DeepSeek-V4-Pro | 0.291 | 0.277 | 0.325 |
| Qwen3.7-Max | 0.340 | 0.264 | 0.273 |
| Qwen3.6-Flash | 0.335 | 0.238 | 0.262 |
| Qwen3.5-35B-A3B | 0.262 | 0.253 | 0.256 |

## Thinking minus non-thinking on identical samples

| Model | SCS non-think | SCS think | Delta SCS | Delta Any OPB | Delta Any UPB | Delta Exact |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 0.417 | 0.427 | +0.010 | -0.016 | -0.004 | +0.016 |
| Kimi-K2.6 | 0.359 | 0.349 | -0.010 | +0.002 | +0.014 | -0.016 |
| DeepSeek-V4-Flash | 0.294 | 0.326 | +0.031 | -0.024 | -0.048 | +0.042 |
| Qwen3.6-Flash | 0.268 | 0.313 | +0.045 | -0.078 | -0.008 | +0.038 |
| GLM-5.2 | 0.309 | 0.307 | -0.002 | +0.056 | -0.070 | -0.002 |
| Qwen3-8B | 0.301 | 0.304 | +0.003 | +0.178 | -0.124 | +0.010 |
| DeepSeek-V4-Pro | 0.292 | 0.276 | -0.017 | +0.042 | -0.078 | +0.000 |
| Qwen3.5-35B-A3B | 0.256 | 0.271 | +0.015 | -0.026 | +0.000 | +0.018 |
| Qwen3.7-Max | 0.285 | 0.257 | -0.028 | +0.076 | -0.096 | -0.022 |

Negative deltas are improvements for Any OPB/UPB; positive deltas are improvements for SCS/Exact.
Codex reuses identical answers and therefore remains a repeated-Judge control rather than an answer-mode effect.

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
