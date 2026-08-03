# MemCalib v2.4.1 Non-Think DeepSeek-V4-Pro Judge repeat 3

Locked 494-record, nine-model, paired full-memory/no-memory evaluation; independent answer repeat 3 of 3; all primary judgments by DeepSeek-V4-Pro using the broad Bailian credential.

## Headline comparison

| Model | OPB↓ | UPB↓ | H↑ | MinCalib↑ | MCC↑ | Linear κ↑ | CVaR90↓ | PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.062 | 0.174 | 0.878 | 0.826 | 0.633 | 0.666 | 0.252 | 0.631 |
| DeepSeek-V4-Pro | 0.067 | 0.170 | 0.878 | 0.830 | 0.615 | 0.640 | 0.258 | 0.629 |
| Qwen3.5-35B-A3B | 0.086 | 0.165 | 0.873 | 0.835 | 0.571 | 0.591 | 0.281 | 0.600 |
| Qwen3.6-Flash | 0.088 | 0.172 | 0.868 | 0.828 | 0.570 | 0.590 | 0.291 | 0.585 |
| GLM-5.2 | 0.058 | 0.211 | 0.859 | 0.789 | 0.616 | 0.652 | 0.251 | 0.579 |
| Codex GPT-5.6 Sol | 0.027 | 0.274 | 0.831 | 0.726 | 0.687 | 0.733 | 0.211 | 0.557 |
| DeepSeek-V4-Flash | 0.055 | 0.263 | 0.828 | 0.737 | 0.592 | 0.637 | 0.252 | 0.548 |
| Qwen3.7-Max | 0.054 | 0.272 | 0.823 | 0.728 | 0.592 | 0.636 | 0.248 | 0.516 |
| Qwen3-8B | 0.031 | 0.484 | 0.674 | 0.516 | 0.519 | 0.567 | 0.291 | 0.403 |

Numeric ranges across differently scaled metrics are not directly comparable. Use paired confidence intervals and ranking robustness, not range alone.

## Classification and chance-corrected metrics

| Model | Exact↑ | Balanced acc.↑ | Macro F1↑ | MCC↑ | κ↑ | Linear κ↑ | Quadratic κ↑ | NMI↑ | Cramér V↑ | Ordinal r↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.873 | 0.843 | 0.760 | 0.633 | 0.614 | 0.666 | 0.713 | 0.417 | 0.672 | 0.724 |
| DeepSeek-V4-Pro | 0.863 | 0.842 | 0.746 | 0.615 | 0.593 | 0.640 | 0.684 | 0.398 | 0.653 | 0.699 |
| Qwen3.5-35B-A3B | 0.832 | 0.832 | 0.714 | 0.571 | 0.536 | 0.591 | 0.642 | 0.360 | 0.622 | 0.667 |
| Qwen3.6-Flash | 0.833 | 0.827 | 0.712 | 0.570 | 0.537 | 0.590 | 0.641 | 0.355 | 0.617 | 0.664 |
| GLM-5.2 | 0.873 | 0.820 | 0.750 | 0.616 | 0.602 | 0.652 | 0.698 | 0.395 | 0.654 | 0.706 |
| Codex GPT-5.6 Sol | 0.914 | 0.799 | 0.793 | 0.687 | 0.687 | 0.733 | 0.773 | 0.469 | 0.702 | 0.773 |
| DeepSeek-V4-Flash | 0.871 | 0.788 | 0.733 | 0.592 | 0.583 | 0.637 | 0.685 | 0.370 | 0.626 | 0.692 |
| Qwen3.7-Max | 0.872 | 0.783 | 0.732 | 0.592 | 0.584 | 0.636 | 0.683 | 0.365 | 0.623 | 0.688 |
| Qwen3-8B | 0.873 | 0.657 | 0.671 | 0.519 | 0.518 | 0.567 | 0.610 | 0.292 | 0.529 | 0.613 |

## Ordinal severity metrics

| Model | MAE↓ | RMSE↓ | Macro L1↑ | Macro L2↑ | A↔C atom rate↓ | Over quadratic cost↓ | Under quadratic cost↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.152 | 0.450 | 0.869 | 0.882 | 0.025 | 0.046 | 0.116 |
| DeepSeek-V4-Pro | 0.169 | 0.482 | 0.866 | 0.878 | 0.032 | 0.055 | 0.110 |
| Qwen3.5-35B-A3B | 0.203 | 0.522 | 0.866 | 0.882 | 0.035 | 0.068 | 0.101 |
| Qwen3.6-Flash | 0.202 | 0.522 | 0.860 | 0.877 | 0.035 | 0.067 | 0.108 |
| GLM-5.2 | 0.156 | 0.461 | 0.844 | 0.856 | 0.028 | 0.046 | 0.142 |
| Codex GPT-5.6 Sol | 0.106 | 0.381 | 0.816 | 0.825 | 0.020 | 0.023 | 0.176 |
| DeepSeek-V4-Flash | 0.159 | 0.468 | 0.814 | 0.827 | 0.030 | 0.046 | 0.163 |
| Qwen3.7-Max | 0.158 | 0.468 | 0.808 | 0.821 | 0.030 | 0.044 | 0.176 |
| Qwen3-8B | 0.161 | 0.479 | 0.694 | 0.712 | 0.034 | 0.028 | 0.356 |

## Composite-score sensitivity

| Model | H | Arithmetic | Geometric | Product | Softmin −2 | Softmin −4 | Softmin −8 | MinCalib | Ideal L2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.878 | 0.882 | 0.880 | 0.775 | 0.877 | 0.873 | 0.866 | 0.826 | 0.869 |
| DeepSeek-V4-Pro | 0.878 | 0.881 | 0.880 | 0.774 | 0.877 | 0.874 | 0.868 | 0.830 | 0.871 |
| Qwen3.5-35B-A3B | 0.873 | 0.874 | 0.873 | 0.763 | 0.872 | 0.870 | 0.867 | 0.835 | 0.868 |
| Qwen3.6-Flash | 0.868 | 0.870 | 0.869 | 0.756 | 0.867 | 0.865 | 0.861 | 0.828 | 0.864 |
| GLM-5.2 | 0.859 | 0.865 | 0.862 | 0.743 | 0.855 | 0.849 | 0.837 | 0.789 | 0.845 |
| Codex GPT-5.6 Sol | 0.831 | 0.849 | 0.840 | 0.706 | 0.823 | 0.807 | 0.783 | 0.726 | 0.805 |
| DeepSeek-V4-Flash | 0.828 | 0.841 | 0.835 | 0.697 | 0.822 | 0.810 | 0.791 | 0.737 | 0.810 |
| Qwen3.7-Max | 0.823 | 0.837 | 0.830 | 0.689 | 0.816 | 0.803 | 0.783 | 0.728 | 0.804 |
| Qwen3-8B | 0.674 | 0.743 | 0.707 | 0.500 | 0.644 | 0.602 | 0.563 | 0.516 | 0.657 |

## Sample-level tail risk

| Model | Strict sample↑ | Any A↔C sample↓ | Mean L1 loss↓ | P90↓ | CVaR90↓ | CVaR95↓ | Quadratic CVaR90↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.231 | 0.344 | 0.086 | 0.195 | 0.252 | 0.290 | 0.192 |
| DeepSeek-V4-Pro | 0.168 | 0.435 | 0.096 | 0.204 | 0.258 | 0.295 | 0.194 |
| Qwen3.5-35B-A3B | 0.123 | 0.439 | 0.114 | 0.227 | 0.281 | 0.319 | 0.217 |
| Qwen3.6-Flash | 0.130 | 0.460 | 0.114 | 0.227 | 0.291 | 0.335 | 0.226 |
| GLM-5.2 | 0.206 | 0.389 | 0.087 | 0.200 | 0.251 | 0.285 | 0.190 |
| Codex GPT-5.6 Sol | 0.289 | 0.271 | 0.063 | 0.158 | 0.211 | 0.252 | 0.171 |
| DeepSeek-V4-Flash | 0.164 | 0.397 | 0.093 | 0.194 | 0.252 | 0.294 | 0.202 |
| Qwen3.7-Max | 0.168 | 0.399 | 0.091 | 0.200 | 0.248 | 0.283 | 0.196 |
| Qwen3-8B | 0.156 | 0.433 | 0.096 | 0.214 | 0.291 | 0.350 | 0.235 |

CVaR90 is the mean loss among the worst 10% of samples; CVaR95 uses the worst 5%. Sample loss is normalized absolute ordinal distance.

### Why CVaR90 can reorder models

| Model | H rank | Mean L1 rank | CVaR90 rank | CVaR90↓ |
| --- | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 1 | 2 | 5 | 0.252 |
| DeepSeek-V4-Pro | 2 | 7 | 6 | 0.258 |
| Qwen3.5-35B-A3B | 3 | 9 | 7 | 0.281 |
| Qwen3.6-Flash | 4 | 8 | 8 | 0.291 |
| GLM-5.2 | 5 | 3 | 3 | 0.251 |
| Codex GPT-5.6 Sol | 6 | 1 | 1 | 0.211 |
| DeepSeek-V4-Flash | 7 | 5 | 4 | 0.252 |
| Qwen3.7-Max | 8 | 4 | 2 | 0.248 |
| Qwen3-8B | 9 | 6 | 9 | 0.291 |

For a full-memory sample `s` with `n_s` scorable atoms, `L_s = mean_i(|u_hat_si - u*_si| / 2)`. CVaR90 is the arithmetic mean of the largest 50 values of `L_s` among the locked 494 samples. It therefore changes both the aggregation unit (sample rather than gold-label macro average) and the evaluated population (only the worst decile).

A model can make moderately sized errors across many samples and have worse H or mean loss but a less extreme worst decile. Conversely, errors concentrated within a smaller set of samples increase CVaR90. The ordering difference is expected and is not an arithmetic inconsistency.

[Open the tail, Pareto, and metric-rank diagnostics](candidate-metric-diagnostics.html).

## Paired memory utility

| Model | Induced OPB↓ | Reduced UPB↑ | PMU(0.5)↑ | PMU(1)↑ | PMU(2)↑ | Relative PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.059 | 0.690 | 0.661 | 0.631 | 0.572 | 0.739 |
| DeepSeek-V4-Pro | 0.063 | 0.692 | 0.660 | 0.629 | 0.566 | 0.740 |
| Qwen3.5-35B-A3B | 0.083 | 0.683 | 0.641 | 0.600 | 0.516 | 0.722 |
| Qwen3.6-Flash | 0.085 | 0.670 | 0.628 | 0.585 | 0.500 | 0.711 |
| GLM-5.2 | 0.056 | 0.635 | 0.607 | 0.579 | 0.522 | 0.694 |
| Codex GPT-5.6 Sol | 0.026 | 0.583 | 0.570 | 0.557 | 0.532 | 0.655 |
| DeepSeek-V4-Flash | 0.053 | 0.600 | 0.574 | 0.548 | 0.495 | 0.643 |
| Qwen3.7-Max | 0.051 | 0.566 | 0.541 | 0.516 | 0.465 | 0.625 |
| Qwen3-8B | 0.030 | 0.433 | 0.418 | 0.403 | 0.373 | 0.443 |

`PMU(λ) = reduced_UPB - λ × induced_OPB`. Its ranking is a policy choice, so the weight sensitivity must remain visible.

## Latent and pairwise models

| Model | Rasch over θ↑ | Rasch under θ↑ | Mean θ↑ | Min θ↑ | Bradley–Terry ability↑ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 1.310 | -0.416 | 0.447 | -0.416 | 0.645 |
| Kimi-K2.6 | -0.124 | 0.793 | 0.334 | -0.124 | 0.139 |
| GLM-5.2 | 0.012 | 0.308 | 0.160 | 0.012 | 0.089 |
| DeepSeek-V4-Flash | 0.172 | -0.292 | -0.060 | -0.292 | 0.018 |
| Qwen3.7-Max | 0.254 | -0.381 | -0.064 | -0.381 | 0.014 |
| Qwen3-8B | 1.210 | -2.596 | -0.693 | -2.596 | -0.016 |
| DeepSeek-V4-Pro | -0.401 | 0.839 | 0.219 | -0.401 | -0.067 |
| Qwen3.5-35B-A3B | -1.252 | 0.919 | -0.166 | -1.252 | -0.410 |
| Qwen3.6-Flash | -1.181 | 0.827 | -0.177 | -1.181 | -0.411 |

The two Rasch dimensions adjust separately for atom difficulty. The current 1PL fit is exploratory: standard errors condition on estimated item difficulties and are not a full Bayesian uncertainty estimate.

## Pairwise win-share matrix

Rows are the candidate model; each cell is its win share against the column model using full-memory normalized sample-level ordinal loss. Ties count 0.5.

| Model | Kimi-K2.6 | DeepSeek-V4-Pro | Qwen3.5-35B-A3B | Qwen3.6-Flash | GLM-5.2 | Codex GPT-5.6 Sol | DeepSeek-V4-Flash | Qwen3.7-Max | Qwen3-8B |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | — | 0.553 | 0.648 | 0.627 | 0.520 | 0.381 | 0.529 | 0.531 | 0.520 |
| DeepSeek-V4-Pro | 0.447 | — | 0.577 | 0.590 | 0.469 | 0.330 | 0.480 | 0.471 | 0.491 |
| Qwen3.5-35B-A3B | 0.352 | 0.423 | — | 0.495 | 0.361 | 0.276 | 0.398 | 0.387 | 0.418 |
| Qwen3.6-Flash | 0.373 | 0.410 | 0.505 | — | 0.371 | 0.259 | 0.386 | 0.390 | 0.415 |
| GLM-5.2 | 0.480 | 0.531 | 0.639 | 0.629 | — | 0.372 | 0.521 | 0.511 | 0.515 |
| Codex GPT-5.6 Sol | 0.619 | 0.670 | 0.724 | 0.741 | 0.628 | — | 0.661 | 0.677 | 0.658 |
| DeepSeek-V4-Flash | 0.471 | 0.520 | 0.602 | 0.614 | 0.479 | 0.339 | — | 0.508 | 0.508 |
| Qwen3.7-Max | 0.469 | 0.529 | 0.613 | 0.610 | 0.489 | 0.323 | 0.492 | — | 0.507 |
| Qwen3-8B | 0.480 | 0.509 | 0.582 | 0.585 | 0.485 | 0.342 | 0.492 | 0.493 | — |

## Pareto analysis

Non-dominated OPB–UPB models: Codex GPT-5.6 Sol, DeepSeek-V4-Pro, DeepSeek-V4-Flash, GLM-5.2, Kimi-K2.6, Qwen3.7-Max, Qwen3.5-35B-A3B.

## Observed metric spread

| Metric | Minimum | Maximum | Range | Population SD |
| --- | ---: | ---: | ---: | ---: |
| MinCalib | 0.516 | 0.835 | 0.319 | 0.096 |
| product_resistance | 0.500 | 0.775 | 0.274 | 0.081 |
| PMU_lambda_1 | 0.403 | 0.631 | 0.228 | 0.066 |
| H | 0.674 | 0.878 | 0.205 | 0.061 |
| balanced_accuracy | 0.657 | 0.843 | 0.186 | 0.054 |
| MCC | 0.519 | 0.687 | 0.168 | 0.044 |
| linear_kappa | 0.567 | 0.733 | 0.166 | 0.047 |
| strict_sample_accuracy | 0.123 | 0.289 | 0.166 | 0.050 |
| quadratic_kappa | 0.610 | 0.773 | 0.163 | 0.045 |
| macro_F1 | 0.671 | 0.793 | 0.122 | 0.032 |
| CVaR90_linear_loss | 0.211 | 0.291 | 0.080 | 0.024 |

## Sample-cluster bootstrap uncertainty

| Model | H 95% CI | MinCalib 95% CI | MCC 95% CI | Linear κ 95% CI | Strict sample 95% CI | CVaR90 95% CI | PMU(1) 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | [0.863, 0.892] | [0.798, 0.851] | [0.611, 0.657] | [0.643, 0.688] | [0.194, 0.269] | [0.231, 0.273] | [0.597, 0.664] |
| DeepSeek-V4-Pro | [0.865, 0.892] | [0.805, 0.854] | [0.593, 0.638] | [0.618, 0.662] | [0.136, 0.200] | [0.238, 0.280] | [0.596, 0.660] |
| Qwen3.5-35B-A3B | [0.859, 0.886] | [0.810, 0.861] | [0.551, 0.593] | [0.569, 0.613] | [0.095, 0.154] | [0.261, 0.303] | [0.567, 0.631] |
| Qwen3.6-Flash | [0.854, 0.882] | [0.803, 0.854] | [0.551, 0.593] | [0.571, 0.612] | [0.101, 0.160] | [0.267, 0.317] | [0.552, 0.620] |
| GLM-5.2 | [0.842, 0.875] | [0.760, 0.817] | [0.591, 0.640] | [0.629, 0.674] | [0.170, 0.243] | [0.233, 0.270] | [0.543, 0.612] |
| Codex GPT-5.6 Sol | [0.811, 0.849] | [0.696, 0.754] | [0.663, 0.710] | [0.711, 0.755] | [0.251, 0.332] | [0.190, 0.232] | [0.523, 0.590] |
| DeepSeek-V4-Flash | [0.810, 0.846] | [0.709, 0.766] | [0.566, 0.616] | [0.613, 0.660] | [0.132, 0.196] | [0.228, 0.276] | [0.515, 0.579] |
| Qwen3.7-Max | [0.804, 0.842] | [0.700, 0.759] | [0.566, 0.617] | [0.612, 0.660] | [0.136, 0.198] | [0.228, 0.269] | [0.481, 0.551] |
| Qwen3-8B | [0.643, 0.702] | [0.480, 0.552] | [0.491, 0.549] | [0.536, 0.597] | [0.123, 0.188] | [0.261, 0.322] | [0.368, 0.438] |

All intervals resample the same 494 sample IDs as clusters. Full/no-memory atom groups are preserved.

## Interpretation boundary

- MCC, Kappa, NMI, and ordinal correlation discard the over-use versus under-use direction even when they improve numerical separation.
- Product and power-mean scores partly enlarge the numeric range through rescaling; this does not create new statistical evidence.
- PMU depends on the full/no-memory causal contrast and on λ.
- CVaR exposes tail failures but should not replace average performance.
- Brier score, log loss, and ordinal CRPS are not validly computable without a probability distribution over A/B/C.
- Pairwise bootstrap intervals and blinded human validation remain necessary before making significance or external leaderboard claims.
