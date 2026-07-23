# MemCalib v2.3 Qwen3.5-35B-A3B Base versus SFT pilot

This release compares the base Qwen3.5-35B-A3B checkpoint with the checkpoint
obtained from the MemCalib SFT pilot. Both checkpoints were served through vLLM
with non-thinking decoding and evaluated on the same completed Full-memory
records.

## Paired cohort

- The source evaluation sample contains 500 locked MemCalib v2.3 records.
- Each checkpoint returned 498 valid Full-memory answers.
- The two missing sets differ, so the strict intersection contains 496 records.
- The four non-common records were excluded from both sides. They were not
  regenerated, following the decision to use the completed outputs as-is.
- Both imported answer files have unique request and sample IDs, matching input
  fingerprints, nonempty responses, `finish_reason=stop`, and no observable
  reasoning content or `<think>` blocks.
- Base responses identify the served model as `qwen35-a3b-base-vllm`; SFT
  responses identify the cluster service alias as `med_chat`. The analysis
  retains the stable experiment key `qwen35-a3b-sft-vllm`.

The ordered common sample IDs and all omissions are recorded in
[`paired-answer-import.manifest.json`](paired-answer-import.manifest.json).

## Evaluation protocol

- Condition: Full-memory only.
- Primary Judge: Qwen3.7-Plus, temperature 0, thinking disabled.
- Secondary Judge: DeepSeek-V4-Pro on 25 stratified answers per checkpoint.
- Primary judgments: 992/992 valid after four targeted structural retries.
- Secondary judgments: 50/50 valid without structural retry.
- Residual structural invalid: 0.
- Ordered-usage agreement over 893 double-judged atoms: exact 0.9664, linear
  weighted kappa 0.9212.

No No-memory answers were generated. PMU, memory-induced OPB, and
memory-reduced UPB therefore remain intentionally uncomputed.

## Results

| Metric | Base | SFT | Preferred direction |
|---|---:|---:|---|
| OPB error | 0.104 | **0.029** | lower |
| UPB error | **0.201** | 0.284 | lower |
| H | **0.845** | 0.824 | higher |
| MinCalib | **0.799** | 0.716 | higher |
| Multiclass MCC | 0.557 | **0.752** | higher |
| Linear weighted kappa | 0.558 | **0.782** | higher |
| Strict sample accuracy | 0.107 | **0.387** | higher |
| SCS(0.5) | 0.235 | **0.570** | higher |
| Any A-to-C or C-to-A sample | 0.651 | **0.244** | lower |
| Mean normalized ordinal loss | 0.130 | **0.049** | lower |
| CVaR90 sample loss | 0.359 | **0.197** | lower |

The SFT checkpoint became substantially more conservative: A-label success
rose from 0.851 to 0.981, while B and C success fell from 0.701/0.837 to
0.604/0.790. This reduces OPB but increases UPB, so the directional harmonic
score H decreases by 0.020 even though atom classification, strict whole-sample
correctness, severe-error rate, mean sample loss, and tail risk improve.

On paired normalized sample loss, SFT is better on 371 records, tied on 78, and
worse on 47. Its tie-adjusted win share is 0.827. The Base-minus-SFT mean loss
difference is 0.0804 with a paired sample-bootstrap 95% interval of
[0.0709, 0.0896]. This supports a real reduction in aggregate ordinal error,
but does not remove the observed SFT under-use bias.

The sample-level calibration score tells the same aggregate-error story more
directly. For each answer, all one-step ordered A/B/C errors are added to an
error budget; an A-to-C or C-to-A error adds two units. The answer receives
`SCS_rho = rho^budget`, and answers are then averaged with equal weight.
At the fixed primary setting `rho=0.5`, SCS rises from 0.2348 to
0.5704. The sensitivity values for `rho=0.25/0.5/0.75` are
0.1430/0.2348/0.4519 for Base and 0.4600/0.5704/0.7393 for SFT. Any-OPB
sample incidence falls from 83.3% to 24.2%, while any-UPB incidence rises
from 37.1% to 50.4%. SCS therefore complements, rather than replaces, the
directional OPB and UPB rates.

## Interpretation boundary

This is a 496-record, two-checkpoint pilot, not a five-model benchmark validity
study or a public leaderboard. The repository's automatic validity gate
therefore reports `needs_review` only because fewer than five models are
present. Judge agreement passes its configured thresholds.

H and MinCalib preserve the OPB-versus-UPB policy balance and correctly expose
the SFT checkpoint's increased under-use. MCC, kappa, strict sample accuracy,
and CVaR answer different questions and show that the SFT checkpoint makes far
fewer total and severe ordinal mistakes. Both views must be reported.

## Files

- [Visual report](report.html)
- [Machine-readable official metrics](metrics.json)
- [Paired answer import manifest](paired-answer-import.manifest.json)
- [Judge request manifest](judge-request.manifest.json)
- [Judge run manifest](judge-run.manifest.json)
- [Compressed hidden evaluation subset](hidden-evaluation.jsonl.gz)
- [Compressed model-facing subset](model-facing.jsonl.gz)
- [Candidate metric study](../../analyses/memcalib-v23-sft-base-full-only-paired-candidate-metrics/README.md)
- [Tail, Pareto, and rank diagnostics](../../analyses/memcalib-v23-sft-base-full-only-paired-candidate-metrics/candidate-metric-diagnostics.html)
- [Sample-level SCS analysis](../../analyses/memcalib-v23-sft-base-full-only-paired-sample-level/README.md)
- [Sample-level SCS distributions](../../analyses/memcalib-v23-sft-base-full-only-paired-sample-level/sample-level-score-distributions.html)

Raw cluster answers, raw Judge API outputs, targeted retry artifacts, and
normalized per-answer judgments remain in the local ignored
`evaluation/runs/memcalib-v23-sft-base-full-only-paired/` directory.
