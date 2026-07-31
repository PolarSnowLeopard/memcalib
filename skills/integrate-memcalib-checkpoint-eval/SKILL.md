---
name: integrate-memcalib-checkpoint-eval
description: Integrate MemCalib evaluation into model training or checkpoint workflows, including periodic evaluation on a selected sample release, Full-memory and No-memory inference, Non-Think validation, primary-Judge scoring, sample-level SCS/sOPB/sUPB/Exact metrics, and TensorBoard export. Use when Codex needs to add automated checkpoint evaluation, training-time benchmark curves, or adapt the repository's current MemCalib evaluation scripts to another trainer or cluster.
---

# Integrate MemCalib Checkpoint Evaluation

Add a small, runnable evaluation hook around the existing MemCalib scripts.
Adapt paths and launch commands to the target trainer; do not rebuild the
benchmark implementation unless required.

## Inspect Before Editing

1. Find the training entry point, checkpoint save callback, global step, DDP
   rank, and TensorBoard log directory.
2. Ask which MemCalib release to use if it is not explicit. The dataset changes
   frequently, so do not assume a particular version.
3. Locate the current answer runner, Judge scripts, metric script, prompts, and
   selected model-facing/hidden evaluation files. Read
   [references/current-repository-workflow.md](references/current-repository-workflow.md).
4. Decide how checkpoint inference will run:
   - use a separate evaluation worker/node when available;
   - otherwise run evaluation after saving a checkpoint or after training.

## Build the Minimal Integration

Use rank 0 to trigger evaluation every configured number of steps:

```python
if rank == 0 and global_step % memcalib_eval_steps == 0:
    save_checkpoint(global_step)
    launch_memcalib_eval(
        checkpoint=checkpoint_path,
        step=global_step,
        log_dir=tensorboard_log_dir,
    )
```

Prefer launching a subprocess or scheduler job so training can continue. A
synchronous call is acceptable for a pilot.

Pass these values to the evaluator:

- checkpoint path;
- global step;
- model key and display name;
- inference endpoint or server launch command;
- selected MemCalib release/config;
- TensorBoard log directory.

Use a simple per-step output directory and a `completed` file. If that file
exists, skip the checkpoint. Existing valid JSONL outputs should be resumed
rather than regenerated.

See [references/simple-integration.md](references/simple-integration.md) for a
minimal shell/Python layout.

## Run One Checkpoint

For each checkpoint:

1. Start or connect to its OpenAI-compatible inference service.
2. Run a small smoke request set.
3. Generate answers for `full_memory` and `no_memory`.
4. Validate row counts, unique request IDs, nonempty responses, and Non-Think
   output. Preserve failure files and retry only missing rows.
5. Prepare primary-Judge requests from the hidden evaluation file.
6. Run the configured primary Judge with temperature 0.
7. Postprocess Judge output. Retry only structurally invalid rows.
8. Compute sample-level metrics.
9. Write the main metrics to TensorBoard at the checkpoint's training step.
10. Write the `completed` file.

Use the same sample release, prompts, generation mode, and Judge for checkpoints
shown on one curve. If the data release changes, start a new run name or
TensorBoard prefix.

## Keep the Evaluation Comparable

Keep only these practical checks:

- evaluate the same selected samples at every checkpoint;
- use both Full-memory and No-memory;
- disable thinking consistently;
- use configurable model names rather than hard-coded baseline names;
- do not silently treat failed or truncated outputs as valid;
- do not rerun already valid request IDs;
- report how many samples were scored.

Aim for the full selected release, normally a 500-sample pilot. If a few rows
cannot be recovered, use one common retained sample set for checkpoint
comparisons and log its size.

## Export TensorBoard Metrics

The metric script produces `sample-level-metrics.json`. Export it with:

```bash
python3 scripts/export_tensorboard.py \
  --metrics /path/to/sample-level-metrics.json \
  --step 200 \
  --log-dir /path/to/training/tensorboard \
  --model-key checkpoint-200 \
  --expected-samples 500 \
  --dry-run
```

Remove `--dry-run` after checking the tags. Main tags:

- `memcalib/full_memory/scs_rho_0_5` — higher is better;
- `memcalib/full_memory/sopb_rho_0_5` — lower is better;
- `memcalib/full_memory/supb_rho_0_5` — lower is better;
- `memcalib/full_memory/exact` — higher is better;
- corresponding `no_memory` controls;
- sample coverage and mean error budgets.

Always use the training `global_step`, not evaluation completion time.

## Verify the Integration

Before handing it off:

1. Run one checkpoint end to end.
2. Confirm Full-memory and No-memory sample counts.
3. Confirm Non-Think validation passes.
4. Confirm primary Judge output and main metrics exist.
5. Open TensorBoard and confirm the point appears at the expected step.
6. Run the same command again and confirm valid answer/Judge rows are resumed.

Add queues, locks, retention policies, or multi-Judge release checks only when
the user's training platform actually needs them.
