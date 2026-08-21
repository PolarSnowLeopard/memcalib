# Qwen3-8B original and v2.4.1 training comparison

This is the strict same-prompt comparison requested after rerunning the official
Qwen3-8B checkpoint on the cluster. All four models use the same 485 corrected
v2.4.1 samples, current answer-system prompt, fluent Full-memory input,
Non-Think generation, Qwen3.7-Plus primary Judge, and ordered-usage-v2.1
protocol.

The original checkpoint returned 493/494 valid answers. Its one truncated
sample was already outside the 485-sample intersection of the three trained
checkpoints, so the shared comparison set remains 485. The 485 new Judge calls
all succeeded; one structurally invalid response was retried in isolation.
Existing judgments for the other three checkpoints were reused.

## All primary metrics

| Model | SCS(0.5) up | sOPB(0.5) down | sUPB(0.5) down | Directional H up | Any OPB down | Any UPB down | Event H up | Exact up |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **12K fluent SFT** | **65.6%** | **11.0%** | **26.0%** | **80.8%** | **17.1%** | **42.1%** | **68.2%** | **47.8%** |
| 12K atomic-concat SFT | 63.5% | 13.6% | 26.7% | 79.3% | 21.4% | 42.7% | 66.3% | 46.4% |
| 4K cold-start | 50.8% | 18.5% | 37.7% | 70.6% | 27.4% | 56.7% | 54.2% | 32.4% |
| Original Qwen3-8B | 27.7% | 35.1% | 51.2% | 55.7% | 46.6% | 70.1% | 38.3% | 10.7% |

`SCS(0.5)` is the overall primary endpoint. `sOPB(0.5)` and `sUPB(0.5)`
must accompany it because they retain error direction and severity. `Any OPB`
and `Any UPB` are event-rate guardrails, while `Exact` is the strict
sample-level zero-error rate. Directional H and Event H are compact summaries,
not replacements for their paired directional columns.

## Reading the result

- All three trained checkpoints substantially improve both over-use and
  under-use relative to the strict current-prompt original checkpoint.
- Both 12K SFT variants outperform the 4K cold-start checkpoint.
- Fluent 12K is numerically best on all eight primary columns and is the only
  OPB-UPB Pareto-front model.
- Fluent versus atomic remains numerically close; the earlier paired analysis
  found no statistically resolved difference between them.
- No No-memory answers were requested, so PMU is not computable in this study.

## Supporting metrics

| Model | Atomic OPB down | Atomic UPB down | H up | MinCalib up | MCC up | Linear kappa up | CVaR90 down |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **12K fluent SFT** | **0.033** | **0.227** | **0.859** | **0.773** | **0.811** | **0.841** | **0.156** |
| 12K atomic-concat SFT | 0.036 | 0.233 | 0.854 | 0.767 | 0.797 | 0.829 | 0.163 |
| 4K cold-start | 0.045 | 0.345 | 0.777 | 0.655 | 0.693 | 0.733 | 0.202 |
| Original Qwen3-8B | 0.041 | 0.519 | 0.641 | 0.481 | 0.479 | 0.528 | 0.286 |

## Artifacts

- [Primary metrics, bootstrap intervals, and score distributions](sample-level/README.md)
- [Interactive sample-level distributions](sample-level/sample-level-score-distributions.html)
- [All candidate, chance-corrected, ordinal, tail-risk, and pairwise metrics](candidate-metrics/README.md)
- [Interactive tail-risk, Pareto, and rank diagnostics](candidate-metrics/candidate-metric-diagnostics.html)
- [Original Qwen3-8B cross-Judge stability check](../qwen3-8b-original-current-prompt-485-deepseek-v4-pro-judge/README.md)
