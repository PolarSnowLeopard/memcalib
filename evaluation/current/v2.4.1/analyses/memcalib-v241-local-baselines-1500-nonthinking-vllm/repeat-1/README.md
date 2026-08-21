# MemCalib v2.4.1 local vLLM baselines, seed 42

Locked 1,500-record Full-memory Non-Think evaluation of two local vLLM baselines; DeepSeek-V4-Pro Judge; inference failures remain in the denominator.

## Headline comparison

| Model | OPB↓ | UPB↓ | H↑ | MinCalib↑ | MCC↑ | Linear κ↑ | CVaR90↓ | PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen35-35b-a3b-local-vllm | 0.093 | 0.168 | 0.868 | 0.832 | 0.566 | 0.587 | 0.297 | NA |
| ministral3-8b-instruct-2512-bf16-local-vllm | 0.072 | 0.226 | 0.844 | 0.774 | 0.579 | 0.608 | 0.321 | NA |

Numeric ranges across differently scaled metrics are not directly comparable. Use paired confidence intervals and ranking robustness, not range alone.

## Classification and chance-corrected metrics

| Model | Exact↑ | Balanced acc.↑ | Macro F1↑ | MCC↑ | κ↑ | Linear κ↑ | Quadratic κ↑ | NMI↑ | Cramér V↑ | Ordinal r↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen35-35b-a3b-local-vllm | 0.825 | 0.826 | 0.710 | 0.566 | 0.532 | 0.587 | 0.640 | 0.354 | 0.617 | 0.665 |
| ministral3-8b-instruct-2512-bf16-local-vllm | 0.849 | 0.801 | 0.718 | 0.579 | 0.560 | 0.608 | 0.652 | 0.350 | 0.609 | 0.665 |

## Ordinal severity metrics

| Model | MAE↓ | RMSE↓ | Macro L1↑ | Macro L2↑ | A↔C atom rate↓ | Over quadratic cost↓ | Under quadratic cost↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen35-35b-a3b-local-vllm | 0.211 | 0.534 | 0.859 | 0.875 | 0.037 | 0.071 | 0.102 |
| ministral3-8b-instruct-2512-bf16-local-vllm | 0.188 | 0.511 | 0.834 | 0.850 | 0.037 | 0.060 | 0.144 |

## Composite-score sensitivity

| Model | H | Arithmetic | Geometric | Product | Softmin −2 | Softmin −4 | Softmin −8 | MinCalib | Ideal L2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen35-35b-a3b-local-vllm | 0.868 | 0.870 | 0.869 | 0.755 | 0.867 | 0.865 | 0.862 | 0.832 | 0.864 |
| ministral3-8b-instruct-2512-bf16-local-vllm | 0.844 | 0.851 | 0.847 | 0.718 | 0.840 | 0.834 | 0.822 | 0.774 | 0.832 |

## Sample-level tail risk

| Model | Strict sample↑ | Any A↔C sample↓ | Mean L1 loss↓ | P90↓ | CVaR90↓ | CVaR95↓ | Quadratic CVaR90↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen35-35b-a3b-local-vllm | 0.099 | 0.483 | 0.120 | 0.231 | 0.297 | 0.334 | 0.224 |
| ministral3-8b-instruct-2512-bf16-local-vllm | 0.151 | 0.455 | 0.109 | 0.234 | 0.321 | 0.378 | 0.246 |

CVaR90 is the mean loss among the worst 10% of samples; CVaR95 uses the worst 5%. Sample loss is normalized absolute ordinal distance.

### Why CVaR90 can reorder models

| Model | H rank | Mean L1 rank | CVaR90 rank | CVaR90↓ |
| --- | ---: | ---: | ---: | ---: |
| qwen35-35b-a3b-local-vllm | 1 | 2 | 1 | 0.297 |
| ministral3-8b-instruct-2512-bf16-local-vllm | 2 | 1 | 2 | 0.321 |

For a full-memory sample `s` with `n_s` scorable atoms, `L_s = mean_i(|u_hat_si - u*_si| / 2)`. CVaR90 is the arithmetic mean of the largest 150 values of `L_s` among the locked 1500 samples. It therefore changes both the aggregation unit (sample rather than gold-label macro average) and the evaluated population (only the worst decile).

A model can make moderately sized errors across many samples and have worse H or mean loss but a less extreme worst decile. Conversely, errors concentrated within a smaller set of samples increase CVaR90. The ordering difference is expected and is not an arithmetic inconsistency.

[Open the tail, Pareto, and metric-rank diagnostics](candidate-metric-diagnostics.html).

## Paired memory utility

| Model | Induced OPB↓ | Reduced UPB↑ | PMU(0.5)↑ | PMU(1)↑ | PMU(2)↑ | Relative PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen35-35b-a3b-local-vllm | NA | NA | NA | NA | NA | NA |
| ministral3-8b-instruct-2512-bf16-local-vllm | NA | NA | NA | NA | NA | NA |

Not computable in this Full-memory-only run because no matched No-memory responses were generated.

## Latent and pairwise models

| Model | Rasch over θ↑ | Rasch under θ↑ | Mean θ↑ | Min θ↑ | Bradley–Terry ability↑ |
| --- | ---: | ---: | ---: | ---: | ---: |
| ministral3-8b-instruct-2512-bf16-local-vllm | 0.526 | -0.580 | -0.027 | -0.580 | 0.114 |
| qwen35-35b-a3b-local-vllm | -0.526 | 0.580 | 0.027 | -0.526 | -0.114 |

The two Rasch dimensions adjust separately for atom difficulty. The current 1PL fit is exploratory: standard errors condition on estimated item difficulties and are not a full Bayesian uncertainty estimate.

## Pairwise win-share matrix

Rows are the candidate model; each cell is its win share against the column model using full-memory normalized sample-level ordinal loss. Ties count 0.5.

| Model | qwen35-35b-a3b-local-vllm | ministral3-8b-instruct-2512-bf16-local-vllm |
| --- | ---: | ---: |
| qwen35-35b-a3b-local-vllm | — | 0.443 |
| ministral3-8b-instruct-2512-bf16-local-vllm | 0.557 | — |

## Pareto analysis

Non-dominated OPB–UPB models: ministral3-8b-instruct-2512-bf16-local-vllm, qwen35-35b-a3b-local-vllm.

## Observed metric spread

| Metric | Minimum | Maximum | Range | Population SD |
| --- | ---: | ---: | ---: | ---: |
| MinCalib | 0.774 | 0.832 | 0.058 | 0.029 |
| strict_sample_accuracy | 0.099 | 0.151 | 0.052 | 0.026 |
| product_resistance | 0.718 | 0.755 | 0.037 | 0.018 |
| balanced_accuracy | 0.801 | 0.826 | 0.025 | 0.013 |
| CVaR90_linear_loss | 0.297 | 0.321 | 0.024 | 0.012 |
| H | 0.844 | 0.868 | 0.024 | 0.012 |
| linear_kappa | 0.587 | 0.608 | 0.021 | 0.010 |
| MCC | 0.566 | 0.579 | 0.013 | 0.007 |
| quadratic_kappa | 0.640 | 0.652 | 0.012 | 0.006 |
| macro_F1 | 0.710 | 0.718 | 0.008 | 0.004 |

## Sample-cluster bootstrap uncertainty

| Model | H 95% CI | MinCalib 95% CI | MCC 95% CI | Linear κ 95% CI | Strict sample 95% CI | CVaR90 95% CI | PMU(1) 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen35-35b-a3b-local-vllm | [0.860, 0.875] | [0.817, 0.846] | [0.554, 0.577] | [0.576, 0.599] | [0.084, 0.115] | [0.283, 0.309] | NA |
| ministral3-8b-instruct-2512-bf16-local-vllm | [0.834, 0.853] | [0.758, 0.790] | [0.565, 0.593] | [0.594, 0.622] | [0.134, 0.170] | [0.302, 0.338] | NA |

All intervals resample the same 1500 sample IDs as clusters. This run contains only Full-memory judgments.

## Interpretation boundary

- MCC, Kappa, NMI, and ordinal correlation discard the over-use versus under-use direction even when they improve numerical separation.
- Product and power-mean scores partly enlarge the numeric range through rescaling; this does not create new statistical evidence.
- PMU depends on the full/no-memory causal contrast and on λ.
- CVaR exposes tail failures but should not replace average performance.
- Brier score, log loss, and ordinal CRPS are not validly computable without a probability distribution over A/B/C.
- Pairwise bootstrap intervals and blinded human validation remain necessary before making significance or external leaderboard claims.
