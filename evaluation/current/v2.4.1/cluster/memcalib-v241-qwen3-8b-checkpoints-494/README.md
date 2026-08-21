# MemCalib v2.4.1 Qwen3-8B checkpoint evaluation

This bundle compares any number of Qwen3-8B-compatible checkpoints on the
locked v2.4.1 494-record pilot. Every checkpoint receives the same fluent
model-facing memory, current answer system prompt, and deterministic
non-thinking decoding in the Full-memory condition.

The v2.4.1 pilot contains 494 rather than 500 records because it preserves the
complete-case IDs used by the corrected release. Do not use the v2.4 500-row
runner for this experiment.

## Build the cluster bundle

```bash
bash evaluation/current/v2.4.1/cluster/memcalib-v241-qwen3-8b-checkpoints-494/package_cluster_bundle.sh
```

Extract the archive in the cluster workspace. It contains model-facing data
and answer-generation code only; hidden labels and Judge rubrics are excluded.

## Initialize a fresh cluster

Upload the generated cluster bundle, then extract it into an empty workspace:

```bash
mkdir -p /workspace/memcalib-v241-eval
tar -xzf memcalib-v241-qwen3-8b-checkpoints-494-cluster-bundle.tar.gz \
  -C /workspace/memcalib-v241-eval
cd /workspace/memcalib-v241-eval

python3 --version
curl --version
```

The answer runner uses only the Python standard library and `curl`; do not
create a Conda environment. Download model weights using an instance RAM role
or credentials supplied outside the command history. Never write access keys
into this repository, shell scripts, or result archives.

Before evaluation, confirm that the model directory is complete and that vLLM
serves the intended alias:

```bash
test -s /models/MODEL_DIRECTORY/config.json
curl -fsS http://127.0.0.1:8000/v1/models
```

The benchmark does not use tools, so tool-choice and tool-parser flags should
be omitted from the vLLM server. A minimal launch is:

```bash
MODEL_CKPT=/models/MODEL_DIRECTORY
vllm serve "$MODEL_CKPT" \
  --served-model-name med_chat \
  --port 8000 \
  --host 0.0.0.0 \
  --tensor-parallel-size 8 \
  --max-model-len 16384 \
  --reasoning-parser qwen3
```

## Run one checkpoint

Start vLLM in one terminal. The served alias may remain `med_chat` for every
checkpoint. Then run this in another terminal:

```bash
VLLM_EVAL_WORKERS=128 VLLM_EVAL_RPM=0 \
bash evaluation/current/v2.4.1/cluster/memcalib-v241-qwen3-8b-checkpoints-494/run_answer_model.sh \
  UNIQUE_MODEL_KEY med_chat \
  http://127.0.0.1:8000/v1/chat/completions \
  "Report display name" \
  checkpoint_role
```

Use a distinct `UNIQUE_MODEL_KEY` for every checkpoint. The key controls the
request IDs and output directory, so reusing a key would resume or mix a prior
checkpoint rather than create a new experimental cell.

For a retrained checkpoint, also use a unique run directory. For example:

```bash
MEMCALIB_RUN=evaluation/runs/memcalib-v241-coldstart-4k-0803-1-494-vllm \
VLLM_EVAL_WORKERS=128 VLLM_EVAL_RPM=0 \
bash evaluation/current/v2.4.1/cluster/memcalib-v241-qwen3-8b-checkpoints-494/run_answer_model.sh \
  qwen3-8b-v241-coldstart-4k-0803-1 med_chat \
  http://127.0.0.1:8000/v1/chat/completions \
  "Qwen3-8B v2.4.1 4K Cold-start 0803-1" \
  coldstart_retrained_tf4
```

Recommended keys for the current comparison:

- `qwen3-8b-v241-coldstart-4k`
- `qwen3-8b-v241-sft-atomic-12k`
- `qwen3-8b-v241-sft-fluent-12k`

The runner sends `chat_template_kwargs.enable_thinking=false` and validates
that returned rows contain neither reasoning content nor visible nonempty
`<think>` blocks. Existing valid rows are retained on rerun, while failures
remain auditable.

## Check and package results

```bash
bash evaluation/current/v2.4.1/cluster/memcalib-v241-qwen3-8b-checkpoints-494/check_results.sh
bash evaluation/current/v2.4.1/cluster/memcalib-v241-qwen3-8b-checkpoints-494/package_raw_results.sh
```

Use `package_results.sh` instead of `package_raw_results.sh` only when every
cell is complete. Judge scoring and metric aggregation run after the answer
archive is transferred back to the local workspace.
