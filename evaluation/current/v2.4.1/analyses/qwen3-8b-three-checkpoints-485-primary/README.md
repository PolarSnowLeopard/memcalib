# Qwen3-8B v2.4.1 training-view comparison

This study compares three Non-Think Qwen3-8B checkpoints on the corrected
MemCalib v2.4.1 pilot using the same fluent Full-memory inputs:

- 4K selected examples used for cold-start training;
- 12K atomic-concat SFT, trained for one epoch;
- 12K canonical-fluent SFT, trained for one epoch.

The cluster returned 490, 491, and 489 valid answers respectively. All missing
rows ended with `finish_reason=length`; no answer was regenerated. The analysis
uses the strict intersection of **485 samples** completed by every checkpoint.
Qwen3.7-Plus judged 1,455 answers under ordered-usage-v2.1 with thinking
disabled. One structurally invalid Judge row was retried in isolation, yielding
1,455/1,455 valid normalized judgments.

## Main result

| Checkpoint | SCS(0.5) up | sOPB(0.5) down | sUPB(0.5) down | Exact up | CVaR90 down |
| --- | ---: | ---: | ---: | ---: | ---: |
| **12K fluent SFT** | **65.6%** | **11.0%** | **26.0%** | **47.8%** | **0.156** |
| 12K atomic-concat SFT | 63.5% | 13.6% | 26.7% | 46.4% | 0.163 |
| 4K cold-start | 50.8% | 18.5% | 37.7% | 32.4% | 0.202 |

Both 12K SFT checkpoints clearly improve both error directions over the 4K
cold-start checkpoint. The fluent checkpoint is numerically best on every
headline column and is the only OPB-UPB Pareto-front model.

The fluent-versus-atomic difference is not yet statistically resolved. Their
paired normalized-loss comparison has 123 fluent wins, 101 atomic wins, and
261 ties; the two-sided sign-test p-value is 0.160. The mean atomic-minus-fluent
loss difference is 0.00284 with a bootstrap 95% interval of [-0.00188, 0.00727].
The defensible conclusion is therefore that both 12K variants outperform the
4K cold-start, while fluent is a small, currently inconclusive numerical lead
over atomic-concat.

## Supporting metrics

| Checkpoint | Atomic OPB down | Atomic UPB down | H up | MinCalib up | MCC up | Linear kappa up |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **12K fluent SFT** | **0.033** | **0.227** | **0.859** | **0.773** | **0.811** | **0.841** |
| 12K atomic-concat SFT | 0.036 | 0.233 | 0.854 | 0.767 | 0.797 | 0.829 |
| 4K cold-start | 0.045 | 0.345 | 0.777 | 0.655 | 0.693 | 0.733 |

No No-memory responses were requested, so PMU and other matched memory-utility
contrasts are intentionally not available for this run.

## Artifacts

- [Sample-level metrics, intervals, and distributions](sample-level/README.md)
- [Interactive sample-level distribution report](sample-level/sample-level-score-distributions.html)
- [All candidate metrics and paired comparisons](candidate-metrics/README.md)
- [Tail-risk, Pareto, and rank diagnostics](candidate-metrics/candidate-metric-diagnostics.html)
