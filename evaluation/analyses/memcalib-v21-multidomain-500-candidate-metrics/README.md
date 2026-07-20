# MemCalib v2.1 candidate metric study

This diagnostic uses the same locked 500 records and all 8,000 primary-Judge rows from the eight-model full/no-memory comparison. It does not change the official metric definition.

## Headline comparison

| Model | OPB↓ | UPB↓ | H↑ | MinCalib↑ | MCC↑ | Linear κ↑ | CVaR90↓ | PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 0.212 | 0.294 | 0.745 | 0.706 | 0.496 | 0.483 | 0.601 | 0.436 |
| Kimi-K2.6 | 0.311 | 0.196 | 0.742 | 0.689 | 0.506 | 0.436 | 0.643 | 0.455 |
| DeepSeek-V4-Pro | 0.383 | 0.193 | 0.699 | 0.617 | 0.446 | 0.343 | 0.642 | 0.383 |
| Qwen3.7-Max | 0.384 | 0.201 | 0.696 | 0.616 | 0.434 | 0.339 | 0.660 | 0.382 |
| DeepSeek-V4-Flash | 0.393 | 0.199 | 0.691 | 0.607 | 0.429 | 0.330 | 0.621 | 0.357 |
| Qwen3.6-Flash | 0.394 | 0.201 | 0.689 | 0.606 | 0.427 | 0.319 | 0.651 | 0.386 |
| Qwen3.5-35B-A3B | 0.414 | 0.176 | 0.685 | 0.586 | 0.439 | 0.312 | 0.631 | 0.379 |
| Qwen3-8B | 0.251 | 0.452 | 0.633 | 0.548 | 0.302 | 0.277 | 0.728 | 0.266 |

Numeric ranges across differently scaled metrics are not directly comparable. Use paired confidence intervals and ranking robustness, not range alone.

## Classification and chance-corrected metrics

| Model | Exact↑ | Balanced acc.↑ | Macro F1↑ | MCC↑ | κ↑ | Linear κ↑ | Quadratic κ↑ | NMI↑ | Cramér V↑ | Ordinal r↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 0.662 | 0.663 | 0.662 | 0.496 | 0.493 | 0.483 | 0.472 | 0.278 | 0.537 | 0.472 |
| Kimi-K2.6 | 0.666 | 0.662 | 0.653 | 0.506 | 0.498 | 0.436 | 0.373 | 0.300 | 0.549 | 0.383 |
| DeepSeek-V4-Pro | 0.622 | 0.616 | 0.597 | 0.446 | 0.433 | 0.343 | 0.250 | 0.271 | 0.510 | 0.266 |
| Qwen3.7-Max | 0.615 | 0.610 | 0.590 | 0.434 | 0.422 | 0.339 | 0.256 | 0.274 | 0.511 | 0.269 |
| DeepSeek-V4-Flash | 0.611 | 0.605 | 0.583 | 0.429 | 0.416 | 0.330 | 0.243 | 0.276 | 0.509 | 0.258 |
| Qwen3.6-Flash | 0.610 | 0.604 | 0.584 | 0.427 | 0.414 | 0.319 | 0.221 | 0.264 | 0.502 | 0.235 |
| Qwen3.5-35B-A3B | 0.615 | 0.607 | 0.577 | 0.439 | 0.421 | 0.312 | 0.200 | 0.296 | 0.521 | 0.219 |
| Qwen3-8B | 0.529 | 0.532 | 0.532 | 0.302 | 0.297 | 0.277 | 0.257 | 0.166 | 0.397 | 0.260 |

## Ordinal severity metrics

| Model | MAE↓ | RMSE↓ | Macro L1↑ | Macro L2↑ | A↔C atom rate↓ | Over quadratic cost↓ | Under quadratic cost↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 0.462 | 0.841 | 0.703 | 0.723 | 0.123 | 0.246 | 0.187 |
| Kimi-K2.6 | 0.499 | 0.910 | 0.695 | 0.711 | 0.165 | 0.389 | 0.119 |
| DeepSeek-V4-Pro | 0.577 | 0.988 | 0.656 | 0.675 | 0.199 | 0.484 | 0.114 |
| Qwen3.7-Max | 0.584 | 0.991 | 0.646 | 0.665 | 0.199 | 0.477 | 0.126 |
| DeepSeek-V4-Flash | 0.591 | 0.997 | 0.644 | 0.664 | 0.202 | 0.492 | 0.118 |
| Qwen3.6-Flash | 0.600 | 1.009 | 0.642 | 0.661 | 0.210 | 0.498 | 0.127 |
| Qwen3.5-35B-A3B | 0.601 | 1.017 | 0.646 | 0.665 | 0.216 | 0.533 | 0.102 |
| Qwen3-8B | 0.659 | 1.017 | 0.577 | 0.599 | 0.187 | 0.313 | 0.318 |

## Composite-score sensitivity

| Model | H | Arithmetic | Geometric | Product | Softmin −2 | Softmin −4 | Softmin −8 | MinCalib | Ideal L2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 0.745 | 0.747 | 0.746 | 0.557 | 0.744 | 0.742 | 0.737 | 0.706 | 0.744 |
| Kimi-K2.6 | 0.742 | 0.747 | 0.745 | 0.554 | 0.740 | 0.736 | 0.728 | 0.689 | 0.740 |
| DeepSeek-V4-Pro | 0.699 | 0.712 | 0.706 | 0.498 | 0.693 | 0.682 | 0.664 | 0.617 | 0.697 |
| Qwen3.7-Max | 0.696 | 0.707 | 0.701 | 0.492 | 0.690 | 0.679 | 0.662 | 0.616 | 0.693 |
| DeepSeek-V4-Flash | 0.691 | 0.704 | 0.697 | 0.486 | 0.684 | 0.672 | 0.654 | 0.607 | 0.689 |
| Qwen3.6-Flash | 0.689 | 0.703 | 0.696 | 0.485 | 0.683 | 0.671 | 0.653 | 0.606 | 0.687 |
| Qwen3.5-35B-A3B | 0.685 | 0.705 | 0.695 | 0.483 | 0.676 | 0.659 | 0.634 | 0.586 | 0.682 |
| Qwen3-8B | 0.633 | 0.649 | 0.641 | 0.411 | 0.626 | 0.612 | 0.592 | 0.548 | 0.635 |

## Sample-level tail risk

| Model | Strict sample↑ | Any A↔C sample↓ | Mean L1 loss↓ | P90↓ | CVaR90↓ | CVaR95↓ | Quadratic CVaR90↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 0.270 | 0.374 | 0.234 | 0.500 | 0.601 | 0.684 | 0.533 |
| Kimi-K2.6 | 0.250 | 0.522 | 0.257 | 0.500 | 0.643 | 0.719 | 0.556 |
| DeepSeek-V4-Pro | 0.170 | 0.642 | 0.294 | 0.500 | 0.642 | 0.708 | 0.545 |
| Qwen3.7-Max | 0.152 | 0.634 | 0.300 | 0.500 | 0.660 | 0.728 | 0.576 |
| DeepSeek-V4-Flash | 0.126 | 0.650 | 0.302 | 0.500 | 0.621 | 0.710 | 0.539 |
| Qwen3.6-Flash | 0.136 | 0.670 | 0.309 | 0.500 | 0.651 | 0.715 | 0.572 |
| Qwen3.5-35B-A3B | 0.124 | 0.698 | 0.309 | 0.500 | 0.631 | 0.692 | 0.561 |
| Qwen3-8B | 0.142 | 0.548 | 0.332 | 0.625 | 0.728 | 0.788 | 0.632 |

CVaR90 is the mean loss among the worst 10% of samples; CVaR95 uses the worst 5%. Sample loss is normalized absolute ordinal distance.

## Paired memory utility

| Model | Induced OPB↓ | Reduced UPB↑ | PMU(0.5)↑ | PMU(1)↑ | PMU(2)↑ | Relative PMU(1)↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 0.188 | 0.624 | 0.530 | 0.436 | 0.248 | 0.492 |
| Kimi-K2.6 | 0.262 | 0.717 | 0.586 | 0.455 | 0.192 | 0.523 |
| DeepSeek-V4-Pro | 0.331 | 0.714 | 0.549 | 0.383 | 0.052 | 0.456 |
| Qwen3.7-Max | 0.328 | 0.709 | 0.546 | 0.382 | 0.054 | 0.452 |
| DeepSeek-V4-Flash | 0.346 | 0.703 | 0.530 | 0.357 | 0.011 | 0.433 |
| Qwen3.6-Flash | 0.329 | 0.715 | 0.550 | 0.386 | 0.057 | 0.452 |
| Qwen3.5-35B-A3B | 0.359 | 0.738 | 0.558 | 0.379 | 0.019 | 0.448 |
| Qwen3-8B | 0.227 | 0.493 | 0.379 | 0.266 | 0.039 | 0.295 |

`PMU(λ) = reduced_UPB - λ × induced_OPB`. Its ranking is a policy choice, so the weight sensitivity must remain visible.

## Latent and pairwise models

| Model | Rasch over θ↑ | Rasch under θ↑ | Mean θ↑ | Min θ↑ | Bradley–Terry ability↑ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | 1.991 | -0.649 | 0.671 | -0.649 | 0.398 |
| Kimi-K2.6 | 0.462 | 0.456 | 0.459 | 0.456 | 0.276 |
| DeepSeek-V4-Pro | -0.608 | 0.509 | -0.049 | -0.608 | 0.001 |
| Qwen3.7-Max | -0.621 | 0.384 | -0.119 | -0.621 | -0.053 |
| DeepSeek-V4-Flash | -0.745 | 0.405 | -0.170 | -0.745 | -0.093 |
| Qwen3.6-Flash | -0.773 | 0.405 | -0.184 | -0.773 | -0.126 |
| Qwen3.5-35B-A3B | -1.069 | 0.726 | -0.172 | -1.069 | -0.139 |
| Qwen3-8B | 1.363 | -2.236 | -0.436 | -2.236 | -0.265 |

The two Rasch dimensions adjust separately for atom difficulty. The current 1PL fit is exploratory: standard errors condition on estimated item difficulties and are not a full Bayesian uncertainty estimate.

## Pairwise win-share matrix

Rows are the candidate model; each cell is its win share against the column model using full-memory normalized sample-level ordinal loss. Ties count 0.5.

| Model | Codex GPT-5.6 Sol | Kimi-K2.6 | DeepSeek-V4-Pro | Qwen3.7-Max | DeepSeek-V4-Flash | Qwen3.6-Flash | Qwen3.5-35B-A3B | Qwen3-8B |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | — | 0.527 | 0.596 | 0.616 | 0.625 | 0.624 | 0.629 | 0.662 |
| Kimi-K2.6 | 0.473 | — | 0.572 | 0.587 | 0.593 | 0.599 | 0.599 | 0.621 |
| DeepSeek-V4-Pro | 0.404 | 0.428 | — | 0.517 | 0.529 | 0.528 | 0.533 | 0.565 |
| Qwen3.7-Max | 0.384 | 0.413 | 0.483 | — | 0.502 | 0.522 | 0.528 | 0.564 |
| DeepSeek-V4-Flash | 0.375 | 0.407 | 0.471 | 0.498 | — | 0.506 | 0.514 | 0.547 |
| Qwen3.6-Flash | 0.376 | 0.401 | 0.472 | 0.478 | 0.494 | — | 0.505 | 0.527 |
| Qwen3.5-35B-A3B | 0.371 | 0.401 | 0.467 | 0.472 | 0.486 | 0.495 | — | 0.535 |
| Qwen3-8B | 0.338 | 0.379 | 0.435 | 0.436 | 0.453 | 0.473 | 0.465 | — |

## Pareto analysis

Non-dominated OPB–UPB models: Codex GPT-5.6 Sol, DeepSeek-V4-Pro, Kimi-K2.6, Qwen3.5-35B-A3B.

## Observed metric spread

| Metric | Minimum | Maximum | Range | Population SD |
| --- | ---: | ---: | ---: | ---: |
| quadratic_kappa | 0.200 | 0.472 | 0.271 | 0.086 |
| linear_kappa | 0.277 | 0.483 | 0.206 | 0.064 |
| MCC | 0.302 | 0.506 | 0.204 | 0.058 |
| PMU_lambda_1 | 0.266 | 0.455 | 0.189 | 0.053 |
| MinCalib | 0.548 | 0.706 | 0.158 | 0.049 |
| strict_sample_accuracy | 0.124 | 0.270 | 0.146 | 0.053 |
| product_resistance | 0.411 | 0.557 | 0.146 | 0.043 |
| balanced_accuracy | 0.532 | 0.663 | 0.131 | 0.038 |
| macro_F1 | 0.532 | 0.662 | 0.129 | 0.039 |
| CVaR90_linear_loss | 0.601 | 0.728 | 0.127 | 0.035 |
| H | 0.633 | 0.745 | 0.112 | 0.033 |

## Sample-cluster bootstrap uncertainty

| Model | H 95% CI | MinCalib 95% CI | MCC 95% CI | Linear κ 95% CI | Strict sample 95% CI | CVaR90 95% CI | PMU(1) 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.6 Sol | [0.726, 0.763] | [0.676, 0.736] | [0.460, 0.531] | [0.443, 0.519] | [0.232, 0.308] | [0.565, 0.640] | [0.398, 0.474] |
| Kimi-K2.6 | [0.725, 0.759] | [0.667, 0.712] | [0.471, 0.541] | [0.397, 0.474] | [0.212, 0.292] | [0.598, 0.692] | [0.414, 0.494] |
| DeepSeek-V4-Pro | [0.683, 0.717] | [0.597, 0.638] | [0.409, 0.482] | [0.306, 0.379] | [0.138, 0.202] | [0.597, 0.687] | [0.345, 0.421] |
| Qwen3.7-Max | [0.679, 0.711] | [0.595, 0.637] | [0.398, 0.468] | [0.302, 0.377] | [0.122, 0.184] | [0.610, 0.707] | [0.342, 0.419] |
| DeepSeek-V4-Flash | [0.675, 0.707] | [0.588, 0.627] | [0.396, 0.462] | [0.294, 0.366] | [0.098, 0.156] | [0.580, 0.669] | [0.320, 0.395] |
| Qwen3.6-Flash | [0.673, 0.706] | [0.585, 0.628] | [0.393, 0.460] | [0.285, 0.355] | [0.106, 0.168] | [0.605, 0.698] | [0.348, 0.424] |
| Qwen3.5-35B-A3B | [0.670, 0.701] | [0.567, 0.607] | [0.407, 0.473] | [0.280, 0.345] | [0.096, 0.154] | [0.590, 0.674] | [0.344, 0.416] |
| Qwen3-8B | [0.611, 0.654] | [0.518, 0.580] | [0.266, 0.339] | [0.235, 0.316] | [0.112, 0.174] | [0.692, 0.761] | [0.229, 0.303] |

All intervals resample the same 500 sample IDs as clusters and preserve their full/no-memory atom groups.

## Interpretation boundary

- MCC, Kappa, NMI, and ordinal correlation discard the over-use versus under-use direction even when they improve numerical separation.
- Product and power-mean scores partly enlarge the numeric range through rescaling; this does not create new statistical evidence.
- PMU depends on the full/no-memory causal contrast and on λ.
- CVaR exposes tail failures but should not replace average performance.
- Brier score, log loss, and ordinal CRPS are not validly computable without a probability distribution over A/B/C.
- Pairwise bootstrap intervals and blinded human validation remain necessary before making significance or external leaderboard claims.
