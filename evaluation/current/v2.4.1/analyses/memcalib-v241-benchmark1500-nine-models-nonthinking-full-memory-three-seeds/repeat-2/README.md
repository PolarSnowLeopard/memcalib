# MemCalib v2.4.1 benchmark-1500 nine-model Non-Think Full-memory seed 43

Locked 1,500-record, nine-model Full-memory evaluation; stochastic answer seed 43; DeepSeek-V4-Pro deterministic Judge; Bailian and company crawl-platform answer channels.

## Headline comparison

| Model | OPB↓ | UPB↓ | H↑ | MinCalib↑ | MCC↑ | Linear κ↑ | CVaR90↓ | PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.068 | 0.186 | 0.869 | 0.814 | 0.612 | 0.645 | 0.276 | NA |
| GPT-5.6-SOL | 0.036 | 0.211 | 0.868 | 0.789 | 0.694 | 0.732 | 0.228 | NA |
| Qwen3.5-35B-A3B | 0.092 | 0.175 | 0.865 | 0.825 | 0.561 | 0.585 | 0.302 | NA |
| DeepSeek-V4-Flash-0731 | 0.060 | 0.199 | 0.865 | 0.801 | 0.621 | 0.653 | 0.259 | NA |
| GLM-5.2 | 0.061 | 0.218 | 0.854 | 0.782 | 0.607 | 0.641 | 0.277 | NA |
| Claude Sonnet 4.6 | 0.054 | 0.227 | 0.851 | 0.773 | 0.627 | 0.665 | 0.253 | NA |
| Gemini 3.5 Flash | 0.047 | 0.233 | 0.850 | 0.767 | 0.640 | 0.664 | 0.254 | NA |
| Qwen3.8-Max | 0.053 | 0.256 | 0.833 | 0.744 | 0.607 | 0.645 | 0.264 | NA |
| Qwen3-8B | 0.036 | 0.488 | 0.669 | 0.512 | 0.507 | 0.559 | 0.280 | NA |

Numeric ranges across differently scaled metrics are not directly comparable. Use paired confidence intervals and ranking robustness, not range alone.

## Classification and chance-corrected metrics

| Model | Exact↑ | Balanced acc.↑ | Macro F1↑ | MCC↑ | κ↑ | Linear κ↑ | Quadratic κ↑ | NMI↑ | Cramér V↑ | Ordinal r↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.860 | 0.831 | 0.745 | 0.612 | 0.592 | 0.645 | 0.694 | 0.396 | 0.654 | 0.707 |
| GPT-5.6-SOL | 0.908 | 0.835 | 0.799 | 0.694 | 0.691 | 0.732 | 0.767 | 0.478 | 0.711 | 0.770 |
| Qwen3.5-35B-A3B | 0.823 | 0.822 | 0.708 | 0.561 | 0.527 | 0.585 | 0.640 | 0.352 | 0.616 | 0.665 |
| DeepSeek-V4-Flash-0731 | 0.869 | 0.827 | 0.750 | 0.621 | 0.606 | 0.653 | 0.695 | 0.399 | 0.653 | 0.706 |
| GLM-5.2 | 0.865 | 0.814 | 0.742 | 0.607 | 0.593 | 0.641 | 0.684 | 0.384 | 0.642 | 0.694 |
| Claude Sonnet 4.6 | 0.878 | 0.813 | 0.755 | 0.627 | 0.617 | 0.665 | 0.706 | 0.402 | 0.654 | 0.713 |
| Gemini 3.5 Flash | 0.886 | 0.813 | 0.759 | 0.640 | 0.634 | 0.664 | 0.690 | 0.409 | 0.653 | 0.698 |
| Qwen3.8-Max | 0.875 | 0.794 | 0.742 | 0.607 | 0.600 | 0.645 | 0.683 | 0.379 | 0.634 | 0.689 |
| Qwen3-8B | 0.866 | 0.651 | 0.666 | 0.507 | 0.506 | 0.559 | 0.606 | 0.280 | 0.522 | 0.608 |

## Ordinal severity metrics

| Model | MAE↓ | RMSE↓ | Macro L1↑ | Macro L2↑ | A↔C atom rate↓ | Over quadratic cost↓ | Under quadratic cost↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.169 | 0.478 | 0.858 | 0.871 | 0.030 | 0.053 | 0.115 |
| GPT-5.6-SOL | 0.116 | 0.405 | 0.851 | 0.859 | 0.024 | 0.033 | 0.127 |
| Qwen3.5-35B-A3B | 0.212 | 0.532 | 0.856 | 0.873 | 0.036 | 0.071 | 0.103 |
| DeepSeek-V4-Flash-0731 | 0.163 | 0.476 | 0.851 | 0.863 | 0.032 | 0.052 | 0.125 |
| GLM-5.2 | 0.167 | 0.482 | 0.839 | 0.851 | 0.033 | 0.051 | 0.144 |
| Claude Sonnet 4.6 | 0.152 | 0.461 | 0.836 | 0.847 | 0.030 | 0.046 | 0.144 |
| Gemini 3.5 Flash | 0.152 | 0.480 | 0.830 | 0.839 | 0.039 | 0.050 | 0.146 |
| Qwen3.8-Max | 0.160 | 0.479 | 0.814 | 0.824 | 0.035 | 0.048 | 0.169 |
| Qwen3-8B | 0.170 | 0.493 | 0.686 | 0.703 | 0.036 | 0.030 | 0.359 |

## Composite-score sensitivity

| Model | H | Arithmetic | Geometric | Product | Softmin −2 | Softmin −4 | Softmin −8 | MinCalib | Ideal L2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.869 | 0.873 | 0.871 | 0.759 | 0.867 | 0.864 | 0.856 | 0.814 | 0.860 |
| GPT-5.6-SOL | 0.868 | 0.876 | 0.872 | 0.761 | 0.863 | 0.855 | 0.841 | 0.789 | 0.848 |
| Qwen3.5-35B-A3B | 0.865 | 0.867 | 0.866 | 0.749 | 0.864 | 0.862 | 0.858 | 0.825 | 0.860 |
| DeepSeek-V4-Flash-0731 | 0.865 | 0.870 | 0.867 | 0.752 | 0.862 | 0.857 | 0.847 | 0.801 | 0.853 |
| GLM-5.2 | 0.854 | 0.861 | 0.857 | 0.735 | 0.850 | 0.843 | 0.831 | 0.782 | 0.840 |
| Claude Sonnet 4.6 | 0.851 | 0.860 | 0.856 | 0.732 | 0.847 | 0.839 | 0.825 | 0.773 | 0.835 |
| Gemini 3.5 Flash | 0.850 | 0.860 | 0.855 | 0.731 | 0.845 | 0.835 | 0.819 | 0.767 | 0.832 |
| Qwen3.8-Max | 0.833 | 0.846 | 0.840 | 0.705 | 0.828 | 0.816 | 0.798 | 0.744 | 0.815 |
| Qwen3-8B | 0.669 | 0.738 | 0.703 | 0.494 | 0.640 | 0.598 | 0.558 | 0.512 | 0.654 |

## Sample-level tail risk

| Model | Strict sample↑ | Any A↔C sample↓ | Mean L1 loss↓ | P90↓ | CVaR90↓ | CVaR95↓ | Quadratic CVaR90↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.204 | 0.377 | 0.097 | 0.219 | 0.276 | 0.316 | 0.212 |
| GPT-5.6-SOL | 0.290 | 0.327 | 0.068 | 0.167 | 0.228 | 0.270 | 0.178 |
| Qwen3.5-35B-A3B | 0.103 | 0.459 | 0.121 | 0.231 | 0.302 | 0.346 | 0.230 |
| DeepSeek-V4-Flash-0731 | 0.162 | 0.426 | 0.095 | 0.200 | 0.259 | 0.298 | 0.202 |
| GLM-5.2 | 0.187 | 0.429 | 0.095 | 0.214 | 0.277 | 0.318 | 0.217 |
| Claude Sonnet 4.6 | 0.187 | 0.403 | 0.087 | 0.200 | 0.253 | 0.290 | 0.200 |
| Gemini 3.5 Flash | 0.183 | 0.521 | 0.089 | 0.193 | 0.254 | 0.297 | 0.205 |
| Qwen3.8-Max | 0.183 | 0.449 | 0.093 | 0.200 | 0.264 | 0.305 | 0.211 |
| Qwen3-8B | 0.155 | 0.437 | 0.099 | 0.214 | 0.280 | 0.327 | 0.226 |

CVaR90 is the mean loss among the worst 10% of samples; CVaR95 uses the worst 5%. Sample loss is normalized absolute ordinal distance.

### Why CVaR90 can reorder models

| Model | H rank | Mean L1 rank | CVaR90 rank | CVaR90↓ |
| --- | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 1 | 7 | 6 | 0.276 |
| GPT-5.6-SOL | 2 | 1 | 1 | 0.228 |
| Qwen3.5-35B-A3B | 3 | 9 | 9 | 0.302 |
| DeepSeek-V4-Flash-0731 | 4 | 5 | 4 | 0.259 |
| GLM-5.2 | 5 | 6 | 7 | 0.277 |
| Claude Sonnet 4.6 | 6 | 2 | 2 | 0.253 |
| Gemini 3.5 Flash | 7 | 3 | 3 | 0.254 |
| Qwen3.8-Max | 8 | 4 | 5 | 0.264 |
| Qwen3-8B | 9 | 8 | 8 | 0.280 |

For a full-memory sample `s` with `n_s` scorable atoms, `L_s = mean_i(|u_hat_si - u*_si| / 2)`. CVaR90 is the arithmetic mean of the largest 150 values of `L_s` among the locked 1500 samples. It therefore changes both the aggregation unit (sample rather than gold-label macro average) and the evaluated population (only the worst decile).

A model can make moderately sized errors across many samples and have worse H or mean loss but a less extreme worst decile. Conversely, errors concentrated within a smaller set of samples increase CVaR90. The ordering difference is expected and is not an arithmetic inconsistency.

[Open the tail, Pareto, and metric-rank diagnostics](candidate-metric-diagnostics.html).

## Paired memory utility

| Model | Induced OPB↓ | Reduced UPB↑ | PMU(0.5)↑ | PMU(1)↑ | PMU(2)↑ | Relative PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | NA | NA | NA | NA | NA | NA |
| GPT-5.6-SOL | NA | NA | NA | NA | NA | NA |
| Qwen3.5-35B-A3B | NA | NA | NA | NA | NA | NA |
| DeepSeek-V4-Flash-0731 | NA | NA | NA | NA | NA | NA |
| GLM-5.2 | NA | NA | NA | NA | NA | NA |
| Claude Sonnet 4.6 | NA | NA | NA | NA | NA | NA |
| Gemini 3.5 Flash | NA | NA | NA | NA | NA | NA |
| Qwen3.8-Max | NA | NA | NA | NA | NA | NA |
| Qwen3-8B | NA | NA | NA | NA | NA | NA |

Not computable in this Full-memory-only run because no matched No-memory responses were generated.

## Latent and pairwise models

| Model | Rasch over θ↑ | Rasch under θ↑ | Mean θ↑ | Min θ↑ | Bradley–Terry ability↑ |
| --- | ---: | ---: | ---: | ---: | ---: |
| GPT-5.6-SOL | 0.917 | 0.335 | 0.626 | 0.335 | 0.540 |
| Claude Sonnet 4.6 | 0.127 | 0.162 | 0.144 | 0.127 | 0.128 |
| Gemini 3.5 Flash | 0.390 | 0.077 | 0.234 | 0.077 | 0.075 |
| Qwen3.8-Max | 0.159 | -0.173 | -0.007 | -0.173 | -0.005 |
| GLM-5.2 | -0.253 | 0.274 | 0.010 | -0.253 | -0.028 |
| DeepSeek-V4-Flash-0731 | -0.238 | 0.495 | 0.128 | -0.238 | -0.039 |
| Kimi-K2.6 | -0.526 | 0.671 | 0.072 | -0.526 | -0.042 |
| Qwen3-8B | 0.976 | -2.654 | -0.839 | -2.654 | -0.090 |
| Qwen3.5-35B-A3B | -1.551 | 0.814 | -0.369 | -1.551 | -0.539 |

The two Rasch dimensions adjust separately for atom difficulty. The current 1PL fit is exploratory: standard errors condition on estimated item difficulties and are not a full Bayesian uncertainty estimate.

## Pairwise win-share matrix

Rows are the candidate model; each cell is its win share against the column model using full-memory normalized sample-level ordinal loss. Ties count 0.5.

| Model | Kimi-K2.6 | GPT-5.6-SOL | Qwen3.5-35B-A3B | DeepSeek-V4-Flash-0731 | GLM-5.2 | Claude Sonnet 4.6 | Gemini 3.5 Flash | Qwen3.8-Max | Qwen3-8B |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | — | 0.360 | 0.619 | 0.497 | 0.496 | 0.454 | 0.469 | 0.495 | 0.516 |
| GPT-5.6-SOL | 0.640 | — | 0.740 | 0.649 | 0.646 | 0.602 | 0.617 | 0.632 | 0.642 |
| Qwen3.5-35B-A3B | 0.381 | 0.260 | — | 0.364 | 0.380 | 0.332 | 0.359 | 0.358 | 0.400 |
| DeepSeek-V4-Flash-0731 | 0.503 | 0.351 | 0.636 | — | 0.492 | 0.457 | 0.473 | 0.492 | 0.512 |
| GLM-5.2 | 0.504 | 0.354 | 0.620 | 0.508 | — | 0.462 | 0.474 | 0.497 | 0.519 |
| Claude Sonnet 4.6 | 0.546 | 0.398 | 0.668 | 0.543 | 0.538 | — | 0.507 | 0.536 | 0.548 |
| Gemini 3.5 Flash | 0.531 | 0.383 | 0.641 | 0.527 | 0.526 | 0.493 | — | 0.522 | 0.542 |
| Qwen3.8-Max | 0.505 | 0.368 | 0.642 | 0.508 | 0.503 | 0.464 | 0.478 | — | 0.521 |
| Qwen3-8B | 0.484 | 0.358 | 0.600 | 0.488 | 0.481 | 0.452 | 0.458 | 0.479 | — |

## Pareto analysis

Non-dominated OPB–UPB models: DeepSeek-V4-Flash-0731, GPT-5.6-SOL, Kimi-K2.6, Qwen3-8B, Qwen3.5-35B-A3B.

## Observed metric spread

| Metric | Minimum | Maximum | Range | Population SD |
| --- | ---: | ---: | ---: | ---: |
| MinCalib | 0.512 | 0.825 | 0.313 | 0.089 |
| product_resistance | 0.494 | 0.761 | 0.266 | 0.079 |
| H | 0.669 | 0.869 | 0.200 | 0.060 |
| MCC | 0.507 | 0.694 | 0.188 | 0.049 |
| strict_sample_accuracy | 0.103 | 0.290 | 0.187 | 0.047 |
| balanced_accuracy | 0.651 | 0.835 | 0.184 | 0.054 |
| linear_kappa | 0.559 | 0.732 | 0.173 | 0.046 |
| quadratic_kappa | 0.606 | 0.767 | 0.161 | 0.042 |
| macro_F1 | 0.666 | 0.799 | 0.133 | 0.035 |
| CVaR90_linear_loss | 0.228 | 0.302 | 0.074 | 0.020 |

## Sample-cluster bootstrap uncertainty

| Model | H 95% CI | MinCalib 95% CI | MCC 95% CI | Linear κ 95% CI | Strict sample 95% CI | CVaR90 95% CI | PMU(1) 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | [0.861, 0.877] | [0.800, 0.828] | [0.598, 0.625] | [0.632, 0.658] | [0.184, 0.224] | [0.264, 0.290] | NA |
| GPT-5.6-SOL | [0.858, 0.877] | [0.773, 0.804] | [0.681, 0.708] | [0.720, 0.744] | [0.267, 0.313] | [0.215, 0.243] | NA |
| Qwen3.5-35B-A3B | [0.857, 0.873] | [0.810, 0.840] | [0.550, 0.573] | [0.573, 0.597] | [0.087, 0.119] | [0.286, 0.318] | NA |
| DeepSeek-V4-Flash-0731 | [0.855, 0.874] | [0.785, 0.816] | [0.608, 0.633] | [0.640, 0.665] | [0.143, 0.181] | [0.247, 0.271] | NA |
| GLM-5.2 | [0.844, 0.863] | [0.767, 0.798] | [0.594, 0.621] | [0.628, 0.654] | [0.167, 0.207] | [0.263, 0.291] | NA |
| Claude Sonnet 4.6 | [0.841, 0.860] | [0.756, 0.789] | [0.613, 0.640] | [0.652, 0.677] | [0.168, 0.208] | [0.240, 0.265] | NA |
| Gemini 3.5 Flash | [0.839, 0.860] | [0.749, 0.783] | [0.626, 0.653] | [0.652, 0.677] | [0.163, 0.204] | [0.241, 0.267] | NA |
| Qwen3.8-Max | [0.823, 0.844] | [0.728, 0.761] | [0.593, 0.620] | [0.631, 0.657] | [0.163, 0.202] | [0.251, 0.277] | NA |
| Qwen3-8B | [0.651, 0.687] | [0.491, 0.534] | [0.489, 0.523] | [0.541, 0.576] | [0.137, 0.173] | [0.265, 0.295] | NA |

All intervals resample the same 1500 sample IDs as clusters. This run contains only Full-memory judgments.

## Interpretation boundary

- MCC, Kappa, NMI, and ordinal correlation discard the over-use versus under-use direction even when they improve numerical separation.
- Product and power-mean scores partly enlarge the numeric range through rescaling; this does not create new statistical evidence.
- PMU depends on the full/no-memory causal contrast and on λ.
- CVaR exposes tail failures but should not replace average performance.
- Brier score, log loss, and ordinal CRPS are not validly computable without a probability distribution over A/B/C.
- Pairwise bootstrap intervals and blinded human validation remain necessary before making significance or external leaderboard claims.
