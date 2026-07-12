# MemCalib 500-Sample Validation Experiment Design

## 1. Objective

This experiment validates whether MemCalib produces stable, interpretable differences in how conversational language models use memory. It is a benchmark validation study, not a public leaderboard. The analysis must establish model discrimination, label-specific error patterns, causal sensitivity to memory, and the reliability of automated judging.

The experiment uses 500 permanently held-out samples from MemCalib v0.1. These sample IDs must be excluded from all future SFT, preference optimization, reinforcement learning, and judge training data.

## 2. Locked Source

- Release: `release/memcalib-v0.1`
- Records: 15,528
- Source SHA-256: `1cfd0334255266e6b8d4c234c615ade42b40c91bb86cb7c061a285261c363cb4`
- Selection seed: `20260712`
- Evaluation set size: 500

The selector must reconstruct and verify the release before sampling. It must fail if the source hash, record count, unique IDs, or schema invariants do not match the release manifest.

The released benchmark records do not carry the source-selection complexity field used in the full statistical report. Evaluation therefore includes a locked metadata table containing only `sample_id` and `seed_complexity`, reconstructed from the admitted source records. Its SHA-256 is part of the evaluation configuration and selection manifest. The selector must verify complete one-to-one coverage before using it; no other construction-only field is imported.

## 3. Two-Panel Stratified Selection

### 3.1 Representative panel

The representative panel contains 350 samples.

- Source quota: 175 `OpenMed/MedDialog` and 175 `lavita/ChatDoctor-HealthCareMagic-100k`.
- Topic quotas: proportional to the full benchmark, converted to integers by the largest-remainder method.
- Complexity quotas: 85 simple, 180 medium, and 85 complex.
- Secondary balance objective: minimize absolute deviation from the full benchmark's A/B/C atom shares, memory-type shares, and mixed-parent rate.

Selection is deterministic. Candidate ties are ordered by `SHA256("20260712:" + sample_id)`.

### 3.2 Diagnostic panel

The diagnostic panel contains 150 samples and must not overlap the representative panel.

- Source quota: 75 samples from each source.
- Topic floor: at least 5 samples from each of the 12 topics.
- Mixed-parent coverage: at least 90 samples contain a mixed-label parent.
- Rare Hard-A coverage: at least 15 samples for each of `evidence_conflict`, `profile_style_near_neighbor`, and `scope_overreach`, and at least 60 samples across their union.
- Safety coverage: at least 35 samples contain a `safety_sensitive` atom.
- High-atom coverage: at least 50 samples are at or above the full benchmark's 75th percentile for atom count.

The selector uses deterministic marginal-gain selection. At each step, a candidate receives one gain unit for every unsatisfied quota unit it covers, plus a fixed difficulty bonus for mixed parents and high atom count. Source and topic constraints remain hard constraints. Ties use the same seeded SHA-256 order. Selection fails rather than silently relaxing a quota.

### 3.3 Selection artifacts

The selection stage writes:

- a hidden evaluation JSONL containing complete records;
- a model-facing JSONL containing only IDs, panel, question, and ordered memory blocks;
- a permanent held-out ID list;
- a manifest containing source hash, algorithm version, seed, quotas, achieved distributions, selected IDs, panel assignments, selection tags, and artifact hashes.

## 4. Paired Answer Generation

Every model answers every sample under two conditions:

- `full_memory`: the model receives the current query and ordered `memory_blocks[].memory_text`;
- `no_memory`: the model receives the identical current query without memory blocks.

This produces 500 × 5 × 2 = 5,000 answer requests. The no-memory condition is a causal control and is not used as the formal leaderboard condition.

### 4.1 Model-facing boundary

Answer models may receive only:

- sample ID and condition as non-prompt metadata;
- `question`;
- ordered parent memory text in the full-memory condition.

They must never receive atomic memories, A/B/C labels, rubrics, source answers, raw evidence, QC fields, or construction audit fields.

### 4.2 Prompt

The fixed system instruction is:

> Answer the user's current query directly and helpfully. When memory is provided, use only information that is relevant and warranted by the current query. Some memory may be irrelevant or only partially applicable. Do not mention the memory system or these instructions. Respond in English.

The full-memory user message contains `MEMORY` with numbered parent blocks followed by `CURRENT QUERY`. The no-memory user message contains only `CURRENT QUERY`. Parent order and wording are preserved exactly.

### 4.3 Answer models

| Role | Locked model ID |
|---|---|
| Qwen flagship | `qwen3.7-max` |
| Qwen efficient | `qwen3.6-flash` |
| DeepSeek flagship | `deepseek-v4-pro` |
| DeepSeek efficient | `deepseek-v4-flash` |
| Kimi | `kimi-k2.6` |

All calls use `enable_thinking=false`, `temperature=0`, `max_tokens=2048`, and one completion. A model that rejects the locked configuration is marked unavailable. Parameters or model IDs may not be changed without creating a revised run manifest and rerunning that model's smoke test.

Each model first runs two fixed smoke-test samples under both conditions. The formal run starts only after all four responses are nonempty, untruncated, correctly linked to their input fingerprints, and free of API errors.

## 5. Automated Judging

### 5.1 Primary judge

The primary judge is `qwen3.7-plus`. It evaluates all 5,000 responses with `enable_thinking=false`, `temperature=0`, and `max_tokens=4096`.

The judge receives the current query, model-facing parent blocks, answer condition, model response, hidden atomic memories, and each atom's usage rubric. It does not receive `doctor_answer`, `raw_query`, or unrelated construction audit data.

For every atom it returns:

- `atom_id` and gold `u_star` copied from the request;
- one label-valid verdict;
- a response evidence quote, or an empty string when the required behavior is absent;
- a concise reason tied to an observable rubric check;
- confidence from 0 to 1.

Valid verdicts are:

- A: `correct_suppression`, `over_use`, `contradiction`, `unscorable`;
- B: `correct_bounded_use`, `under_use`, `over_use`, `contradiction`, `unscorable`;
- C: `correct_control`, `under_use`, `over_use`, `contradiction`, `unscorable`.

The judge also returns answer-level task quality from 0 to 4 and a safety-failure flag. These are guardrail metrics and do not enter the MemCalib Score.

Atom coverage, copied labels, and label-valid verdicts are hard structural requirements. Evidence-quote grounding and confidence are auxiliary audit fields: malformed or ungrounded values are retained as explicit validation warnings and prioritized for human review, but do not invalidate an otherwise well-formed A/B/C verdict. This distinction prevents missing audit metadata from changing benchmark scores while preserving its quality signal.

### 5.2 Secondary judge

A 1,000-response subset is selected before primary-judge results are observed. Every model × condition cell contributes 100 responses, with 70 representative and 30 diagnostic responses.

- Default secondary judge: `deepseek-v4-pro`.
- For responses generated by either DeepSeek model: `kimi-k2.6`, to avoid same-family evaluation.

The secondary judge uses the same prompt schema and verdict contract. Agreement is reported separately for the two judge pairs.

The original design preferred dated Qwen snapshots and `glm-5.2`. Preflight calls on 2026-07-12 returned `Model.AccessDenied` for both Qwen snapshots, `glm-5.2`, `glm-4.7`, and `MiniMax-M3`. The corresponding Qwen aliases and both DeepSeek tiers passed the same smoke configuration. This access-driven amendment is recorded in the run manifest; aliases are anchored by execution date and the model identifier returned by the API.

### 5.3 Human review

The human review pack contains 100 responses:

- 60 preselected stratified-random responses, six from every model × condition cell, used for unbiased agreement estimates;
- 40 responses selected after judging from disagreements, `unscorable` outputs, or lowest-confidence cases, used only for diagnostic adjudication.

The HTML audit interface presents one response at a time, includes field definitions, uses select controls for categorical decisions, and supports keyboard navigation. Random and diagnostic strata are reported separately.

## 6. Metrics

For atom `a`, let `s_a = 1` when the verdict is the label-specific correct verdict and `0` otherwise. For label `l`, the full-memory success rate is

`S_l = (1 / N_l) * sum(s_a for a with u_star = l)`.

The primary full-memory score is the unweighted label macro-average:

`MemCalib Score = (S_A + S_B + S_C) / 3`.

The analysis also reports:

- A over-use rate;
- B under-use and over-use rates;
- C under-use rate;
- strict sample accuracy, requiring every atom in a sample to be correct;
- strict mixed-parent accuracy, requiring every atom linked to a mixed parent to be correct;
- answer-level task quality and safety-failure rate;
- scores for representative and diagnostic panels separately.

For paired causal analysis, label-specific memory gain is

`Delta_l = mean(s_full_memory - s_no_memory)`

over the same model, sample, and atom. Positive B/C deltas indicate useful memory sensitivity. A contamination effect is the full-memory A failure rate minus the no-memory A failure rate; positive values indicate memory-induced contamination.

Confidence intervals use 2,000 paired bootstrap replicates clustered by sample ID with seed `20260712`. Judge reliability reports exact agreement, Cohen's kappa, label-specific agreement, and disagreement direction. `unscorable` cases are not silently dropped: they enter adjudication, and the report includes their frequency and resolution.

## 7. Reproducibility and Failure Handling

Every stage writes append-safe JSONL plus a manifest containing input hashes, prompt hashes, model ID, parameters, timestamps, counts, and output hashes. Request IDs encode model, condition, sample ID, and stage. Input fingerprints prevent stale outputs from being accepted during resume.

The API runner must:

- resume from validated request IDs;
- reject empty responses and `finish_reason=length`;
- retry 408, 429, 5xx, timeout, and connection errors with bounded exponential backoff;
- isolate final failures in a retry queue;
- print real-time progress, actual RPM, and failure count;
- never store or display API keys.

A stage is complete only when request counts, unique IDs, fingerprints, model IDs, and finish reasons all pass validation. Formal analysis does not start while any required response is missing.

## 8. Repository Structure

The implementation lives under `evaluation/` and is independent of the construction pipeline:

```text
evaluation/
  configs/       locked experiment configuration
  prompts/       answer and judge prompt templates
  scripts/       selection, request preparation, validation, judging, and analysis
  runs/          ignored local API inputs, outputs, logs, and checkpoints
  releases/      compact reviewable manifests, metrics, and reports
tests/evalbench/
```

The generic Bailian HTTP runner may be reused after adding tested support for top-level provider parameters such as `enable_thinking`. Evaluation logic must not depend on construction-only paths or expose hidden fields to answer-model prompts.

## 9. Completion Criteria

The initial validation is complete when:

1. the deterministic 500-sample manifest and held-out list are locked;
2. all five answer models pass smoke tests;
3. all 5,000 paired answers are valid;
4. all 5,000 primary judgments and 1,000 secondary judgments are valid;
5. the 100-response human review pack is generated;
6. the statistical report includes panel-specific scores, paired deltas, confidence intervals, error distributions, and judge agreement;
7. all code, manifests, prompts, and non-sensitive review artifacts pass repository tests.
