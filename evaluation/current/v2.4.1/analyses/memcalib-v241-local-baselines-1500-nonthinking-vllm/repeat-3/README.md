# MemCalib v2.4.1 local vLLM baselines, seed 44

Locked 1,500-record Full-memory Non-Think evaluation of two local vLLM baselines; DeepSeek-V4-Pro Judge; inference failures remain in the denominator.

## Headline comparison

| Model | OPB↓ | UPB↓ | H↑ | MinCalib↑ | MCC↑ | Linear κ↑ | CVaR90↓ | PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen35-35b-a3b-local-vllm | 0.092 | 0.169 | 0.868 | 0.831 | 0.567 | 0.587 | 0.300 | NA |
| ministral3-8b-instruct-2512-bf16-local-vllm | 0.071 | 0.220 | 0.848 | 0.780 | 0.583 | 0.614 | 0.311 | NA |

Numeric ranges across differently scaled metrics are not directly comparable. Use paired confidence intervals and ranking robustness, not range alone.

## Classification and chance-corrected metrics

| Model | Exact↑ | Balanced acc.↑ | Macro F1↑ | MCC↑ | κ↑ | Linear κ↑ | Quadratic κ↑ | NMI↑ | Cramér V↑ | Ordinal r↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen35-35b-a3b-local-vllm | 0.826 | 0.826 | 0.709 | 0.567 | 0.533 | 0.587 | 0.638 | 0.353 | 0.615 | 0.664 |
| ministral3-8b-instruct-2512-bf16-local-vllm | 0.851 | 0.806 | 0.723 | 0.583 | 0.564 | 0.614 | 0.659 | 0.358 | 0.617 | 0.672 |

## Ordinal severity metrics

| Model | MAE↓ | RMSE↓ | Macro L1↑ | Macro L2↑ | A↔C atom rate↓ | Over quadratic cost↓ | Under quadratic cost↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen35-35b-a3b-local-vllm | 0.212 | 0.536 | 0.859 | 0.875 | 0.038 | 0.072 | 0.101 |
| ministral3-8b-instruct-2512-bf16-local-vllm | 0.185 | 0.507 | 0.835 | 0.850 | 0.036 | 0.059 | 0.141 |

## Composite-score sensitivity

| Model | H | Arithmetic | Geometric | Product | Softmin −2 | Softmin −4 | Softmin −8 | MinCalib | Ideal L2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen35-35b-a3b-local-vllm | 0.868 | 0.869 | 0.869 | 0.755 | 0.867 | 0.865 | 0.862 | 0.831 | 0.864 |
| ministral3-8b-instruct-2512-bf16-local-vllm | 0.848 | 0.854 | 0.851 | 0.724 | 0.845 | 0.838 | 0.827 | 0.780 | 0.836 |

## Sample-level tail risk

| Model | Strict sample↑ | Any A↔C sample↓ | Mean L1 loss↓ | P90↓ | CVaR90↓ | CVaR95↓ | Quadratic CVaR90↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen35-35b-a3b-local-vllm | 0.101 | 0.481 | 0.120 | 0.233 | 0.300 | 0.342 | 0.232 |
| ministral3-8b-instruct-2512-bf16-local-vllm | 0.147 | 0.451 | 0.108 | 0.228 | 0.311 | 0.367 | 0.244 |

CVaR90 is the mean loss among the worst 10% of samples; CVaR95 uses the worst 5%. Sample loss is normalized absolute ordinal distance.

### Why CVaR90 can reorder models

| Model | H rank | Mean L1 rank | CVaR90 rank | CVaR90↓ |
| --- | ---: | ---: | ---: | ---: |
| qwen35-35b-a3b-local-vllm | 1 | 2 | 1 | 0.300 |
| ministral3-8b-instruct-2512-bf16-local-vllm | 2 | 1 | 2 | 0.311 |

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
| ministral3-8b-instruct-2512-bf16-local-vllm | 0.527 | -0.493 | 0.017 | -0.493 | 0.139 |
| qwen35-35b-a3b-local-vllm | -0.527 | 0.493 | -0.017 | -0.527 | -0.139 |

The two Rasch dimensions adjust separately for atom difficulty. The current 1PL fit is exploratory: standard errors condition on estimated item difficulties and are not a full Bayesian uncertainty estimate.

## Pairwise win-share matrix

Rows are the candidate model; each cell is its win share against the column model using full-memory normalized sample-level ordinal loss. Ties count 0.5.

| Model | qwen35-35b-a3b-local-vllm | ministral3-8b-instruct-2512-bf16-local-vllm |
| --- | ---: | ---: |
| qwen35-35b-a3b-local-vllm | — | 0.431 |
| ministral3-8b-instruct-2512-bf16-local-vllm | 0.569 | — |

## Pareto analysis

Non-dominated OPB–UPB models: ministral3-8b-instruct-2512-bf16-local-vllm, qwen35-35b-a3b-local-vllm.

## Observed metric spread

| Metric | Minimum | Maximum | Range | Population SD |
| --- | ---: | ---: | ---: | ---: |
| MinCalib | 0.780 | 0.831 | 0.052 | 0.026 |
| strict_sample_accuracy | 0.101 | 0.147 | 0.045 | 0.023 |
| product_resistance | 0.724 | 0.755 | 0.030 | 0.015 |
| linear_kappa | 0.587 | 0.614 | 0.026 | 0.013 |
| balanced_accuracy | 0.806 | 0.826 | 0.020 | 0.010 |
| quadratic_kappa | 0.638 | 0.659 | 0.020 | 0.010 |
| H | 0.848 | 0.868 | 0.020 | 0.010 |
| MCC | 0.567 | 0.583 | 0.017 | 0.008 |
| macro_F1 | 0.709 | 0.723 | 0.014 | 0.007 |
| CVaR90_linear_loss | 0.300 | 0.311 | 0.012 | 0.006 |

## Sample-cluster bootstrap uncertainty

| Model | H 95% CI | MinCalib 95% CI | MCC 95% CI | Linear κ 95% CI | Strict sample 95% CI | CVaR90 95% CI | PMU(1) 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen35-35b-a3b-local-vllm | [0.860, 0.875] | [0.817, 0.845] | [0.555, 0.579] | [0.575, 0.600] | [0.086, 0.118] | [0.285, 0.314] | NA |
| ministral3-8b-instruct-2512-bf16-local-vllm | [0.838, 0.857] | [0.763, 0.796] | [0.569, 0.597] | [0.600, 0.628] | [0.130, 0.165] | [0.293, 0.329] | NA |

All intervals resample the same 1500 sample IDs as clusters. This run contains only Full-memory judgments.

## Interpretation boundary

- MCC, Kappa, NMI, and ordinal correlation discard the over-use versus under-use direction even when they improve numerical separation.
- Product and power-mean scores partly enlarge the numeric range through rescaling; this does not create new statistical evidence.
- PMU depends on the full/no-memory causal contrast and on λ.
- CVaR exposes tail failures but should not replace average performance.
- Brier score, log loss, and ordinal CRPS are not validly computable without a probability distribution over A/B/C.
- Pairwise bootstrap intervals and blinded human validation remain necessary before making significance or external leaderboard claims.
