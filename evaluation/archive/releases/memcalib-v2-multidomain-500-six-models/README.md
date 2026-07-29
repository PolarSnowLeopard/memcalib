# MemCalib v2 six-model comparison

This comparison evaluates six Model Studio models on the same deterministic
500-record MemCalib v2 sample. Every model has 500 `full_memory` answers and
500 paired `no_memory` answers.

## Full-memory ranking

Higher H is better. Lower OPB and UPB are better.

| Rank | Model | H | OPB | UPB |
|---:|---|---:|---:|---:|
| 1 | Kimi-K2.6 | 0.7339 | 0.3173 | 0.2065 |
| 2 | Qwen3.7-Max | 0.7285 | 0.3450 | 0.1795 |
| 3 | DeepSeek-V4-Pro | 0.7131 | 0.3676 | 0.1826 |
| 4 | Qwen3.6-Flash | 0.7058 | 0.3923 | 0.1585 |
| 5 | DeepSeek-V4-Flash | 0.7011 | 0.3867 | 0.1818 |
| 6 | Qwen3.5-35B-A3B | 0.6992 | 0.4042 | 0.1541 |

## Interpretation

Qwen3.5-35B-A3B is strongest at using relevant memory:

- Its UPB of 0.1541 is the lowest in the panel.
- Its C-label success of 0.9118 is the highest in the panel.
- Its safety failure rate of 0.024 is also the lowest.

Its overall H is limited by memory overuse:

- Its OPB of 0.4042 is the highest in the panel.
- Its A-label success is 0.2532, the lowest in the panel.
- Providing memory induces 0.3798 additional OPB relative to the paired
  no-memory condition.

The domain H scores are 0.7356 for coding, 0.6945 for general, and 0.6819 for
health. The aggregate judge exact agreement is 0.9365 with Cohen's kappa
0.9151. Ordered-usage exact agreement is 0.8976 with linear weighted kappa
0.8677.

## Evaluation volume

- Samples per model: 500
- Answer conditions per model: 2
- Primary judgments: 6,000
- Secondary judgments: 300
- Primary-scored atoms for Qwen3.5-35B-A3B: 3,546
- Structural invalid judgments for the added model: 0

The automated-judge result is provisionally supported. Human validation
remains pending, so this release should be treated as an internal diagnostic
rather than a definitive public leaderboard.

## Artifacts

- `metrics.json`: complete six-model metrics, panels, bootstrap intervals, and
  judge agreement
- `report.html`: visual six-model comparison

The source sample and original five-model manifests remain in
`evaluation/releases/memcalib-v2-multidomain-500/`. The added model's
answer/judge manifests are in
`evaluation/releases/memcalib-v2-multidomain-500-qwen35/`.
