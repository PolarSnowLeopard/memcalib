# MemCalib v2.3 thinking vs non-thinking

This is a descriptive, same-sample comparison of answer-side thinking on the
locked MemCalib v2.3 500-record diagnostic set. The 500 model-facing rows,
full-memory/no-memory conditions, answer prompts, temperature, Judge prompts,
primary Judge, secondary Judges, and aggregation code are held fixed.

Eight Bailian models are the answer-mode contrast: thinking is enabled in one
run and disabled in the other. Codex GPT-5.6 Sol uses `reasoning_effort=none`
in both columns; its exact answers are reused in the non-thinking run. The
Codex row is therefore a repeated-Judge control, not a thinking effect.

The locked model-facing SHA-256 is
`84ae94bba9c01a2edaa91a1c5e25a1a5c7e5449306ff39530df474b1b7fea28d`.
The ordered sample-ID SHA-256 is
`0f167e665807f1ed4bbbb0ab9f9ef11f28fd7cd388edd4be1d67660b8aaba0bf`.

## Full-memory comparison

All deltas are `thinking - non-thinking`. Lower is better for OPB, UPB, and
CVaR90; higher is better for H, MinCalib, MCC, and PMU(1).

| Model | H non-think | H think | Delta H | Delta OPB | Delta UPB | Delta MinCalib | Delta MCC | Delta CVaR90 | Delta PMU(1) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| GLM-5.2 | 0.839 | 0.872 | +0.033 | -0.001 | -0.057 | +0.057 | +0.020 | -0.007 | +0.069 |
| Qwen3.7-Max | 0.838 | 0.870 | +0.032 | +0.017 | -0.070 | +0.070 | +0.011 | +0.014 | +0.061 |
| DeepSeek-V4-Pro | 0.842 | 0.859 | +0.018 | +0.011 | -0.039 | +0.039 | +0.003 | +0.029 | +0.019 |
| Qwen3.5-35B-A3B | 0.849 | 0.853 | +0.004 | -0.012 | +0.002 | -0.002 | +0.017 | -0.023 | +0.016 |
| DeepSeek-V4-Flash | 0.834 | 0.850 | +0.016 | +0.002 | -0.028 | +0.028 | +0.018 | +0.013 | +0.023 |
| Qwen3.6-Flash | 0.836 | 0.837 | +0.001 | -0.016 | +0.010 | -0.010 | +0.025 | -0.004 | -0.003 |
| Kimi-K2.6 | 0.837 | 0.828 | -0.009 | -0.006 | +0.019 | -0.019 | +0.000 | -0.020 | -0.020 |
| Qwen3-8B | 0.657 | 0.760 | +0.103 | +0.019 | -0.137 | +0.137 | +0.041 | -0.004 | +0.103 |
| Codex GPT-5.6 Sol control | 0.797 | 0.801 | +0.004 | +0.001 | -0.006 | +0.006 | +0.005 | -0.000 | +0.003 |

Across the eight Bailian models, H improves for seven and declines for one.
The mean delta is +0.0247 and the median is +0.0168, but the mean is strongly
influenced by Qwen3-8B (+0.1025). Thinking does not uniformly improve every
dimension: OPB changes are nearly centered on zero, while the median UPB
change is -0.0336. This pattern is more consistent with improved use of
relevant memory than with uniformly better suppression.

The Codex control changes by +0.0037 H despite identical answer files. This
quantifies the scale of repeated automated-Judge variation in these two runs
and is a reason not to over-interpret very small answer-mode deltas. The table
is descriptive; a paired answer-mode bootstrap or human adjudication is still
required for significance claims.

## Completion and Judge stability

Each run contains 9,000 answers, 9,000 normalized primary judgments, and 450
normalized secondary judgments. Residual API failures and structural invalids
are zero after targeted retries. Primary-versus-secondary exact agreement is
0.9736 with Cohen kappa 0.9210 for the thinking run, and 0.9753 with kappa
0.9259 for the non-thinking run.

## Source artifacts

- [Thinking release](../../releases/memcalib-v23-multidomain-500-nine-models/README.md)
- [Non-thinking release](../../releases/memcalib-v23-multidomain-500-nonthinking-nine-models/README.md)
- [Thinking candidate metrics](../memcalib-v23-multidomain-500-nine-models-candidate-metrics/README.md)
- [Non-thinking candidate metrics](../memcalib-v23-multidomain-500-nonthinking-nine-models-candidate-metrics/README.md)
- [Thinking diagnostics](../memcalib-v23-multidomain-500-nine-models-candidate-metrics/candidate-metric-diagnostics.html)
- [Non-thinking diagnostics](../memcalib-v23-multidomain-500-nonthinking-nine-models-candidate-metrics/candidate-metric-diagnostics.html)
