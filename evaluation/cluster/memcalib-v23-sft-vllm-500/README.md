# MemCalib v2.3 base-versus-SFT cluster evaluation

This bundle evaluates the Qwen3.5-35B-A3B base checkpoint and its MemCalib
LoRA SFT checkpoint on the same locked 500-record MemCalib v2.3 pilot.
The cluster only generates model answers. Hidden labels remain outside the
model requests; judging and metric aggregation reuse the repository's existing
ordered-usage-v2.1 protocol.

## Fixed comparison

- Samples: the existing locked 500-record v2.3 pilot.
- Conditions: 500 full-memory and 500 no-memory answers per checkpoint.
- Answer mode: non-thinking for both checkpoints.
- Decoding: temperature 0, top-p 1, seed 20260723, max output 8,192 tokens.
- Backend controls: same vLLM version, dtype, tensor parallelism, chat template,
  maximum context length, and generation configuration.
- Model aliases:
  - `qwen35-a3b-base-vllm`
  - `qwen35-a3b-sft-vllm`

The formal answer set therefore contains 2,000 rows. The no-memory condition
is a counterfactual control, not a separate leaderboard.

## 1. Prepare requests

Run from a checkout of this repository:

```bash
bash evaluation/cluster/memcalib-v23-sft-vllm-500/prepare_requests.sh
```

This writes model-facing requests under
`evaluation/runs/memcalib-v23-sft-base-500-vllm/requests/answers/`.
No hidden atom labels or Judge rubrics are included in those requests.

## 2. Recommended: serve merged checkpoints sequentially

This matches the existing cluster workflow: pull each complete merged model to
cluster-local storage, keep vLLM in terminal 1, and run the evaluation client
in terminal 2. The base and SFT services reuse the same port and every serving
argument except model path and alias.

### Terminal 1: start the base model

```bash
vllm serve /cluster/local/path/to/base \
  --host 0.0.0.0 \
  --port 8000 \
  --served-model-name qwen35-a3b-base-vllm \
  --tensor-parallel-size 8 \
  --dtype bfloat16 \
  --max-model-len 32768 \
  --generation-config vllm \
  --gpu-memory-utilization 0.90
```

### Terminal 2: evaluate the base model

```bash
export VLLM_EVAL_WORKERS=128
export VLLM_EVAL_RPM=0

bash evaluation/cluster/memcalib-v23-sft-vllm-500/run_answer_model.sh \
  qwen35-a3b-base-vllm \
  med_chat \
  http://127.0.0.1:8000/v1/chat/completions
```

After it finishes, stop the base vLLM service.

### Terminal 1: start the merged SFT model

```bash
vllm serve /cluster/local/path/to/merged-sft \
  --host 0.0.0.0 \
  --port 8000 \
  --served-model-name qwen35-a3b-sft-vllm \
  --tensor-parallel-size 8 \
  --dtype bfloat16 \
  --max-model-len 32768 \
  --generation-config vllm \
  --gpu-memory-utilization 0.90
```

### Terminal 2: evaluate the SFT model

```bash
bash evaluation/cluster/memcalib-v23-sft-vllm-500/run_answer_model.sh \
  qwen35-a3b-sft-vllm \
  med_chat \
  http://127.0.0.1:8000/v1/chat/completions
```

Do not change quantization, dtype, chat template, context length, tensor
parallelism, or vLLM version between the two deployments. Serving the models
sequentially is acceptable because each answer is independent and the
comparison is paired by the locked sample ID.

## 2A. Optional: serve base and LoRA together

Use this form when the SFT artifact is a PEFT-compatible LoRA adapter. A single
server exposes both model aliases, minimizing serving differences:

```bash
export BASE_MODEL=/cluster/path/to/Qwen3.5-35B-A3B
export SFT_ADAPTER=/cluster/path/to/memcalib-lora-checkpoint

vllm serve "$BASE_MODEL" \
  --host 0.0.0.0 \
  --port 8000 \
  --served-model-name qwen35-a3b-base-vllm \
  --enable-lora \
  --lora-modules qwen35-a3b-sft-vllm="$SFT_ADAPTER" \
  --max-lora-rank 32 \
  --tensor-parallel-size 8 \
  --dtype bfloat16 \
  --max-model-len 32768 \
  --generation-config vllm \
  --gpu-memory-utilization 0.90
```

If the cluster requires authentication, add `--api-key` to the server and set
the same value in `MEMCALIB_VLLM_TOKEN`. Do not put that value in a command log
or committed file.

Check the model aliases without printing credentials:

```bash
curl -s http://127.0.0.1:8000/v1/models
```

## 3. Generate answers

The recommended merged-checkpoint commands are shown above. For a joint
base-plus-LoRA endpoint, run both commands while the one service remains active:

```bash
export VLLM_EVAL_WORKERS=128
export VLLM_EVAL_RPM=0

bash evaluation/cluster/memcalib-v23-sft-vllm-500/run_answer_model.sh \
  qwen35-a3b-base-vllm \
  qwen35-a3b-base-vllm \
  http://127.0.0.1:8000/v1/chat/completions

bash evaluation/cluster/memcalib-v23-sft-vllm-500/run_answer_model.sh \
  qwen35-a3b-sft-vllm \
  qwen35-a3b-sft-vllm \
  http://127.0.0.1:8000/v1/chat/completions
```

For sequential merged deployments, run the matching command while each server
is active. The runner is resumable and does not re-submit already valid rows.
Every cell first runs four smoke requests, then 500 full-memory and 500
no-memory requests.

Before the formal run, inspect the smoke outputs and confirm:

1. the returned `model` exactly matches the requested alias;
2. `finish_reason` is `stop`;
3. the automatic non-thinking audit reports zero nonempty reasoning fields and
   zero nonempty `<think>...</think>` blocks;
4. full-memory and no-memory prompts use the expected chat template.

## 4. Validate and package

After all four 500-row cells complete:

```bash
bash evaluation/cluster/memcalib-v23-sft-vllm-500/package_results.sh
```

The script rejects missing IDs, duplicate IDs, input-fingerprint mismatches,
empty answers, model mismatches, and truncated outputs. It creates:

`evaluation/runs/memcalib-v23-sft-base-500-vllm/memcalib-v23-sft-base-500-vllm-results.tar.gz`

Transfer that archive and its printed SHA-256 digest back to the local
workspace. The local stage will:

1. verify the archive digest and all 2,000 answer rows;
2. run the existing Qwen3.7-Plus primary Judge on every answer;
3. run the existing stratified secondary Judge sample;
4. retry only structurally invalid Judge rows;
5. compute atomic, sample-level, candidate, tail-risk, and diagnostic metrics;
6. report paired base-versus-SFT differences with clustered bootstrap
   confidence intervals.

Do not use the remaining 1,000 held-out test records during this pilot.
