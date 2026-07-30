# MemCalib v2.3 nine-model candidate metric study

Locked 500-record, nine-model, paired full-memory/no-memory evaluation on MemCalib v2.3.

## Headline comparison

| Model | OPB↓ | UPB↓ | H↑ | MinCalib↑ | MCC↑ | Linear κ↑ | CVaR90↓ | PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GLM-5.2 | 0.078 | 0.173 | 0.872 | 0.827 | 0.623 | 0.634 | 0.272 | 0.638 |
| Qwen3.7-Max | 0.092 | 0.165 | 0.870 | 0.835 | 0.598 | 0.600 | 0.306 | 0.630 |
| DeepSeek-V4-Pro | 0.092 | 0.184 | 0.859 | 0.816 | 0.586 | 0.590 | 0.336 | 0.606 |
| Qwen3.5-35B-A3B | 0.087 | 0.200 | 0.853 | 0.800 | 0.588 | 0.595 | 0.308 | 0.617 |
| DeepSeek-V4-Flash | 0.070 | 0.216 | 0.850 | 0.784 | 0.613 | 0.628 | 0.299 | 0.610 |
| Qwen3.6-Flash | 0.078 | 0.234 | 0.837 | 0.766 | 0.595 | 0.615 | 0.303 | 0.577 |
| Kimi-K2.6 | 0.063 | 0.258 | 0.828 | 0.742 | 0.614 | 0.639 | 0.277 | 0.571 |
| Codex GPT-5.6 Sol | 0.046 | 0.310 | 0.801 | 0.690 | 0.648 | 0.689 | 0.242 | 0.555 |
| Qwen3heyi-8B | 0.057 | 0.364 | 0.760 | 0.636 | 0.554 | 0.588 | 0.288 | 0.499 |

Numeric ranges across differently scaled metrics are not directly comparable. Use paired confidence intervals and ranking robustness, not range alone.

## Classification and chance-corrected metrics

| Model | Exact↑ | Balanced acc.↑ | Macro F1↑ | MCC↑ | κ↑ | Linear κ↑ | Quadratic κ↑ | NMI↑ | Cramér V↑ | Ordinal r↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GLM-5.2 | 0.871 | 0.833 | 0.737 | 0.623 | 0.605 | 0.634 | 0.659 | 0.386 | 0.629 | 0.678 |
| Qwen3.7-Max | 0.856 | 0.829 | 0.716 | 0.598 | 0.575 | 0.600 | 0.621 | 0.363 | 0.603 | 0.649 |
| DeepSeek-V4-Pro | 0.852 | 0.816 | 0.708 | 0.586 | 0.563 | 0.590 | 0.612 | 0.346 | 0.590 | 0.638 |
| Qwen3.5-35B-A3B | 0.856 | 0.809 | 0.710 | 0.588 | 0.568 | 0.595 | 0.620 | 0.345 | 0.590 | 0.640 |
| DeepSeek-V4-Flash | 0.874 | 0.809 | 0.730 | 0.613 | 0.600 | 0.628 | 0.651 | 0.373 | 0.614 | 0.666 |
| Qwen3.6-Flash | 0.869 | 0.792 | 0.719 | 0.595 | 0.584 | 0.615 | 0.641 | 0.351 | 0.596 | 0.655 |
| Kimi-K2.6 | 0.883 | 0.786 | 0.735 | 0.614 | 0.608 | 0.639 | 0.665 | 0.370 | 0.614 | 0.672 |
| Codex GPT-5.6 Sol | 0.905 | 0.763 | 0.753 | 0.648 | 0.648 | 0.689 | 0.723 | 0.412 | 0.640 | 0.724 |
| Qwen3-8B | 0.871 | 0.719 | 0.689 | 0.554 | 0.552 | 0.588 | 0.619 | 0.311 | 0.548 | 0.622 |

## Ordinal severity metrics

| Model | MAE↓ | RMSE↓ | Macro L1↑ | Macro L2↑ | A↔C atom rate↓ | Over quadratic cost↓ | Under quadratic cost↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GLM-5.2 | 0.172 | 0.509 | 0.856 | 0.867 | 0.043 | 0.063 | 0.108 |
| Qwen3.7-Max | 0.198 | 0.552 | 0.851 | 0.862 | 0.054 | 0.078 | 0.094 |
| DeepSeek-V4-Pro | 0.201 | 0.555 | 0.841 | 0.853 | 0.053 | 0.077 | 0.113 |
| Qwen3.5-35B-A3B | 0.194 | 0.541 | 0.837 | 0.851 | 0.049 | 0.070 | 0.130 |
| DeepSeek-V4-Flash | 0.171 | 0.510 | 0.834 | 0.846 | 0.045 | 0.061 | 0.132 |
| Qwen3.6-Flash | 0.176 | 0.516 | 0.815 | 0.827 | 0.045 | 0.060 | 0.153 |
| Kimi-K2.6 | 0.157 | 0.489 | 0.806 | 0.816 | 0.041 | 0.051 | 0.172 |
| Codex GPT-5.6 Sol | 0.124 | 0.425 | 0.785 | 0.796 | 0.028 | 0.031 | 0.198 |
| Qwen3-8B | 0.172 | 0.507 | 0.754 | 0.771 | 0.043 | 0.048 | 0.243 |

## Composite-score sensitivity

| Model | H | Arithmetic | Geometric | Product | Softmin −2 | Softmin −4 | Softmin −8 | MinCalib | Ideal L2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GLM-5.2 | 0.872 | 0.875 | 0.873 | 0.763 | 0.871 | 0.868 | 0.863 | 0.827 | 0.866 |
| Qwen3.7-Max | 0.870 | 0.871 | 0.871 | 0.758 | 0.869 | 0.868 | 0.865 | 0.835 | 0.866 |
| DeepSeek-V4-Pro | 0.859 | 0.862 | 0.861 | 0.741 | 0.858 | 0.856 | 0.851 | 0.816 | 0.854 |
| Qwen3.5-35B-A3B | 0.853 | 0.857 | 0.855 | 0.731 | 0.851 | 0.847 | 0.840 | 0.800 | 0.846 |
| DeepSeek-V4-Flash | 0.850 | 0.857 | 0.854 | 0.729 | 0.847 | 0.841 | 0.831 | 0.784 | 0.839 |
| Qwen3.6-Flash | 0.837 | 0.844 | 0.840 | 0.706 | 0.833 | 0.826 | 0.814 | 0.766 | 0.825 |
| Kimi-K2.6 | 0.828 | 0.839 | 0.834 | 0.695 | 0.823 | 0.812 | 0.795 | 0.742 | 0.812 |
| Codex GPT-5.6 Sol | 0.801 | 0.822 | 0.811 | 0.658 | 0.791 | 0.772 | 0.746 | 0.690 | 0.778 |
| Qwen3-8B | 0.760 | 0.789 | 0.774 | 0.600 | 0.746 | 0.721 | 0.690 | 0.636 | 0.739 |

## Sample-level tail risk

| Model | Strict sample↑ | Any A↔C sample↓ | Mean L1 loss↓ | P90↓ | CVaR90↓ | CVaR95↓ | Quadratic CVaR90↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GLM-5.2 | 0.148 | 0.554 | 0.100 | 0.214 | 0.272 | 0.307 | 0.224 |
| Qwen3.7-Max | 0.108 | 0.672 | 0.115 | 0.250 | 0.306 | 0.345 | 0.255 |
| DeepSeek-V4-Pro | 0.136 | 0.624 | 0.116 | 0.250 | 0.336 | 0.395 | 0.283 |
| Qwen3.5-35B-A3B | 0.128 | 0.604 | 0.113 | 0.250 | 0.308 | 0.350 | 0.258 |
| DeepSeek-V4-Flash | 0.178 | 0.564 | 0.100 | 0.225 | 0.299 | 0.347 | 0.245 |
| Qwen3.6-Flash | 0.164 | 0.560 | 0.103 | 0.222 | 0.303 | 0.356 | 0.253 |
| Kimi-K2.6 | 0.182 | 0.528 | 0.093 | 0.214 | 0.277 | 0.321 | 0.230 |
| Codex GPT-5.6 Sol | 0.246 | 0.384 | 0.075 | 0.167 | 0.242 | 0.287 | 0.195 |
| Qwen3-8B | 0.142 | 0.526 | 0.103 | 0.222 | 0.288 | 0.334 | 0.243 |

CVaR90 is the mean loss among the worst 10% of samples; CVaR95 uses the worst 5%. Sample loss is normalized absolute ordinal distance.

### Why CVaR90 can reorder models

| Model | H rank | Mean L1 rank | CVaR90 rank | CVaR90↓ |
| --- | ---: | ---: | ---: | ---: |
| GLM-5.2 | 1 | 3 | 2 | 0.272 |
| Qwen3.7-Max | 2 | 8 | 7 | 0.306 |
| DeepSeek-V4-Pro | 3 | 9 | 9 | 0.336 |
| Qwen3.5-35B-A3B | 4 | 7 | 8 | 0.308 |
| DeepSeek-V4-Flash | 5 | 4 | 5 | 0.299 |
| Qwen3.6-Flash | 6 | 6 | 6 | 0.303 |
| Kimi-K2.6 | 7 | 2 | 3 | 0.277 |
| Codex GPT-5.6 Sol | 8 | 1 | 1 | 0.242 |
| Qwen3-8B | 9 | 5 | 4 | 0.288 |

For a full-memory sample `s` with `n_s` scorable atoms, `L_s = mean_i(|u_hat_si - u*_si| / 2)`. CVaR90 is the arithmetic mean of the largest 50 values of `L_s` among the locked 500 samples. It therefore changes both the aggregation unit (sample rather than gold-label macro average) and the evaluated population (only the worst decile).

A model can make moderately sized errors across many samples and have worse H or mean loss but a less extreme worst decile. Conversely, errors concentrated within a smaller set of samples increase CVaR90. The ordering difference is expected and is not an arithmetic inconsistency.

[Open the tail, Pareto, and metric-rank diagnostics](candidate-metric-diagnostics.html).

## Paired memory utility

| Model | Induced OPB↓ | Reduced UPB↑ | PMU(0.5)↑ | PMU(1)↑ | PMU(2)↑ | Relative PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GLM-5.2 | 0.072 | 0.710 | 0.674 | 0.638 | 0.566 | 0.732 |
| Qwen3.7-Max | 0.087 | 0.717 | 0.674 | 0.630 | 0.544 | 0.726 |
| DeepSeek-V4-Pro | 0.087 | 0.693 | 0.650 | 0.606 | 0.519 | 0.703 |
| Qwen3.5-35B-A3B | 0.082 | 0.698 | 0.657 | 0.617 | 0.535 | 0.696 |
| DeepSeek-V4-Flash | 0.065 | 0.675 | 0.643 | 0.610 | 0.545 | 0.692 |
| Qwen3.6-Flash | 0.072 | 0.649 | 0.613 | 0.577 | 0.504 | 0.662 |
| Kimi-K2.6 | 0.059 | 0.630 | 0.601 | 0.571 | 0.513 | 0.651 |
| Codex GPT-5.6 Sol | 0.041 | 0.596 | 0.575 | 0.555 | 0.513 | 0.617 |
| Qwen3-8B | 0.054 | 0.553 | 0.526 | 0.499 | 0.445 | 0.549 |

`PMU(λ) = reduced_UPB - λ × induced_OPB`. Its ranking is a policy choice, so the weight sensitivity must remain visible.

## Latent and pairwise models

| Model | Rasch over θ↑ | Rasch under θ↑ | Mean θ↑ | Min θ↑ | Bradley–Terry ability↑ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 1.345 | -0.894 | 0.226 | -0.894 | 0.552 |
| Kimi-K2.6 | 0.454 | -0.325 | 0.065 | -0.325 | 0.191 |
| DeepSeek-V4-Flash | -0.003 | 0.168 | 0.083 | -0.003 | 0.027 |
| Qwen3-8B | 0.542 | -1.452 | -0.455 | -1.452 | 0.016 |
| Qwen3.6-Flash | -0.048 | -0.050 | -0.049 | -0.050 | 0.005 |
| GLM-5.2 | -0.274 | 0.744 | 0.235 | -0.274 | 0.003 |
| DeepSeek-V4-Pro | -0.732 | 0.583 | -0.075 | -0.732 | -0.238 |
| Qwen3.5-35B-A3B | -0.572 | 0.386 | -0.093 | -0.572 | -0.265 |
| Qwen3.7-Max | -0.712 | 0.839 | 0.064 | -0.712 | -0.291 |

The two Rasch dimensions adjust separately for atom difficulty. The current 1PL fit is exploratory: standard errors condition on estimated item difficulties and are not a full Bayesian uncertainty estimate.

## Pairwise win-share matrix

Rows are the candidate model; each cell is its win share against the column model using full-memory normalized sample-level ordinal loss. Ties count 0.5.

| Model | GLM-5.2 | Qwen3.7-Max | DeepSeek-V4-Pro | Qwen3.5-35B-A3B | DeepSeek-V4-Flash | Qwen3.6-Flash | Kimi-K2.6 | Codex GPT-5.6 Sol | Qwen3-8B |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GLM-5.2 | — | 0.580 | 0.561 | 0.574 | 0.491 | 0.500 | 0.445 | 0.365 | 0.494 |
| Qwen3.7-Max | 0.420 | — | 0.499 | 0.487 | 0.418 | 0.430 | 0.375 | 0.300 | 0.432 |
| DeepSeek-V4-Pro | 0.439 | 0.501 | — | 0.516 | 0.431 | 0.434 | 0.401 | 0.319 | 0.436 |
| Qwen3.5-35B-A3B | 0.426 | 0.513 | 0.484 | — | 0.437 | 0.434 | 0.381 | 0.309 | 0.435 |
| DeepSeek-V4-Flash | 0.509 | 0.582 | 0.569 | 0.563 | — | 0.514 | 0.461 | 0.363 | 0.501 |
| Qwen3.6-Flash | 0.500 | 0.570 | 0.566 | 0.566 | 0.486 | — | 0.455 | 0.372 | 0.498 |
| Kimi-K2.6 | 0.555 | 0.625 | 0.599 | 0.619 | 0.539 | 0.545 | — | 0.403 | 0.539 |
| Codex GPT-5.6 Sol | 0.635 | 0.700 | 0.681 | 0.691 | 0.637 | 0.628 | 0.597 | — | 0.628 |
| Qwen3-8B | 0.506 | 0.568 | 0.564 | 0.565 | 0.499 | 0.502 | 0.461 | 0.372 | — |

## Pareto analysis

Non-dominated OPB–UPB models: Codex GPT-5.6 Sol, DeepSeek-V4-Flash, GLM-5.2, Kimi-K2.6, Qwen3.7-Max.

## Observed metric spread

| Metric | Minimum | Maximum | Range | Population SD |
| --- | ---: | ---: | ---: | ---: |
| MinCalib | 0.636 | 0.835 | 0.199 | 0.063 |
| product_resistance | 0.600 | 0.763 | 0.163 | 0.049 |
| PMU_lambda_1 | 0.499 | 0.638 | 0.139 | 0.041 |
| strict_sample_accuracy | 0.108 | 0.246 | 0.138 | 0.038 |
| balanced_accuracy | 0.719 | 0.833 | 0.113 | 0.034 |
| H | 0.760 | 0.872 | 0.112 | 0.034 |
| quadratic_kappa | 0.612 | 0.723 | 0.111 | 0.033 |
| linear_kappa | 0.588 | 0.689 | 0.101 | 0.030 |
| CVaR90_linear_loss | 0.242 | 0.336 | 0.094 | 0.025 |
| MCC | 0.554 | 0.648 | 0.093 | 0.025 |
| macro_F1 | 0.689 | 0.753 | 0.064 | 0.018 |

## Sample-cluster bootstrap uncertainty

| Model | H 95% CI | MinCalib 95% CI | MCC 95% CI | Linear κ 95% CI | Strict sample 95% CI | CVaR90 95% CI | PMU(1) 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GLM-5.2 | [0.859, 0.885] | [0.804, 0.849] | [0.602, 0.644] | [0.612, 0.654] | [0.118, 0.178] | [0.251, 0.291] | [0.608, 0.668] |
| Qwen3.7-Max | [0.856, 0.883] | [0.810, 0.858] | [0.576, 0.619] | [0.578, 0.620] | [0.082, 0.136] | [0.286, 0.330] | [0.599, 0.661] |
| DeepSeek-V4-Pro | [0.844, 0.874] | [0.790, 0.841] | [0.563, 0.609] | [0.566, 0.614] | [0.108, 0.168] | [0.299, 0.372] | [0.571, 0.638] |
| Qwen3.5-35B-A3B | [0.837, 0.867] | [0.775, 0.823] | [0.565, 0.611] | [0.571, 0.618] | [0.098, 0.158] | [0.284, 0.332] | [0.582, 0.647] |
| DeepSeek-V4-Flash | [0.834, 0.867] | [0.757, 0.810] | [0.589, 0.636] | [0.603, 0.651] | [0.144, 0.212] | [0.271, 0.327] | [0.578, 0.640] |
| Qwen3.6-Flash | [0.819, 0.853] | [0.737, 0.793] | [0.571, 0.619] | [0.591, 0.639] | [0.132, 0.198] | [0.272, 0.334] | [0.542, 0.610] |
| Kimi-K2.6 | [0.809, 0.846] | [0.711, 0.770] | [0.588, 0.638] | [0.613, 0.662] | [0.148, 0.214] | [0.251, 0.303] | [0.536, 0.607] |
| Codex GPT-5.6 Sol | [0.780, 0.821] | [0.660, 0.720] | [0.622, 0.674] | [0.665, 0.713] | [0.208, 0.286] | [0.219, 0.266] | [0.521, 0.589] |
| Qwen3-8B | [0.737, 0.779] | [0.605, 0.665] | [0.528, 0.580] | [0.560, 0.614] | [0.112, 0.172] | [0.263, 0.316] | [0.467, 0.530] |

All intervals resample the same 500 sample IDs as clusters and preserve their full/no-memory atom groups.

## Interpretation boundary

- MCC, Kappa, NMI, and ordinal correlation discard the over-use versus under-use direction even when they improve numerical separation.
- Product and power-mean scores partly enlarge the numeric range through rescaling; this does not create new statistical evidence.
- PMU depends on the full/no-memory causal contrast and on λ.
- CVaR exposes tail failures but should not replace average performance.
- Brier score, log loss, and ordinal CRPS are not validly computable without a probability distribution over A/B/C.
- Pairwise bootstrap intervals and blinded human validation remain necessary before making significance or external leaderboard claims.
