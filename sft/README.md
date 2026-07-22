# MemCalib SFT

This directory contains the reproducible MemCalib v2.3 SFT split and target-generation workflow.

The public student input must match evaluation-time input exactly: the answer system prompt, numbered model-facing memory blocks, and the current query. Hidden atomic labels, actions, rubrics, source answers, teacher reasoning, and judge outputs are construction-only artifacts and must never enter the student input.

## Locked split

- train: 12,000 records
- dev: 1,500 records
- test: 1,500 records
- the existing evaluated v2.3 500-record set is locked inside test
- pilot: 500 records selected only from train

The committed release contains only record IDs and a manifest. Full hidden records, API requests, responses, and SFT targets are local under `sft/runs/`.

## Pilot stages

1. Prepare the fixed split and 500-record pilot.
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

The pilot used about 3.54 million teacher tokens in total. Before generating targets for all 12,000 train records, train a small adapter on the 461 dual-strict records and verify directional improvement on the already evaluated 500-record locked test subset.
