# MemCalib v2.4 Nine-Model Complete-Case Evaluation

## Scope

This release evaluates MemCalib v2.4 on the sample IDs locked for the v2.3
nine-model experiment. The parent sample contains 500 records:

| Domain | Parent records |
|---|---:|
| health_seed | 250 |
| general | 125 |
| coding | 125 |

All 125 coding records use the v2.4 natural-language task interface. The
health/general model-facing rows are unchanged controls. v2.3 coding answers
and judgments were not reused.

Eight Bailian answer models used thinking mode. Codex GPT-5.6 Sol used
`reasoning_effort=none`. The primary and secondary Judges used non-thinking
generation.

## Complete-Case Policy

The answer stage completed 8,994 of 9,000 requested responses. GLM-5.2
no-memory had six persistent `finish_reason=length` records after the main
8,192-token call and three targeted retries at 16,384/32,768 tokens. No answer
was imputed and no further API round was launched.

To prevent GLM from being scored on an easier or different sample, those same
six sample IDs were excluded from **every** model-condition cell:

| Audit item | Count |
|---|---:|
| Locked parent samples | 500 |
| Globally excluded samples | 6 |
| Common samples per cell | 494 |
| Models | 9 |
| Conditions | 2 |
| Fully paired answers | 8,892 |

The six IDs are in `excluded-sample-ids.txt`. The exact intersection policy,
cell-level missing audit, hashes, and output paths are in
`complete-case.manifest.json`.

## Judge Coverage

| Stage | Requested | Valid final | Residual invalid |
|---|---:|---:|---:|
| Primary Judge | 8,892 | 8,892 | 0 |
| Secondary Judge | 450 | 450 | 0 |

The primary pass initially produced 24 structurally invalid outputs; 23
resolved in retry 1 and one in retry 2. The secondary Kimi panel had two
initial structural invalids, both resolved in retry 1. Valid rows were never
rerun.

Across 7,554 atoms scored by both panels:

| Agreement measure | Result |
|---|---:|
| Ordered exact agreement | 95.71% |
| Linear weighted kappa | 85.04% |
| Verdict exact agreement | 96.96% |
| Verdict Cohen kappa | 91.08% |

## Sample-Level Primary Results

All values are percentages. SCS and Exact are higher-is-better; the four
directional/event error rates are lower-is-better.

| Model | SCS↑ | sOPB↓ | sUPB↓ | Any-OPB↓ | Any-UPB↓ | Exact↑ |
|---|---:|---:|---:|---:|---:|---:|
| Codex GPT-5.6 Sol | **39.8%** | **38.5%** | 33.7% | **52.6%** | 51.4% | **21.9%** |
| Kimi-K2.6 | 32.3% | 53.3% | 28.9% | 67.0% | 44.1% | 18.0% |
| Qwen3-8B | 30.4% | 47.0% | 39.6% | 59.9% | 59.3% | 15.0% |
| DeepSeek-V4-Flash | 28.6% | 60.9% | 24.9% | 75.9% | 39.9% | 14.2% |
| Qwen3.6-Flash | 27.9% | 60.9% | 27.0% | 74.5% | 42.3% | 15.4% |
| GLM-5.2 | 25.9% | 64.7% | 22.2% | 78.1% | 36.4% | 11.7% |
| DeepSeek-V4-Pro | 24.4% | 67.8% | 20.9% | 81.4% | 33.4% | 11.7% |
| Qwen3.5-35B-A3B | 21.0% | 70.0% | 26.1% | 84.4% | 41.1% | 8.5% |
| Qwen3.7-Max | 20.7% | 71.8% | **19.9%** | 86.0% | **32.4%** | 6.7% |

The primary report must keep all three layers:

1. **Overall:** `SCS(0.5)` gives every answer equal model-level weight.
2. **Directional:** `sOPB/sUPB(0.5)` retains direction, multiplicity, and
   A/B/C ordinal severity.
3. **Event guardrails:** Any-OPB/Any-UPB reports whether each direction occurs
   at least once, but intentionally discards multiplicity.

## Atomic and Tail Diagnostics

The atomic macro H ranking differs from the sample-level ranking:

| Model | OPB↓ | UPB↓ | H↑ | MinCalib↑ | CVaR90 loss↓ |
|---|---:|---:|---:|---:|---:|
| Qwen3.7-Max | 11.4% | **18.6%** | **84.9%** | **81.4%** | 34.1% |
| DeepSeek-V4-Pro | 11.1% | 19.3% | 84.6% | 80.7% | 34.8% |
| GLM-5.2 | 10.6% | 20.1% | 84.4% | 79.9% | 31.2% |
| DeepSeek-V4-Flash | 8.6% | 23.6% | 83.2% | 76.4% | 30.1% |
| Qwen3.5-35B-A3B | 11.3% | 24.2% | 81.8% | 75.8% | 33.8% |
| Qwen3.6-Flash | 9.8% | 25.7% | 81.5% | 74.3% | 32.3% |
| Kimi-K2.6 | 8.1% | 27.1% | 81.3% | 72.9% | 30.3% |
| Codex GPT-5.6 Sol | **4.8%** | 32.3% | 79.2% | 67.7% | **25.3%** |
| Qwen3-8B | 6.1% | 37.9% | 74.8% | 62.1% | 29.3% |

Atomic H rewards a favorable average across atoms. SCS, Exact, Any events, and
CVaR reveal how errors cluster within answers. Neither view should replace the
other.

## Files

- `metrics.json`: official atomic and paired metrics.
- `report.html`: interactive official report.
- `model-facing.jsonl[.gz]`: the 494-record model-facing sample.
- `hidden-evaluation.jsonl[.gz]`: hidden atomic supervision.
- `sample-ids.txt`: ordered complete-case IDs.
- `excluded-sample-ids.txt`: six globally excluded IDs.
- `complete-case.manifest.json`: complete-case audit and hashes.
- `answer-run.manifest.json`: answer protocol, usage, and cell validation.
- `judge-request.manifest.json`: primary/secondary request counts and hashes.
- `judge-run.manifest.json`: final Judge validation.

Additional analyses:

- [Candidate metrics](../../analyses/candidate-metrics/README.md)
- [Tail, Pareto, and rank diagnostics](../../analyses/candidate-metrics/candidate-metric-diagnostics.html)
- [Three-layer sample-level metrics](../../analyses/sample-level/README.md)
- [Sample-level distributions](../../analyses/sample-level/sample-level-score-distributions.html)
