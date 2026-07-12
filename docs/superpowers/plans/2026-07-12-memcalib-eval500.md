# MemCalib 500-Sample Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run a reproducible 500-sample, five-model paired validation experiment for MemCalib v0.1, including automated judging and statistical reporting.

**Architecture:** A standalone `evaluation/` package reconstructs the locked release, selects two deterministic panels, prepares leak-free answer requests, validates API outputs, prepares atom-level judge requests, and analyzes paired outcomes. The existing Bailian runner gains a tested provider-parameter option and remains responsible for concurrency, retries, resume, fingerprints, and progress.

**Tech Stack:** Python 3.12 standard library, JSON/JSONL, raw HTTP OpenAI-compatible Bailian API, `unittest`, self-contained HTML/CSS/JavaScript.

## Global Constraints

- Use `/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`; do not use Conda Python.
- The source release SHA-256 must equal `1cfd0334255266e6b8d4c234c615ade42b40c91bb86cb7c061a285261c363cb4`.
- Selection seed is `20260712`; panel sizes are 350 representative and 150 diagnostic.
- Answer-model prompts must not expose `memories`, labels, rubrics, source answers, raw evidence, QC, or construction audit.
- API keys must remain environment-only and must never be written or printed.
- Every API stage is resumable and validates unique request IDs plus input fingerprints.

---

### Task 1: Provider Parameters in the Bailian Runner

**Files:**
- Modify: `tests/pipeline/test_bailian_runner_progress.py`
- Modify: `pipeline/06_run_bailian_api.py`

**Interfaces:**
- Produces: `parse_extra_body(value: str) -> dict[str, object]` and `call_chat_completions(..., extra_body: dict[str, object])`.
- Consumers: all answer and judge runs requiring `enable_thinking=false`.

- [ ] Write a failing test asserting that valid JSON object input is parsed and non-object JSON is rejected.
- [ ] Run `PYTHONPATH=pipeline $PY -m unittest tests.pipeline.test_bailian_runner_progress -v` and confirm the new test fails because `parse_extra_body` is missing.
- [ ] Add `--extra-body-json`, parse it once, merge it into the request payload while preventing overrides of `model`, `messages`, `temperature`, and `max_tokens`, and pass the value through `run_one`.
- [ ] Run the focused test and the full test suite; require zero failures.
- [ ] Commit with message `Support provider parameters in Bailian runner`.

### Task 2: Deterministic Evaluation Selection

**Files:**
- Create: `evaluation/__init__.py`
- Create: `evaluation/common.py`
- Create: `evaluation/configs/memcalib-v0.1-500.json`
- Create: `evaluation/scripts/select_eval_subset.py`
- Create: `tests/evalbench/__init__.py`
- Create: `tests/evalbench/test_selection.py`

**Interfaces:**
- `load_release_records(release_dir: Path) -> list[dict]` verifies and reconstructs shards.
- `select_representative(records: list[dict], config: dict) -> list[dict]` returns 350 records.
- `select_diagnostic(records: list[dict], excluded_ids: set[str], config: dict) -> list[dict]` returns 150 records.
- `build_selection_artifacts(...)` writes hidden/model-facing JSONL, held-out IDs, and a manifest.

- [ ] Write failing unit tests with a synthetic candidate pool for exact panel size, source quotas, deterministic IDs, no overlap, hidden/model-facing boundary, and fail-closed diagnostic quotas.
- [ ] Run `PYTHONPATH=. $PY -m unittest tests.evalbench.test_selection -v` and confirm failures are caused by missing implementation.
- [ ] Implement release reconstruction, stable hash ordering, largest-remainder quotas, representative constrained selection, diagnostic marginal-gain selection, SHA-256 helpers, and manifests.
- [ ] Run focused tests, then generate the real 500-sample artifacts under `evaluation/releases/memcalib-v0.1-500/`.
- [ ] Verify 500 unique IDs, 350/150 panels, 250/250 total source balance, all hard diagnostic quotas, and absence of hidden fields from model-facing JSONL.
- [ ] Commit with message `Lock MemCalib 500-sample evaluation set`.

### Task 3: Paired Answer Requests and Validation

**Files:**
- Create: `evaluation/prompts/answer-system.txt`
- Create: `evaluation/scripts/prepare_answer_requests.py`
- Create: `evaluation/scripts/validate_api_results.py`
- Create: `tests/evalbench/test_answer_requests.py`

**Interfaces:**
- `build_answer_messages(sample: dict, condition: str, system_prompt: str) -> list[dict[str, str]]`.
- `prepare_answer_requests(...)` writes one request file per model and condition.
- `validate_results(input_path: Path, output_path: Path, expected_model: str) -> dict` returns completeness and integrity counts.

- [ ] Write failing tests proving that full-memory messages preserve parent order, no-memory messages contain no memory text, hidden fields never enter prompts, request IDs are stable, and validation rejects missing, duplicate, truncated, wrong-model, or fingerprint-mismatched rows.
- [ ] Run focused tests and observe expected failures.
- [ ] Implement prompt construction, 10 deterministic request files, smoke subsets, input manifests, and generic API-result validation.
- [ ] Generate 5,000 formal requests plus model-specific smoke files; verify 500 requests in each model × condition cell.
- [ ] Run focused and full tests, then commit with message `Prepare paired MemCalib answer requests`.

### Task 4: Answer Generation

**Files:**
- Runtime only: `evaluation/runs/memcalib-v0.1-500/answers/`
- Create after completion: `evaluation/releases/memcalib-v0.1-500/answer-run.manifest.json`

**Interfaces:**
- Consumes the ten answer request files and environment-only Bailian key.
- Produces validated answer JSONL files with 5,000 unique request IDs total.

- [ ] Run four requests per answer model as smoke tests using the exact model IDs and parameters in the design.
- [ ] Validate nonempty content, `finish_reason`, model identity, fingerprints, and zero final failures for all five models.
- [ ] Launch formal runs with bounded concurrency, `--timeout 300`, `--max-retries 5`, `--extra-body-json '{"enable_thinking":false}'`, and live progress.
- [ ] Monitor line growth, RPM, 429, 5xx, timeout, and connection errors; reduce concurrency/RPM on sustained failure or ten-minute stagnation.
- [ ] Retry final failures, validate 5,000 complete answers, and write the locked answer-run manifest.

### Task 5: Judge Requests, Parsing, and Human Review Pack

**Files:**
- Create: `evaluation/prompts/judge-system.txt`
- Create: `evaluation/scripts/prepare_judge_requests.py`
- Create: `evaluation/scripts/postprocess_judgments.py`
- Create: `evaluation/scripts/build_human_review.py`
- Create: `tests/evalbench/test_judging.py`

**Interfaces:**
- `build_judge_request(sample: dict, answer: dict) -> dict` includes rubrics but excludes source answers and audit data.
- `validate_judgment(value: object, expected_atoms: dict[str, str]) -> tuple[bool, list[str]]` enforces label-specific verdicts and atom coverage.
- `select_secondary_ids(...)` locks 100 responses per model × condition with a 70/30 panel split.
- `build_human_review(...)` writes 60 random and 40 disagreement/low-confidence cases to JSONL and HTML.

- [ ] Write failing tests for judge-field boundaries, exact atom coverage, verdict-label compatibility, evidence-quote grounding, secondary quotas, and human-review strata.
- [ ] Run focused tests and observe expected failures.
- [ ] Implement primary and secondary request preparation, robust JSON extraction, schema validation, invalid retry queues, normalized atom-level judgment rows, and one-response-per-page review HTML.
- [ ] Run the primary judge over all 5,000 answers, retry invalid outputs, and validate completion.
- [ ] Run secondary judges over the locked 1,000-response subset, retry invalid outputs, and validate completion.
- [ ] Generate the 100-response human review pack and commit non-sensitive prompts, code, manifests, and review artifacts.

### Task 6: Statistical Analysis and Report

**Files:**
- Create: `evaluation/scripts/analyze_evaluation.py`
- Create: `tests/evalbench/test_analysis.py`
- Create: `evaluation/releases/memcalib-v0.1-500/metrics.json`
- Create: `evaluation/releases/memcalib-v0.1-500/report.html`
- Modify: `README.md`

**Interfaces:**
- `compute_metrics(judgments: list[dict], config: dict) -> dict` calculates label, panel, model, paired, strict, quality, safety, and agreement metrics.
- `paired_bootstrap(...)` returns deterministic 95% confidence intervals from 2,000 sample-clustered replicates.
- `render_report(metrics: dict, provenance: dict) -> str` returns a self-contained HTML report.

- [ ] Write failing tests for label macro-score, paired delta, A contamination effect, strict sample/mixed-parent accuracy, judge agreement, and deterministic bootstrap output.
- [ ] Run focused tests and observe expected failures.
- [ ] Implement metrics and a self-contained Chinese HTML report with model/condition/panel filters, readable tables, error distributions, confidence intervals, and methodology notes.
- [ ] Generate metrics and report from validated results; inspect the report at desktop and mobile widths.
- [ ] Run all tests, compile all Python, verify release hashes, run `git diff --check`, and scan tracked files plus Git history for API-key patterns.
- [ ] Update the README with evaluation entry points, commit with message `Report MemCalib validation experiment`, and push the feature branch.
