# Current Repository Workflow

## Contents

1. Discover the selected release
2. Generate and validate answers
3. Run and normalize the Judge
4. Generate metrics
5. Locate reference artifacts

This reference maps the reusable integration contract to a checkout of
`create_medpreferncedata_from_public_data`.

The dataset is expected to evolve. Do not hard-code a version directory,
release name, sample count, model key, or run name from an earlier experiment.
Treat versioned paths as implementations to discover and inspect.

## Discover the Selected Release

Before writing integration code:

1. Read the repository's main README and current evaluation README.
2. Enumerate versioned directories below `evaluation/current/`.
3. Ask which release/config is authoritative if no current alias or explicit
   experiment config resolves that choice.
4. Inspect the selected config and release manifests.
5. Record the selected release ID, expected sample count, prompts, Judge model,
   and generation settings in the evaluation config.

Useful discovery commands:

```bash
find evaluation/current -maxdepth 3 -type f \
  \( -name 'README.md' -o -name '*.json' \) | sort

find evaluation/current -type f \
  \( -name 'model-facing.jsonl' -o -name 'hidden-evaluation.jsonl' \
     -o -name 'sample-ids.txt' -o -name '*manifest.json' \) | sort

find evaluation -type f \
  \( -name 'prepare_answer_requests.py' \
     -o -name 'prepare_judge_requests.py' \
     -o -name 'analyze_sample_level_calibration.py' \) | sort
```

Do not choose the lexicographically largest directory and call it current
without checking repository documentation and manifests.

The selected release should provide:

- `model-facing.jsonl`: model-visible query, memory blocks, and public context;
- `hidden-evaluation.jsonl`: hidden atom rubric and scoring metadata;
- an ordered sample-ID list or reproducible sampling manifest;
- source and sampling provenance.

Locate the answer and Judge prompts from the selected config. Do not assume
their filenames remain unchanged.

## Generate and Validate Answers

Find the maintained OpenAI-compatible checkpoint runner under
`evaluation/current/` or compose the workflow from:

- `evaluation/scripts/prepare_answer_requests.py`;
- `pipeline/06_run_bailian_api.py`;
- `evaluation/scripts/validate_api_results.py`;
- the current Non-Think validator.

Keep the runner interface equivalent to:

```bash
bash RUN_ANSWER_MODEL \
  MODEL_KEY \
  SERVED_MODEL_NAME \
  CHAT_COMPLETIONS_URL \
  "DISPLAY NAME" \
  CHECKPOINT_ROLE
```

Example with generic paths:

```bash
MEMCALIB_RUN=/shared/eval/EXPERIMENT/step-200 \
MEMCALIB_CONFIG=/shared/eval/spec/eval-config.json \
MEMCALIB_SAMPLE_RELEASE=/shared/eval/releases/SELECTED_RELEASE \
MEMCALIB_ANSWER_PROMPT=/shared/eval/prompts/answer-system.txt \
VLLM_EVAL_WORKERS=128 \
VLLM_EVAL_RPM=0 \
bash "$RUN_ANSWER_MODEL" \
  checkpoint-200 \
  med_chat \
  http://127.0.0.1:8000/v1/chat/completions \
  "Checkpoint step 200" \
  sft
```

`MODEL_KEY` is an experiment identifier. `SERVED_MODEL_NAME` must match the
name returned by the inference server. Keep both configurable. Do not append a
serving-framework suffix to the public display name.

The answer workflow must:

1. prepare requests for the selected release;
2. run a small smoke cell;
3. run `full_memory` and `no_memory`;
4. validate API results and Non-Think behavior;
5. preserve failed and invalid rows.

The underlying API runner supports OpenAI-compatible endpoints, concurrency,
RPM limiting, timeouts, retries, and resume. Provide
credentials through environment variables or a secret manager. Never put them
in an evaluation config.

Freeze deterministic answer settings in the evaluation specification:

```json
{
  "temperature": 0,
  "top_p": 1,
  "seed": 20260730,
  "max_tokens": 8192,
  "chat_template_kwargs": {
    "enable_thinking": false
  }
}
```

Values may change between releases, but must remain fixed between checkpoints
on one curve. If a backend uses a different Non-Think switch, adapt the request
body and validator. Strip a trailing slash from `/v1/chat/completions` URLs to
avoid redirects that some clients misparse.

Required answer checks:

- one output per expected request ID;
- matching served model when returned;
- nonempty response and `finish_reason=stop`;
- no visible think block or nonempty reasoning field;
- no duplicate or extra IDs.

Retry by request ID:

- connection, timeout, 429, or 5xx: retry missing requests after backoff;
- `finish_reason=length`: raise `max_tokens` only for truncated requests;
- structurally invalid provider output: retry only invalid rows;
- valid output: never submit it again.

Prefer strict completion of the selected release in both conditions. If a
permanent block makes this impossible, derive one frozen common subset and
reuse it for every checkpoint. Log retained count, fraction, and exclusions.
A repository complete-case builder can produce that frozen subset, but must not
replace recoverable retries.

## Run and Normalize the Judge

Prepare Judge requests:

```bash
PYTHONPATH=. python3 evaluation/scripts/prepare_judge_requests.py \
  --config "$EVAL_CONFIG" \
  --hidden "$SAMPLE_RELEASE/hidden-evaluation.jsonl" \
  --answers "$RUN/answers" \
  --output-dir "$RUN/requests/judges" \
  --manifest "$RUN/manifests/judge-request.manifest.json" \
  --conditions full_memory no_memory
```

Run the primary request file with `pipeline/06_run_bailian_api.py` using the
Judge model, temperature, output limit, and thinking mode from the selected
config. Validate expected and returned request IDs.

Normalize:

```bash
PYTHONPATH=. python3 evaluation/scripts/postprocess_judgments.py \
  --input "$RUN/requests/judges/primary.jsonl" \
  --result "$RUN/judge-api/primary.jsonl" \
  --valid "$RUN/judgments/primary.initial.valid.jsonl" \
  --invalid "$RUN/judgments/primary.initial.invalid.jsonl" \
  --summary "$RUN/judgments/primary.initial.summary.json"
```

For structural invalid rows:

1. run `evaluation/scripts/prepare_judge_retry.py`;
2. submit only the retry requests;
3. postprocess the retry;
4. merge with `evaluation/scripts/merge_judgments.py`;
5. require one valid judgment per answer request.

Do not reinterpret malformed Judge text locally or drop it silently.

## Generate Metrics

Locate the maintained sample-level analysis script. Its current interface is:

```bash
PYTHONPATH=. python3 evaluation/scripts/analyze_sample_level_calibration.py \
  --judgments nonthinking="$RUN/judgments/primary.valid.jsonl" \
  --hidden "$SAMPLE_RELEASE/hidden-evaluation.jsonl" \
  --output-dir "$RUN/analysis/sample-level" \
  --bootstrap-replicates 0 \
  --study-title "MemCalib SELECTED_RELEASE checkpoint step 200"
```

Use zero bootstrap replicates on the frequent training-time path. Run bootstrap
confidence intervals for milestone or release checkpoints.

Primary sample-level definitions:

```text
rank(A)=0, rank(B)=1, rank(C)=2
over_budget(s)  = sum_i max(rank(pred_i) - rank(gold_i), 0)
under_budget(s) = sum_i max(rank(gold_i) - rank(pred_i), 0)
SCS_rho(s)      = rho ^ (over_budget(s) + under_budget(s))
sOPB_rho(s)     = 1 - rho ^ over_budget(s)
sUPB_rho(s)     = 1 - rho ^ under_budget(s)
Exact(s)        = 1[over_budget(s) + under_budget(s) = 0]
```

Aggregate by arithmetic mean over samples. Use the primary `rho` declared by
the selected evaluation specification. Report SCS with both directional errors.

## Locate Reference Artifacts

Search rather than hard-code:

```bash
find evaluation/runs -path '*/judgments/primary.valid.jsonl' | sort
find evaluation/current -path '*/sample-level/sample-level-metrics.json' | sort
find evaluation/current -path '*/sample-level/sample-level-scores.csv' | sort
```

Choose an example whose manifest, release, conditions, and protocol match the
selected integration. Use it to inspect schemas, not to inherit its sample IDs
or version automatically.
