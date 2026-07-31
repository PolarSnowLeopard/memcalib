# Simple Training Integration

## Recommended Layout

```text
memcalib_eval/
  eval_checkpoint.sh
  runs/
    step-000200/
      answers/
      judge-api/
      judgments/
      analysis/
      completed
```

Keep one directory per training step. Existing answer and Judge files provide
the resume state.

## Training Hook

Only rank 0 should launch evaluation:

```python
def maybe_run_memcalib(state):
    interval = state.args.memcalib_eval_steps
    if state.rank != 0 or interval <= 0 or state.global_step % interval:
        return

    checkpoint = save_checkpoint_and_return_path(state)
    command = [
        "bash",
        "memcalib_eval/eval_checkpoint.sh",
        checkpoint,
        str(state.global_step),
        state.tensorboard_log_dir,
    ]

    # Use Popen for a separate evaluation worker. Use run(..., check=True)
    # for a synchronous pilot.
    subprocess.Popen(command)
```

If the training machine has no spare evaluation GPUs, publish the checkpoint
path to the cluster scheduler instead of starting inference locally.

## Evaluation Script Shape

```bash
#!/usr/bin/env bash
set -euo pipefail

CHECKPOINT=$1
STEP=$2
TB_LOG_DIR=$3
RUN_ROOT="memcalib_eval/runs/step-$(printf '%06d' "$STEP")"

if [[ -f "$RUN_ROOT/completed" ]]; then
  echo "MemCalib step $STEP already completed"
  exit 0
fi

mkdir -p "$RUN_ROOT"

# 1. Start or connect to the checkpoint inference service.
# 2. Run the repository's answer runner for Full-memory and No-memory.
# 3. Prepare and run primary-Judge requests.
# 4. Postprocess judgments and run sample-level metric analysis.
# 5. Export TensorBoard scalars.

python3 /path/to/skill/scripts/export_tensorboard.py \
  --metrics "$RUN_ROOT/analysis/sample-level/sample-level-metrics.json" \
  --step "$STEP" \
  --log-dir "$TB_LOG_DIR" \
  --model-key "checkpoint-$STEP" \
  --expected-samples 500

date -Iseconds > "$RUN_ROOT/completed"
```

Replace the five comments with the current repository commands described in
`current-repository-workflow.md`.

## Suggested Configuration

Expose a small set of trainer or environment options:

```text
memcalib_eval_steps
memcalib_release
memcalib_config
memcalib_run_root
memcalib_tensorboard_log_dir
memcalib_answer_workers
memcalib_answer_rpm
memcalib_judge_workers
memcalib_judge_rpm
```

Do not expose every internal script option through the trainer. Put stable
evaluation settings in the selected MemCalib config.

## TensorBoard Tags

Use:

```text
memcalib/full_memory/scs_rho_0_5
memcalib/full_memory/sopb_rho_0_5
memcalib/full_memory/supb_rho_0_5
memcalib/full_memory/exact
memcalib/full_memory/any_opb
memcalib/full_memory/any_upb
memcalib/full_memory/mean_total_budget
memcalib/no_memory/scs_rho_0_5
memcalib/no_memory/sopb_rho_0_5
memcalib/no_memory/supb_rho_0_5
memcalib/no_memory/exact
memcalib/coverage/samples
memcalib/coverage/sample_fraction
```

TensorBoard is a summary view. Keep the JSONL answers, Judge outputs, and
machine-readable metrics in the per-step directory for later analysis.

## Common Failures

| Symptom | Action |
| --- | --- |
| Every DDP rank starts evaluation | Guard the hook with rank 0 |
| vLLM receives requests before ready | Add a `/v1/models` health wait |
| Provider returns invalid JSON after 307 | Remove the endpoint trailing slash |
| `finish_reason=length` | Retry only missing rows with more output tokens |
| Thinking appears | Fix backend-specific Non-Think request options |
| TensorBoard point uses wrong x-axis | Pass training global step to exporter |
| Restart repeats all API calls | Keep the same run directory and request IDs |
