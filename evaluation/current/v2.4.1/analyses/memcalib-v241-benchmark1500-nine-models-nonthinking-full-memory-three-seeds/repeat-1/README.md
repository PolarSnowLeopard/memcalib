# MemCalib v2.4.1 benchmark-1500 nine-model Non-Think Full-memory seed 42

Locked 1,500-record, nine-model Full-memory evaluation; stochastic answer seed 42; DeepSeek-V4-Pro deterministic Judge; Bailian and company crawl-platform answer channels.

## Headline comparison

| Model | OPB↓ | UPB↓ | H↑ | MinCalib↑ | MCC↑ | Linear κ↑ | CVaR90↓ | PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.067 | 0.175 | 0.875 | 0.825 | 0.621 | 0.655 | 0.267 | NA |
| DeepSeek-V4-Flash-0731 | 0.060 | 0.194 | 0.868 | 0.806 | 0.628 | 0.661 | 0.263 | NA |
| Qwen3.5-35B-A3B | 0.090 | 0.178 | 0.863 | 0.822 | 0.562 | 0.585 | 0.301 | NA |
| GPT-5.6-SOL | 0.037 | 0.220 | 0.862 | 0.780 | 0.687 | 0.726 | 0.228 | NA |
| GLM-5.2 | 0.061 | 0.218 | 0.853 | 0.782 | 0.608 | 0.645 | 0.269 | NA |
| Claude Sonnet 4.6 | 0.052 | 0.233 | 0.848 | 0.767 | 0.624 | 0.662 | 0.251 | NA |
| Gemini 3.5 Flash | 0.048 | 0.237 | 0.847 | 0.763 | 0.639 | 0.664 | 0.257 | NA |
| Qwen3.8-Max | 0.053 | 0.258 | 0.832 | 0.742 | 0.604 | 0.641 | 0.264 | NA |
| Qwen3-8B | 0.036 | 0.484 | 0.672 | 0.516 | 0.510 | 0.562 | 0.287 | NA |

Numeric ranges across differently scaled metrics are not directly comparable. Use paired confidence intervals and ranking robustness, not range alone.

## Classification and chance-corrected metrics

| Model | Exact↑ | Balanced acc.↑ | Macro F1↑ | MCC↑ | κ↑ | Linear κ↑ | Quadratic κ↑ | NMI↑ | Cramér V↑ | Ordinal r↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.863 | 0.838 | 0.751 | 0.621 | 0.601 | 0.655 | 0.704 | 0.407 | 0.663 | 0.718 |
| DeepSeek-V4-Flash-0731 | 0.872 | 0.831 | 0.756 | 0.628 | 0.614 | 0.661 | 0.702 | 0.407 | 0.661 | 0.713 |
| Qwen3.5-35B-A3B | 0.825 | 0.821 | 0.708 | 0.562 | 0.528 | 0.585 | 0.639 | 0.350 | 0.614 | 0.662 |
| GPT-5.6-SOL | 0.906 | 0.829 | 0.794 | 0.687 | 0.684 | 0.726 | 0.762 | 0.469 | 0.705 | 0.764 |
| GLM-5.2 | 0.866 | 0.814 | 0.744 | 0.608 | 0.593 | 0.645 | 0.692 | 0.387 | 0.645 | 0.701 |
| Claude Sonnet 4.6 | 0.877 | 0.810 | 0.754 | 0.624 | 0.615 | 0.662 | 0.704 | 0.398 | 0.652 | 0.710 |
| Gemini 3.5 Flash | 0.886 | 0.810 | 0.758 | 0.639 | 0.633 | 0.664 | 0.689 | 0.406 | 0.650 | 0.697 |
| Qwen3.8-Max | 0.873 | 0.793 | 0.741 | 0.604 | 0.597 | 0.641 | 0.680 | 0.376 | 0.632 | 0.686 |
| Qwen3-8B | 0.867 | 0.653 | 0.668 | 0.510 | 0.510 | 0.562 | 0.607 | 0.282 | 0.524 | 0.609 |

## Ordinal severity metrics

| Model | MAE↓ | RMSE↓ | Macro L1↑ | Macro L2↑ | A↔C atom rate↓ | Over quadratic cost↓ | Under quadratic cost↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.165 | 0.470 | 0.864 | 0.878 | 0.028 | 0.052 | 0.105 |
| DeepSeek-V4-Flash-0731 | 0.159 | 0.470 | 0.853 | 0.864 | 0.031 | 0.050 | 0.122 |
| Qwen3.5-35B-A3B | 0.211 | 0.532 | 0.855 | 0.871 | 0.036 | 0.070 | 0.109 |
| GPT-5.6-SOL | 0.119 | 0.409 | 0.845 | 0.853 | 0.024 | 0.034 | 0.133 |
| GLM-5.2 | 0.165 | 0.475 | 0.839 | 0.852 | 0.030 | 0.050 | 0.140 |
| Claude Sonnet 4.6 | 0.153 | 0.461 | 0.833 | 0.845 | 0.030 | 0.045 | 0.153 |
| Gemini 3.5 Flash | 0.152 | 0.479 | 0.827 | 0.836 | 0.039 | 0.050 | 0.149 |
| Qwen3.8-Max | 0.162 | 0.481 | 0.813 | 0.823 | 0.035 | 0.048 | 0.174 |
| Qwen3-8B | 0.170 | 0.493 | 0.687 | 0.703 | 0.037 | 0.031 | 0.357 |

## Composite-score sensitivity

| Model | H | Arithmetic | Geometric | Product | Softmin −2 | Softmin −4 | Softmin −8 | MinCalib | Ideal L2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.875 | 0.879 | 0.877 | 0.769 | 0.874 | 0.870 | 0.864 | 0.825 | 0.867 |
| DeepSeek-V4-Flash-0731 | 0.868 | 0.873 | 0.871 | 0.758 | 0.866 | 0.861 | 0.852 | 0.806 | 0.857 |
| Qwen3.5-35B-A3B | 0.863 | 0.866 | 0.864 | 0.747 | 0.862 | 0.860 | 0.856 | 0.822 | 0.859 |
| GPT-5.6-SOL | 0.862 | 0.872 | 0.867 | 0.752 | 0.858 | 0.849 | 0.833 | 0.780 | 0.843 |
| GLM-5.2 | 0.853 | 0.860 | 0.857 | 0.734 | 0.850 | 0.843 | 0.831 | 0.782 | 0.840 |
| Claude Sonnet 4.6 | 0.848 | 0.857 | 0.852 | 0.727 | 0.843 | 0.834 | 0.819 | 0.767 | 0.831 |
| Gemini 3.5 Flash | 0.847 | 0.858 | 0.852 | 0.726 | 0.842 | 0.832 | 0.816 | 0.763 | 0.829 |
| Qwen3.8-Max | 0.832 | 0.845 | 0.838 | 0.703 | 0.826 | 0.815 | 0.796 | 0.742 | 0.814 |
| Qwen3-8B | 0.672 | 0.740 | 0.705 | 0.497 | 0.643 | 0.601 | 0.562 | 0.516 | 0.657 |

## Sample-level tail risk

| Model | Strict sample↑ | Any A↔C sample↓ | Mean L1 loss↓ | P90↓ | CVaR90↓ | CVaR95↓ | Quadratic CVaR90↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.198 | 0.377 | 0.094 | 0.208 | 0.267 | 0.304 | 0.201 |
| DeepSeek-V4-Flash-0731 | 0.183 | 0.411 | 0.093 | 0.200 | 0.263 | 0.304 | 0.207 |
| Qwen3.5-35B-A3B | 0.111 | 0.469 | 0.119 | 0.235 | 0.301 | 0.344 | 0.226 |
| GPT-5.6-SOL | 0.272 | 0.336 | 0.070 | 0.167 | 0.228 | 0.275 | 0.180 |
| GLM-5.2 | 0.186 | 0.402 | 0.094 | 0.205 | 0.269 | 0.310 | 0.208 |
| Claude Sonnet 4.6 | 0.190 | 0.402 | 0.088 | 0.200 | 0.251 | 0.288 | 0.196 |
| Gemini 3.5 Flash | 0.184 | 0.514 | 0.089 | 0.200 | 0.257 | 0.295 | 0.208 |
| Qwen3.8-Max | 0.180 | 0.452 | 0.094 | 0.200 | 0.264 | 0.304 | 0.213 |
| Qwen3-8B | 0.159 | 0.449 | 0.100 | 0.214 | 0.287 | 0.337 | 0.233 |

CVaR90 is the mean loss among the worst 10% of samples; CVaR95 uses the worst 5%. Sample loss is normalized absolute ordinal distance.

### Why CVaR90 can reorder models

| Model | H rank | Mean L1 rank | CVaR90 rank | CVaR90↓ |
| --- | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 1 | 6 | 6 | 0.267 |
| DeepSeek-V4-Flash-0731 | 2 | 4 | 4 | 0.263 |
| Qwen3.5-35B-A3B | 3 | 9 | 9 | 0.301 |
| GPT-5.6-SOL | 4 | 1 | 1 | 0.228 |
| GLM-5.2 | 5 | 7 | 7 | 0.269 |
| Claude Sonnet 4.6 | 6 | 2 | 2 | 0.251 |
| Gemini 3.5 Flash | 7 | 3 | 3 | 0.257 |
| Qwen3.8-Max | 8 | 5 | 5 | 0.264 |
| Qwen3-8B | 9 | 8 | 8 | 0.287 |

For a full-memory sample `s` with `n_s` scorable atoms, `L_s = mean_i(|u_hat_si - u*_si| / 2)`. CVaR90 is the arithmetic mean of the largest 150 values of `L_s` among the locked 1500 samples. It therefore changes both the aggregation unit (sample rather than gold-label macro average) and the evaluated population (only the worst decile).

A model can make moderately sized errors across many samples and have worse H or mean loss but a less extreme worst decile. Conversely, errors concentrated within a smaller set of samples increase CVaR90. The ordering difference is expected and is not an arithmetic inconsistency.

[Open the tail, Pareto, and metric-rank diagnostics](candidate-metric-diagnostics.html).

## Paired memory utility

| Model | Induced OPB↓ | Reduced UPB↑ | PMU(0.5)↑ | PMU(1)↑ | PMU(2)↑ | Relative PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | NA | NA | NA | NA | NA | NA |
| DeepSeek-V4-Flash-0731 | NA | NA | NA | NA | NA | NA |
| Qwen3.5-35B-A3B | NA | NA | NA | NA | NA | NA |
| GPT-5.6-SOL | NA | NA | NA | NA | NA | NA |
| GLM-5.2 | NA | NA | NA | NA | NA | NA |
| Claude Sonnet 4.6 | NA | NA | NA | NA | NA | NA |
| Gemini 3.5 Flash | NA | NA | NA | NA | NA | NA |
| Qwen3.8-Max | NA | NA | NA | NA | NA | NA |
| Qwen3-8B | NA | NA | NA | NA | NA | NA |

Not computable in this Full-memory-only run because no matched No-memory responses were generated.

## Latent and pairwise models

| Model | Rasch over θ↑ | Rasch under θ↑ | Mean θ↑ | Min θ↑ | Bradley–Terry ability↑ |
| --- | ---: | ---: | ---: | ---: | ---: |
| GPT-5.6-SOL | 0.875 | 0.245 | 0.560 | 0.245 | 0.488 |
| Claude Sonnet 4.6 | 0.119 | 0.097 | 0.108 | 0.097 | 0.105 |
| Gemini 3.5 Flash | 0.389 | 0.043 | 0.216 | 0.043 | 0.091 |
| DeepSeek-V4-Flash-0731 | -0.188 | 0.581 | 0.197 | -0.188 | 0.009 |
| Qwen3.8-Max | 0.116 | -0.193 | -0.039 | -0.193 | -0.012 |
| Kimi-K2.6 | -0.504 | 0.829 | 0.163 | -0.504 | -0.017 |
| GLM-5.2 | -0.264 | 0.275 | 0.005 | -0.264 | -0.027 |
| Qwen3-8B | 0.973 | -2.671 | -0.849 | -2.671 | -0.127 |
| Qwen3.5-35B-A3B | -1.517 | 0.795 | -0.361 | -1.517 | -0.509 |

The two Rasch dimensions adjust separately for atom difficulty. The current 1PL fit is exploratory: standard errors condition on estimated item difficulties and are not a full Bayesian uncertainty estimate.

## Pairwise win-share matrix

Rows are the candidate model; each cell is its win share against the column model using full-memory normalized sample-level ordinal loss. Ties count 0.5.

| Model | Kimi-K2.6 | DeepSeek-V4-Flash-0731 | Qwen3.5-35B-A3B | GPT-5.6-SOL | GLM-5.2 | Claude Sonnet 4.6 | Gemini 3.5 Flash | Qwen3.8-Max | Qwen3-8B |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | — | 0.492 | 0.618 | 0.384 | 0.501 | 0.462 | 0.470 | 0.500 | 0.534 |
| DeepSeek-V4-Flash-0731 | 0.508 | — | 0.637 | 0.377 | 0.511 | 0.473 | 0.476 | 0.510 | 0.529 |
| Qwen3.5-35B-A3B | 0.382 | 0.363 | — | 0.273 | 0.384 | 0.347 | 0.363 | 0.366 | 0.416 |
| GPT-5.6-SOL | 0.616 | 0.623 | 0.727 | — | 0.626 | 0.600 | 0.598 | 0.630 | 0.642 |
| GLM-5.2 | 0.499 | 0.489 | 0.616 | 0.374 | — | 0.468 | 0.473 | 0.489 | 0.530 |
| Claude Sonnet 4.6 | 0.538 | 0.527 | 0.653 | 0.400 | 0.532 | — | 0.500 | 0.532 | 0.551 |
| Gemini 3.5 Flash | 0.530 | 0.524 | 0.637 | 0.402 | 0.527 | 0.500 | — | 0.532 | 0.548 |
| Qwen3.8-Max | 0.500 | 0.490 | 0.634 | 0.370 | 0.511 | 0.468 | 0.468 | — | 0.532 |
| Qwen3-8B | 0.466 | 0.471 | 0.584 | 0.358 | 0.470 | 0.449 | 0.452 | 0.468 | — |

## Pareto analysis

Non-dominated OPB–UPB models: DeepSeek-V4-Flash-0731, GPT-5.6-SOL, Kimi-K2.6, Qwen3-8B.

## Observed metric spread

| Metric | Minimum | Maximum | Range | Population SD |
| --- | ---: | ---: | ---: | ---: |
| MinCalib | 0.516 | 0.825 | 0.309 | 0.089 |
| product_resistance | 0.497 | 0.769 | 0.272 | 0.078 |
| H | 0.672 | 0.875 | 0.203 | 0.059 |
| balanced_accuracy | 0.653 | 0.838 | 0.185 | 0.053 |
| MCC | 0.510 | 0.687 | 0.177 | 0.047 |
| linear_kappa | 0.562 | 0.726 | 0.164 | 0.045 |
| strict_sample_accuracy | 0.111 | 0.272 | 0.161 | 0.039 |
| quadratic_kappa | 0.607 | 0.762 | 0.155 | 0.041 |
| macro_F1 | 0.668 | 0.794 | 0.127 | 0.033 |
| CVaR90_linear_loss | 0.228 | 0.301 | 0.073 | 0.020 |

## Sample-cluster bootstrap uncertainty

| Model | H 95% CI | MinCalib 95% CI | MCC 95% CI | Linear κ 95% CI | Strict sample 95% CI | CVaR90 95% CI | PMU(1) 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | [0.867, 0.883] | [0.810, 0.839] | [0.608, 0.634] | [0.643, 0.667] | [0.179, 0.218] | [0.253, 0.279] | NA |
| DeepSeek-V4-Flash-0731 | [0.859, 0.877] | [0.791, 0.822] | [0.615, 0.642] | [0.648, 0.673] | [0.164, 0.203] | [0.250, 0.277] | NA |
| Qwen3.5-35B-A3B | [0.856, 0.871] | [0.807, 0.836] | [0.550, 0.573] | [0.573, 0.597] | [0.095, 0.127] | [0.287, 0.315] | NA |
| GPT-5.6-SOL | [0.853, 0.872] | [0.765, 0.795] | [0.675, 0.701] | [0.714, 0.738] | [0.250, 0.294] | [0.214, 0.243] | NA |
| GLM-5.2 | [0.843, 0.863] | [0.764, 0.799] | [0.593, 0.621] | [0.631, 0.658] | [0.167, 0.206] | [0.255, 0.282] | NA |
| Claude Sonnet 4.6 | [0.838, 0.858] | [0.750, 0.784] | [0.610, 0.638] | [0.650, 0.675] | [0.170, 0.211] | [0.238, 0.263] | NA |
| Gemini 3.5 Flash | [0.837, 0.858] | [0.746, 0.780] | [0.625, 0.652] | [0.651, 0.676] | [0.163, 0.203] | [0.244, 0.268] | NA |
| Qwen3.8-Max | [0.821, 0.843] | [0.724, 0.760] | [0.591, 0.619] | [0.628, 0.655] | [0.161, 0.200] | [0.251, 0.277] | NA |
| Qwen3-8B | [0.654, 0.690] | [0.495, 0.537] | [0.493, 0.528] | [0.544, 0.579] | [0.141, 0.178] | [0.272, 0.303] | NA |

All intervals resample the same 1500 sample IDs as clusters. This run contains only Full-memory judgments.

## Interpretation boundary

- MCC, Kappa, NMI, and ordinal correlation discard the over-use versus under-use direction even when they improve numerical separation.
- Product and power-mean scores partly enlarge the numeric range through rescaling; this does not create new statistical evidence.
- PMU depends on the full/no-memory causal contrast and on λ.
- CVaR exposes tail failures but should not replace average performance.
- Brier score, log loss, and ordinal CRPS are not validly computable without a probability distribution over A/B/C.
- Pairwise bootstrap intervals and blinded human validation remain necessary before making significance or external leaderboard claims.
