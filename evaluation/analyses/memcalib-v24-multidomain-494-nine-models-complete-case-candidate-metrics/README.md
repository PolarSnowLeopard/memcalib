# MemCalib v2.4 nine-model complete-case candidate metric study

The common 494-sample subset of the locked v2.4 500-sample evaluation after globally excluding six GLM-5.2 no-memory length failures from every model-condition cell.

## Headline comparison

| Model | OPB↓ | UPB↓ | H↑ | MinCalib↑ | MCC↑ | Linear κ↑ | CVaR90↓ | PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.7-Max | 0.114 | 0.186 | 0.849 | 0.814 | 0.560 | 0.554 | 0.341 | 0.594 |
| DeepSeek-V4-Pro | 0.111 | 0.193 | 0.846 | 0.807 | 0.551 | 0.554 | 0.348 | 0.588 |
| GLM-5.2 | 0.106 | 0.201 | 0.844 | 0.799 | 0.559 | 0.573 | 0.312 | 0.583 |
| DeepSeek-V4-Flash | 0.086 | 0.236 | 0.832 | 0.764 | 0.570 | 0.588 | 0.301 | 0.586 |
| Qwen3.5-35B-A3B | 0.113 | 0.242 | 0.818 | 0.758 | 0.516 | 0.520 | 0.338 | 0.559 |
| Qwen3.6-Flash | 0.098 | 0.257 | 0.815 | 0.743 | 0.543 | 0.562 | 0.323 | 0.542 |
| Kimi-K2.6 | 0.081 | 0.271 | 0.813 | 0.729 | 0.569 | 0.597 | 0.303 | 0.551 |
| Codex GPT-5.6 Sol | 0.048 | 0.323 | 0.792 | 0.677 | 0.617 | 0.666 | 0.253 | 0.534 |
| Qwen3-8B | 0.061 | 0.379 | 0.748 | 0.621 | 0.534 | 0.576 | 0.293 | 0.495 |

Numeric ranges across differently scaled metrics are not directly comparable. Use paired confidence intervals and ranking robustness, not range alone.

## Classification and chance-corrected metrics

| Model | Exact↑ | Balanced acc.↑ | Macro F1↑ | MCC↑ | κ↑ | Linear κ↑ | Quadratic κ↑ | NMI↑ | Cramér V↑ | Ordinal r↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.7-Max | 0.836 | 0.800 | 0.682 | 0.560 | 0.533 | 0.554 | 0.571 | 0.317 | 0.556 | 0.605 |
| DeepSeek-V4-Pro | 0.831 | 0.797 | 0.679 | 0.551 | 0.522 | 0.554 | 0.581 | 0.310 | 0.555 | 0.611 |
| GLM-5.2 | 0.839 | 0.795 | 0.688 | 0.559 | 0.534 | 0.573 | 0.607 | 0.320 | 0.566 | 0.632 |
| DeepSeek-V4-Flash | 0.852 | 0.785 | 0.697 | 0.570 | 0.552 | 0.588 | 0.620 | 0.329 | 0.571 | 0.638 |
| Qwen3.5-35B-A3B | 0.817 | 0.764 | 0.653 | 0.516 | 0.488 | 0.520 | 0.548 | 0.274 | 0.515 | 0.576 |
| Qwen3.6-Flash | 0.841 | 0.763 | 0.675 | 0.543 | 0.524 | 0.562 | 0.596 | 0.301 | 0.541 | 0.615 |
| Kimi-K2.6 | 0.863 | 0.765 | 0.702 | 0.569 | 0.560 | 0.597 | 0.629 | 0.324 | 0.571 | 0.640 |
| Codex GPT-5.6 Sol | 0.893 | 0.753 | 0.736 | 0.617 | 0.616 | 0.666 | 0.708 | 0.383 | 0.618 | 0.709 |
| Qwen3-8B | 0.862 | 0.707 | 0.676 | 0.534 | 0.531 | 0.576 | 0.615 | 0.295 | 0.532 | 0.618 |

## Ordinal severity metrics

| Model | MAE↓ | RMSE↓ | Macro L1↑ | Macro L2↑ | A↔C atom rate↓ | Over quadratic cost↓ | Under quadratic cost↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.7-Max | 0.229 | 0.599 | 0.829 | 0.843 | 0.065 | 0.091 | 0.110 |
| DeepSeek-V4-Pro | 0.226 | 0.583 | 0.829 | 0.845 | 0.057 | 0.085 | 0.120 |
| GLM-5.2 | 0.210 | 0.555 | 0.828 | 0.845 | 0.049 | 0.076 | 0.123 |
| DeepSeek-V4-Flash | 0.194 | 0.535 | 0.820 | 0.838 | 0.046 | 0.068 | 0.140 |
| Qwen3.5-35B-A3B | 0.242 | 0.602 | 0.806 | 0.827 | 0.060 | 0.088 | 0.152 |
| Qwen3.6-Flash | 0.209 | 0.557 | 0.801 | 0.820 | 0.050 | 0.073 | 0.151 |
| Kimi-K2.6 | 0.181 | 0.520 | 0.792 | 0.805 | 0.044 | 0.059 | 0.181 |
| Codex GPT-5.6 Sol | 0.135 | 0.437 | 0.781 | 0.795 | 0.028 | 0.034 | 0.200 |
| Qwen3-8B | 0.178 | 0.508 | 0.747 | 0.768 | 0.040 | 0.048 | 0.245 |

## Composite-score sensitivity

| Model | H | Arithmetic | Geometric | Product | Softmin −2 | Softmin −4 | Softmin −8 | MinCalib | Ideal L2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.7-Max | 0.849 | 0.850 | 0.850 | 0.722 | 0.848 | 0.847 | 0.844 | 0.814 | 0.846 |
| DeepSeek-V4-Pro | 0.846 | 0.848 | 0.847 | 0.717 | 0.845 | 0.843 | 0.839 | 0.807 | 0.843 |
| GLM-5.2 | 0.844 | 0.846 | 0.845 | 0.714 | 0.842 | 0.840 | 0.835 | 0.799 | 0.839 |
| DeepSeek-V4-Flash | 0.832 | 0.839 | 0.836 | 0.698 | 0.829 | 0.823 | 0.811 | 0.764 | 0.822 |
| Qwen3.5-35B-A3B | 0.818 | 0.823 | 0.820 | 0.673 | 0.815 | 0.810 | 0.801 | 0.758 | 0.811 |
| Qwen3.6-Flash | 0.815 | 0.822 | 0.819 | 0.670 | 0.811 | 0.804 | 0.791 | 0.743 | 0.805 |
| Kimi-K2.6 | 0.813 | 0.824 | 0.818 | 0.670 | 0.808 | 0.797 | 0.781 | 0.729 | 0.800 |
| Codex GPT-5.6 Sol | 0.792 | 0.815 | 0.803 | 0.645 | 0.781 | 0.761 | 0.733 | 0.677 | 0.769 |
| Qwen3-8B | 0.748 | 0.780 | 0.764 | 0.583 | 0.733 | 0.707 | 0.675 | 0.621 | 0.729 |

## Sample-level tail risk

| Model | Strict sample↑ | Any A↔C sample↓ | Mean L1 loss↓ | P90↓ | CVaR90↓ | CVaR95↓ | Quadratic CVaR90↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.7-Max | 0.067 | 0.704 | 0.133 | 0.273 | 0.341 | 0.394 | 0.301 |
| DeepSeek-V4-Pro | 0.117 | 0.628 | 0.129 | 0.273 | 0.348 | 0.407 | 0.294 |
| GLM-5.2 | 0.117 | 0.591 | 0.118 | 0.250 | 0.312 | 0.361 | 0.253 |
| DeepSeek-V4-Flash | 0.142 | 0.557 | 0.112 | 0.247 | 0.301 | 0.345 | 0.244 |
| Qwen3.5-35B-A3B | 0.085 | 0.650 | 0.136 | 0.276 | 0.338 | 0.385 | 0.288 |
| Qwen3.6-Flash | 0.154 | 0.561 | 0.118 | 0.250 | 0.323 | 0.376 | 0.273 |
| Kimi-K2.6 | 0.180 | 0.518 | 0.106 | 0.227 | 0.303 | 0.357 | 0.251 |
| Codex GPT-5.6 Sol | 0.219 | 0.358 | 0.079 | 0.167 | 0.253 | 0.308 | 0.208 |
| Qwen3-8B | 0.150 | 0.504 | 0.105 | 0.230 | 0.293 | 0.331 | 0.239 |

CVaR90 is the mean loss among the worst 10% of samples; CVaR95 uses the worst 5%. Sample loss is normalized absolute ordinal distance.

### Why CVaR90 can reorder models

| Model | H rank | Mean L1 rank | CVaR90 rank | CVaR90↓ |
| --- | ---: | ---: | ---: | ---: |
| Qwen3.7-Max | 1 | 8 | 8 | 0.341 |
| DeepSeek-V4-Pro | 2 | 7 | 9 | 0.348 |
| GLM-5.2 | 3 | 5 | 5 | 0.312 |
| DeepSeek-V4-Flash | 4 | 4 | 3 | 0.301 |
| Qwen3.5-35B-A3B | 5 | 9 | 7 | 0.338 |
| Qwen3.6-Flash | 6 | 6 | 6 | 0.323 |
| Kimi-K2.6 | 7 | 3 | 4 | 0.303 |
| Codex GPT-5.6 Sol | 8 | 1 | 1 | 0.253 |
| Qwen3-8B | 9 | 2 | 2 | 0.293 |

For a full-memory sample `s` with `n_s` scorable atoms, `L_s = mean_i(|u_hat_si - u*_si| / 2)`. CVaR90 is the arithmetic mean of the largest 50 values of `L_s` among the locked 494 samples. It therefore changes both the aggregation unit (sample rather than gold-label macro average) and the evaluated population (only the worst decile).

A model can make moderately sized errors across many samples and have worse H or mean loss but a less extreme worst decile. Conversely, errors concentrated within a smaller set of samples increase CVaR90. The ordering difference is expected and is not an arithmetic inconsistency.

[Open the tail, Pareto, and metric-rank diagnostics](candidate-metric-diagnostics.html).

## Paired memory utility

| Model | Induced OPB↓ | Reduced UPB↑ | PMU(0.5)↑ | PMU(1)↑ | PMU(2)↑ | Relative PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.7-Max | 0.109 | 0.703 | 0.648 | 0.594 | 0.485 | 0.682 |
| DeepSeek-V4-Pro | 0.107 | 0.695 | 0.642 | 0.588 | 0.481 | 0.676 |
| GLM-5.2 | 0.100 | 0.683 | 0.633 | 0.583 | 0.483 | 0.673 |
| DeepSeek-V4-Flash | 0.082 | 0.668 | 0.627 | 0.586 | 0.504 | 0.657 |
| Qwen3.5-35B-A3B | 0.109 | 0.668 | 0.613 | 0.559 | 0.450 | 0.625 |
| Qwen3.6-Flash | 0.094 | 0.635 | 0.588 | 0.542 | 0.448 | 0.618 |
| Kimi-K2.6 | 0.075 | 0.626 | 0.589 | 0.551 | 0.477 | 0.623 |
| Codex GPT-5.6 Sol | 0.046 | 0.580 | 0.557 | 0.534 | 0.488 | 0.597 |
| Qwen3-8B | 0.058 | 0.553 | 0.524 | 0.495 | 0.436 | 0.535 |

`PMU(λ) = reduced_UPB - λ × induced_OPB`. Its ranking is a policy choice, so the weight sensitivity must remain visible.

## Latent and pairwise models

| Model | Rasch over θ↑ | Rasch under θ↑ | Mean θ↑ | Min θ↑ | Bradley–Terry ability↑ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 1.473 | -0.809 | 0.332 | -0.809 | 0.651 |
| Qwen3-8B | 0.828 | -1.376 | -0.274 | -1.376 | 0.228 |
| Kimi-K2.6 | 0.423 | -0.237 | 0.093 | -0.237 | 0.203 |
| DeepSeek-V4-Flash | -0.005 | 0.179 | 0.087 | -0.005 | 0.034 |
| GLM-5.2 | -0.458 | 0.621 | 0.081 | -0.458 | -0.067 |
| Qwen3.6-Flash | -0.187 | -0.066 | -0.126 | -0.187 | -0.094 |
| DeepSeek-V4-Pro | -0.673 | 0.733 | 0.030 | -0.673 | -0.221 |
| Qwen3.7-Max | -0.570 | 0.825 | 0.127 | -0.570 | -0.331 |
| Qwen3.5-35B-A3B | -0.832 | 0.129 | -0.352 | -0.832 | -0.402 |

The two Rasch dimensions adjust separately for atom difficulty. The current 1PL fit is exploratory: standard errors condition on estimated item difficulties and are not a full Bayesian uncertainty estimate.

## Pairwise win-share matrix

Rows are the candidate model; each cell is its win share against the column model using full-memory normalized sample-level ordinal loss. Ties count 0.5.

| Model | Qwen3.7-Max | DeepSeek-V4-Pro | GLM-5.2 | DeepSeek-V4-Flash | Qwen3.5-35B-A3B | Qwen3.6-Flash | Kimi-K2.6 | Codex GPT-5.6 Sol | Qwen3-8B |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.7-Max | — | 0.479 | 0.432 | 0.410 | 0.512 | 0.448 | 0.367 | 0.280 | 0.352 |
| DeepSeek-V4-Pro | 0.521 | — | 0.471 | 0.422 | 0.537 | 0.469 | 0.407 | 0.308 | 0.385 |
| GLM-5.2 | 0.568 | 0.529 | — | 0.477 | 0.582 | 0.515 | 0.448 | 0.315 | 0.421 |
| DeepSeek-V4-Flash | 0.590 | 0.578 | 0.523 | — | 0.613 | 0.526 | 0.449 | 0.346 | 0.451 |
| Qwen3.5-35B-A3B | 0.488 | 0.463 | 0.418 | 0.387 | — | 0.417 | 0.340 | 0.259 | 0.358 |
| Qwen3.6-Flash | 0.552 | 0.531 | 0.485 | 0.474 | 0.583 | — | 0.431 | 0.319 | 0.423 |
| Kimi-K2.6 | 0.633 | 0.593 | 0.552 | 0.551 | 0.660 | 0.569 | — | 0.400 | 0.492 |
| Codex GPT-5.6 Sol | 0.720 | 0.692 | 0.685 | 0.654 | 0.741 | 0.681 | 0.600 | — | 0.614 |
| Qwen3-8B | 0.648 | 0.615 | 0.579 | 0.549 | 0.642 | 0.577 | 0.508 | 0.386 | — |

## Pareto analysis

Non-dominated OPB–UPB models: Codex GPT-5.6 Sol, DeepSeek-V4-Pro, DeepSeek-V4-Flash, GLM-5.2, Kimi-K2.6, Qwen3.7-Max.

## Observed metric spread

| Metric | Minimum | Maximum | Range | Population SD |
| --- | ---: | ---: | ---: | ---: |
| MinCalib | 0.621 | 0.814 | 0.193 | 0.060 |
| quadratic_kappa | 0.548 | 0.708 | 0.160 | 0.043 |
| strict_sample_accuracy | 0.067 | 0.219 | 0.152 | 0.044 |
| linear_kappa | 0.520 | 0.666 | 0.146 | 0.038 |
| product_resistance | 0.583 | 0.722 | 0.138 | 0.041 |
| MCC | 0.516 | 0.617 | 0.101 | 0.027 |
| H | 0.748 | 0.849 | 0.101 | 0.030 |
| PMU_lambda_1 | 0.495 | 0.594 | 0.099 | 0.031 |
| CVaR90_linear_loss | 0.253 | 0.348 | 0.095 | 0.028 |
| balanced_accuracy | 0.707 | 0.800 | 0.093 | 0.028 |
| macro_F1 | 0.653 | 0.736 | 0.083 | 0.022 |

## Sample-cluster bootstrap uncertainty

| Model | H 95% CI | MinCalib 95% CI | MCC 95% CI | Linear κ 95% CI | Strict sample 95% CI | CVaR90 95% CI | PMU(1) 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.7-Max | [0.833, 0.863] | [0.786, 0.840] | [0.539, 0.582] | [0.532, 0.574] | [0.047, 0.091] | [0.314, 0.368] | [0.560, 0.626] |
| DeepSeek-V4-Pro | [0.831, 0.861] | [0.781, 0.832] | [0.529, 0.574] | [0.530, 0.577] | [0.089, 0.146] | [0.314, 0.385] | [0.553, 0.621] |
| GLM-5.2 | [0.828, 0.859] | [0.772, 0.825] | [0.535, 0.583] | [0.550, 0.595] | [0.089, 0.146] | [0.286, 0.337] | [0.548, 0.620] |
| DeepSeek-V4-Flash | [0.814, 0.850] | [0.734, 0.794] | [0.544, 0.593] | [0.563, 0.611] | [0.111, 0.174] | [0.276, 0.325] | [0.551, 0.619] |
| Qwen3.5-35B-A3B | [0.800, 0.834] | [0.729, 0.786] | [0.493, 0.539] | [0.496, 0.543] | [0.061, 0.111] | [0.315, 0.362] | [0.525, 0.593] |
| Qwen3.6-Flash | [0.797, 0.832] | [0.714, 0.772] | [0.518, 0.569] | [0.538, 0.588] | [0.123, 0.190] | [0.295, 0.353] | [0.508, 0.576] |
| Kimi-K2.6 | [0.794, 0.833] | [0.699, 0.760] | [0.543, 0.597] | [0.572, 0.624] | [0.148, 0.217] | [0.276, 0.330] | [0.515, 0.586] |
| Codex GPT-5.6 Sol | [0.769, 0.812] | [0.645, 0.709] | [0.592, 0.644] | [0.642, 0.691] | [0.184, 0.255] | [0.226, 0.283] | [0.500, 0.569] |
| Qwen3-8B | [0.725, 0.769] | [0.591, 0.652] | [0.508, 0.561] | [0.548, 0.603] | [0.119, 0.182] | [0.270, 0.314] | [0.462, 0.527] |

All intervals resample the same 494 sample IDs as clusters. Full/no-memory atom groups are preserved.

## Interpretation boundary

- MCC, Kappa, NMI, and ordinal correlation discard the over-use versus under-use direction even when they improve numerical separation.
- Product and power-mean scores partly enlarge the numeric range through rescaling; this does not create new statistical evidence.
- PMU depends on the full/no-memory causal contrast and on λ.
- CVaR exposes tail failures but should not replace average performance.
- Brier score, log loss, and ordinal CRPS are not validly computable without a probability distribution over A/B/C.
- Pairwise bootstrap intervals and blinded human validation remain necessary before making significance or external leaderboard claims.
