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

## thinking: three-layer full-memory results

| Model | SCS(0.5) up | sOPB(0.5) down | sUPB(0.5) down | Directional H up | Any OPB down | Any UPB down | Event H up | Exact up |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 0.427 | 0.353 | 0.330 | 0.659 | 0.490 | 0.508 | 0.501 | 0.246 |
| Kimi-K2.6 | 0.349 | 0.494 | 0.277 | 0.595 | 0.638 | 0.424 | 0.445 | 0.182 |
| DeepSeek-V4-Flash | 0.326 | 0.568 | 0.239 | 0.551 | 0.716 | 0.382 | 0.389 | 0.178 |
| Qwen3.6-Flash | 0.313 | 0.566 | 0.256 | 0.548 | 0.716 | 0.398 | 0.386 | 0.164 |
| GLM-5.2 | 0.307 | 0.603 | 0.198 | 0.531 | 0.760 | 0.328 | 0.354 | 0.148 |
| Qwen3-8B | 0.304 | 0.477 | 0.387 | 0.565 | 0.622 | 0.580 | 0.398 | 0.142 |
| DeepSeek-V4-Pro | 0.276 | 0.648 | 0.199 | 0.489 | 0.802 | 0.320 | 0.307 | 0.136 |
| Qwen3.5-35B-A3B | 0.271 | 0.643 | 0.229 | 0.488 | 0.794 | 0.380 | 0.309 | 0.128 |
| Qwen3.7-Max | 0.257 | 0.669 | 0.182 | 0.471 | 0.818 | 0.308 | 0.288 | 0.108 |

### thinking: sample-bootstrap 95% intervals

| Model | SCS | sOPB | sUPB | Any OPB | Any UPB |
| --- | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | [0.395, 0.460] | [0.320, 0.385] | [0.301, 0.361] | [0.448, 0.534] | [0.466, 0.552] |
| Kimi-K2.6 | [0.319, 0.379] | [0.460, 0.529] | [0.247, 0.308] | [0.596, 0.680] | [0.382, 0.470] |
| DeepSeek-V4-Flash | [0.296, 0.356] | [0.535, 0.601] | [0.210, 0.267] | [0.678, 0.754] | [0.340, 0.426] |
| Qwen3.6-Flash | [0.282, 0.342] | [0.533, 0.600] | [0.228, 0.286] | [0.678, 0.756] | [0.356, 0.440] |
| GLM-5.2 | [0.279, 0.337] | [0.569, 0.635] | [0.172, 0.224] | [0.722, 0.796] | [0.284, 0.370] |
| Qwen3-8B | [0.276, 0.334] | [0.441, 0.512] | [0.355, 0.417] | [0.580, 0.666] | [0.534, 0.624] |
| DeepSeek-V4-Pro | [0.249, 0.302] | [0.618, 0.679] | [0.172, 0.225] | [0.768, 0.838] | [0.280, 0.358] |
| Qwen3.5-35B-A3B | [0.243, 0.297] | [0.612, 0.673] | [0.204, 0.257] | [0.760, 0.828] | [0.340, 0.422] |
| Qwen3.7-Max | [0.230, 0.283] | [0.638, 0.700] | [0.158, 0.207] | [0.784, 0.852] | [0.268, 0.348] |

### thinking: total error-budget distribution

| Model | Mean | B=0 | B=1 | B=2 | B=3 | B=4 | B>=5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 1.984 | 0.246 | 0.194 | 0.228 | 0.148 | 0.102 | 0.082 |
| Kimi-K2.6 | 2.522 | 0.182 | 0.158 | 0.232 | 0.156 | 0.124 | 0.148 |
| DeepSeek-V4-Flash | 2.740 | 0.178 | 0.112 | 0.232 | 0.180 | 0.130 | 0.168 |
| Qwen3.6-Flash | 2.816 | 0.164 | 0.114 | 0.234 | 0.176 | 0.124 | 0.188 |
| GLM-5.2 | 2.764 | 0.148 | 0.130 | 0.250 | 0.164 | 0.128 | 0.180 |
| Qwen3-8B | 2.754 | 0.142 | 0.140 | 0.220 | 0.202 | 0.134 | 0.162 |
| DeepSeek-V4-Pro | 3.222 | 0.136 | 0.104 | 0.210 | 0.182 | 0.136 | 0.232 |
| Qwen3.5-35B-A3B | 3.102 | 0.128 | 0.102 | 0.232 | 0.162 | 0.148 | 0.228 |
| Qwen3.7-Max | 3.172 | 0.108 | 0.112 | 0.232 | 0.178 | 0.136 | 0.234 |

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

## nonthinking: three-layer full-memory results

| Model | SCS(0.5) up | sOPB(0.5) down | sUPB(0.5) down | Directional H up | Any OPB down | Any UPB down | Event H up | Exact up |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 0.417 | 0.360 | 0.333 | 0.653 | 0.506 | 0.512 | 0.491 | 0.230 |
| Kimi-K2.6 | 0.359 | 0.495 | 0.260 | 0.600 | 0.636 | 0.410 | 0.450 | 0.198 |
| GLM-5.2 | 0.309 | 0.556 | 0.252 | 0.557 | 0.704 | 0.398 | 0.397 | 0.150 |
| Qwen3-8B | 0.301 | 0.328 | 0.503 | 0.571 | 0.444 | 0.704 | 0.386 | 0.132 |
| DeepSeek-V4-Flash | 0.294 | 0.577 | 0.272 | 0.535 | 0.740 | 0.430 | 0.357 | 0.136 |
| DeepSeek-V4-Pro | 0.292 | 0.599 | 0.249 | 0.523 | 0.760 | 0.398 | 0.343 | 0.136 |
| Qwen3.7-Max | 0.285 | 0.592 | 0.257 | 0.527 | 0.742 | 0.404 | 0.360 | 0.130 |
| Qwen3.6-Flash | 0.268 | 0.638 | 0.254 | 0.488 | 0.794 | 0.406 | 0.306 | 0.126 |
| Qwen3.5-35B-A3B | 0.256 | 0.664 | 0.227 | 0.469 | 0.820 | 0.380 | 0.279 | 0.110 |

### nonthinking: sample-bootstrap 95% intervals

| Model | SCS | sOPB | sUPB | Any OPB | Any UPB |
| --- | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | [0.388, 0.447] | [0.327, 0.393] | [0.302, 0.362] | [0.462, 0.552] | [0.468, 0.556] |
| Kimi-K2.6 | [0.328, 0.390] | [0.459, 0.527] | [0.231, 0.291] | [0.592, 0.676] | [0.368, 0.456] |
| GLM-5.2 | [0.280, 0.339] | [0.521, 0.589] | [0.221, 0.281] | [0.662, 0.744] | [0.354, 0.442] |
| Qwen3-8B | [0.274, 0.330] | [0.294, 0.361] | [0.470, 0.535] | [0.398, 0.486] | [0.662, 0.744] |
| DeepSeek-V4-Flash | [0.266, 0.321] | [0.544, 0.607] | [0.242, 0.300] | [0.702, 0.778] | [0.384, 0.472] |
| DeepSeek-V4-Pro | [0.264, 0.322] | [0.567, 0.630] | [0.222, 0.277] | [0.722, 0.796] | [0.356, 0.442] |
| Qwen3.7-Max | [0.258, 0.311] | [0.560, 0.625] | [0.229, 0.286] | [0.706, 0.780] | [0.362, 0.446] |
| Qwen3.6-Flash | [0.242, 0.296] | [0.607, 0.667] | [0.225, 0.282] | [0.758, 0.828] | [0.362, 0.448] |
| Qwen3.5-35B-A3B | [0.230, 0.284] | [0.632, 0.693] | [0.201, 0.254] | [0.786, 0.854] | [0.336, 0.422] |

### nonthinking: total error-budget distribution

| Model | Mean | B=0 | B=1 | B=2 | B=3 | B=4 | B>=5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 2.002 | 0.230 | 0.196 | 0.246 | 0.158 | 0.092 | 0.078 |
| Kimi-K2.6 | 2.556 | 0.198 | 0.148 | 0.228 | 0.158 | 0.120 | 0.148 |
| GLM-5.2 | 2.720 | 0.150 | 0.124 | 0.272 | 0.136 | 0.146 | 0.172 |
| Qwen3-8B | 2.640 | 0.132 | 0.138 | 0.250 | 0.202 | 0.144 | 0.134 |
| DeepSeek-V4-Flash | 2.820 | 0.136 | 0.122 | 0.242 | 0.212 | 0.118 | 0.170 |
| DeepSeek-V4-Pro | 3.052 | 0.136 | 0.138 | 0.224 | 0.154 | 0.132 | 0.216 |
| Qwen3.7-Max | 2.898 | 0.130 | 0.122 | 0.234 | 0.186 | 0.142 | 0.186 |
| Qwen3.6-Flash | 3.168 | 0.126 | 0.112 | 0.210 | 0.162 | 0.140 | 0.250 |
| Qwen3.5-35B-A3B | 3.318 | 0.110 | 0.120 | 0.216 | 0.154 | 0.138 | 0.262 |

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

| Model | SCS non-think | SCS think | Delta SCS | Delta sOPB | Delta sUPB | Delta Any OPB | Delta Any UPB | Delta Exact |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 0.417 | 0.427 | +0.010 | -0.007 | -0.003 | -0.016 | -0.004 | +0.016 |
| Kimi-K2.6 | 0.359 | 0.349 | -0.010 | -0.001 | +0.017 | +0.002 | +0.014 | -0.016 |
| DeepSeek-V4-Flash | 0.294 | 0.326 | +0.031 | -0.009 | -0.033 | -0.024 | -0.048 | +0.042 |
| Qwen3.6-Flash | 0.268 | 0.313 | +0.045 | -0.072 | +0.002 | -0.078 | -0.008 | +0.038 |
| GLM-5.2 | 0.309 | 0.307 | -0.002 | +0.046 | -0.054 | +0.056 | -0.070 | -0.002 |
| Qwen3-8B | 0.301 | 0.304 | +0.003 | +0.149 | -0.116 | +0.178 | -0.124 | +0.010 |
| DeepSeek-V4-Pro | 0.292 | 0.276 | -0.017 | +0.049 | -0.050 | +0.042 | -0.078 | +0.000 |
| Qwen3.5-35B-A3B | 0.256 | 0.271 | +0.015 | -0.021 | +0.002 | -0.026 | +0.000 | +0.018 |
| Qwen3.7-Max | 0.285 | 0.257 | -0.028 | +0.078 | -0.075 | +0.076 | -0.096 | -0.022 |

Negative deltas are improvements for sOPB/sUPB and Any OPB/UPB; positive deltas are
improvements for SCS/Exact.
Codex reuses identical answers and therefore remains a repeated-Judge control rather than an answer-mode effect.

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
