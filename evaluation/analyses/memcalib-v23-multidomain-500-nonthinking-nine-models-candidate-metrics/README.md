# MemCalib v2.3 non-thinking nine-model candidate metric study

Same locked v2.3 500-record sample, eight Bailian models with thinking disabled, and reused Codex reasoning-none answers.

## Headline comparison

| Model | OPB↓ | UPB↓ | H↑ | MinCalib↑ | MCC↑ | Linear κ↑ | CVaR90↓ | PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-35B-A3B | 0.098 | 0.198 | 0.849 | 0.802 | 0.571 | 0.578 | 0.330 | 0.601 |
| DeepSeek-V4-Pro | 0.082 | 0.223 | 0.842 | 0.777 | 0.583 | 0.594 | 0.308 | 0.587 |
| GLM-5.2 | 0.079 | 0.230 | 0.839 | 0.770 | 0.603 | 0.626 | 0.279 | 0.569 |
| Qwen3.7-Max | 0.074 | 0.235 | 0.838 | 0.765 | 0.588 | 0.607 | 0.293 | 0.570 |
| Kimi-K2.6 | 0.069 | 0.239 | 0.837 | 0.761 | 0.614 | 0.641 | 0.297 | 0.592 |
| Qwen3.6-Flash | 0.094 | 0.224 | 0.836 | 0.776 | 0.570 | 0.583 | 0.307 | 0.580 |
| DeepSeek-V4-Flash | 0.068 | 0.245 | 0.834 | 0.755 | 0.595 | 0.612 | 0.286 | 0.587 |
| Codex GPT-5.6 Sol | 0.045 | 0.316 | 0.797 | 0.684 | 0.643 | 0.686 | 0.242 | 0.552 |
| Qwen3-8B | 0.038 | 0.501 | 0.657 | 0.499 | 0.513 | 0.552 | 0.291 | 0.396 |

Numeric ranges across differently scaled metrics are not directly comparable. Use paired confidence intervals and ranking robustness, not range alone.

## Classification and chance-corrected metrics

| Model | Exact↑ | Balanced acc.↑ | Macro F1↑ | MCC↑ | κ↑ | Linear κ↑ | Quadratic κ↑ | NMI↑ | Cramér V↑ | Ordinal r↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-35B-A3B | 0.845 | 0.802 | 0.695 | 0.571 | 0.547 | 0.578 | 0.606 | 0.330 | 0.573 | 0.631 |
| DeepSeek-V4-Pro | 0.858 | 0.797 | 0.709 | 0.583 | 0.566 | 0.594 | 0.619 | 0.339 | 0.585 | 0.637 |
| GLM-5.2 | 0.872 | 0.794 | 0.722 | 0.603 | 0.591 | 0.626 | 0.656 | 0.359 | 0.601 | 0.668 |
| Qwen3.7-Max | 0.865 | 0.794 | 0.715 | 0.588 | 0.574 | 0.607 | 0.635 | 0.347 | 0.594 | 0.650 |
| Kimi-K2.6 | 0.879 | 0.794 | 0.732 | 0.614 | 0.605 | 0.641 | 0.671 | 0.372 | 0.614 | 0.681 |
| Qwen3.6-Flash | 0.853 | 0.788 | 0.698 | 0.570 | 0.553 | 0.583 | 0.609 | 0.324 | 0.571 | 0.628 |
| DeepSeek-V4-Flash | 0.870 | 0.792 | 0.721 | 0.595 | 0.584 | 0.612 | 0.635 | 0.352 | 0.597 | 0.648 |
| Codex GPT-5.6 Sol | 0.903 | 0.759 | 0.750 | 0.643 | 0.643 | 0.686 | 0.721 | 0.408 | 0.636 | 0.722 |
| Qwen3-8B | 0.877 | 0.641 | 0.658 | 0.513 | 0.512 | 0.552 | 0.586 | 0.279 | 0.505 | 0.588 |

## Ordinal severity metrics

| Model | MAE↓ | RMSE↓ | Macro L1↑ | Macro L2↑ | A↔C atom rate↓ | Over quadratic cost↓ | Under quadratic cost↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-35B-A3B | 0.207 | 0.558 | 0.834 | 0.849 | 0.052 | 0.077 | 0.118 |
| DeepSeek-V4-Pro | 0.190 | 0.537 | 0.824 | 0.838 | 0.049 | 0.067 | 0.148 |
| GLM-5.2 | 0.170 | 0.503 | 0.820 | 0.833 | 0.042 | 0.058 | 0.145 |
| Qwen3.7-Max | 0.181 | 0.521 | 0.818 | 0.831 | 0.046 | 0.063 | 0.149 |
| Kimi-K2.6 | 0.159 | 0.487 | 0.818 | 0.830 | 0.039 | 0.053 | 0.149 |
| Qwen3.6-Flash | 0.198 | 0.546 | 0.816 | 0.830 | 0.050 | 0.070 | 0.152 |
| DeepSeek-V4-Flash | 0.176 | 0.518 | 0.817 | 0.830 | 0.046 | 0.060 | 0.160 |
| Codex GPT-5.6 Sol | 0.125 | 0.426 | 0.783 | 0.794 | 0.028 | 0.031 | 0.200 |
| Qwen3-8B | 0.165 | 0.498 | 0.672 | 0.688 | 0.042 | 0.032 | 0.373 |

## Composite-score sensitivity

| Model | H | Arithmetic | Geometric | Product | Softmin −2 | Softmin −4 | Softmin −8 | MinCalib | Ideal L2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-35B-A3B | 0.849 | 0.852 | 0.850 | 0.723 | 0.847 | 0.845 | 0.839 | 0.802 | 0.844 |
| DeepSeek-V4-Pro | 0.842 | 0.848 | 0.845 | 0.714 | 0.839 | 0.833 | 0.823 | 0.777 | 0.832 |
| GLM-5.2 | 0.839 | 0.845 | 0.842 | 0.709 | 0.835 | 0.829 | 0.817 | 0.770 | 0.828 |
| Qwen3.7-Max | 0.838 | 0.845 | 0.841 | 0.708 | 0.834 | 0.827 | 0.814 | 0.765 | 0.826 |
| Kimi-K2.6 | 0.837 | 0.846 | 0.841 | 0.708 | 0.833 | 0.825 | 0.811 | 0.761 | 0.824 |
| Qwen3.6-Flash | 0.836 | 0.841 | 0.839 | 0.703 | 0.834 | 0.829 | 0.820 | 0.776 | 0.828 |
| DeepSeek-V4-Flash | 0.834 | 0.844 | 0.839 | 0.704 | 0.830 | 0.821 | 0.806 | 0.755 | 0.820 |
| Codex GPT-5.6 Sol | 0.797 | 0.819 | 0.808 | 0.653 | 0.786 | 0.767 | 0.740 | 0.684 | 0.774 |
| Qwen3-8B | 0.657 | 0.730 | 0.693 | 0.480 | 0.626 | 0.583 | 0.544 | 0.499 | 0.645 |

## Sample-level tail risk

| Model | Strict sample↑ | Any A↔C sample↓ | Mean L1 loss↓ | P90↓ | CVaR90↓ | CVaR95↓ | Quadratic CVaR90↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-35B-A3B | 0.110 | 0.606 | 0.121 | 0.250 | 0.330 | 0.378 | 0.277 |
| DeepSeek-V4-Pro | 0.136 | 0.570 | 0.110 | 0.250 | 0.308 | 0.348 | 0.250 |
| GLM-5.2 | 0.150 | 0.530 | 0.098 | 0.206 | 0.279 | 0.322 | 0.230 |
| Qwen3.7-Max | 0.130 | 0.590 | 0.107 | 0.222 | 0.293 | 0.332 | 0.240 |
| Kimi-K2.6 | 0.198 | 0.476 | 0.094 | 0.214 | 0.297 | 0.353 | 0.243 |
| Qwen3.6-Flash | 0.126 | 0.604 | 0.114 | 0.250 | 0.307 | 0.349 | 0.254 |
| DeepSeek-V4-Flash | 0.136 | 0.586 | 0.102 | 0.211 | 0.286 | 0.332 | 0.231 |
| Codex GPT-5.6 Sol | 0.230 | 0.384 | 0.075 | 0.167 | 0.242 | 0.291 | 0.194 |
| Qwen3-8B | 0.132 | 0.538 | 0.100 | 0.222 | 0.291 | 0.338 | 0.243 |

CVaR90 is the mean loss among the worst 10% of samples; CVaR95 uses the worst 5%. Sample loss is normalized absolute ordinal distance.

### Why CVaR90 can reorder models

| Model | H rank | Mean L1 rank | CVaR90 rank | CVaR90↓ |
| --- | ---: | ---: | ---: | ---: |
| Qwen3.5-35B-A3B | 1 | 9 | 9 | 0.330 |
| DeepSeek-V4-Pro | 2 | 7 | 8 | 0.308 |
| GLM-5.2 | 3 | 3 | 2 | 0.279 |
| Qwen3.7-Max | 4 | 6 | 5 | 0.293 |
| Kimi-K2.6 | 5 | 2 | 6 | 0.297 |
| Qwen3.6-Flash | 6 | 8 | 7 | 0.307 |
| DeepSeek-V4-Flash | 7 | 5 | 3 | 0.286 |
| Codex GPT-5.6 Sol | 8 | 1 | 1 | 0.242 |
| Qwen3-8B | 9 | 4 | 4 | 0.291 |

For a full-memory sample `s` with `n_s` scorable atoms, `L_s = mean_i(|u_hat_si - u*_si| / 2)`. CVaR90 is the arithmetic mean of the largest 50 values of `L_s` among the locked 500 samples. It therefore changes both the aggregation unit (sample rather than gold-label macro average) and the evaluated population (only the worst decile).

A model can make moderately sized errors across many samples and have worse H or mean loss but a less extreme worst decile. Conversely, errors concentrated within a smaller set of samples increase CVaR90. The ordering difference is expected and is not an arithmetic inconsistency.

[Open the tail, Pareto, and metric-rank diagnostics](candidate-metric-diagnostics.html).

## Paired memory utility

| Model | Induced OPB↓ | Reduced UPB↑ | PMU(0.5)↑ | PMU(1)↑ | PMU(2)↑ | Relative PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-35B-A3B | 0.092 | 0.693 | 0.647 | 0.601 | 0.509 | 0.686 |
| DeepSeek-V4-Pro | 0.072 | 0.659 | 0.623 | 0.587 | 0.515 | 0.675 |
| GLM-5.2 | 0.075 | 0.644 | 0.607 | 0.569 | 0.495 | 0.662 |
| Qwen3.7-Max | 0.069 | 0.639 | 0.604 | 0.570 | 0.501 | 0.662 |
| Kimi-K2.6 | 0.066 | 0.657 | 0.624 | 0.592 | 0.526 | 0.667 |
| Qwen3.6-Flash | 0.088 | 0.668 | 0.624 | 0.580 | 0.492 | 0.661 |
| DeepSeek-V4-Flash | 0.061 | 0.649 | 0.618 | 0.587 | 0.526 | 0.665 |
| Codex GPT-5.6 Sol | 0.042 | 0.594 | 0.573 | 0.552 | 0.509 | 0.611 |
| Qwen3-8B | 0.034 | 0.430 | 0.413 | 0.396 | 0.361 | 0.427 |

`PMU(λ) = reduced_UPB - λ × induced_OPB`. Its ranking is a policy choice, so the weight sensitivity must remain visible.

## Latent and pairwise models

| Model | Rasch over θ↑ | Rasch under θ↑ | Mean θ↑ | Min θ↑ | Bradley–Terry ability↑ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 1.222 | -0.550 | 0.336 | -0.550 | 0.561 |
| Kimi-K2.6 | 0.130 | 0.284 | 0.207 | 0.130 | 0.194 |
| GLM-5.2 | -0.114 | 0.400 | 0.143 | -0.114 | 0.052 |
| Qwen3-8B | 1.266 | -2.460 | -0.597 | -2.460 | 0.025 |
| DeepSeek-V4-Flash | -0.104 | 0.226 | 0.061 | -0.104 | -0.024 |
| DeepSeek-V4-Pro | -0.505 | 0.489 | -0.008 | -0.505 | -0.091 |
| Qwen3.7-Max | -0.286 | 0.332 | 0.023 | -0.286 | -0.095 |
| Qwen3.6-Flash | -0.653 | 0.479 | -0.087 | -0.653 | -0.292 |
| Qwen3.5-35B-A3B | -0.957 | 0.800 | -0.078 | -0.957 | -0.331 |

The two Rasch dimensions adjust separately for atom difficulty. The current 1PL fit is exploratory: standard errors condition on estimated item difficulties and are not a full Bayesian uncertainty estimate.

## Pairwise win-share matrix

Rows are the candidate model; each cell is its win share against the column model using full-memory normalized sample-level ordinal loss. Ties count 0.5.

| Model | Qwen3.5-35B-A3B | DeepSeek-V4-Pro | GLM-5.2 | Qwen3.7-Max | Kimi-K2.6 | Qwen3.6-Flash | DeepSeek-V4-Flash | Codex GPT-5.6 Sol | Qwen3-8B |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-35B-A3B | — | 0.430 | 0.401 | 0.437 | 0.367 | 0.498 | 0.416 | 0.300 | 0.427 |
| DeepSeek-V4-Pro | 0.570 | — | 0.460 | 0.495 | 0.421 | 0.555 | 0.494 | 0.345 | 0.461 |
| GLM-5.2 | 0.599 | 0.540 | — | 0.530 | 0.466 | 0.583 | 0.528 | 0.379 | 0.492 |
| Qwen3.7-Max | 0.563 | 0.505 | 0.470 | — | 0.415 | 0.545 | 0.472 | 0.343 | 0.479 |
| Kimi-K2.6 | 0.633 | 0.579 | 0.534 | 0.585 | — | 0.615 | 0.542 | 0.412 | 0.532 |
| Qwen3.6-Flash | 0.502 | 0.445 | 0.417 | 0.455 | 0.385 | — | 0.423 | 0.300 | 0.433 |
| DeepSeek-V4-Flash | 0.584 | 0.506 | 0.472 | 0.528 | 0.458 | 0.577 | — | 0.344 | 0.480 |
| Codex GPT-5.6 Sol | 0.700 | 0.655 | 0.621 | 0.657 | 0.588 | 0.700 | 0.656 | — | 0.638 |
| Qwen3-8B | 0.573 | 0.539 | 0.508 | 0.521 | 0.468 | 0.567 | 0.520 | 0.362 | — |

## Pareto analysis

Non-dominated OPB–UPB models: Codex GPT-5.6 Sol, DeepSeek-V4-Pro, DeepSeek-V4-Flash, GLM-5.2, Kimi-K2.6, Qwen3.7-Max, Qwen3-8B, Qwen3.5-35B-A3B.

## Observed metric spread

| Metric | Minimum | Maximum | Range | Population SD |
| --- | ---: | ---: | ---: | ---: |
| MinCalib | 0.499 | 0.802 | 0.303 | 0.088 |
| product_resistance | 0.480 | 0.723 | 0.243 | 0.072 |
| PMU_lambda_1 | 0.396 | 0.601 | 0.206 | 0.059 |
| H | 0.657 | 0.849 | 0.192 | 0.057 |
| balanced_accuracy | 0.641 | 0.802 | 0.162 | 0.048 |
| quadratic_kappa | 0.586 | 0.721 | 0.135 | 0.038 |
| linear_kappa | 0.552 | 0.686 | 0.134 | 0.037 |
| MCC | 0.513 | 0.643 | 0.130 | 0.034 |
| strict_sample_accuracy | 0.110 | 0.230 | 0.120 | 0.037 |
| macro_F1 | 0.658 | 0.750 | 0.092 | 0.025 |
| CVaR90_linear_loss | 0.242 | 0.330 | 0.088 | 0.023 |

## Sample-cluster bootstrap uncertainty

| Model | H 95% CI | MinCalib 95% CI | MCC 95% CI | Linear κ 95% CI | Strict sample 95% CI | CVaR90 95% CI | PMU(1) 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-35B-A3B | [0.834, 0.863] | [0.777, 0.826] | [0.549, 0.593] | [0.556, 0.602] | [0.084, 0.138] | [0.304, 0.356] | [0.570, 0.633] |
| DeepSeek-V4-Pro | [0.825, 0.857] | [0.750, 0.803] | [0.558, 0.608] | [0.568, 0.621] | [0.108, 0.166] | [0.282, 0.334] | [0.552, 0.618] |
| GLM-5.2 | [0.822, 0.853] | [0.742, 0.795] | [0.581, 0.624] | [0.604, 0.646] | [0.120, 0.182] | [0.253, 0.301] | [0.538, 0.601] |
| Qwen3.7-Max | [0.821, 0.854] | [0.737, 0.792] | [0.565, 0.612] | [0.586, 0.631] | [0.102, 0.162] | [0.269, 0.316] | [0.538, 0.603] |
| Kimi-K2.6 | [0.819, 0.854] | [0.733, 0.790] | [0.588, 0.638] | [0.616, 0.666] | [0.164, 0.236] | [0.266, 0.330] | [0.557, 0.625] |
| Qwen3.6-Flash | [0.820, 0.851] | [0.749, 0.801] | [0.548, 0.593] | [0.560, 0.605] | [0.096, 0.154] | [0.283, 0.332] | [0.546, 0.611] |
| DeepSeek-V4-Flash | [0.817, 0.851] | [0.728, 0.782] | [0.572, 0.619] | [0.587, 0.635] | [0.106, 0.166] | [0.257, 0.314] | [0.555, 0.619] |
| Codex GPT-5.6 Sol | [0.776, 0.817] | [0.654, 0.714] | [0.618, 0.669] | [0.661, 0.711] | [0.194, 0.268] | [0.217, 0.269] | [0.518, 0.586] |
| Qwen3-8B | [0.629, 0.685] | [0.467, 0.532] | [0.485, 0.541] | [0.523, 0.580] | [0.102, 0.162] | [0.265, 0.318] | [0.364, 0.430] |

All intervals resample the same 500 sample IDs as clusters and preserve their full/no-memory atom groups.

## Interpretation boundary

- MCC, Kappa, NMI, and ordinal correlation discard the over-use versus under-use direction even when they improve numerical separation.
- Product and power-mean scores partly enlarge the numeric range through rescaling; this does not create new statistical evidence.
- PMU depends on the full/no-memory causal contrast and on λ.
- CVaR exposes tail failures but should not replace average performance.
- Brier score, log loss, and ordinal CRPS are not validly computable without a probability distribution over A/B/C.
- Pairwise bootstrap intervals and blinded human validation remain necessary before making significance or external leaderboard claims.
