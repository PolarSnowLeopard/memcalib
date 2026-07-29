# MemCalib v2.1 thinking-mode candidate metric study

This diagnostic uses the locked 500 records and all 8,000 primary-Judge rows from the eight-model thinking-enabled full/no-memory comparison. It does not change the official metric definition.

## Headline comparison

| Model | OPB↓ | UPB↓ | H↑ | MinCalib↑ | MCC↑ | Linear κ↑ | CVaR90↓ | PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.307 | 0.207 | 0.740 | 0.693 | 0.498 | 0.425 | 0.599 | 0.448 |
| Qwen3.5-35B-A3B | 0.347 | 0.181 | 0.727 | 0.653 | 0.491 | 0.402 | 0.588 | 0.441 |
| GLM-5.2 | 0.372 | 0.156 | 0.720 | 0.628 | 0.497 | 0.386 | 0.591 | 0.430 |
| DeepSeek-V4-Pro | 0.402 | 0.137 | 0.707 | 0.598 | 0.493 | 0.361 | 0.624 | 0.419 |
| Qwen3.6-Flash | 0.384 | 0.189 | 0.700 | 0.616 | 0.448 | 0.348 | 0.628 | 0.397 |
| DeepSeek-V4-Flash | 0.384 | 0.193 | 0.699 | 0.616 | 0.444 | 0.345 | 0.609 | 0.383 |
| Qwen3.7-Max | 0.432 | 0.127 | 0.689 | 0.568 | 0.480 | 0.337 | 0.613 | 0.410 |
| Qwen3-8B | 0.304 | 0.339 | 0.678 | 0.661 | 0.361 | 0.319 | 0.692 | 0.322 |

Numeric ranges across differently scaled metrics are not directly comparable. Use paired confidence intervals and ranking robustness, not range alone.

## Classification and chance-corrected metrics

| Model | Exact↑ | Balanced acc.↑ | Macro F1↑ | MCC↑ | κ↑ | Linear κ↑ | Quadratic κ↑ | NMI↑ | Cramér V↑ | Ordinal r↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.660 | 0.657 | 0.649 | 0.498 | 0.490 | 0.425 | 0.360 | 0.301 | 0.549 | 0.368 |
| Qwen3.5-35B-A3B | 0.654 | 0.648 | 0.633 | 0.491 | 0.480 | 0.402 | 0.322 | 0.300 | 0.539 | 0.337 |
| GLM-5.2 | 0.655 | 0.648 | 0.628 | 0.497 | 0.481 | 0.386 | 0.289 | 0.305 | 0.544 | 0.309 |
| DeepSeek-V4-Pro | 0.648 | 0.641 | 0.614 | 0.493 | 0.471 | 0.361 | 0.247 | 0.316 | 0.546 | 0.272 |
| Qwen3.6-Flash | 0.624 | 0.618 | 0.598 | 0.448 | 0.435 | 0.348 | 0.260 | 0.278 | 0.515 | 0.275 |
| DeepSeek-V4-Flash | 0.622 | 0.616 | 0.595 | 0.444 | 0.432 | 0.345 | 0.256 | 0.279 | 0.514 | 0.271 |
| Qwen3.7-Max | 0.635 | 0.628 | 0.598 | 0.480 | 0.452 | 0.337 | 0.222 | 0.308 | 0.539 | 0.251 |
| Qwen3-8B | 0.572 | 0.571 | 0.569 | 0.361 | 0.359 | 0.319 | 0.279 | 0.200 | 0.442 | 0.280 |

## Ordinal severity metrics

| Model | MAE↓ | RMSE↓ | Macro L1↑ | Macro L2↑ | A↔C atom rate↓ | Over quadratic cost↓ | Under quadratic cost↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.512 | 0.925 | 0.685 | 0.699 | 0.172 | 0.392 | 0.133 |
| Qwen3.5-35B-A3B | 0.523 | 0.937 | 0.687 | 0.707 | 0.177 | 0.427 | 0.111 |
| GLM-5.2 | 0.537 | 0.960 | 0.683 | 0.700 | 0.192 | 0.469 | 0.096 |
| DeepSeek-V4-Pro | 0.559 | 0.987 | 0.673 | 0.688 | 0.208 | 0.510 | 0.089 |
| Qwen3.6-Flash | 0.575 | 0.985 | 0.655 | 0.673 | 0.198 | 0.474 | 0.121 |
| DeepSeek-V4-Flash | 0.575 | 0.985 | 0.656 | 0.675 | 0.197 | 0.477 | 0.118 |
| Qwen3.7-Max | 0.585 | 1.012 | 0.654 | 0.667 | 0.220 | 0.555 | 0.075 |
| Qwen3-8B | 0.608 | 0.984 | 0.619 | 0.642 | 0.180 | 0.368 | 0.224 |

## Composite-score sensitivity

| Model | H | Arithmetic | Geometric | Product | Softmin −2 | Softmin −4 | Softmin −8 | MinCalib | Ideal L2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.740 | 0.743 | 0.741 | 0.549 | 0.738 | 0.735 | 0.728 | 0.693 | 0.738 |
| Qwen3.5-35B-A3B | 0.727 | 0.736 | 0.732 | 0.535 | 0.722 | 0.714 | 0.699 | 0.653 | 0.724 |
| GLM-5.2 | 0.720 | 0.736 | 0.728 | 0.530 | 0.713 | 0.699 | 0.678 | 0.628 | 0.715 |
| DeepSeek-V4-Pro | 0.707 | 0.731 | 0.718 | 0.516 | 0.695 | 0.675 | 0.648 | 0.598 | 0.700 |
| Qwen3.6-Flash | 0.700 | 0.713 | 0.707 | 0.499 | 0.694 | 0.682 | 0.663 | 0.616 | 0.697 |
| DeepSeek-V4-Flash | 0.699 | 0.712 | 0.705 | 0.498 | 0.693 | 0.681 | 0.663 | 0.616 | 0.696 |
| Qwen3.7-Max | 0.689 | 0.721 | 0.704 | 0.496 | 0.674 | 0.649 | 0.617 | 0.568 | 0.682 |
| Qwen3-8B | 0.678 | 0.678 | 0.678 | 0.460 | 0.678 | 0.677 | 0.676 | 0.661 | 0.678 |

## Sample-level tail risk

| Model | Strict sample↑ | Any A↔C sample↓ | Mean L1 loss↓ | P90↓ | CVaR90↓ | CVaR95↓ | Quadratic CVaR90↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.222 | 0.556 | 0.261 | 0.500 | 0.599 | 0.691 | 0.520 |
| Qwen3.5-35B-A3B | 0.202 | 0.566 | 0.267 | 0.500 | 0.588 | 0.668 | 0.522 |
| GLM-5.2 | 0.196 | 0.632 | 0.275 | 0.500 | 0.591 | 0.675 | 0.511 |
| DeepSeek-V4-Pro | 0.158 | 0.674 | 0.287 | 0.500 | 0.624 | 0.702 | 0.541 |
| Qwen3.6-Flash | 0.154 | 0.634 | 0.293 | 0.500 | 0.628 | 0.699 | 0.544 |
| DeepSeek-V4-Flash | 0.140 | 0.638 | 0.294 | 0.500 | 0.609 | 0.686 | 0.533 |
| Qwen3.7-Max | 0.130 | 0.726 | 0.299 | 0.500 | 0.613 | 0.707 | 0.523 |
| Qwen3-8B | 0.142 | 0.538 | 0.308 | 0.500 | 0.692 | 0.748 | 0.611 |

CVaR90 is the mean loss among the worst 10% of samples; CVaR95 uses the worst 5%. Sample loss is normalized absolute ordinal distance.

### Why CVaR90 can reorder models

| Model | H rank | Mean L1 rank | CVaR90 rank | CVaR90↓ |
| --- | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 1 | 1 | 3 | 0.599 |
| Qwen3.5-35B-A3B | 2 | 2 | 1 | 0.588 |
| GLM-5.2 | 3 | 3 | 2 | 0.591 |
| DeepSeek-V4-Pro | 4 | 4 | 6 | 0.624 |
| Qwen3.6-Flash | 5 | 5 | 7 | 0.628 |
| DeepSeek-V4-Flash | 6 | 6 | 4 | 0.609 |
| Qwen3.7-Max | 7 | 7 | 5 | 0.613 |
| Qwen3-8B | 8 | 8 | 8 | 0.692 |

For a full-memory sample `s` with `n_s` scorable atoms, `L_s = mean_i(|u_hat_si - u*_si| / 2)`. CVaR90 is the arithmetic mean of the largest 50 values of `L_s` among the locked 500 samples. It therefore changes both the aggregation unit (sample rather than gold-label macro average) and the evaluated population (only the worst decile).

A model can make moderately sized errors across many samples and have worse H or mean loss but a less extreme worst decile. Conversely, errors concentrated within a smaller set of samples increase CVaR90. The ordering difference is expected and is not an arithmetic inconsistency.

[Open the tail, Pareto, and metric-rank diagnostics](candidate-metric-diagnostics.html).

## Paired memory utility

| Model | Induced OPB↓ | Reduced UPB↑ | PMU(0.5)↑ | PMU(1)↑ | PMU(2)↑ | Relative PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.261 | 0.708 | 0.578 | 0.448 | 0.187 | 0.513 |
| Qwen3.5-35B-A3B | 0.293 | 0.734 | 0.587 | 0.441 | 0.148 | 0.509 |
| GLM-5.2 | 0.318 | 0.748 | 0.589 | 0.430 | 0.113 | 0.509 |
| DeepSeek-V4-Pro | 0.351 | 0.770 | 0.594 | 0.419 | 0.068 | 0.498 |
| Qwen3.6-Flash | 0.326 | 0.723 | 0.560 | 0.397 | 0.071 | 0.467 |
| DeepSeek-V4-Flash | 0.339 | 0.723 | 0.553 | 0.383 | 0.044 | 0.451 |
| Qwen3.7-Max | 0.369 | 0.779 | 0.594 | 0.410 | 0.041 | 0.491 |
| Qwen3-8B | 0.273 | 0.595 | 0.458 | 0.322 | 0.049 | 0.364 |

`PMU(λ) = reduced_UPB - λ × induced_OPB`. Its ranking is a policy choice, so the weight sensitivity must remain visible.

## Latent and pairwise models

| Model | Rasch over θ↑ | Rasch under θ↑ | Mean θ↑ | Min θ↑ | Bradley–Terry ability↑ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.996 | -0.275 | 0.360 | -0.275 | 0.180 |
| Qwen3.5-35B-A3B | 0.335 | 0.098 | 0.217 | 0.098 | 0.132 |
| GLM-5.2 | -0.093 | 0.465 | 0.186 | -0.093 | 0.077 |
| DeepSeek-V4-Pro | -0.590 | 0.771 | 0.091 | -0.590 | 0.002 |
| Qwen3.6-Flash | -0.298 | -0.029 | -0.164 | -0.298 | -0.062 |
| DeepSeek-V4-Flash | -0.283 | -0.075 | -0.179 | -0.283 | -0.073 |
| Qwen3.7-Max | -1.125 | 0.942 | -0.092 | -1.125 | -0.109 |
| Qwen3-8B | 1.059 | -1.898 | -0.419 | -1.898 | -0.147 |

The two Rasch dimensions adjust separately for atom difficulty. The current 1PL fit is exploratory: standard errors condition on estimated item difficulties and are not a full Bayesian uncertainty estimate.

## Pairwise win-share matrix

Rows are the candidate model; each cell is its win share against the column model using full-memory normalized sample-level ordinal loss. Ties count 0.5.

| Model | Kimi-K2.6 | Qwen3.5-35B-A3B | GLM-5.2 | DeepSeek-V4-Pro | Qwen3.6-Flash | DeepSeek-V4-Flash | Qwen3.7-Max | Qwen3-8B |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | — | 0.518 | 0.521 | 0.547 | 0.561 | 0.566 | 0.573 | 0.572 |
| Qwen3.5-35B-A3B | 0.482 | — | 0.512 | 0.537 | 0.554 | 0.553 | 0.554 | 0.571 |
| GLM-5.2 | 0.479 | 0.488 | — | 0.516 | 0.536 | 0.529 | 0.550 | 0.555 |
| DeepSeek-V4-Pro | 0.453 | 0.463 | 0.484 | — | 0.510 | 0.522 | 0.538 | 0.535 |
| Qwen3.6-Flash | 0.439 | 0.446 | 0.464 | 0.490 | — | 0.502 | 0.515 | 0.520 |
| DeepSeek-V4-Flash | 0.434 | 0.447 | 0.471 | 0.478 | 0.498 | — | 0.506 | 0.521 |
| Qwen3.7-Max | 0.427 | 0.446 | 0.450 | 0.462 | 0.485 | 0.494 | — | 0.519 |
| Qwen3-8B | 0.428 | 0.429 | 0.445 | 0.465 | 0.480 | 0.479 | 0.481 | — |

## Pareto analysis

Non-dominated OPB–UPB models: DeepSeek-V4-Pro, GLM-5.2, Kimi-K2.6, Qwen3.7-Max, Qwen3-8B, Qwen3.5-35B-A3B.

## Observed metric spread

| Metric | Minimum | Maximum | Range | Population SD |
| --- | ---: | ---: | ---: | ---: |
| quadratic_kappa | 0.222 | 0.360 | 0.138 | 0.041 |
| MCC | 0.361 | 0.498 | 0.137 | 0.044 |
| PMU_lambda_1 | 0.322 | 0.448 | 0.126 | 0.038 |
| MinCalib | 0.568 | 0.693 | 0.124 | 0.036 |
| linear_kappa | 0.319 | 0.425 | 0.106 | 0.034 |
| CVaR90_linear_loss | 0.588 | 0.692 | 0.105 | 0.031 |
| strict_sample_accuracy | 0.130 | 0.222 | 0.092 | 0.032 |
| product_resistance | 0.460 | 0.549 | 0.090 | 0.027 |
| balanced_accuracy | 0.571 | 0.657 | 0.086 | 0.026 |
| macro_F1 | 0.569 | 0.649 | 0.080 | 0.024 |
| H | 0.678 | 0.740 | 0.062 | 0.019 |

## Sample-cluster bootstrap uncertainty

| Model | H 95% CI | MinCalib 95% CI | MCC 95% CI | Linear κ 95% CI | Strict sample 95% CI | CVaR90 95% CI | PMU(1) 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | [0.724, 0.755] | [0.670, 0.715] | [0.465, 0.531] | [0.389, 0.461] | [0.186, 0.260] | [0.562, 0.642] | [0.408, 0.485] |
| Qwen3.5-35B-A3B | [0.710, 0.743] | [0.631, 0.674] | [0.456, 0.525] | [0.365, 0.438] | [0.166, 0.238] | [0.553, 0.627] | [0.403, 0.478] |
| GLM-5.2 | [0.703, 0.737] | [0.606, 0.650] | [0.463, 0.530] | [0.349, 0.421] | [0.162, 0.232] | [0.559, 0.630] | [0.392, 0.467] |
| DeepSeek-V4-Pro | [0.691, 0.722] | [0.578, 0.619] | [0.461, 0.524] | [0.326, 0.395] | [0.126, 0.190] | [0.585, 0.668] | [0.381, 0.456] |
| Qwen3.6-Flash | [0.684, 0.716] | [0.595, 0.638] | [0.413, 0.480] | [0.313, 0.386] | [0.124, 0.186] | [0.588, 0.672] | [0.360, 0.436] |
| DeepSeek-V4-Flash | [0.684, 0.715] | [0.596, 0.636] | [0.412, 0.477] | [0.311, 0.379] | [0.110, 0.170] | [0.573, 0.649] | [0.348, 0.421] |
| Qwen3.7-Max | [0.670, 0.705] | [0.546, 0.590] | [0.448, 0.512] | [0.305, 0.370] | [0.100, 0.160] | [0.569, 0.660] | [0.376, 0.446] |
| Qwen3-8B | [0.659, 0.696] | [0.631, 0.688] | [0.325, 0.397] | [0.277, 0.359] | [0.112, 0.172] | [0.638, 0.727] | [0.284, 0.360] |

All intervals resample the same 500 sample IDs as clusters and preserve their full/no-memory atom groups.

## Interpretation boundary

- MCC, Kappa, NMI, and ordinal correlation discard the over-use versus under-use direction even when they improve numerical separation.
- Product and power-mean scores partly enlarge the numeric range through rescaling; this does not create new statistical evidence.
- PMU depends on the full/no-memory causal contrast and on λ.
- CVaR exposes tail failures but should not replace average performance.
- Brier score, log loss, and ordinal CRPS are not validly computable without a probability distribution over A/B/C.
- Pairwise bootstrap intervals and blinded human validation remain necessary before making significance or external leaderboard claims.
