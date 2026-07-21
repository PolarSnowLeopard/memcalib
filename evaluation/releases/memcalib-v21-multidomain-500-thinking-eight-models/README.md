# MemCalib v2.1 thinking-mode eight-model diagnostic

This release evaluates eight Bailian-hosted models with thinking enabled on
the exact locked 500-record MemCalib v2.1 sample used by the prior
seven-model non-thinking baseline. It adds GLM-5.2 and does not rerun Codex.

## Locked comparison

- benchmark SHA-256:
  `bd45f77534351cd096476080096ce9ba6250a375941a171ab561ad78704bed44`;
- model-facing SHA-256:
  `1e37ba0435f2ceb65d369c817660b0822c934d8318823c402fc657453ac127d8`;
- hidden-evaluation SHA-256:
  `2fca7b2a75a9b8f4f0fb0386a9ea1ef1b0d4e59173f84fa864d90372e77993e0`;
- ordered sample-ID digest:
  `92292219c596e790720456754376354be30c5954bf7875085594fbce40c52d29`;
- 500 records: health 250, general 125, coding 125;
- 556 A, 635 B, and 570 C hidden atoms;
- paired full-memory and no-memory answers for every model.

Answer generation used temperature 0 and thinking enabled. Initial calls used
an 8,192-token output limit; targeted completion retries could raise that
limit to at most 32,768 without changing the request content. Qwen3-8B
required the provider's streaming interface; the stream was deterministically
merged into the same final response schema. Judges remained non-thinking to
preserve the established v2.1 protocol.

## Full-memory results

| Model | Macro OPB | Macro UPB | Macro H | Strict sample accuracy | Mean task quality | Safety failure |
|---|---:|---:|---:|---:|---:|---:|
| Kimi-K2.6 | 0.307 | 0.207 | 0.740 | 0.222 | 3.122 | 0.024 |
| Qwen3.5-35B-A3B | 0.347 | 0.181 | 0.727 | 0.202 | 3.030 | 0.028 |
| GLM-5.2 | 0.372 | 0.156 | 0.720 | 0.196 | 3.094 | 0.020 |
| DeepSeek-V4-Pro | 0.402 | 0.137 | 0.707 | 0.158 | 3.062 | 0.028 |
| Qwen3.6-Flash | 0.384 | 0.189 | 0.700 | 0.154 | 3.086 | 0.034 |
| DeepSeek-V4-Flash | 0.384 | 0.193 | 0.699 | 0.140 | 2.998 | 0.022 |
| Qwen3.7-Max | 0.432 | 0.127 | 0.689 | 0.130 | 2.954 | 0.030 |
| Qwen3-8B | 0.304 | 0.339 | 0.678 | 0.142 | 2.866 | 0.028 |

Macro H is retained for protocol continuity, but the directional OPB/UPB
pair should be reported with it. For example, Qwen3.7-Max has the lowest UPB
in this run but the highest OPB, while Qwen3-8B has low OPB and high UPB.

## No-memory counterfactual

| Model | Macro OPB | Macro UPB | Macro H |
|---|---:|---:|---:|
| GLM-5.2 | 0.054 | 0.904 | 0.174 |
| Qwen3.7-Max | 0.063 | 0.906 | 0.171 |
| DeepSeek-V4-Pro | 0.051 | 0.907 | 0.170 |
| Qwen3.6-Flash | 0.058 | 0.912 | 0.161 |
| Qwen3.5-35B-A3B | 0.054 | 0.914 | 0.157 |
| DeepSeek-V4-Flash | 0.045 | 0.915 | 0.156 |
| Kimi-K2.6 | 0.047 | 0.915 | 0.156 |
| Qwen3-8B | 0.031 | 0.934 | 0.124 |

No-memory uses the same questions without memory blocks. It is a paired
counterfactual rather than an independent leaderboard.

## Thinking versus non-thinking

The following deltas compare the seven shared models against
`memcalib-v21-multidomain-500-seven-models` on the identical sample and
protocol. Positive H is an improvement; negative OPB/UPB is an improvement.

| Model | Delta OPB | Delta UPB | Delta H |
|---|---:|---:|---:|
| Qwen3.5-35B-A3B | -0.067 | +0.005 | +0.042 |
| Qwen3-8B | +0.053 | -0.113 | +0.045 |
| Qwen3.6-Flash | -0.010 | -0.012 | +0.011 |
| DeepSeek-V4-Flash | -0.009 | -0.007 | +0.008 |
| DeepSeek-V4-Pro | +0.019 | -0.056 | +0.007 |
| Kimi-K2.6 | -0.003 | +0.011 | -0.003 |
| Qwen3.7-Max | +0.048 | -0.074 | -0.007 |

Thinking therefore does not produce a uniform improvement. It often changes
the balance between over-use and under-use rather than moving both directions
together. These are paired descriptive deltas; model serving snapshots and
provider-side implementations remain potential confounds.

## Extended candidate metrics

The same 8,000 primary-Judge rows were also evaluated with the complete
candidate-metric suite used for the non-thinking study: MinCalib,
arithmetic/geometric/product/soft-min composites, balanced accuracy, macro F1,
MCC, unweighted/linear/quadratic Kappa, NMI, Cramer V, ordinal distance and
severe-error measures, CVaR90/95, PMU weight sensitivity, 28 pairwise win
shares, Bradley-Terry ability, two-dimensional Rasch 1PL, Pareto analysis, and
2,000 sample-cluster bootstrap replicates.

H spans only 0.062 across the eight models. Quadratic Kappa and MCC span about
0.138 and 0.137, while PMU(1), MinCalib, and CVaR90 span 0.126, 0.124, and
0.105. H ranks Kimi first, Qwen3.5-35B-A3B second, and GLM-5.2 third; CVaR90
ranks Qwen3.5-35B-A3B first, GLM-5.2 second, and Kimi third. The rank change is
expected because CVaR evaluates the worst 50 of 500 samples rather than the
overall directional average.

- [Candidate-metric study](../../analyses/memcalib-v21-multidomain-500-thinking-candidate-metrics/README.md)
- [Tail, Pareto, and rank diagnostics](../../analyses/memcalib-v21-multidomain-500-thinking-candidate-metrics/candidate-metric-diagnostics.html)
- [Machine-readable metrics](../../analyses/memcalib-v21-multidomain-500-thinking-candidate-metrics/candidate-metrics.json)
- [Flat comparison table](../../analyses/memcalib-v21-multidomain-500-thinking-candidate-metrics/candidate-metrics.csv)

## Completeness and controlled exceptions

- 8 models x 2 conditions x 500 samples = 8,000 final answers;
- every final answer has a unique request ID, non-empty reasoning content,
  and `finish_reason=stop`;
- the primary Judge produced 8,000 valid judgments;
- the secondary Judges produced 400 valid stratified judgments;
- all 8 structural Judge invalids were repaired by targeted retry, leaving
  zero residual invalids.

Two GLM-5.2 no-memory requests repeatedly exhausted larger unrestricted
generation attempts. They were rerun with the
[provider-supported thinking budget](https://help.aliyun.com/zh/model-studio/deep-thinking)
set to 8,192, while retaining `enable_thinking=true`; both ended
with `finish_reason=stop` and non-empty reasoning. The other 998 GLM answers
did not use this bound. Paths, hashes, and merge counts are recorded in
`glm52-thinking-budget-rescue.manifest.json`.

Qwen3-4B was requested but is not an online inference model available to
either configured credential. `qwen3-4b` returned access denied and
`qwen3-4b-instruct-2507` was not found. The official
[online text-model catalog](https://help.aliyun.com/zh/model-studio/text-generation)
starts the Qwen3 dense family at 8B, while 4B appears in
[model-training documentation](https://help.aliyun.com/zh/model-studio/model-training-overview).
It was not silently substituted and has no score in this release.

## Judge stability

The primary Judge is Qwen3.7-Plus. DeepSeek-V4-Pro reviewed 300 stratified
answers and Kimi-K2.6 reviewed 100. Across 1,493 double-judged atoms:

| Agreement view | Exact agreement | Kappa |
|---|---:|---:|
| Overall verdict | 0.914 | 0.886 |
| Ordered usage level | 0.884 | 0.840 (linear weighted) |
| DeepSeek secondary | 0.918 | 0.893 |
| Kimi secondary | 0.899 | 0.867 |

Human expert validation remains pending. This is an internal diagnostic, not
a public leaderboard.

## Files and provenance

- `model-facing.jsonl(.gz)`, `hidden-evaluation.jsonl(.gz)`, and
  `sample-ids.txt`: exact locked evaluation sample;
- `metrics.json`: macro/micro, confusion, bootstrap, paired, panel, and
  Judge-agreement metrics;
- `report.html`: self-contained visual report;
- `thinking-audit.json`: per-cell answer count, finish-reason, reasoning, and
  credential-role audit;
- `glm52-thinking-budget-rescue.manifest.json`: two-row controlled-exception
  audit;
- request/run/release manifests: counts, configuration, and content hashes;
- sibling `memcalib-v21-multidomain-500-seven-models/`: non-thinking baseline
  for the seven shared models.

Raw answer responses, reasoning content, raw Judge responses, retries,
failures, and logs are retained under the gitignored local directory
`evaluation/runs/memcalib-v21-multidomain-500-thinking-eight-models/`.
Credentials are not stored in release artifacts.
