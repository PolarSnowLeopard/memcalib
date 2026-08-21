# MemCalib v2.4.1 Benchmark Test (1,500)

This is the locked release candidate for the final MemCalib v2.4.1 benchmark
test set.

- records: 1,500
- health_seed / general / coding: 750 / 375 / 375
- historical evaluation anchor retained: 500 records
- newly selected records: 1,000
- duplicate normalized questions: 0
- overlap with SFT or RL: 0
- model evaluation: completed for nine remote inference models and two local
  vLLM baselines, each with three Full-memory Non-Think generations

`model-facing.jsonl` contains only fields supplied to answer models.
`hidden-evaluation.jsonl` contains the complete scoring supervision and must not
be exposed to evaluated models. Exact hashes are recorded in
`release-manifest.json`.

The source split and selection audit are recorded in:

```text
sft/releases/memcalib-v241-sft4000-rl8000-test3000/split-manifest.json
```

The immutable release manifest records the selection-time evaluation status.
Current evaluation results are reported in:

```text
evaluation/current/v2.4.1/analyses/
  memcalib-v241-benchmark1500-nine-models-nonthinking-full-memory-three-seeds/
  memcalib-v241-local-baselines-1500-nonthinking-vllm/
```
