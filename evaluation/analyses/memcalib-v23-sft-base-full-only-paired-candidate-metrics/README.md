# MemCalib v2.3 Qwen3.5-35B-A3B Base vs SFT

Strictly paired Full-memory-only evaluation on the 496 locked v2.3 samples completed by both the Base and SFT checkpoints.

## Headline comparison

| Model | OPB↓ | UPB↓ | H↑ | MinCalib↑ | MCC↑ | Linear κ↑ | CVaR90↓ | PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-35B-A3B Base | 0.104 | 0.201 | 0.845 | 0.799 | 0.557 | 0.558 | 0.359 | NA |
| Qwen3.5-35B-A3B SFT | 0.029 | 0.284 | 0.824 | 0.716 | 0.752 | 0.782 | 0.197 | NA |

Numeric ranges across differently scaled metrics are not directly comparable. Use paired confidence intervals and ranking robustness, not range alone.

## Classification and chance-corrected metrics

| Model | Exact↑ | Balanced acc.↑ | Macro F1↑ | MCC↑ | κ↑ | Linear κ↑ | Quadratic κ↑ | NMI↑ | Cramér V↑ | Ordinal r↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-35B-A3B Base | 0.838 | 0.796 | 0.685 | 0.557 | 0.532 | 0.558 | 0.580 | 0.313 | 0.559 | 0.608 |
| Qwen3.5-35B-A3B SFT | 0.937 | 0.791 | 0.821 | 0.752 | 0.749 | 0.782 | 0.809 | 0.542 | 0.740 | 0.811 |

## Ordinal severity metrics

| Model | MAE↓ | RMSE↓ | Macro L1↑ | Macro L2↑ | A↔C atom rate↓ | Over quadratic cost↓ | Under quadratic cost↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-35B-A3B Base | 0.221 | 0.583 | 0.825 | 0.839 | 0.059 | 0.084 | 0.131 |
| Qwen3.5-35B-A3B SFT | 0.081 | 0.341 | 0.804 | 0.810 | 0.018 | 0.012 | 0.204 |

## Composite-score sensitivity

| Model | H | Arithmetic | Geometric | Product | Softmin −2 | Softmin −4 | Softmin −8 | MinCalib | Ideal L2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-35B-A3B Base | 0.845 | 0.847 | 0.846 | 0.716 | 0.843 | 0.840 | 0.835 | 0.799 | 0.840 |
| Qwen3.5-35B-A3B SFT | 0.824 | 0.843 | 0.834 | 0.695 | 0.815 | 0.798 | 0.773 | 0.716 | 0.798 |

## Sample-level tail risk

| Model | Strict sample↑ | Any A↔C sample↓ | Mean L1 loss↓ | P90↓ | CVaR90↓ | CVaR95↓ | Quadratic CVaR90↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-35B-A3B Base | 0.107 | 0.651 | 0.130 | 0.271 | 0.359 | 0.426 | 0.314 |
| Qwen3.5-35B-A3B SFT | 0.387 | 0.244 | 0.049 | 0.125 | 0.197 | 0.244 | 0.167 |

CVaR90 is the mean loss among the worst 10% of samples; CVaR95 uses the worst 5%. Sample loss is normalized absolute ordinal distance.

### Why CVaR90 can reorder models

| Model | H rank | Mean L1 rank | CVaR90 rank | CVaR90↓ |
| --- | ---: | ---: | ---: | ---: |
| Qwen3.5-35B-A3B Base | 1 | 2 | 2 | 0.359 |
| Qwen3.5-35B-A3B SFT | 2 | 1 | 1 | 0.197 |

For a full-memory sample `s` with `n_s` scorable atoms, `L_s = mean_i(|u_hat_si - u*_si| / 2)`. CVaR90 is the arithmetic mean of the largest 50 values of `L_s` among the locked 496 samples. It therefore changes both the aggregation unit (sample rather than gold-label macro average) and the evaluated population (only the worst decile).

A model can make moderately sized errors across many samples and have worse H or mean loss but a less extreme worst decile. Conversely, errors concentrated within a smaller set of samples increase CVaR90. The ordering difference is expected and is not an arithmetic inconsistency.

[Open the tail, Pareto, and metric-rank diagnostics](candidate-metric-diagnostics.html).

## Paired memory utility

| Model | Induced OPB↓ | Reduced UPB↑ | PMU(0.5)↑ | PMU(1)↑ | PMU(2)↑ | Relative PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-35B-A3B Base | NA | NA | NA | NA | NA | NA |
| Qwen3.5-35B-A3B SFT | NA | NA | NA | NA | NA | NA |

Not computable in this Full-memory-only run because no matched No-memory responses were generated.

## Latent and pairwise models

| Model | Rasch over θ↑ | Rasch under θ↑ | Mean θ↑ | Min θ↑ | Bradley–Terry ability↑ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-35B-A3B SFT | 1.606 | -0.640 | 0.483 | -0.640 | 0.781 |
| Qwen3.5-35B-A3B Base | -1.606 | 0.640 | -0.483 | -1.606 | -0.781 |

The two Rasch dimensions adjust separately for atom difficulty. The current 1PL fit is exploratory: standard errors condition on estimated item difficulties and are not a full Bayesian uncertainty estimate.

## Pairwise win-share matrix

Rows are the candidate model; each cell is its win share against the column model using full-memory normalized sample-level ordinal loss. Ties count 0.5.

| Model | Qwen3.5-35B-A3B Base | Qwen3.5-35B-A3B SFT |
| --- | ---: | ---: |
| Qwen3.5-35B-A3B Base | — | 0.173 |
| Qwen3.5-35B-A3B SFT | 0.827 | — |

## Pareto analysis

Non-dominated OPB–UPB models: Qwen3.5-35B-A3B Base, Qwen3.5-35B-A3B SFT.

## Observed metric spread

| Metric | Minimum | Maximum | Range | Population SD |
| --- | ---: | ---: | ---: | ---: |
| strict_sample_accuracy | 0.107 | 0.387 | 0.280 | 0.140 |
| quadratic_kappa | 0.580 | 0.809 | 0.229 | 0.114 |
| linear_kappa | 0.558 | 0.782 | 0.224 | 0.112 |
| MCC | 0.557 | 0.752 | 0.195 | 0.098 |
| CVaR90_linear_loss | 0.197 | 0.359 | 0.162 | 0.081 |
| macro_F1 | 0.685 | 0.821 | 0.136 | 0.068 |
| MinCalib | 0.716 | 0.799 | 0.083 | 0.042 |
| product_resistance | 0.695 | 0.716 | 0.020 | 0.010 |
| H | 0.824 | 0.845 | 0.020 | 0.010 |
| balanced_accuracy | 0.791 | 0.796 | 0.005 | 0.003 |

## Sample-cluster bootstrap uncertainty

| Model | H 95% CI | MinCalib 95% CI | MCC 95% CI | Linear κ 95% CI | Strict sample 95% CI | CVaR90 95% CI | PMU(1) 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-35B-A3B Base | [0.829, 0.859] | [0.773, 0.825] | [0.533, 0.579] | [0.534, 0.581] | [0.081, 0.135] | [0.321, 0.403] | NA |
| Qwen3.5-35B-A3B SFT | [0.804, 0.843] | [0.686, 0.744] | [0.729, 0.774] | [0.760, 0.804] | [0.343, 0.429] | [0.170, 0.228] | NA |

All intervals resample the same 496 sample IDs as clusters. This run contains only Full-memory judgments.

## Interpretation boundary

- MCC, Kappa, NMI, and ordinal correlation discard the over-use versus under-use direction even when they improve numerical separation.
- Product and power-mean scores partly enlarge the numeric range through rescaling; this does not create new statistical evidence.
- PMU depends on the full/no-memory causal contrast and on λ.
- CVaR exposes tail failures but should not replace average performance.
- Brier score, log loss, and ordinal CRPS are not validly computable without a probability distribution over A/B/C.
- Pairwise bootstrap intervals and blinded human validation remain necessary before making significance or external leaderboard claims.
