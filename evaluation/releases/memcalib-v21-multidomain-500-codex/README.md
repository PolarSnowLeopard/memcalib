# MemCalib v2.1 Codex GPT-5.6 Sol diagnostic

This release evaluates the Codex-hosted `gpt-5.6-sol` model on exactly the
same locked 500 MemCalib v2.1 records used by the seven-model diagnostic.
It is an answer-only, paired full-memory/no-memory evaluation.

## Comparability controls

- exact model-facing sample SHA-256:
  `1e37ba0435f2ceb65d369c817660b0822c934d8318823c402fc657453ac127d8`;
- exact hidden-evaluation SHA-256:
  `2fca7b2a75a9b8f4f0fb0386a9ea1ef1b0d4e59173f84fa864d90372e77993e0`;
- exact ordered sample-ID SHA-256:
  `92292219c596e790720456754376354be30c5954bf7875085594fbce40c52d29`;
- 500 health/general/coding records in the same 250/125/125 order;
- separate ephemeral Codex session and empty temporary workspace per answer;
- `reasoning_effort=none`, with zero reasoning output tokens in all 1,000
  formal answers;
- user configuration and project rules ignored, read-only sandbox, and no
  tool events in any formal answer;
- the same answer instruction, full/no-memory conditions, primary Judge,
  secondary Judge sampling, Judge prompt, and aggregate metrics as the
  seven-model baseline.

Codex still injects its own fixed system context, and the CLI does not expose
the same explicit temperature and output-token controls used by the Bailian
Chat Completions runs. Therefore this is a controlled proxy for direct
GPT-5.6 evaluation, not a direct OpenAI API measurement.

## Completeness

The run contains 500 valid full-memory and 500 valid no-memory answers. All
1,000 request IDs are unique, all input fingerprints match, all finish
reasons are `stop`, and there are no missing, duplicate, truncated, reasoning,
or tool-using answers.

Qwen3.7-Plus judged all 1,000 answers. One malformed Judge response was retried
by request ID; the 999 valid original rows were not rerun. DeepSeek-V4-Pro
independently reviewed 50 stratified answers. The final normalized artifacts
contain 1,000 primary and 50 secondary judgments with no residual structural
invalid rows.

## Results

| Condition | Macro OPB | Macro UPB | Macro H | Micro OPB | Micro UPB | Micro H |
|---|---:|---:|---:|---:|---:|---:|
| Full memory | 0.212 | 0.294 | 0.745 | 0.200 | 0.297 | 0.748 |
| No memory | 0.024 | 0.918 | 0.151 | 0.023 | 0.918 | 0.152 |

The macro full-memory H 95% sample-cluster bootstrap interval is
`[0.726, 0.764]`. Full-memory strict sample accuracy is 0.270, mean task
quality is 3.264/4, and the safety-failure rate is 0.008.

Across 185 double-judged atoms, overall exact agreement is 0.924 and Cohen
kappa is 0.894. Ordered usage-level agreement is 0.897 with linearly weighted
kappa 0.837.

Macro OPB and UPB first compute error rates within each gold label and then
average the relevant labels. The supplemental micro definitions are:

```text
micro OPB = (A->B + A->C + B->C) / (gold A + gold B)
micro UPB = (B->A + C->A + C->B) / (gold B + gold C)
micro H   = harmonic_mean(1 - micro OPB, 1 - micro UPB)
```

## Files

- `answer-request.manifest.json` and `answer-run.manifest.json`: exact request
  hashes, completeness, model settings, token use, and output hashes;
- `judge-request.manifest.json` and `judge-run.manifest.json`: Judge coverage,
  stratified secondary sampling, structural retry, warnings, and hashes;
- `metrics.json`: full macro/micro, confusion, panel, paired, bootstrap, and
  Judge-agreement metrics;
- `report.html`: self-contained visual report.

The exact locked sample remains in the sibling
`memcalib-v21-multidomain-500-seven-models` release and is duplicated in the
combined eight-model release. Raw answers, raw Judge outputs, and retry audit
rows remain in the gitignored local run directory.
