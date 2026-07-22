# MemCalib v2.3 non-thinking nine-model control

This companion run uses the exact locked v2.3 500-record sample from the
thinking evaluation. Eight Bailian models have answer-side thinking disabled.
Codex GPT-5.6 Sol remains at `reasoning_effort=none`; its exact answer files are
reused, so its row is a repeated-Judge control rather than an answer-mode
contrast. All Judges also have thinking disabled.

## Headline results

| Model | Full OPB down | Full UPB down | Full H up | No-memory H |
|---|---:|---:|---:|---:|
| Qwen3.5-35B-A3B | 0.098 | 0.198 | 0.849 | 0.196 |
| DeepSeek-V4-Pro | 0.082 | 0.223 | 0.842 | 0.211 |
| GLM-5.2 | 0.079 | 0.230 | 0.839 | 0.223 |
| Qwen3.7-Max | 0.074 | 0.235 | 0.838 | 0.224 |
| Kimi-K2.6 | 0.069 | 0.239 | 0.837 | 0.187 |
| Qwen3.6-Flash | 0.094 | 0.224 | 0.836 | 0.195 |
| DeepSeek-V4-Flash | 0.068 | 0.245 | 0.834 | 0.192 |
| Codex GPT-5.6 Sol control | 0.045 | 0.316 | 0.797 | 0.165 |
| Qwen3-8B | 0.038 | 0.501 | 0.657 | 0.129 |

Across the eight Bailian models, answer-side thinking changes full-memory H by
-0.009 to +0.103. Seven models improve and one declines. The median change is
+0.0168; the largest change is Qwen3-8B. OPB does not move uniformly, while
UPB usually falls, indicating that thinking mainly changes how strongly models
use relevant memory. See the comparison report for the full multi-metric view
and interpretation limits.

## Completeness and audit

- Answers: 9,000/9,000.
- Primary Judge: 9,000/9,000 normalized rows.
- Secondary Judges: 450/450 normalized rows.
- Initial primary structural valid/invalid: 8,978/22.
- Targeted structural retry: 22/22 valid; residual invalid 0.
- Judge exact agreement: 0.9753; Cohen kappa: 0.9259.
- Ordered-usage exact agreement: 0.9670; linear weighted kappa: 0.8765.

The Qwen3.5-35B-A3B answer cells required targeted retries after length and
rate-limit failures. All successful rows were preserved, only missing IDs were
retried, and the final answer set is complete and fingerprint-validated.

## Files

- [Visual report](report.html)
- [Machine-readable metrics](metrics.json)
- [Answer run manifest](answer-run.manifest.json)
- [Judge run manifest](judge-run.manifest.json)
- [Candidate metric study](../../analyses/memcalib-v23-multidomain-500-nonthinking-nine-models-candidate-metrics/README.md)
- [Thinking versus non-thinking comparison](../../analyses/memcalib-v23-thinking-vs-nonthinking/README.md)
