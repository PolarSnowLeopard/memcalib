# MemCalib SFT

> Historical experiment line: this workflow is tied to MemCalib v2.3 and is
> not part of the current v2.4 data release or leaderboard.

This directory contains the reproducible MemCalib v2.3 SFT split and target-generation workflow. The corresponding evaluation artifacts are archived under [`evaluation/archive/`](../evaluation/archive/).

The public student input must match evaluation-time input exactly: the answer system prompt, numbered model-facing memory blocks, and the current query. Hidden atomic labels, actions, rubrics, source answers, teacher reasoning, and judge outputs are construction-only artifacts and must never enter the student input.

## Locked split

- train: 12,000 records
- dev: 1,500 records
- test: 1,500 records
- the existing evaluated v2.3 500-record set is locked inside test
- pilot: 500 records selected only from train

The committed release contains only record IDs and a manifest. Full hidden records, API requests, responses, and SFT targets are local under `sft/runs/`.

## Target-generation stages

1. Prepare the fixed split and the selected train partition.
2. Generate privileged teacher requests with Qwen3.7-Max.
3. Judge generated answers with the existing ordered-usage protocol.
4. Admit only answers that pass target-quality and atom-level calibration checks.
5. Convert admitted answers to single-target ms-swift `messages` JSONL.

The source answer is supplied to the teacher only as a non-authoritative draft. It is not treated as ground truth.

## 500-record target pilot

The first train-only pilot completed on 2026-07-22:

- Qwen3.7-Max teacher API: 500/500 valid, all `finish_reason=stop`
- Qwen3.7-Plus primary judge: 500/500 structurally valid
- DeepSeek-V4-Pro secondary judge: 500/500 structurally valid
- primary-strict targets: 463/500
- dual-strict targets: 461/500 (92.2%)
- correction records: 11/11 dual-strict
- dual-strict by domain: health 237/250, general 108/125, coding 116/125
- dual-strict by difficulty: level 1 116/125, level 2 233/251, level 3 112/124

The dual-strict Swift file passed schema validation with exactly one system, user, and assistant message per record; only the assistant message has `loss=true`. Local target and judge artifacts are under `sft/runs/memcalib-v23-sft-pilot-500/`.

The pilot used about 3.54 million teacher tokens in total.

## 12,000-record train build

The full train target build completed on 2026-07-23. It reused the 500 pilot teacher and judge results by exact request fingerprint and called the APIs only for the remaining 11,500 records.

- Qwen3.7-Max teacher: 12,000/12,000 complete, all `finish_reason=stop`
- teacher usage: 62,187,747 prompt tokens, 21,971,482 completion tokens, 84,159,229 total tokens
- Qwen3.7-Plus primary judge: 12,000/12,000 structurally valid
- DeepSeek-V4-Pro secondary judge: 12,000/12,000 structurally valid
- one secondary API request required a targeted retry after a provider inspection failure
- primary-strict targets: 11,353/12,000
- dual-strict targets: 11,275/12,000 (93.96%)
- excluded with complete audit: 725/12,000
- correction records: 244/259 dual-strict
- dual-strict by domain: health 5,789/6,000, general 2,665/3,000, coding 2,821/3,000
- dual-strict by difficulty: level 1 2,822/3,000, level 2 5,652/6,002, level 3 2,801/2,998

The final local training file is `sft/runs/memcalib-v23-sft-train-12000/sft/swift-sft.dual-strict.jsonl`. It contains 11,275 unique records, is disjoint from the locked test partition, contains no hidden supervision fields, and has SHA-256 `3dada446798912fe79a76c194317625b646575be31d4eed08342489824ea1bdd`.

The corresponding rejected-target audit is `sft/runs/memcalib-v23-sft-train-12000/sft/target-admission.non-dual-strict.jsonl`. Reproduce or resume the build with `sft/scripts/run_memcalib_v23_sft_full.sh`; the workflow never resubmits a valid request.
