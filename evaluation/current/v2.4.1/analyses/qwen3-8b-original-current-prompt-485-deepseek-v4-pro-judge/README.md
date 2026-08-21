# Original Qwen3-8B cross-Judge comparison

This study evaluates the same 485 Non-Think Full-memory answers from the
official Qwen3-8B checkpoint with two full-coverage Judges. Both use the
ordered-usage-v2.1 protocol, temperature 0, the same hidden atoms and rubrics,
and the same current answer-system prompt used to generate the answers.

DeepSeek-V4-Pro was run independently with the second configured Bailian
credential. The first credential was not available to the runner. The initial
API pass completed 482/485 requests; three HTTP 429 failures were retried at a
lower rate and all recovered. All 485 normalized outputs passed structural
validation without a Judge-format retry.

## Main metrics

| Judge | SCS(0.5) up | sOPB(0.5) down | sUPB(0.5) down | Directional H up | Any OPB down | Any UPB down | Event H up | Exact up |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.7-Plus | 27.7% | 35.1% | 51.2% | 55.7% | 46.6% | 70.1% | 38.3% | 10.7% |
| DeepSeek-V4-Pro | 31.1% | 33.4% | 48.0% | 58.4% | 45.2% | 64.5% | 43.1% | 13.8% |

DeepSeek-V4-Pro is modestly more favorable: SCS is 3.4 percentage points
higher, sOPB is 1.7 points lower, sUPB is 3.2 points lower, and Exact is 3.1
points higher. The substantive conclusion is unchanged: the original Qwen3-8B
checkpoint is far below all three trained checkpoints in the strict
same-prompt comparison.

## Judge agreement

Agreement is measured on all 7,818 scored atoms from the 485 answers.

| Agreement measure | Value |
| --- | ---: |
| Ordered A/B/C exact agreement | 96.30% |
| Linear weighted kappa | 0.888 |
| Overall normalized-judgment agreement | 97.47% |
| Overall kappa | 0.929 |
| Scorable-status agreement | 100.00% |

Agreement by gold label is 98.75% for A, 91.44% for B, and 89.01% for C.
All configured automatic stability checks passed, including the exact-agreement,
weighted-kappa, and scorable-status thresholds. The residual metric shift should
therefore be reported as a small but visible Judge calibration effect rather
than a protocol failure.

## Artifacts

- [DeepSeek-V4-Pro sample-level metrics and bootstrap intervals](sample-level/README.md)
- [Interactive DeepSeek-V4-Pro sample-level distributions](sample-level/sample-level-score-distributions.html)
- [Machine-readable cross-Judge agreement](judge-agreement.json)
- [Strict four-model Qwen3.7-Plus comparison](../qwen3-8b-four-model-current-prompt-485-primary/README.md)
