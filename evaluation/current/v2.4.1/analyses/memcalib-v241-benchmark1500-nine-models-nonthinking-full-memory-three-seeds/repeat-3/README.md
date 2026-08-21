# MemCalib v2.4.1 benchmark-1500 nine-model Non-Think Full-memory seed 44

Locked 1,500-record, nine-model Full-memory evaluation; stochastic answer seed 44; DeepSeek-V4-Pro deterministic Judge; Bailian and company crawl-platform answer channels.

## Headline comparison

| Model | OPB↓ | UPB↓ | H↑ | MinCalib↑ | MCC↑ | Linear κ↑ | CVaR90↓ | PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DeepSeek-V4-Flash-0731 | 0.063 | 0.184 | 0.872 | 0.816 | 0.622 | 0.654 | 0.258 | NA |
| Qwen3.5-35B-A3B | 0.093 | 0.164 | 0.870 | 0.836 | 0.564 | 0.585 | 0.312 | NA |
| Kimi-K2.6 | 0.067 | 0.186 | 0.869 | 0.814 | 0.614 | 0.647 | 0.269 | NA |
| GPT-5.6-SOL | 0.036 | 0.211 | 0.867 | 0.789 | 0.694 | 0.730 | 0.230 | NA |
| GLM-5.2 | 0.062 | 0.222 | 0.851 | 0.778 | 0.604 | 0.639 | 0.270 | NA |
| Gemini 3.5 Flash | 0.049 | 0.238 | 0.847 | 0.762 | 0.634 | 0.658 | 0.264 | NA |
| Claude Sonnet 4.6 | 0.051 | 0.237 | 0.846 | 0.763 | 0.626 | 0.665 | 0.249 | NA |
| Qwen3.8-Max | 0.053 | 0.264 | 0.829 | 0.736 | 0.600 | 0.635 | 0.266 | NA |
| Qwen3-8B | 0.036 | 0.481 | 0.674 | 0.519 | 0.510 | 0.563 | 0.281 | NA |

Numeric ranges across differently scaled metrics are not directly comparable. Use paired confidence intervals and ranking robustness, not range alone.

## Classification and chance-corrected metrics

| Model | Exact↑ | Balanced acc.↑ | Macro F1↑ | MCC↑ | κ↑ | Linear κ↑ | Quadratic κ↑ | NMI↑ | Cramér V↑ | Ordinal r↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DeepSeek-V4-Flash-0731 | 0.867 | 0.835 | 0.752 | 0.622 | 0.605 | 0.654 | 0.698 | 0.405 | 0.660 | 0.711 |
| Qwen3.5-35B-A3B | 0.823 | 0.828 | 0.709 | 0.564 | 0.529 | 0.585 | 0.638 | 0.355 | 0.619 | 0.664 |
| Kimi-K2.6 | 0.862 | 0.831 | 0.746 | 0.614 | 0.594 | 0.647 | 0.695 | 0.397 | 0.653 | 0.709 |
| GPT-5.6-SOL | 0.907 | 0.835 | 0.798 | 0.694 | 0.691 | 0.730 | 0.763 | 0.475 | 0.709 | 0.766 |
| GLM-5.2 | 0.864 | 0.811 | 0.739 | 0.604 | 0.590 | 0.639 | 0.684 | 0.380 | 0.637 | 0.694 |
| Gemini 3.5 Flash | 0.884 | 0.809 | 0.755 | 0.634 | 0.628 | 0.658 | 0.683 | 0.402 | 0.646 | 0.691 |
| Claude Sonnet 4.6 | 0.879 | 0.808 | 0.755 | 0.626 | 0.618 | 0.665 | 0.706 | 0.400 | 0.653 | 0.712 |
| Qwen3.8-Max | 0.872 | 0.789 | 0.737 | 0.600 | 0.592 | 0.635 | 0.672 | 0.369 | 0.626 | 0.678 |
| Qwen3-8B | 0.867 | 0.655 | 0.671 | 0.510 | 0.509 | 0.563 | 0.609 | 0.283 | 0.529 | 0.612 |

## Ordinal severity metrics

| Model | MAE↓ | RMSE↓ | Macro L1↑ | Macro L2↑ | A↔C atom rate↓ | Over quadratic cost↓ | Under quadratic cost↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DeepSeek-V4-Flash-0731 | 0.164 | 0.475 | 0.858 | 0.870 | 0.031 | 0.053 | 0.113 |
| Qwen3.5-35B-A3B | 0.214 | 0.536 | 0.861 | 0.877 | 0.037 | 0.072 | 0.101 |
| Kimi-K2.6 | 0.168 | 0.478 | 0.857 | 0.870 | 0.030 | 0.054 | 0.111 |
| GPT-5.6-SOL | 0.117 | 0.408 | 0.851 | 0.858 | 0.025 | 0.034 | 0.128 |
| GLM-5.2 | 0.168 | 0.483 | 0.836 | 0.849 | 0.033 | 0.052 | 0.141 |
| Gemini 3.5 Flash | 0.156 | 0.486 | 0.827 | 0.835 | 0.040 | 0.052 | 0.149 |
| Claude Sonnet 4.6 | 0.150 | 0.458 | 0.831 | 0.843 | 0.030 | 0.043 | 0.155 |
| Qwen3.8-Max | 0.164 | 0.486 | 0.810 | 0.821 | 0.036 | 0.048 | 0.180 |
| Qwen3-8B | 0.169 | 0.492 | 0.686 | 0.702 | 0.036 | 0.030 | 0.358 |

## Composite-score sensitivity

| Model | H | Arithmetic | Geometric | Product | Softmin −2 | Softmin −4 | Softmin −8 | MinCalib | Ideal L2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DeepSeek-V4-Flash-0731 | 0.872 | 0.876 | 0.874 | 0.764 | 0.870 | 0.866 | 0.859 | 0.816 | 0.863 |
| Qwen3.5-35B-A3B | 0.870 | 0.871 | 0.871 | 0.758 | 0.869 | 0.868 | 0.865 | 0.836 | 0.867 |
| Kimi-K2.6 | 0.869 | 0.873 | 0.871 | 0.759 | 0.867 | 0.863 | 0.856 | 0.814 | 0.860 |
| GPT-5.6-SOL | 0.867 | 0.876 | 0.872 | 0.760 | 0.863 | 0.855 | 0.841 | 0.789 | 0.848 |
| GLM-5.2 | 0.851 | 0.858 | 0.854 | 0.730 | 0.847 | 0.840 | 0.827 | 0.778 | 0.837 |
| Gemini 3.5 Flash | 0.847 | 0.857 | 0.852 | 0.725 | 0.841 | 0.832 | 0.815 | 0.762 | 0.829 |
| Claude Sonnet 4.6 | 0.846 | 0.856 | 0.851 | 0.724 | 0.841 | 0.831 | 0.815 | 0.763 | 0.828 |
| Qwen3.8-Max | 0.829 | 0.842 | 0.835 | 0.697 | 0.822 | 0.810 | 0.790 | 0.736 | 0.810 |
| Qwen3-8B | 0.674 | 0.741 | 0.707 | 0.500 | 0.646 | 0.604 | 0.565 | 0.519 | 0.659 |

## Sample-level tail risk

| Model | Strict sample↑ | Any A↔C sample↓ | Mean L1 loss↓ | P90↓ | CVaR90↓ | CVaR95↓ | Quadratic CVaR90↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DeepSeek-V4-Flash-0731 | 0.164 | 0.413 | 0.095 | 0.200 | 0.258 | 0.300 | 0.200 |
| Qwen3.5-35B-A3B | 0.100 | 0.468 | 0.122 | 0.250 | 0.312 | 0.361 | 0.238 |
| Kimi-K2.6 | 0.198 | 0.391 | 0.095 | 0.214 | 0.269 | 0.308 | 0.205 |
| GPT-5.6-SOL | 0.290 | 0.336 | 0.069 | 0.167 | 0.230 | 0.275 | 0.184 |
| GLM-5.2 | 0.173 | 0.430 | 0.096 | 0.214 | 0.270 | 0.308 | 0.209 |
| Gemini 3.5 Flash | 0.171 | 0.527 | 0.091 | 0.200 | 0.264 | 0.307 | 0.213 |
| Claude Sonnet 4.6 | 0.195 | 0.395 | 0.087 | 0.192 | 0.249 | 0.287 | 0.196 |
| Qwen3.8-Max | 0.171 | 0.455 | 0.095 | 0.208 | 0.266 | 0.305 | 0.216 |
| Qwen3-8B | 0.152 | 0.445 | 0.099 | 0.214 | 0.281 | 0.324 | 0.223 |

CVaR90 is the mean loss among the worst 10% of samples; CVaR95 uses the worst 5%. Sample loss is normalized absolute ordinal distance.

### Why CVaR90 can reorder models

| Model | H rank | Mean L1 rank | CVaR90 rank | CVaR90↓ |
| --- | ---: | ---: | ---: | ---: |
| DeepSeek-V4-Flash-0731 | 1 | 4 | 3 | 0.258 |
| Qwen3.5-35B-A3B | 2 | 9 | 9 | 0.312 |
| Kimi-K2.6 | 3 | 6 | 6 | 0.269 |
| GPT-5.6-SOL | 4 | 1 | 1 | 0.230 |
| GLM-5.2 | 5 | 7 | 7 | 0.270 |
| Gemini 3.5 Flash | 6 | 3 | 4 | 0.264 |
| Claude Sonnet 4.6 | 7 | 2 | 2 | 0.249 |
| Qwen3.8-Max | 8 | 5 | 5 | 0.266 |
| Qwen3-8B | 9 | 8 | 8 | 0.281 |

For a full-memory sample `s` with `n_s` scorable atoms, `L_s = mean_i(|u_hat_si - u*_si| / 2)`. CVaR90 is the arithmetic mean of the largest 150 values of `L_s` among the locked 1500 samples. It therefore changes both the aggregation unit (sample rather than gold-label macro average) and the evaluated population (only the worst decile).

A model can make moderately sized errors across many samples and have worse H or mean loss but a less extreme worst decile. Conversely, errors concentrated within a smaller set of samples increase CVaR90. The ordering difference is expected and is not an arithmetic inconsistency.

[Open the tail, Pareto, and metric-rank diagnostics](candidate-metric-diagnostics.html).

## Paired memory utility

| Model | Induced OPB↓ | Reduced UPB↑ | PMU(0.5)↑ | PMU(1)↑ | PMU(2)↑ | Relative PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| DeepSeek-V4-Flash-0731 | NA | NA | NA | NA | NA | NA |
| Qwen3.5-35B-A3B | NA | NA | NA | NA | NA | NA |
| Kimi-K2.6 | NA | NA | NA | NA | NA | NA |
| GPT-5.6-SOL | NA | NA | NA | NA | NA | NA |
| GLM-5.2 | NA | NA | NA | NA | NA | NA |
| Gemini 3.5 Flash | NA | NA | NA | NA | NA | NA |
| Claude Sonnet 4.6 | NA | NA | NA | NA | NA | NA |
| Qwen3.8-Max | NA | NA | NA | NA | NA | NA |
| Qwen3-8B | NA | NA | NA | NA | NA | NA |

Not computable in this Full-memory-only run because no matched No-memory responses were generated.

## Latent and pairwise models

| Model | Rasch over θ↑ | Rasch under θ↑ | Mean θ↑ | Min θ↑ | Bradley–Terry ability↑ |
| --- | ---: | ---: | ---: | ---: | ---: |
| GPT-5.6-SOL | 0.920 | 0.334 | 0.627 | 0.334 | 0.531 |
| Claude Sonnet 4.6 | 0.222 | 0.038 | 0.130 | 0.038 | 0.137 |
| Gemini 3.5 Flash | 0.362 | 0.025 | 0.194 | 0.025 | 0.057 |
| DeepSeek-V4-Flash-0731 | -0.343 | 0.686 | 0.172 | -0.343 | -0.020 |
| Qwen3.8-Max | 0.131 | -0.261 | -0.065 | -0.261 | -0.027 |
| Kimi-K2.6 | -0.464 | 0.658 | 0.097 | -0.464 | -0.028 |
| GLM-5.2 | -0.249 | 0.217 | -0.016 | -0.249 | -0.037 |
| Qwen3-8B | 1.000 | -2.654 | -0.827 | -2.654 | -0.089 |
| Qwen3.5-35B-A3B | -1.580 | 0.958 | -0.311 | -1.580 | -0.523 |

The two Rasch dimensions adjust separately for atom difficulty. The current 1PL fit is exploratory: standard errors condition on estimated item difficulties and are not a full Bayesian uncertainty estimate.

## Pairwise win-share matrix

Rows are the candidate model; each cell is its win share against the column model using full-memory normalized sample-level ordinal loss. Ties count 0.5.

| Model | DeepSeek-V4-Flash-0731 | Qwen3.5-35B-A3B | Kimi-K2.6 | GPT-5.6-SOL | GLM-5.2 | Gemini 3.5 Flash | Claude Sonnet 4.6 | Qwen3.8-Max | Qwen3-8B |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DeepSeek-V4-Flash-0731 | — | 0.631 | 0.511 | 0.361 | 0.502 | 0.480 | 0.458 | 0.499 | 0.514 |
| Qwen3.5-35B-A3B | 0.369 | — | 0.379 | 0.266 | 0.379 | 0.368 | 0.328 | 0.368 | 0.409 |
| Kimi-K2.6 | 0.489 | 0.621 | — | 0.371 | 0.507 | 0.476 | 0.458 | 0.504 | 0.512 |
| GPT-5.6-SOL | 0.639 | 0.734 | 0.629 | — | 0.644 | 0.619 | 0.604 | 0.636 | 0.645 |
| GLM-5.2 | 0.498 | 0.621 | 0.493 | 0.356 | — | 0.474 | 0.450 | 0.502 | 0.523 |
| Gemini 3.5 Flash | 0.520 | 0.632 | 0.524 | 0.381 | 0.526 | — | 0.489 | 0.515 | 0.537 |
| Claude Sonnet 4.6 | 0.542 | 0.672 | 0.542 | 0.396 | 0.550 | 0.511 | — | 0.540 | 0.551 |
| Qwen3.8-Max | 0.501 | 0.632 | 0.496 | 0.364 | 0.498 | 0.485 | 0.460 | — | 0.506 |
| Qwen3-8B | 0.486 | 0.591 | 0.488 | 0.355 | 0.477 | 0.463 | 0.449 | 0.494 | — |

## Pareto analysis

Non-dominated OPB–UPB models: DeepSeek-V4-Flash-0731, GPT-5.6-SOL, Qwen3-8B, Qwen3.5-35B-A3B.

## Observed metric spread

| Metric | Minimum | Maximum | Range | Population SD |
| --- | ---: | ---: | ---: | ---: |
| MinCalib | 0.519 | 0.836 | 0.317 | 0.089 |
| product_resistance | 0.500 | 0.764 | 0.264 | 0.078 |
| H | 0.674 | 0.872 | 0.198 | 0.059 |
| strict_sample_accuracy | 0.100 | 0.290 | 0.190 | 0.047 |
| MCC | 0.510 | 0.694 | 0.184 | 0.047 |
| balanced_accuracy | 0.655 | 0.835 | 0.180 | 0.053 |
| linear_kappa | 0.563 | 0.730 | 0.167 | 0.045 |
| quadratic_kappa | 0.609 | 0.763 | 0.154 | 0.041 |
| macro_F1 | 0.671 | 0.798 | 0.128 | 0.033 |
| CVaR90_linear_loss | 0.230 | 0.312 | 0.082 | 0.021 |

## Sample-cluster bootstrap uncertainty

| Model | H 95% CI | MinCalib 95% CI | MCC 95% CI | Linear κ 95% CI | Strict sample 95% CI | CVaR90 95% CI | PMU(1) 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DeepSeek-V4-Flash-0731 | [0.864, 0.880] | [0.801, 0.830] | [0.610, 0.635] | [0.642, 0.666] | [0.145, 0.183] | [0.245, 0.271] | NA |
| Qwen3.5-35B-A3B | [0.862, 0.878] | [0.822, 0.850] | [0.553, 0.576] | [0.573, 0.597] | [0.084, 0.115] | [0.295, 0.328] | NA |
| Kimi-K2.6 | [0.861, 0.878] | [0.799, 0.828] | [0.601, 0.627] | [0.635, 0.661] | [0.179, 0.218] | [0.256, 0.282] | NA |
| GPT-5.6-SOL | [0.858, 0.877] | [0.773, 0.804] | [0.681, 0.708] | [0.718, 0.742] | [0.267, 0.312] | [0.216, 0.245] | NA |
| GLM-5.2 | [0.841, 0.860] | [0.762, 0.794] | [0.591, 0.617] | [0.627, 0.652] | [0.154, 0.192] | [0.257, 0.282] | NA |
| Gemini 3.5 Flash | [0.836, 0.857] | [0.745, 0.780] | [0.620, 0.647] | [0.644, 0.670] | [0.153, 0.191] | [0.250, 0.277] | NA |
| Claude Sonnet 4.6 | [0.835, 0.856] | [0.745, 0.780] | [0.613, 0.640] | [0.653, 0.678] | [0.175, 0.216] | [0.236, 0.262] | NA |
| Qwen3.8-Max | [0.817, 0.839] | [0.719, 0.753] | [0.585, 0.614] | [0.621, 0.649] | [0.152, 0.191] | [0.253, 0.279] | NA |
| Qwen3-8B | [0.656, 0.692] | [0.497, 0.540] | [0.493, 0.527] | [0.546, 0.580] | [0.134, 0.170] | [0.267, 0.294] | NA |

All intervals resample the same 1500 sample IDs as clusters. This run contains only Full-memory judgments.

## Interpretation boundary

- MCC, Kappa, NMI, and ordinal correlation discard the over-use versus under-use direction even when they improve numerical separation.
- Product and power-mean scores partly enlarge the numeric range through rescaling; this does not create new statistical evidence.
- PMU depends on the full/no-memory causal contrast and on λ.
- CVaR exposes tail failures but should not replace average performance.
- Brier score, log loss, and ordinal CRPS are not validly computable without a probability distribution over A/B/C.
- Pairwise bootstrap intervals and blinded human validation remain necessary before making significance or external leaderboard claims.
