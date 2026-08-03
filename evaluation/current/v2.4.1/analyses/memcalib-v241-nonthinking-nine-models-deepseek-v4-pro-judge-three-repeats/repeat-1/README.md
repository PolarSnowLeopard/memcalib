# MemCalib v2.4.1 Non-Think DeepSeek-V4-Pro Judge repeat 1

Locked 494-record, nine-model, paired full-memory/no-memory evaluation; independent answer repeat 1 of 3; all primary judgments by DeepSeek-V4-Pro using the broad Bailian credential.

## Headline comparison

| Model | OPB↓ | UPB↓ | H↑ | MinCalib↑ | MCC↑ | Linear κ↑ | CVaR90↓ | PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.062 | 0.188 | 0.870 | 0.812 | 0.619 | 0.652 | 0.255 | 0.612 |
| Qwen3.6-Flash | 0.088 | 0.175 | 0.866 | 0.825 | 0.566 | 0.588 | 0.293 | 0.588 |
| Qwen3.5-35B-A3B | 0.088 | 0.175 | 0.866 | 0.825 | 0.570 | 0.590 | 0.291 | 0.579 |
| DeepSeek-V4-Pro | 0.071 | 0.206 | 0.857 | 0.794 | 0.582 | 0.605 | 0.283 | 0.577 |
| GLM-5.2 | 0.058 | 0.230 | 0.847 | 0.770 | 0.609 | 0.647 | 0.251 | 0.549 |
| Codex GPT-5.6 Sol | 0.028 | 0.259 | 0.841 | 0.741 | 0.700 | 0.745 | 0.204 | 0.571 |
| DeepSeek-V4-Flash | 0.059 | 0.243 | 0.839 | 0.757 | 0.595 | 0.637 | 0.267 | 0.571 |
| Qwen3.7-Max | 0.058 | 0.279 | 0.816 | 0.721 | 0.576 | 0.615 | 0.272 | 0.498 |
| Qwen3-8B | 0.032 | 0.476 | 0.680 | 0.524 | 0.522 | 0.574 | 0.285 | 0.413 |

Numeric ranges across differently scaled metrics are not directly comparable. Use paired confidence intervals and ranking robustness, not range alone.

## Classification and chance-corrected metrics

| Model | Exact↑ | Balanced acc.↑ | Macro F1↑ | MCC↑ | κ↑ | Linear κ↑ | Quadratic κ↑ | NMI↑ | Cramér V↑ | Ordinal r↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.868 | 0.833 | 0.751 | 0.619 | 0.600 | 0.652 | 0.701 | 0.402 | 0.660 | 0.712 |
| Qwen3.6-Flash | 0.831 | 0.825 | 0.710 | 0.566 | 0.532 | 0.588 | 0.642 | 0.353 | 0.616 | 0.665 |
| Qwen3.5-35B-A3B | 0.834 | 0.824 | 0.711 | 0.570 | 0.537 | 0.590 | 0.641 | 0.352 | 0.615 | 0.664 |
| DeepSeek-V4-Pro | 0.849 | 0.816 | 0.721 | 0.582 | 0.558 | 0.605 | 0.648 | 0.359 | 0.617 | 0.664 |
| GLM-5.2 | 0.872 | 0.808 | 0.742 | 0.609 | 0.596 | 0.647 | 0.694 | 0.384 | 0.640 | 0.702 |
| Codex GPT-5.6 Sol | 0.918 | 0.809 | 0.802 | 0.700 | 0.699 | 0.745 | 0.784 | 0.483 | 0.714 | 0.784 |
| DeepSeek-V4-Flash | 0.869 | 0.799 | 0.736 | 0.595 | 0.584 | 0.637 | 0.684 | 0.373 | 0.632 | 0.692 |
| Qwen3.7-Max | 0.868 | 0.775 | 0.722 | 0.576 | 0.568 | 0.615 | 0.655 | 0.346 | 0.606 | 0.662 |
| Qwen3-8B | 0.874 | 0.662 | 0.675 | 0.522 | 0.521 | 0.574 | 0.620 | 0.297 | 0.536 | 0.623 |

## Ordinal severity metrics

| Model | MAE↓ | RMSE↓ | Macro L1↑ | Macro L2↑ | A↔C atom rate↓ | Over quadratic cost↓ | Under quadratic cost↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.159 | 0.460 | 0.861 | 0.875 | 0.026 | 0.048 | 0.123 |
| Qwen3.6-Flash | 0.203 | 0.521 | 0.859 | 0.876 | 0.034 | 0.067 | 0.106 |
| Qwen3.5-35B-A3B | 0.201 | 0.520 | 0.859 | 0.876 | 0.035 | 0.066 | 0.112 |
| DeepSeek-V4-Pro | 0.187 | 0.509 | 0.847 | 0.862 | 0.036 | 0.060 | 0.133 |
| GLM-5.2 | 0.157 | 0.463 | 0.836 | 0.850 | 0.029 | 0.046 | 0.146 |
| Codex GPT-5.6 Sol | 0.101 | 0.372 | 0.825 | 0.833 | 0.019 | 0.022 | 0.168 |
| DeepSeek-V4-Flash | 0.162 | 0.472 | 0.822 | 0.834 | 0.031 | 0.048 | 0.156 |
| Qwen3.7-Max | 0.169 | 0.492 | 0.795 | 0.805 | 0.037 | 0.049 | 0.194 |
| Qwen3-8B | 0.160 | 0.475 | 0.698 | 0.716 | 0.033 | 0.029 | 0.343 |

## Composite-score sensitivity

| Model | H | Arithmetic | Geometric | Product | Softmin −2 | Softmin −4 | Softmin −8 | MinCalib | Ideal L2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.870 | 0.875 | 0.873 | 0.761 | 0.868 | 0.864 | 0.855 | 0.812 | 0.860 |
| Qwen3.6-Flash | 0.866 | 0.869 | 0.868 | 0.753 | 0.865 | 0.863 | 0.859 | 0.825 | 0.862 |
| Qwen3.5-35B-A3B | 0.866 | 0.868 | 0.867 | 0.752 | 0.865 | 0.863 | 0.859 | 0.825 | 0.861 |
| DeepSeek-V4-Pro | 0.857 | 0.862 | 0.859 | 0.738 | 0.854 | 0.849 | 0.840 | 0.794 | 0.846 |
| GLM-5.2 | 0.847 | 0.856 | 0.852 | 0.725 | 0.843 | 0.835 | 0.820 | 0.770 | 0.832 |
| Codex GPT-5.6 Sol | 0.841 | 0.856 | 0.849 | 0.720 | 0.833 | 0.819 | 0.797 | 0.741 | 0.816 |
| DeepSeek-V4-Flash | 0.839 | 0.849 | 0.844 | 0.712 | 0.834 | 0.825 | 0.809 | 0.757 | 0.823 |
| Qwen3.7-Max | 0.816 | 0.831 | 0.824 | 0.679 | 0.809 | 0.796 | 0.775 | 0.721 | 0.798 |
| Qwen3-8B | 0.680 | 0.746 | 0.713 | 0.508 | 0.652 | 0.611 | 0.571 | 0.524 | 0.663 |

## Sample-level tail risk

| Model | Strict sample↑ | Any A↔C sample↓ | Mean L1 loss↓ | P90↓ | CVaR90↓ | CVaR95↓ | Quadratic CVaR90↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.213 | 0.358 | 0.089 | 0.200 | 0.255 | 0.291 | 0.193 |
| Qwen3.6-Flash | 0.126 | 0.470 | 0.114 | 0.236 | 0.293 | 0.333 | 0.216 |
| Qwen3.5-35B-A3B | 0.123 | 0.451 | 0.114 | 0.227 | 0.291 | 0.338 | 0.228 |
| DeepSeek-V4-Pro | 0.144 | 0.480 | 0.106 | 0.222 | 0.283 | 0.325 | 0.218 |
| GLM-5.2 | 0.176 | 0.405 | 0.089 | 0.200 | 0.251 | 0.283 | 0.188 |
| Codex GPT-5.6 Sol | 0.316 | 0.265 | 0.060 | 0.150 | 0.204 | 0.247 | 0.160 |
| DeepSeek-V4-Flash | 0.152 | 0.407 | 0.095 | 0.200 | 0.267 | 0.311 | 0.210 |
| Qwen3.7-Max | 0.164 | 0.451 | 0.098 | 0.210 | 0.272 | 0.316 | 0.224 |
| Qwen3-8B | 0.166 | 0.417 | 0.095 | 0.200 | 0.285 | 0.343 | 0.230 |

CVaR90 is the mean loss among the worst 10% of samples; CVaR95 uses the worst 5%. Sample loss is normalized absolute ordinal distance.

### Why CVaR90 can reorder models

| Model | H rank | Mean L1 rank | CVaR90 rank | CVaR90↓ |
| --- | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 1 | 3 | 3 | 0.255 |
| Qwen3.6-Flash | 2 | 9 | 9 | 0.293 |
| Qwen3.5-35B-A3B | 3 | 8 | 8 | 0.291 |
| DeepSeek-V4-Pro | 4 | 7 | 6 | 0.283 |
| GLM-5.2 | 5 | 2 | 2 | 0.251 |
| Codex GPT-5.6 Sol | 6 | 1 | 1 | 0.204 |
| DeepSeek-V4-Flash | 7 | 4 | 4 | 0.267 |
| Qwen3.7-Max | 8 | 6 | 5 | 0.272 |
| Qwen3-8B | 9 | 5 | 7 | 0.285 |

For a full-memory sample `s` with `n_s` scorable atoms, `L_s = mean_i(|u_hat_si - u*_si| / 2)`. CVaR90 is the arithmetic mean of the largest 50 values of `L_s` among the locked 494 samples. It therefore changes both the aggregation unit (sample rather than gold-label macro average) and the evaluated population (only the worst decile).

A model can make moderately sized errors across many samples and have worse H or mean loss but a less extreme worst decile. Conversely, errors concentrated within a smaller set of samples increase CVaR90. The ordering difference is expected and is not an arithmetic inconsistency.

[Open the tail, Pareto, and metric-rank diagnostics](candidate-metric-diagnostics.html).

## Paired memory utility

| Model | Induced OPB↓ | Reduced UPB↑ | PMU(0.5)↑ | PMU(1)↑ | PMU(2)↑ | Relative PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.060 | 0.672 | 0.642 | 0.612 | 0.552 | 0.721 |
| Qwen3.6-Flash | 0.085 | 0.672 | 0.630 | 0.588 | 0.503 | 0.709 |
| Qwen3.5-35B-A3B | 0.085 | 0.664 | 0.621 | 0.579 | 0.495 | 0.707 |
| DeepSeek-V4-Pro | 0.069 | 0.646 | 0.611 | 0.577 | 0.508 | 0.690 |
| GLM-5.2 | 0.054 | 0.603 | 0.576 | 0.549 | 0.496 | 0.670 |
| Codex GPT-5.6 Sol | 0.025 | 0.596 | 0.583 | 0.571 | 0.545 | 0.671 |
| DeepSeek-V4-Flash | 0.056 | 0.626 | 0.599 | 0.571 | 0.515 | 0.665 |
| Qwen3.7-Max | 0.055 | 0.554 | 0.526 | 0.498 | 0.443 | 0.609 |
| Qwen3-8B | 0.031 | 0.444 | 0.429 | 0.413 | 0.382 | 0.452 |

`PMU(λ) = reduced_UPB - λ × induced_OPB`. Its ranking is a policy choice, so the weight sensitivity must remain visible.

## Latent and pairwise models

| Model | Rasch over θ↑ | Rasch under θ↑ | Mean θ↑ | Min θ↑ | Bradley–Terry ability↑ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 1.383 | -0.175 | 0.604 | -0.175 | 0.686 |
| GLM-5.2 | 0.100 | 0.163 | 0.131 | 0.100 | 0.134 |
| Kimi-K2.6 | -0.165 | 0.677 | 0.256 | -0.165 | 0.128 |
| DeepSeek-V4-Flash | 0.090 | 0.005 | 0.048 | 0.005 | 0.025 |
| Qwen3-8B | 1.210 | -2.444 | -0.617 | -2.444 | 0.023 |
| Qwen3.7-Max | 0.196 | -0.385 | -0.095 | -0.385 | -0.041 |
| DeepSeek-V4-Pro | -0.566 | 0.462 | -0.052 | -0.566 | -0.207 |
| Qwen3.5-35B-A3B | -1.093 | 0.849 | -0.122 | -1.093 | -0.358 |
| Qwen3.6-Flash | -1.155 | 0.849 | -0.153 | -1.155 | -0.391 |

The two Rasch dimensions adjust separately for atom difficulty. The current 1PL fit is exploratory: standard errors condition on estimated item difficulties and are not a full Bayesian uncertainty estimate.

## Pairwise win-share matrix

Rows are the candidate model; each cell is its win share against the column model using full-memory normalized sample-level ordinal loss. Ties count 0.5.

| Model | Kimi-K2.6 | Qwen3.6-Flash | Qwen3.5-35B-A3B | DeepSeek-V4-Pro | GLM-5.2 | Codex GPT-5.6 Sol | DeepSeek-V4-Flash | Qwen3.7-Max | Qwen3-8B |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | — | 0.629 | 0.631 | 0.575 | 0.496 | 0.358 | 0.526 | 0.553 | 0.519 |
| Qwen3.6-Flash | 0.371 | — | 0.488 | 0.456 | 0.371 | 0.261 | 0.387 | 0.407 | 0.412 |
| Qwen3.5-35B-A3B | 0.369 | 0.512 | — | 0.462 | 0.373 | 0.269 | 0.398 | 0.414 | 0.425 |
| DeepSeek-V4-Pro | 0.425 | 0.544 | 0.538 | — | 0.411 | 0.307 | 0.441 | 0.447 | 0.437 |
| GLM-5.2 | 0.504 | 0.629 | 0.627 | 0.589 | — | 0.355 | 0.530 | 0.538 | 0.526 |
| Codex GPT-5.6 Sol | 0.642 | 0.739 | 0.731 | 0.693 | 0.645 | — | 0.671 | 0.685 | 0.654 |
| DeepSeek-V4-Flash | 0.474 | 0.613 | 0.602 | 0.559 | 0.470 | 0.329 | — | 0.524 | 0.489 |
| Qwen3.7-Max | 0.447 | 0.593 | 0.586 | 0.553 | 0.462 | 0.315 | 0.476 | — | 0.483 |
| Qwen3-8B | 0.481 | 0.588 | 0.575 | 0.563 | 0.474 | 0.346 | 0.511 | 0.517 | — |

## Pareto analysis

Non-dominated OPB–UPB models: Codex GPT-5.6 Sol, GLM-5.2, Kimi-K2.6, Qwen3.6-Flash.

## Observed metric spread

| Metric | Minimum | Maximum | Range | Population SD |
| --- | ---: | ---: | ---: | ---: |
| MinCalib | 0.524 | 0.825 | 0.301 | 0.088 |
| product_resistance | 0.508 | 0.761 | 0.253 | 0.074 |
| PMU_lambda_1 | 0.413 | 0.612 | 0.199 | 0.057 |
| strict_sample_accuracy | 0.123 | 0.316 | 0.192 | 0.056 |
| H | 0.680 | 0.870 | 0.190 | 0.056 |
| MCC | 0.522 | 0.700 | 0.178 | 0.046 |
| linear_kappa | 0.574 | 0.745 | 0.171 | 0.049 |
| balanced_accuracy | 0.662 | 0.833 | 0.171 | 0.050 |
| quadratic_kappa | 0.620 | 0.784 | 0.164 | 0.046 |
| macro_F1 | 0.675 | 0.802 | 0.127 | 0.033 |
| CVaR90_linear_loss | 0.204 | 0.293 | 0.090 | 0.026 |

## Sample-cluster bootstrap uncertainty

| Model | H 95% CI | MinCalib 95% CI | MCC 95% CI | Linear κ 95% CI | Strict sample 95% CI | CVaR90 95% CI | PMU(1) 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | [0.855, 0.884] | [0.785, 0.837] | [0.596, 0.642] | [0.630, 0.675] | [0.178, 0.249] | [0.235, 0.275] | [0.577, 0.645] |
| Qwen3.6-Flash | [0.852, 0.880] | [0.799, 0.851] | [0.544, 0.587] | [0.567, 0.609] | [0.097, 0.154] | [0.272, 0.313] | [0.553, 0.623] |
| Qwen3.5-35B-A3B | [0.852, 0.880] | [0.799, 0.850] | [0.548, 0.593] | [0.569, 0.613] | [0.095, 0.154] | [0.268, 0.314] | [0.545, 0.615] |
| DeepSeek-V4-Pro | [0.841, 0.871] | [0.768, 0.819] | [0.560, 0.603] | [0.584, 0.627] | [0.113, 0.174] | [0.260, 0.307] | [0.546, 0.610] |
| GLM-5.2 | [0.830, 0.864] | [0.741, 0.798] | [0.586, 0.632] | [0.625, 0.670] | [0.144, 0.211] | [0.231, 0.270] | [0.514, 0.583] |
| Codex GPT-5.6 Sol | [0.821, 0.858] | [0.711, 0.769] | [0.673, 0.724] | [0.722, 0.767] | [0.275, 0.356] | [0.181, 0.226] | [0.535, 0.604] |
| DeepSeek-V4-Flash | [0.821, 0.856] | [0.729, 0.786] | [0.571, 0.619] | [0.613, 0.659] | [0.121, 0.182] | [0.243, 0.291] | [0.539, 0.603] |
| Qwen3.7-Max | [0.797, 0.836] | [0.691, 0.752] | [0.551, 0.601] | [0.590, 0.639] | [0.132, 0.196] | [0.248, 0.296] | [0.464, 0.534] |
| Qwen3-8B | [0.649, 0.710] | [0.488, 0.560] | [0.491, 0.551] | [0.541, 0.605] | [0.134, 0.200] | [0.256, 0.315] | [0.378, 0.448] |

All intervals resample the same 494 sample IDs as clusters. Full/no-memory atom groups are preserved.

## Interpretation boundary

- MCC, Kappa, NMI, and ordinal correlation discard the over-use versus under-use direction even when they improve numerical separation.
- Product and power-mean scores partly enlarge the numeric range through rescaling; this does not create new statistical evidence.
- PMU depends on the full/no-memory causal contrast and on λ.
- CVaR exposes tail failures but should not replace average performance.
- Brier score, log loss, and ordinal CRPS are not validly computable without a probability distribution over A/B/C.
- Pairwise bootstrap intervals and blinded human validation remain necessary before making significance or external leaderboard claims.
