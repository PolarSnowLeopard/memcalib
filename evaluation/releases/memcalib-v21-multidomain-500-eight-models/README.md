# MemCalib v2.1 eight-model same-sample diagnostic

This directory is the current 500-record MemCalib v2.1 comparison. It adds
Codex GPT-5.6 Sol to the exact locked sample and unchanged seven-model
baseline.

## Locked comparison

- benchmark SHA-256:
  `bd45f77534351cd096476080096ce9ba6250a375941a171ab561ad78704bed44`;
- model-facing SHA-256:
  `1e37ba0435f2ceb65d369c817660b0822c934d8318823c402fc657453ac127d8`;
- hidden-evaluation SHA-256:
  `2fca7b2a75a9b8f4f0fb0386a9ea1ef1b0d4e59173f84fa864d90372e77993e0`;
- ordered sample-ID SHA-256:
  `92292219c596e790720456754376354be30c5954bf7875085594fbce40c52d29`;
- 500 records: health 250, general 125, coding 125;
- 556 A, 635 B, and 570 C hidden atoms;
- paired full-memory and no-memory answers for every model.

The original seven-model answers and judgments are unchanged. Only the Codex
cell was generated and judged, then merged by unique answer request ID.

## Full-memory results

| Model | Macro OPB | Macro UPB | Macro H | Micro OPB | Micro UPB | Micro H | Macro H 95% CI |
|---|---:|---:|---:|---:|---:|---:|---:|
| Codex GPT-5.6 Sol | 0.212 | 0.294 | 0.745 | 0.200 | 0.297 | 0.748 | [0.726, 0.764] |
| Kimi-K2.6 | 0.311 | 0.196 | 0.742 | 0.294 | 0.198 | 0.751 | [0.725, 0.760] |
| DeepSeek-V4-Pro | 0.383 | 0.193 | 0.699 | 0.362 | 0.194 | 0.712 | [0.682, 0.716] |
| Qwen3.7-Max | 0.384 | 0.201 | 0.696 | 0.363 | 0.204 | 0.708 | [0.679, 0.712] |
| DeepSeek-V4-Flash | 0.393 | 0.199 | 0.691 | 0.370 | 0.202 | 0.704 | [0.675, 0.706] |
| Qwen3.6-Flash | 0.394 | 0.201 | 0.689 | 0.372 | 0.202 | 0.703 | [0.673, 0.706] |
| Qwen3.5-35B-A3B | 0.414 | 0.176 | 0.685 | 0.390 | 0.178 | 0.701 | [0.670, 0.701] |
| Qwen3-8B | 0.251 | 0.452 | 0.633 | 0.237 | 0.455 | 0.636 | [0.611, 0.655] |

Codex and Kimi are statistically close: their macro-H intervals strongly
overlap. Macro H places Codex 0.0026 above Kimi, while the coauthor-requested
micro H places Kimi 0.0025 above Codex. The defensible conclusion is a near
tie with different over-use/under-use tradeoffs, not a reliable rank-1 claim.

## No-memory counterfactual

| Model | Macro OPB | Macro UPB | Macro H |
|---|---:|---:|---:|
| DeepSeek-V4-Flash | 0.047 | 0.902 | 0.177 |
| DeepSeek-V4-Pro | 0.052 | 0.907 | 0.170 |
| Qwen3.7-Max | 0.057 | 0.910 | 0.164 |
| Kimi-K2.6 | 0.048 | 0.913 | 0.160 |
| Qwen3.5-35B-A3B | 0.055 | 0.913 | 0.159 |
| Qwen3.6-Flash | 0.065 | 0.915 | 0.155 |
| Codex GPT-5.6 Sol | 0.024 | 0.918 | 0.151 |
| Qwen3-8B | 0.024 | 0.944 | 0.105 |

No-memory is a paired counterfactual baseline rather than a separate
leaderboard.

## Judge stability

The merged primary Judge covers 8,000 answers. The merged secondary set
contains 400 stratified answers: 300 reviewed by DeepSeek-V4-Pro and 100 by
Kimi-K2.6. Across 1,494 double-judged atoms:

| Agreement view | Exact agreement | Kappa |
|---|---:|---:|
| Overall verdict | 0.902 | 0.868 |
| Ordered usage level | 0.865 | 0.808 (linear weighted) |

Human expert validation remains pending, so this is an internal diagnostic,
not a public leaderboard.

## Codex fairness controls and residual confounds

Codex used `gpt-5.6-sol`, `reasoning_effort=none`, one ephemeral session per
answer, empty temporary workspaces, a read-only sandbox, ignored user config
and project rules, structured answer-only output, and audited zero tool
events. All 1,000 answers also report zero reasoning output tokens.

The Codex host still supplies fixed system context, and its CLI does not expose
the same explicit temperature and max-output-token controls as the Bailian
Chat Completions interface. The row should therefore be described as
"Codex GPT-5.6 Sol, answer-only configuration", not as a direct OpenAI API
GPT-5.6 result.

## Qwen3.8-Max availability check

`qwen3.8-max` was requested as an additional cell. On 2026-07-20, both
configured Bailian credentials returned HTTP 404 `model_not_found`, and the
public Bailian text-model catalog did not list that model ID. No formal
Qwen3.8-Max answers were generated, and it is not included in the table.

## Files and provenance

- `model-facing.jsonl(.gz)`, `hidden-evaluation.jsonl(.gz)`, and
  `sample-ids.txt`: the exact locked sample;
- `metrics.json`: eight-model macro/micro, confusion, bootstrap, paired, panel,
  and Judge-agreement metrics;
- `report.html`: self-contained eight-model visual report;
- sibling `memcalib-v21-multidomain-500-seven-models/`: unchanged baseline
  request/run manifests;
- sibling `memcalib-v21-multidomain-500-codex/`: Codex request/run manifests
  and one-model report.

Raw answers and raw Judge responses remain in gitignored local run directories;
credentials are not stored in any release artifact.
