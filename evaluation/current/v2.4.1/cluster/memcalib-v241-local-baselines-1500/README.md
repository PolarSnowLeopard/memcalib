# MemCalib v2.4.1 local baseline evaluation on 1,500 records

This cluster bundle evaluates locally deployed Qwen3.5-35B-A3B and
Ministral-3-8B-Instruct-2512 BF16 checkpoints on the locked MemCalib v2.4.1
benchmark Test set.

The experiment is fixed to:

- 1,500 records: health_seed 750, general 375, coding 375;
- Full-memory only;
- Non-Think only for both models;
- no No-memory inference;
- three independent answer seeds: 42, 43, and 44;
- one sampled answer per record and seed;
- temperature 1.0, Top-P 1.0, Top-K -1, max tokens 8,192;
- the current answer system prompt recorded in the bundle manifest.

The cluster bundle contains model-visible records only. Hidden atom labels,
rubrics, Judge requests, and Judge outputs remain outside the inference
cluster. After answer generation, return the raw-results archive for
DeepSeek-V4-Pro scoring and metric aggregation.

## 1. Build and upload the bundle

From the repository checkout:

```bash
bash evaluation/current/v2.4.1/cluster/memcalib-v241-local-baselines-1500/package_cluster_bundle.sh
```

Upload these two files:

```text
deliverables/memcalib-v241-local-baselines-1500-cluster-bundle.tar.gz
deliverables/memcalib-v241-local-baselines-1500-cluster-bundle.tar.gz.sha256
```

The preferred OSS destination is the owner's private evaluation prefix:

```text
oss://chat-algorithm-data/fg/zfy/memcalib/v2.4.1/local-baselines-1500/
```

Configure OSS credentials through the local secret mechanism, then upload
without embedding credentials in scripts or documentation:

```bash
OSS_DEST='oss://chat-algorithm-data/fg/zfy/memcalib/v2.4.1/local-baselines-1500'

ossutil cp -f \
  deliverables/memcalib-v241-local-baselines-1500-cluster-bundle.tar.gz \
  "$OSS_DEST/memcalib-v241-local-baselines-1500-cluster-bundle.tar.gz" \
  $=OSS_ARGS

ossutil cp -f \
  deliverables/memcalib-v241-local-baselines-1500-cluster-bundle.tar.gz.sha256 \
  "$OSS_DEST/memcalib-v241-local-baselines-1500-cluster-bundle.tar.gz.sha256" \
  $=OSS_ARGS
```

For an SSH-accessible cluster, synchronize them from the local machine with:

```bash
export CLUSTER_SSH=user@cluster-host
export CLUSTER_UPLOAD_DIR=/workspace/uploads

ssh "$CLUSTER_SSH" "mkdir -p '$CLUSTER_UPLOAD_DIR'"
rsync -avP \
  deliverables/memcalib-v241-local-baselines-1500-cluster-bundle.tar.gz \
  deliverables/memcalib-v241-local-baselines-1500-cluster-bundle.tar.gz.sha256 \
  "$CLUSTER_SSH:$CLUSTER_UPLOAD_DIR/"
```

On the cluster:

```bash
cd /workspace/uploads
sha256sum -c memcalib-v241-local-baselines-1500-cluster-bundle.tar.gz.sha256

mkdir -p /workspace/memcalib-v241-local-eval
tar -xzf memcalib-v241-local-baselines-1500-cluster-bundle.tar.gz \
  -C /workspace/memcalib-v241-local-eval
cd /workspace/memcalib-v241-local-eval

python3 --version
vllm --version
curl --version
command -v hf >/dev/null || python3 -m pip install --user --upgrade huggingface_hub
python3 -c 'from importlib.metadata import version; print(version("mistral-common"))'
```

For `Ministral-3-8B-Instruct-2512`, use vLLM 0.12.0 or newer and
`mistral_common` 1.8.6 or newer. If the existing image is older, upgrade those
packages in the image's normal Python environment before downloading models.

Do not put model-download credentials or API keys in this directory or in
shell history. The local answer endpoint does not require a real API key.

Download the exact official checkpoints after supplying Hugging Face access
through the cluster secret manager:

```bash
mkdir -p /models
hf download Qwen/Qwen3.5-35B-A3B \
  --local-dir /models/Qwen3.5-35B-A3B
hf download mistralai/Ministral-3-8B-Instruct-2512 \
  --local-dir /models/Ministral-3-8B-Instruct-2512-BF16

test -s /models/Qwen3.5-35B-A3B/config.json
test -s /models/Ministral-3-8B-Instruct-2512-BF16/config.json || \
  test -s /models/Ministral-3-8B-Instruct-2512-BF16/params.json
```

The second command selects the instruct, not reasoning, member of the
Ministral 3 family. The local directory name records that the cluster copy is
the BF16 representation.

## 2. Evaluate Qwen3.5-35B-A3B

Start the server in terminal 1. Adjust only the checkpoint path if necessary:

```bash
MODEL_CKPT=/models/Qwen3.5-35B-A3B
vllm serve "$MODEL_CKPT" \
  --served-model-name med_chat \
  --host 0.0.0.0 \
  --port 8000 \
  --tensor-parallel-size 8 \
  --max-model-len 16384 \
  --dtype bfloat16 \
  --gpu-memory-utilization 0.90 \
  --reasoning-parser qwen3
```

The benchmark does not use tools, so tool-choice and tool-parser flags must
not be added. The reasoning parser remains as an audit surface, while the
request explicitly disables thinking through Qwen's chat template.

After `/v1/models` reports `med_chat`, run in terminal 2:

```bash
MODEL_CKPT=/models/Qwen3.5-35B-A3B
PYTHON_BIN=python3 \
MEMCALIB_MODEL_PATH="$MODEL_CKPT" \
MEMCALIB_MODEL_ID="Qwen/Qwen3.5-35B-A3B" \
VLLM_EVAL_WORKERS=128 \
VLLM_EVAL_RPM=0 \
bash evaluation/current/v2.4.1/cluster/memcalib-v241-local-baselines-1500/run_model_three_seeds.sh \
  qwen35-35b-a3b-local-vllm \
  med_chat \
  http://127.0.0.1:8000/v1/chat/completions \
  "Qwen3.5-35B-A3B (Local vLLM)" \
  external_local_baseline \
  qwen_nonthinking
```

The script runs seeds 42, 43, and 44 sequentially. Rerunning the same command
preserves valid rows and resumes only unfinished request IDs.

## 3. Evaluate Ministral-3-8B-Instruct-2512 BF16

Stop the Qwen server, verify that port 8000 is free, and then start the
Ministral server in terminal 1:

```bash
MODEL_CKPT=/models/Ministral-3-8B-Instruct-2512-BF16
vllm serve "$MODEL_CKPT" \
  --served-model-name med_chat \
  --host 0.0.0.0 \
  --port 8000 \
  --tensor-parallel-size 8 \
  --max-model-len 16384 \
  --dtype bfloat16 \
  --gpu-memory-utilization 0.90 \
  --tokenizer-mode mistral \
  --config-format mistral \
  --load-format mistral
```

The benchmark does not provide tools. Do not add a tool parser; if tools are
evaluated separately, the correct parser for this model family is `mistral`,
not a Qwen parser.

Run in terminal 2:

```bash
MODEL_CKPT=/models/Ministral-3-8B-Instruct-2512-BF16
PYTHON_BIN=python3 \
MEMCALIB_MODEL_PATH="$MODEL_CKPT" \
MEMCALIB_MODEL_ID="mistralai/Ministral-3-8B-Instruct-2512" \
VLLM_EVAL_WORKERS=128 \
VLLM_EVAL_RPM=0 \
bash evaluation/current/v2.4.1/cluster/memcalib-v241-local-baselines-1500/run_model_three_seeds.sh \
  ministral3-8b-instruct-2512-bf16-local-vllm \
  med_chat \
  http://127.0.0.1:8000/v1/chat/completions \
  "Ministral-3-8B-Instruct-2512 BF16 (Local vLLM)" \
  external_local_baseline \
  standard_nonthinking
```

## 4. Check and return results

After both models finish:

```bash
bash evaluation/current/v2.4.1/cluster/memcalib-v241-local-baselines-1500/check_results.sh
bash evaluation/current/v2.4.1/cluster/memcalib-v241-local-baselines-1500/package_raw_results.sh
```

The result table must show 1,500/1,500 Full-memory rows and `NONTHINK=yes` for
both models in all three repeats. The runner never prepares or evaluates a
No-memory condition. Return:

```text
evaluation/runs/memcalib-v241-local-baselines-1500-nonthinking-vllm/
  memcalib-v241-local-baselines-1500-nonthinking-vllm-raw-results.tar.gz
  memcalib-v241-local-baselines-1500-nonthinking-vllm-raw-results.tar.gz.sha256
```

Do not rename model keys or repeat directories. They are used to generate
stable request IDs and to align the three Judge/metric runs after transfer.
