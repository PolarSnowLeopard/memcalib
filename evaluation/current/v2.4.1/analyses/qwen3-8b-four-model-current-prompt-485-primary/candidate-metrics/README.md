# Qwen3-8B original and v2.4.1 training comparison (current prompt)

Strictly paired Non-Think Full-memory evaluation on 485 corrected v2.4.1 samples. All four models use the same current answer-system prompt and Qwen3.7-Plus ordered-usage-v2.1 primary Judge.

## Headline comparison

| Model | OPB↓ | UPB↓ | H↑ | MinCalib↑ | MCC↑ | Linear κ↑ | CVaR90↓ | PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen3-8b-v241-sft-fluent-12k | 0.033 | 0.227 | 0.859 | 0.773 | 0.811 | 0.841 | 0.156 | NA |
| qwen3-8b-v241-sft-atomic-12k | 0.036 | 0.233 | 0.854 | 0.767 | 0.797 | 0.829 | 0.163 | NA |
| qwen3-8b-v241-coldstart-4k | 0.045 | 0.345 | 0.777 | 0.655 | 0.693 | 0.733 | 0.202 | NA |
| qwen3-8b-v241-original-current-prompt | 0.041 | 0.519 | 0.641 | 0.481 | 0.479 | 0.528 | 0.286 | NA |

Numeric ranges across differently scaled metrics are not directly comparable. Use paired confidence intervals and ranking robustness, not range alone.

## Classification and chance-corrected metrics

| Model | Exact↑ | Balanced acc.↑ | Macro F1↑ | MCC↑ | κ↑ | Linear κ↑ | Quadratic κ↑ | NMI↑ | Cramér V↑ | Ordinal r↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen3-8b-v241-sft-fluent-12k | 0.951 | 0.827 | 0.852 | 0.811 | 0.809 | 0.841 | 0.868 | 0.631 | 0.786 | 0.870 |
| qwen3-8b-v241-sft-atomic-12k | 0.948 | 0.821 | 0.845 | 0.797 | 0.795 | 0.829 | 0.857 | 0.607 | 0.775 | 0.858 |
| qwen3-8b-v241-coldstart-4k | 0.923 | 0.740 | 0.769 | 0.693 | 0.690 | 0.733 | 0.769 | 0.472 | 0.668 | 0.772 |
| qwen3-8b-v241-original-current-prompt | 0.865 | 0.627 | 0.640 | 0.479 | 0.479 | 0.528 | 0.571 | 0.252 | 0.482 | 0.572 |

## Ordinal severity metrics

| Model | MAE↓ | RMSE↓ | Macro L1↑ | Macro L2↑ | A↔C atom rate↓ | Over quadratic cost↓ | Under quadratic cost↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen3-8b-v241-sft-fluent-12k | 0.059 | 0.284 | 0.846 | 0.855 | 0.011 | 0.008 | 0.148 |
| qwen3-8b-v241-sft-atomic-12k | 0.064 | 0.297 | 0.838 | 0.846 | 0.012 | 0.009 | 0.156 |
| qwen3-8b-v241-coldstart-4k | 0.098 | 0.373 | 0.763 | 0.774 | 0.021 | 0.014 | 0.242 |
| qwen3-8b-v241-original-current-prompt | 0.176 | 0.508 | 0.662 | 0.680 | 0.041 | 0.034 | 0.379 |

## Composite-score sensitivity

| Model | H | Arithmetic | Geometric | Product | Softmin −2 | Softmin −4 | Softmin −8 | MinCalib | Ideal L2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen3-8b-v241-sft-fluent-12k | 0.859 | 0.870 | 0.865 | 0.748 | 0.854 | 0.844 | 0.827 | 0.773 | 0.838 |
| qwen3-8b-v241-sft-atomic-12k | 0.854 | 0.866 | 0.860 | 0.740 | 0.849 | 0.838 | 0.821 | 0.767 | 0.833 |
| qwen3-8b-v241-coldstart-4k | 0.777 | 0.805 | 0.791 | 0.625 | 0.764 | 0.741 | 0.710 | 0.655 | 0.754 |
| qwen3-8b-v241-original-current-prompt | 0.641 | 0.720 | 0.679 | 0.462 | 0.608 | 0.564 | 0.525 | 0.481 | 0.632 |

## Sample-level tail risk

| Model | Strict sample↑ | Any A↔C sample↓ | Mean L1 loss↓ | P90↓ | CVaR90↓ | CVaR95↓ | Quadratic CVaR90↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen3-8b-v241-sft-fluent-12k | 0.478 | 0.153 | 0.037 | 0.104 | 0.156 | 0.191 | 0.126 |
| qwen3-8b-v241-sft-atomic-12k | 0.464 | 0.177 | 0.040 | 0.114 | 0.163 | 0.195 | 0.131 |
| qwen3-8b-v241-coldstart-4k | 0.324 | 0.274 | 0.059 | 0.143 | 0.202 | 0.249 | 0.165 |
| qwen3-8b-v241-original-current-prompt | 0.107 | 0.518 | 0.104 | 0.222 | 0.286 | 0.327 | 0.235 |

CVaR90 is the mean loss among the worst 10% of samples; CVaR95 uses the worst 5%. Sample loss is normalized absolute ordinal distance.

### Why CVaR90 can reorder models

| Model | H rank | Mean L1 rank | CVaR90 rank | CVaR90↓ |
| --- | ---: | ---: | ---: | ---: |
| qwen3-8b-v241-sft-fluent-12k | 1 | 1 | 1 | 0.156 |
| qwen3-8b-v241-sft-atomic-12k | 2 | 2 | 2 | 0.163 |
| qwen3-8b-v241-coldstart-4k | 3 | 3 | 3 | 0.202 |
| qwen3-8b-v241-original-current-prompt | 4 | 4 | 4 | 0.286 |

For a full-memory sample `s` with `n_s` scorable atoms, `L_s = mean_i(|u_hat_si - u*_si| / 2)`. CVaR90 is the arithmetic mean of the largest 49 values of `L_s` among the locked 485 samples. It therefore changes both the aggregation unit (sample rather than gold-label macro average) and the evaluated population (only the worst decile).

A model can make moderately sized errors across many samples and have worse H or mean loss but a less extreme worst decile. Conversely, errors concentrated within a smaller set of samples increase CVaR90. The ordering difference is expected and is not an arithmetic inconsistency.

[Open the tail, Pareto, and metric-rank diagnostics](candidate-metric-diagnostics.html).

## Paired memory utility

| Model | Induced OPB↓ | Reduced UPB↑ | PMU(0.5)↑ | PMU(1)↑ | PMU(2)↑ | Relative PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen3-8b-v241-sft-fluent-12k | NA | NA | NA | NA | NA | NA |
| qwen3-8b-v241-sft-atomic-12k | NA | NA | NA | NA | NA | NA |
| qwen3-8b-v241-coldstart-4k | NA | NA | NA | NA | NA | NA |
| qwen3-8b-v241-original-current-prompt | NA | NA | NA | NA | NA | NA |

Not computable in this Full-memory-only run because no matched No-memory responses were generated.

## Latent and pairwise models

| Model | Rasch over θ↑ | Rasch under θ↑ | Mean θ↑ | Min θ↑ | Bradley–Terry ability↑ |
| --- | ---: | ---: | ---: | ---: | ---: |
| qwen3-8b-v241-sft-fluent-12k | 0.357 | 1.162 | 0.760 | 0.357 | 0.551 |
| qwen3-8b-v241-sft-atomic-12k | 0.357 | 1.071 | 0.714 | 0.357 | 0.458 |
| qwen3-8b-v241-coldstart-4k | 0.357 | -0.199 | 0.079 | -0.199 | -0.030 |
| qwen3-8b-v241-original-current-prompt | -1.072 | -2.035 | -1.554 | -2.035 | -0.978 |

The two Rasch dimensions adjust separately for atom difficulty. The current 1PL fit is exploratory: standard errors condition on estimated item difficulties and are not a full Bayesian uncertainty estimate.

## Pairwise win-share matrix

Rows are the candidate model; each cell is its win share against the column model using full-memory normalized sample-level ordinal loss. Ties count 0.5.

| Model | qwen3-8b-v241-sft-fluent-12k | qwen3-8b-v241-sft-atomic-12k | qwen3-8b-v241-coldstart-4k | qwen3-8b-v241-original-current-prompt |
| --- | ---: | ---: | ---: | ---: |
| qwen3-8b-v241-sft-fluent-12k | — | 0.523 | 0.643 | 0.821 |
| qwen3-8b-v241-sft-atomic-12k | 0.477 | — | 0.615 | 0.811 |
| qwen3-8b-v241-coldstart-4k | 0.357 | 0.385 | — | 0.719 |
| qwen3-8b-v241-original-current-prompt | 0.179 | 0.189 | 0.281 | — |

## Pareto analysis

Non-dominated OPB–UPB models: qwen3-8b-v241-sft-fluent-12k.

## Observed metric spread

| Metric | Minimum | Maximum | Range | Population SD |
| --- | ---: | ---: | ---: | ---: |
| strict_sample_accuracy | 0.107 | 0.478 | 0.371 | 0.149 |
| MCC | 0.479 | 0.811 | 0.332 | 0.133 |
| linear_kappa | 0.528 | 0.841 | 0.313 | 0.125 |
| quadratic_kappa | 0.571 | 0.868 | 0.297 | 0.119 |
| MinCalib | 0.481 | 0.773 | 0.292 | 0.118 |
| product_resistance | 0.462 | 0.748 | 0.286 | 0.116 |
| H | 0.641 | 0.859 | 0.218 | 0.088 |
| macro_F1 | 0.640 | 0.852 | 0.213 | 0.085 |
| balanced_accuracy | 0.627 | 0.827 | 0.200 | 0.081 |
| CVaR90_linear_loss | 0.156 | 0.286 | 0.130 | 0.052 |

## Sample-cluster bootstrap uncertainty

| Model | H 95% CI | MinCalib 95% CI | MCC 95% CI | Linear κ 95% CI | Strict sample 95% CI | CVaR90 95% CI | PMU(1) 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen3-8b-v241-sft-fluent-12k | [0.842, 0.875] | [0.746, 0.798] | [0.790, 0.830] | [0.821, 0.859] | [0.435, 0.520] | [0.136, 0.176] | NA |
| qwen3-8b-v241-sft-atomic-12k | [0.838, 0.871] | [0.742, 0.793] | [0.776, 0.818] | [0.810, 0.848] | [0.423, 0.507] | [0.145, 0.181] | NA |
| qwen3-8b-v241-coldstart-4k | [0.755, 0.798] | [0.626, 0.685] | [0.668, 0.718] | [0.710, 0.758] | [0.282, 0.365] | [0.175, 0.233] | NA |
| qwen3-8b-v241-original-current-prompt | [0.611, 0.671] | [0.448, 0.516] | [0.451, 0.510] | [0.499, 0.558] | [0.080, 0.136] | [0.263, 0.309] | NA |

All intervals resample the same 485 sample IDs as clusters. This run contains only Full-memory judgments.

## Interpretation boundary

- MCC, Kappa, NMI, and ordinal correlation discard the over-use versus under-use direction even when they improve numerical separation.
- Product and power-mean scores partly enlarge the numeric range through rescaling; this does not create new statistical evidence.
- PMU depends on the full/no-memory causal contrast and on λ.
- CVaR exposes tail failures but should not replace average performance.
- Brier score, log loss, and ordinal CRPS are not validly computable without a probability distribution over A/B/C.
- Pairwise bootstrap intervals and blinded human validation remain necessary before making significance or external leaderboard claims.
