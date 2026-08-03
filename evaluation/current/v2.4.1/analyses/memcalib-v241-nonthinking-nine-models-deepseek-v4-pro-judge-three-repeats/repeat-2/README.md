# MemCalib v2.4.1 Non-Think DeepSeek-V4-Pro Judge repeat 2

Locked 494-record, nine-model, paired full-memory/no-memory evaluation; independent answer repeat 2 of 3; all primary judgments by DeepSeek-V4-Pro using the broad Bailian credential.

## Headline comparison

| Model | OPB↓ | UPB↓ | H↑ | MinCalib↑ | MCC↑ | Linear κ↑ | CVaR90↓ | PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.6-Flash | 0.087 | 0.160 | 0.875 | 0.840 | 0.580 | 0.599 | 0.291 | 0.596 |
| Kimi-K2.6 | 0.061 | 0.194 | 0.867 | 0.806 | 0.621 | 0.660 | 0.247 | 0.612 |
| DeepSeek-V4-Pro | 0.070 | 0.190 | 0.866 | 0.810 | 0.599 | 0.624 | 0.275 | 0.598 |
| Qwen3.5-35B-A3B | 0.087 | 0.179 | 0.865 | 0.821 | 0.564 | 0.589 | 0.297 | 0.577 |
| GLM-5.2 | 0.057 | 0.216 | 0.856 | 0.784 | 0.621 | 0.656 | 0.240 | 0.565 |
| Codex GPT-5.6 Sol | 0.028 | 0.266 | 0.837 | 0.734 | 0.683 | 0.731 | 0.208 | 0.579 |
| DeepSeek-V4-Flash | 0.057 | 0.253 | 0.834 | 0.747 | 0.598 | 0.642 | 0.245 | 0.568 |
| Qwen3.7-Max | 0.059 | 0.261 | 0.828 | 0.739 | 0.594 | 0.636 | 0.254 | 0.505 |
| Qwen3-8B | 0.032 | 0.479 | 0.677 | 0.521 | 0.520 | 0.574 | 0.280 | 0.407 |

Numeric ranges across differently scaled metrics are not directly comparable. Use paired confidence intervals and ranking robustness, not range alone.

## Classification and chance-corrected metrics

| Model | Exact↑ | Balanced acc.↑ | Macro F1↑ | MCC↑ | κ↑ | Linear κ↑ | Quadratic κ↑ | NMI↑ | Cramér V↑ | Ordinal r↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.6-Flash | 0.836 | 0.835 | 0.716 | 0.580 | 0.545 | 0.599 | 0.650 | 0.366 | 0.624 | 0.674 |
| Kimi-K2.6 | 0.871 | 0.830 | 0.753 | 0.621 | 0.604 | 0.660 | 0.712 | 0.407 | 0.664 | 0.722 |
| DeepSeek-V4-Pro | 0.857 | 0.827 | 0.732 | 0.599 | 0.577 | 0.624 | 0.666 | 0.376 | 0.632 | 0.682 |
| Qwen3.5-35B-A3B | 0.831 | 0.823 | 0.711 | 0.564 | 0.532 | 0.589 | 0.644 | 0.353 | 0.617 | 0.666 |
| GLM-5.2 | 0.876 | 0.818 | 0.752 | 0.621 | 0.608 | 0.656 | 0.700 | 0.396 | 0.653 | 0.707 |
| Codex GPT-5.6 Sol | 0.912 | 0.804 | 0.794 | 0.683 | 0.682 | 0.731 | 0.773 | 0.469 | 0.705 | 0.773 |
| DeepSeek-V4-Flash | 0.872 | 0.794 | 0.737 | 0.598 | 0.588 | 0.642 | 0.689 | 0.374 | 0.632 | 0.696 |
| Qwen3.7-Max | 0.873 | 0.786 | 0.733 | 0.594 | 0.586 | 0.636 | 0.679 | 0.364 | 0.622 | 0.686 |
| Qwen3-8B | 0.874 | 0.659 | 0.674 | 0.520 | 0.520 | 0.574 | 0.622 | 0.296 | 0.537 | 0.625 |

## Ordinal severity metrics

| Model | MAE↓ | RMSE↓ | Macro L1↑ | Macro L2↑ | A↔C atom rate↓ | Over quadratic cost↓ | Under quadratic cost↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.6-Flash | 0.198 | 0.516 | 0.870 | 0.887 | 0.034 | 0.067 | 0.094 |
| Kimi-K2.6 | 0.154 | 0.450 | 0.858 | 0.872 | 0.024 | 0.045 | 0.121 |
| DeepSeek-V4-Pro | 0.177 | 0.496 | 0.855 | 0.869 | 0.034 | 0.058 | 0.120 |
| Qwen3.5-35B-A3B | 0.202 | 0.518 | 0.856 | 0.873 | 0.033 | 0.066 | 0.110 |
| GLM-5.2 | 0.152 | 0.457 | 0.843 | 0.856 | 0.028 | 0.044 | 0.148 |
| Codex GPT-5.6 Sol | 0.107 | 0.383 | 0.821 | 0.829 | 0.020 | 0.024 | 0.173 |
| DeepSeek-V4-Flash | 0.157 | 0.465 | 0.817 | 0.829 | 0.030 | 0.045 | 0.162 |
| Qwen3.7-Max | 0.160 | 0.474 | 0.808 | 0.819 | 0.032 | 0.046 | 0.173 |
| Qwen3-8B | 0.158 | 0.472 | 0.696 | 0.714 | 0.032 | 0.027 | 0.348 |

## Composite-score sensitivity

| Model | H | Arithmetic | Geometric | Product | Softmin −2 | Softmin −4 | Softmin −8 | MinCalib | Ideal L2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.6-Flash | 0.875 | 0.876 | 0.876 | 0.767 | 0.874 | 0.873 | 0.870 | 0.840 | 0.871 |
| Kimi-K2.6 | 0.867 | 0.873 | 0.870 | 0.757 | 0.865 | 0.860 | 0.851 | 0.806 | 0.856 |
| DeepSeek-V4-Pro | 0.866 | 0.870 | 0.868 | 0.753 | 0.864 | 0.860 | 0.852 | 0.810 | 0.857 |
| Qwen3.5-35B-A3B | 0.865 | 0.867 | 0.866 | 0.749 | 0.863 | 0.861 | 0.856 | 0.821 | 0.859 |
| GLM-5.2 | 0.856 | 0.864 | 0.860 | 0.740 | 0.853 | 0.846 | 0.833 | 0.784 | 0.842 |
| Codex GPT-5.6 Sol | 0.837 | 0.853 | 0.845 | 0.714 | 0.829 | 0.814 | 0.791 | 0.734 | 0.811 |
| DeepSeek-V4-Flash | 0.834 | 0.845 | 0.839 | 0.705 | 0.828 | 0.818 | 0.800 | 0.747 | 0.817 |
| Qwen3.7-Max | 0.828 | 0.840 | 0.834 | 0.695 | 0.822 | 0.810 | 0.792 | 0.739 | 0.811 |
| Qwen3-8B | 0.677 | 0.744 | 0.710 | 0.504 | 0.649 | 0.607 | 0.568 | 0.521 | 0.660 |

## Sample-level tail risk

| Model | Strict sample↑ | Any A↔C sample↓ | Mean L1 loss↓ | P90↓ | CVaR90↓ | CVaR95↓ | Quadratic CVaR90↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.6-Flash | 0.132 | 0.460 | 0.112 | 0.226 | 0.291 | 0.341 | 0.224 |
| Kimi-K2.6 | 0.211 | 0.348 | 0.089 | 0.200 | 0.247 | 0.281 | 0.182 |
| DeepSeek-V4-Pro | 0.148 | 0.464 | 0.101 | 0.222 | 0.275 | 0.309 | 0.208 |
| Qwen3.5-35B-A3B | 0.107 | 0.441 | 0.115 | 0.227 | 0.297 | 0.339 | 0.230 |
| GLM-5.2 | 0.213 | 0.393 | 0.086 | 0.192 | 0.240 | 0.276 | 0.186 |
| Codex GPT-5.6 Sol | 0.298 | 0.271 | 0.063 | 0.153 | 0.208 | 0.248 | 0.164 |
| DeepSeek-V4-Flash | 0.162 | 0.407 | 0.092 | 0.198 | 0.245 | 0.278 | 0.187 |
| Qwen3.7-Max | 0.176 | 0.437 | 0.093 | 0.200 | 0.254 | 0.286 | 0.206 |
| Qwen3-8B | 0.146 | 0.425 | 0.095 | 0.207 | 0.280 | 0.329 | 0.222 |

CVaR90 is the mean loss among the worst 10% of samples; CVaR95 uses the worst 5%. Sample loss is normalized absolute ordinal distance.

### Why CVaR90 can reorder models

| Model | H rank | Mean L1 rank | CVaR90 rank | CVaR90↓ |
| --- | ---: | ---: | ---: | ---: |
| Qwen3.6-Flash | 1 | 8 | 8 | 0.291 |
| Kimi-K2.6 | 2 | 3 | 4 | 0.247 |
| DeepSeek-V4-Pro | 3 | 7 | 6 | 0.275 |
| Qwen3.5-35B-A3B | 4 | 9 | 9 | 0.297 |
| GLM-5.2 | 5 | 2 | 2 | 0.240 |
| Codex GPT-5.6 Sol | 6 | 1 | 1 | 0.208 |
| DeepSeek-V4-Flash | 7 | 4 | 3 | 0.245 |
| Qwen3.7-Max | 8 | 5 | 5 | 0.254 |
| Qwen3-8B | 9 | 6 | 7 | 0.280 |

For a full-memory sample `s` with `n_s` scorable atoms, `L_s = mean_i(|u_hat_si - u*_si| / 2)`. CVaR90 is the arithmetic mean of the largest 50 values of `L_s` among the locked 494 samples. It therefore changes both the aggregation unit (sample rather than gold-label macro average) and the evaluated population (only the worst decile).

A model can make moderately sized errors across many samples and have worse H or mean loss but a less extreme worst decile. Conversely, errors concentrated within a smaller set of samples increase CVaR90. The ordering difference is expected and is not an arithmetic inconsistency.

[Open the tail, Pareto, and metric-rank diagnostics](candidate-metric-diagnostics.html).

## Paired memory utility

| Model | Induced OPB↓ | Reduced UPB↑ | PMU(0.5)↑ | PMU(1)↑ | PMU(2)↑ | Relative PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.6-Flash | 0.083 | 0.679 | 0.637 | 0.596 | 0.513 | 0.726 |
| Kimi-K2.6 | 0.058 | 0.671 | 0.641 | 0.612 | 0.554 | 0.717 |
| DeepSeek-V4-Pro | 0.068 | 0.666 | 0.632 | 0.598 | 0.530 | 0.710 |
| Qwen3.5-35B-A3B | 0.085 | 0.662 | 0.620 | 0.577 | 0.493 | 0.703 |
| GLM-5.2 | 0.053 | 0.618 | 0.592 | 0.565 | 0.512 | 0.688 |
| Codex GPT-5.6 Sol | 0.026 | 0.605 | 0.592 | 0.579 | 0.553 | 0.669 |
| DeepSeek-V4-Flash | 0.055 | 0.623 | 0.595 | 0.568 | 0.512 | 0.656 |
| Qwen3.7-Max | 0.056 | 0.561 | 0.533 | 0.505 | 0.449 | 0.626 |
| Qwen3-8B | 0.031 | 0.438 | 0.422 | 0.407 | 0.376 | 0.447 |

`PMU(λ) = reduced_UPB - λ × induced_OPB`. Its ranking is a policy choice, so the weight sensitivity must remain visible.

## Latent and pairwise models

| Model | Rasch over θ↑ | Rasch under θ↑ | Mean θ↑ | Min θ↑ | Bradley–Terry ability↑ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 1.317 | -0.289 | 0.514 | -0.289 | 0.641 |
| GLM-5.2 | 0.102 | 0.284 | 0.193 | 0.102 | 0.172 |
| Kimi-K2.6 | -0.117 | 0.541 | 0.212 | -0.117 | 0.106 |
| Qwen3.7-Max | 0.213 | -0.237 | -0.012 | -0.237 | 0.015 |
| DeepSeek-V4-Flash | 0.166 | -0.149 | 0.008 | -0.149 | 0.012 |
| Qwen3-8B | 1.177 | -2.476 | -0.649 | -2.476 | -0.023 |
| DeepSeek-V4-Pro | -0.483 | 0.592 | 0.055 | -0.483 | -0.158 |
| Qwen3.6-Flash | -1.172 | 0.994 | -0.089 | -1.172 | -0.361 |
| Qwen3.5-35B-A3B | -1.202 | 0.739 | -0.232 | -1.202 | -0.404 |

The two Rasch dimensions adjust separately for atom difficulty. The current 1PL fit is exploratory: standard errors condition on estimated item difficulties and are not a full Bayesian uncertainty estimate.

## Pairwise win-share matrix

Rows are the candidate model; each cell is its win share against the column model using full-memory normalized sample-level ordinal loss. Ties count 0.5.

| Model | Qwen3.6-Flash | Kimi-K2.6 | DeepSeek-V4-Pro | Qwen3.5-35B-A3B | GLM-5.2 | Codex GPT-5.6 Sol | DeepSeek-V4-Flash | Qwen3.7-Max | Qwen3-8B |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.6-Flash | — | 0.379 | 0.451 | 0.502 | 0.380 | 0.277 | 0.401 | 0.401 | 0.425 |
| Kimi-K2.6 | 0.621 | — | 0.563 | 0.629 | 0.485 | 0.378 | 0.522 | 0.516 | 0.522 |
| DeepSeek-V4-Pro | 0.549 | 0.437 | — | 0.570 | 0.417 | 0.313 | 0.465 | 0.446 | 0.459 |
| Qwen3.5-35B-A3B | 0.498 | 0.371 | 0.430 | — | 0.359 | 0.259 | 0.390 | 0.396 | 0.420 |
| GLM-5.2 | 0.620 | 0.515 | 0.583 | 0.641 | — | 0.381 | 0.547 | 0.547 | 0.549 |
| Codex GPT-5.6 Sol | 0.723 | 0.622 | 0.687 | 0.741 | 0.619 | — | 0.663 | 0.668 | 0.648 |
| DeepSeek-V4-Flash | 0.599 | 0.478 | 0.535 | 0.610 | 0.453 | 0.337 | — | 0.494 | 0.522 |
| Qwen3.7-Max | 0.599 | 0.484 | 0.554 | 0.604 | 0.453 | 0.332 | 0.506 | — | 0.503 |
| Qwen3-8B | 0.575 | 0.478 | 0.541 | 0.580 | 0.451 | 0.352 | 0.478 | 0.497 | — |

## Pareto analysis

Non-dominated OPB–UPB models: Codex GPT-5.6 Sol, DeepSeek-V4-Pro, GLM-5.2, Kimi-K2.6, Qwen3.6-Flash.

## Observed metric spread

| Metric | Minimum | Maximum | Range | Population SD |
| --- | ---: | ---: | ---: | ---: |
| MinCalib | 0.521 | 0.840 | 0.319 | 0.090 |
| product_resistance | 0.504 | 0.767 | 0.263 | 0.076 |
| PMU_lambda_1 | 0.407 | 0.612 | 0.205 | 0.060 |
| H | 0.677 | 0.875 | 0.198 | 0.058 |
| strict_sample_accuracy | 0.107 | 0.298 | 0.190 | 0.054 |
| balanced_accuracy | 0.659 | 0.835 | 0.176 | 0.051 |
| MCC | 0.520 | 0.683 | 0.163 | 0.042 |
| linear_kappa | 0.574 | 0.731 | 0.157 | 0.044 |
| quadratic_kappa | 0.622 | 0.773 | 0.150 | 0.042 |
| macro_F1 | 0.674 | 0.794 | 0.120 | 0.031 |
| CVaR90_linear_loss | 0.208 | 0.297 | 0.089 | 0.027 |

## Sample-cluster bootstrap uncertainty

| Model | H 95% CI | MinCalib 95% CI | MCC 95% CI | Linear κ 95% CI | Strict sample 95% CI | CVaR90 95% CI | PMU(1) 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.6-Flash | [0.863, 0.889] | [0.817, 0.865] | [0.561, 0.601] | [0.579, 0.619] | [0.103, 0.162] | [0.264, 0.322] | [0.564, 0.629] |
| Kimi-K2.6 | [0.851, 0.883] | [0.778, 0.832] | [0.598, 0.645] | [0.638, 0.683] | [0.176, 0.247] | [0.229, 0.265] | [0.579, 0.643] |
| DeepSeek-V4-Pro | [0.851, 0.880] | [0.784, 0.836] | [0.577, 0.621] | [0.601, 0.646] | [0.117, 0.180] | [0.255, 0.294] | [0.564, 0.632] |
| Qwen3.5-35B-A3B | [0.850, 0.878] | [0.795, 0.845] | [0.544, 0.585] | [0.568, 0.611] | [0.081, 0.136] | [0.272, 0.321] | [0.544, 0.612] |
| GLM-5.2 | [0.839, 0.872] | [0.755, 0.812] | [0.597, 0.644] | [0.633, 0.678] | [0.176, 0.251] | [0.221, 0.259] | [0.529, 0.601] |
| Codex GPT-5.6 Sol | [0.817, 0.854] | [0.704, 0.762] | [0.658, 0.707] | [0.708, 0.753] | [0.257, 0.338] | [0.186, 0.229] | [0.546, 0.610] |
| DeepSeek-V4-Flash | [0.816, 0.852] | [0.719, 0.776] | [0.575, 0.623] | [0.620, 0.665] | [0.130, 0.196] | [0.227, 0.264] | [0.536, 0.599] |
| Qwen3.7-Max | [0.810, 0.845] | [0.710, 0.768] | [0.569, 0.619] | [0.612, 0.659] | [0.144, 0.211] | [0.235, 0.272] | [0.472, 0.539] |
| Qwen3-8B | [0.647, 0.708] | [0.486, 0.558] | [0.491, 0.549] | [0.544, 0.602] | [0.115, 0.176] | [0.254, 0.304] | [0.372, 0.443] |

All intervals resample the same 494 sample IDs as clusters. Full/no-memory atom groups are preserved.

## Interpretation boundary

- MCC, Kappa, NMI, and ordinal correlation discard the over-use versus under-use direction even when they improve numerical separation.
- Product and power-mean scores partly enlarge the numeric range through rescaling; this does not create new statistical evidence.
- PMU depends on the full/no-memory causal contrast and on λ.
- CVaR exposes tail failures but should not replace average performance.
- Brier score, log loss, and ordinal CRPS are not validly computable without a probability distribution over A/B/C.
- Pairwise bootstrap intervals and blinded human validation remain necessary before making significance or external leaderboard claims.
