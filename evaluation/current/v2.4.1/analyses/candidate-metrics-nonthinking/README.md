# MemCalib v2.4.1 non-thinking nine-model candidate metric study

Primary evaluation on the corrected v2.4.1 release using the exact locked 494 IDs, non-thinking Bailian answers, the unified careful-assistant system prompt, and Codex reasoning none.

## Headline comparison

| Model | OPB↓ | UPB↓ | H↑ | MinCalib↑ | MCC↑ | Linear κ↑ | CVaR90↓ | PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.088 | 0.254 | 0.821 | 0.746 | 0.564 | 0.593 | 0.302 | 0.569 |
| DeepSeek-V4-Pro | 0.096 | 0.253 | 0.818 | 0.747 | 0.540 | 0.555 | 0.323 | 0.548 |
| DeepSeek-V4-Flash | 0.090 | 0.262 | 0.815 | 0.738 | 0.547 | 0.566 | 0.317 | 0.542 |
| Qwen3.6-Flash | 0.108 | 0.251 | 0.814 | 0.749 | 0.515 | 0.528 | 0.348 | 0.549 |
| Qwen3.5-35B-A3B | 0.111 | 0.250 | 0.814 | 0.750 | 0.513 | 0.523 | 0.344 | 0.548 |
| GLM-5.2 | 0.081 | 0.285 | 0.804 | 0.715 | 0.550 | 0.580 | 0.301 | 0.529 |
| Codex GPT-5.6 Sol | 0.041 | 0.348 | 0.776 | 0.652 | 0.613 | 0.668 | 0.244 | 0.513 |
| Qwen3.7-Max | 0.073 | 0.337 | 0.773 | 0.663 | 0.533 | 0.571 | 0.291 | 0.481 |
| Qwen3-8B | 0.043 | 0.496 | 0.661 | 0.504 | 0.484 | 0.520 | 0.302 | 0.398 |

Numeric ranges across differently scaled metrics are not directly comparable. Use paired confidence intervals and ranking robustness, not range alone.

## Classification and chance-corrected metrics

| Model | Exact↑ | Balanced acc.↑ | Macro F1↑ | MCC↑ | κ↑ | Linear κ↑ | Quadratic κ↑ | NMI↑ | Cramér V↑ | Ordinal r↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.854 | 0.772 | 0.698 | 0.564 | 0.550 | 0.593 | 0.630 | 0.321 | 0.570 | 0.643 |
| DeepSeek-V4-Pro | 0.838 | 0.767 | 0.676 | 0.540 | 0.520 | 0.555 | 0.585 | 0.296 | 0.542 | 0.605 |
| DeepSeek-V4-Flash | 0.844 | 0.765 | 0.680 | 0.547 | 0.530 | 0.566 | 0.597 | 0.306 | 0.547 | 0.615 |
| Qwen3.6-Flash | 0.820 | 0.760 | 0.657 | 0.515 | 0.490 | 0.528 | 0.561 | 0.276 | 0.521 | 0.586 |
| Qwen3.5-35B-A3B | 0.816 | 0.760 | 0.653 | 0.513 | 0.485 | 0.523 | 0.557 | 0.274 | 0.517 | 0.583 |
| GLM-5.2 | 0.853 | 0.756 | 0.690 | 0.550 | 0.538 | 0.580 | 0.617 | 0.307 | 0.556 | 0.628 |
| Codex GPT-5.6 Sol | 0.894 | 0.741 | 0.735 | 0.613 | 0.613 | 0.668 | 0.715 | 0.382 | 0.620 | 0.715 |
| Qwen3.7-Max | 0.855 | 0.727 | 0.678 | 0.533 | 0.526 | 0.571 | 0.609 | 0.293 | 0.537 | 0.616 |
| Qwen3-8B | 0.862 | 0.641 | 0.644 | 0.484 | 0.484 | 0.520 | 0.551 | 0.250 | 0.480 | 0.551 |

## Ordinal severity metrics

| Model | MAE↓ | RMSE↓ | Macro L1↑ | Macro L2↑ | A↔C atom rate↓ | Over quadratic cost↓ | Under quadratic cost↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.188 | 0.522 | 0.803 | 0.819 | 0.042 | 0.061 | 0.166 |
| DeepSeek-V4-Pro | 0.215 | 0.567 | 0.802 | 0.820 | 0.053 | 0.076 | 0.160 |
| DeepSeek-V4-Flash | 0.207 | 0.557 | 0.802 | 0.820 | 0.051 | 0.073 | 0.154 |
| Qwen3.6-Flash | 0.236 | 0.590 | 0.801 | 0.821 | 0.056 | 0.084 | 0.156 |
| Qwen3.5-35B-A3B | 0.240 | 0.594 | 0.803 | 0.825 | 0.056 | 0.085 | 0.151 |
| GLM-5.2 | 0.192 | 0.530 | 0.788 | 0.804 | 0.044 | 0.061 | 0.186 |
| Codex GPT-5.6 Sol | 0.132 | 0.427 | 0.769 | 0.783 | 0.025 | 0.029 | 0.220 |
| Qwen3.7-Max | 0.190 | 0.529 | 0.759 | 0.776 | 0.045 | 0.058 | 0.215 |
| Qwen3-8B | 0.186 | 0.531 | 0.675 | 0.692 | 0.048 | 0.042 | 0.370 |

## Composite-score sensitivity

| Model | H | Arithmetic | Geometric | Product | Softmin −2 | Softmin −4 | Softmin −8 | MinCalib | Ideal L2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.821 | 0.829 | 0.825 | 0.680 | 0.816 | 0.809 | 0.795 | 0.746 | 0.810 |
| DeepSeek-V4-Pro | 0.818 | 0.825 | 0.822 | 0.675 | 0.814 | 0.807 | 0.795 | 0.747 | 0.809 |
| DeepSeek-V4-Flash | 0.815 | 0.824 | 0.820 | 0.672 | 0.811 | 0.802 | 0.788 | 0.738 | 0.804 |
| Qwen3.6-Flash | 0.814 | 0.820 | 0.817 | 0.668 | 0.811 | 0.805 | 0.794 | 0.749 | 0.807 |
| Qwen3.5-35B-A3B | 0.814 | 0.820 | 0.817 | 0.667 | 0.811 | 0.805 | 0.795 | 0.750 | 0.807 |
| GLM-5.2 | 0.804 | 0.817 | 0.811 | 0.657 | 0.798 | 0.787 | 0.768 | 0.715 | 0.791 |
| Codex GPT-5.6 Sol | 0.776 | 0.806 | 0.791 | 0.625 | 0.763 | 0.739 | 0.707 | 0.652 | 0.752 |
| Qwen3.7-Max | 0.773 | 0.795 | 0.784 | 0.615 | 0.763 | 0.744 | 0.717 | 0.663 | 0.756 |
| Qwen3-8B | 0.661 | 0.731 | 0.695 | 0.483 | 0.631 | 0.589 | 0.550 | 0.504 | 0.648 |

## Sample-level tail risk

| Model | Strict sample↑ | Any A↔C sample↓ | Mean L1 loss↓ | P90↓ | CVaR90↓ | CVaR95↓ | Quadratic CVaR90↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.146 | 0.480 | 0.108 | 0.224 | 0.302 | 0.356 | 0.250 |
| DeepSeek-V4-Pro | 0.105 | 0.607 | 0.124 | 0.250 | 0.323 | 0.374 | 0.273 |
| DeepSeek-V4-Flash | 0.105 | 0.585 | 0.120 | 0.246 | 0.317 | 0.368 | 0.269 |
| Qwen3.6-Flash | 0.081 | 0.613 | 0.135 | 0.278 | 0.348 | 0.404 | 0.292 |
| Qwen3.5-35B-A3B | 0.087 | 0.605 | 0.136 | 0.278 | 0.344 | 0.391 | 0.288 |
| GLM-5.2 | 0.150 | 0.522 | 0.108 | 0.233 | 0.301 | 0.342 | 0.250 |
| Codex GPT-5.6 Sol | 0.215 | 0.342 | 0.077 | 0.167 | 0.244 | 0.302 | 0.191 |
| Qwen3.7-Max | 0.105 | 0.551 | 0.111 | 0.230 | 0.291 | 0.327 | 0.245 |
| Qwen3-8B | 0.103 | 0.540 | 0.109 | 0.222 | 0.302 | 0.355 | 0.257 |

CVaR90 is the mean loss among the worst 10% of samples; CVaR95 uses the worst 5%. Sample loss is normalized absolute ordinal distance.

### Why CVaR90 can reorder models

| Model | H rank | Mean L1 rank | CVaR90 rank | CVaR90↓ |
| --- | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 1 | 3 | 4 | 0.302 |
| DeepSeek-V4-Pro | 2 | 7 | 7 | 0.323 |
| DeepSeek-V4-Flash | 3 | 6 | 6 | 0.317 |
| Qwen3.6-Flash | 4 | 8 | 9 | 0.348 |
| Qwen3.5-35B-A3B | 5 | 9 | 8 | 0.344 |
| GLM-5.2 | 6 | 2 | 3 | 0.301 |
| Codex GPT-5.6 Sol | 7 | 1 | 1 | 0.244 |
| Qwen3.7-Max | 8 | 5 | 2 | 0.291 |
| Qwen3-8B | 9 | 4 | 5 | 0.302 |

For a full-memory sample `s` with `n_s` scorable atoms, `L_s = mean_i(|u_hat_si - u*_si| / 2)`. CVaR90 is the arithmetic mean of the largest 50 values of `L_s` among the locked 494 samples. It therefore changes both the aggregation unit (sample rather than gold-label macro average) and the evaluated population (only the worst decile).

A model can make moderately sized errors across many samples and have worse H or mean loss but a less extreme worst decile. Conversely, errors concentrated within a smaller set of samples increase CVaR90. The ordering difference is expected and is not an arithmetic inconsistency.

[Open the tail, Pareto, and metric-rank diagnostics](candidate-metric-diagnostics.html).

## Paired memory utility

| Model | Induced OPB↓ | Reduced UPB↑ | PMU(0.5)↑ | PMU(1)↑ | PMU(2)↑ | Relative PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | 0.082 | 0.651 | 0.610 | 0.569 | 0.488 | 0.637 |
| DeepSeek-V4-Pro | 0.093 | 0.641 | 0.594 | 0.548 | 0.455 | 0.624 |
| DeepSeek-V4-Flash | 0.085 | 0.627 | 0.584 | 0.542 | 0.458 | 0.621 |
| Qwen3.6-Flash | 0.105 | 0.654 | 0.602 | 0.549 | 0.444 | 0.617 |
| Qwen3.5-35B-A3B | 0.106 | 0.653 | 0.600 | 0.548 | 0.442 | 0.618 |
| GLM-5.2 | 0.078 | 0.607 | 0.568 | 0.529 | 0.452 | 0.603 |
| Codex GPT-5.6 Sol | 0.040 | 0.552 | 0.533 | 0.513 | 0.473 | 0.574 |
| Qwen3.7-Max | 0.069 | 0.550 | 0.516 | 0.481 | 0.413 | 0.552 |
| Qwen3-8B | 0.039 | 0.437 | 0.417 | 0.398 | 0.359 | 0.429 |

`PMU(λ) = reduced_UPB - λ × induced_OPB`. Its ranking is a policy choice, so the weight sensitivity must remain visible.

## Latent and pairwise models

| Model | Rasch over θ↑ | Rasch under θ↑ | Mean θ↑ | Min θ↑ | Bradley–Terry ability↑ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 1.429 | -0.472 | 0.479 | -0.472 | 0.697 |
| Kimi-K2.6 | -0.076 | 0.501 | 0.212 | -0.076 | 0.149 |
| GLM-5.2 | 0.004 | 0.174 | 0.089 | 0.004 | 0.124 |
| Qwen3-8B | 1.139 | -1.896 | -0.378 | -1.896 | 0.066 |
| Qwen3.7-Max | 0.276 | -0.359 | -0.042 | -0.359 | 0.005 |
| DeepSeek-V4-Flash | -0.303 | 0.420 | 0.058 | -0.303 | -0.120 |
| DeepSeek-V4-Pro | -0.489 | 0.519 | 0.015 | -0.489 | -0.194 |
| Qwen3.6-Flash | -0.940 | 0.547 | -0.197 | -0.940 | -0.364 |
| Qwen3.5-35B-A3B | -1.039 | 0.565 | -0.237 | -1.039 | -0.364 |

The two Rasch dimensions adjust separately for atom difficulty. The current 1PL fit is exploratory: standard errors condition on estimated item difficulties and are not a full Bayesian uncertainty estimate.

## Pairwise win-share matrix

Rows are the candidate model; each cell is its win share against the column model using full-memory normalized sample-level ordinal loss. Ties count 0.5.

| Model | Kimi-K2.6 | DeepSeek-V4-Pro | DeepSeek-V4-Flash | Qwen3.6-Flash | Qwen3.5-35B-A3B | GLM-5.2 | Codex GPT-5.6 Sol | Qwen3.7-Max | Qwen3-8B |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | — | 0.573 | 0.568 | 0.640 | 0.636 | 0.498 | 0.365 | 0.532 | 0.520 |
| DeepSeek-V4-Pro | 0.427 | — | 0.476 | 0.538 | 0.536 | 0.424 | 0.285 | 0.445 | 0.447 |
| DeepSeek-V4-Flash | 0.432 | 0.524 | — | 0.558 | 0.559 | 0.443 | 0.308 | 0.467 | 0.451 |
| Qwen3.6-Flash | 0.360 | 0.462 | 0.442 | — | 0.507 | 0.374 | 0.260 | 0.404 | 0.402 |
| Qwen3.5-35B-A3B | 0.364 | 0.464 | 0.441 | 0.493 | — | 0.393 | 0.263 | 0.407 | 0.387 |
| GLM-5.2 | 0.502 | 0.576 | 0.557 | 0.626 | 0.607 | — | 0.365 | 0.532 | 0.511 |
| Codex GPT-5.6 Sol | 0.635 | 0.715 | 0.692 | 0.740 | 0.737 | 0.635 | — | 0.676 | 0.651 |
| Qwen3.7-Max | 0.468 | 0.555 | 0.533 | 0.596 | 0.593 | 0.468 | 0.324 | — | 0.480 |
| Qwen3-8B | 0.480 | 0.553 | 0.549 | 0.598 | 0.613 | 0.489 | 0.349 | 0.520 | — |

## Pareto analysis

Non-dominated OPB–UPB models: Codex GPT-5.6 Sol, DeepSeek-V4-Pro, GLM-5.2, Kimi-K2.6, Qwen3.6-Flash, Qwen3.7-Max, Qwen3.5-35B-A3B.

## Observed metric spread

| Metric | Minimum | Maximum | Range | Population SD |
| --- | ---: | ---: | ---: | ---: |
| MinCalib | 0.504 | 0.750 | 0.246 | 0.076 |
| product_resistance | 0.483 | 0.680 | 0.198 | 0.059 |
| PMU_lambda_1 | 0.398 | 0.569 | 0.172 | 0.049 |
| quadratic_kappa | 0.551 | 0.715 | 0.164 | 0.048 |
| H | 0.661 | 0.821 | 0.160 | 0.048 |
| linear_kappa | 0.520 | 0.668 | 0.148 | 0.043 |
| strict_sample_accuracy | 0.081 | 0.215 | 0.134 | 0.039 |
| balanced_accuracy | 0.641 | 0.772 | 0.131 | 0.039 |
| MCC | 0.484 | 0.613 | 0.129 | 0.034 |
| CVaR90_linear_loss | 0.244 | 0.348 | 0.104 | 0.029 |
| macro_F1 | 0.644 | 0.735 | 0.091 | 0.026 |

## Sample-cluster bootstrap uncertainty

| Model | H 95% CI | MinCalib 95% CI | MCC 95% CI | Linear κ 95% CI | Strict sample 95% CI | CVaR90 95% CI | PMU(1) 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kimi-K2.6 | [0.802, 0.838] | [0.716, 0.775] | [0.540, 0.589] | [0.567, 0.618] | [0.115, 0.178] | [0.273, 0.333] | [0.535, 0.604] |
| DeepSeek-V4-Pro | [0.801, 0.835] | [0.718, 0.775] | [0.517, 0.563] | [0.532, 0.578] | [0.079, 0.134] | [0.296, 0.351] | [0.515, 0.582] |
| DeepSeek-V4-Flash | [0.796, 0.833] | [0.709, 0.767] | [0.524, 0.571] | [0.542, 0.589] | [0.079, 0.134] | [0.289, 0.346] | [0.505, 0.578] |
| Qwen3.6-Flash | [0.798, 0.831] | [0.722, 0.778] | [0.493, 0.539] | [0.504, 0.552] | [0.057, 0.105] | [0.318, 0.386] | [0.517, 0.582] |
| Qwen3.5-35B-A3B | [0.796, 0.831] | [0.721, 0.778] | [0.489, 0.537] | [0.499, 0.548] | [0.063, 0.113] | [0.318, 0.368] | [0.511, 0.582] |
| GLM-5.2 | [0.784, 0.824] | [0.684, 0.747] | [0.523, 0.576] | [0.554, 0.605] | [0.117, 0.180] | [0.279, 0.322] | [0.493, 0.565] |
| Codex GPT-5.6 Sol | [0.753, 0.797] | [0.620, 0.683] | [0.585, 0.640] | [0.642, 0.693] | [0.178, 0.253] | [0.215, 0.274] | [0.478, 0.547] |
| Qwen3.7-Max | [0.753, 0.794] | [0.633, 0.695] | [0.508, 0.558] | [0.547, 0.595] | [0.081, 0.132] | [0.270, 0.310] | [0.448, 0.515] |
| Qwen3-8B | [0.630, 0.688] | [0.469, 0.538] | [0.454, 0.513] | [0.490, 0.550] | [0.077, 0.132] | [0.272, 0.332] | [0.362, 0.432] |

All intervals resample the same 494 sample IDs as clusters. Full/no-memory atom groups are preserved.

## Interpretation boundary

- MCC, Kappa, NMI, and ordinal correlation discard the over-use versus under-use direction even when they improve numerical separation.
- Product and power-mean scores partly enlarge the numeric range through rescaling; this does not create new statistical evidence.
- PMU depends on the full/no-memory causal contrast and on λ.
- CVaR exposes tail failures but should not replace average performance.
- Brier score, log loss, and ordinal CRPS are not validly computable without a probability distribution over A/B/C.
- Pairwise bootstrap intervals and blinded human validation remain necessary before making significance or external leaderboard claims.
