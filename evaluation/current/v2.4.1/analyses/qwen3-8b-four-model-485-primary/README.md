# Qwen3-8B original and v2.4.1 training comparison

This report adds the official v2.4.1 Non-Think Qwen3-8B result to the three
training-view checkpoints. All four rows use the same 485 sample IDs, corrected
v2.4.1 memories and atomic gold labels, Full-memory condition, Qwen3.7-Plus
primary Judge, and ordered-usage-v2.1 protocol. Existing answers and judgments
were reused; no API call was made for this extension.

The original Qwen3-8B answers were generated with the earlier official
v2.4.1 answer-system prompt, whereas the three trained checkpoints used the
current revised answer-system prompt. Its row is therefore a useful approximate
baseline, but not a strict same-prompt controlled comparison.

## All primary metrics

| Model | SCS(0.5) up | sOPB(0.5) down | sUPB(0.5) down | Directional H up | Any OPB down | Any UPB down | Event H up | Exact up |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **12K fluent SFT** | **65.6%** | **11.0%** | **26.0%** | **80.8%** | **17.1%** | **42.1%** | **68.2%** | **47.8%** |
| 12K atomic-concat SFT | 63.5% | 13.6% | 26.7% | 79.3% | 21.4% | 42.7% | 66.3% | 46.4% |
| 4K cold-start | 50.8% | 18.5% | 37.7% | 70.6% | 27.4% | 56.7% | 54.2% | 32.4% |
| Original Qwen3-8B | 26.7% | 38.4% | 49.8% | 55.3% | 51.1% | 67.8% | 38.8% | 10.1% |

`SCS(0.5)` is the overall primary endpoint. `sOPB(0.5)` and `sUPB(0.5)`
are the directional severity endpoints that must accompany it. `Any OPB` and
`Any UPB` are event-rate guardrails, while `Exact` is the strict sample-level
zero-error rate. Directional H and Event H are compact summaries and should not
replace the paired directional columns.

## Reading the comparison

- All three trained checkpoints substantially improve both over-use and
  under-use relative to original Qwen3-8B.
- Both 12K SFT variants outperform the 4K cold-start checkpoint.
- Fluent 12K is numerically best on all eight primary columns and is the only
  OPB-UPB Pareto-front model.
- Fluent versus atomic remains inconclusive: 123 versus 101 paired wins, 261
  ties, two-sided sign-test p=0.160, and the paired mean-loss interval crosses
  zero.
- No No-memory answers were requested, so PMU is not computable in this study.

## Artifacts

- [Primary metrics, bootstrap intervals, and score distributions](sample-level/README.md)
- [Interactive sample-level distributions](sample-level/sample-level-score-distributions.html)
- [All candidate, chance-corrected, ordinal, tail-risk, and pairwise metrics](candidate-metrics/README.md)
- [Interactive tail-risk, Pareto, and rank diagnostics](candidate-metrics/candidate-metric-diagnostics.html)
