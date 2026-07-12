# MemCalib Repository Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the existing research workspace into a coherent MemCalib repository, package the locked 15,528-sample benchmark as a deterministic private-review release, verify it end to end, and upload it to a private GitHub repository named `memcalib`.

**Architecture:** Preserve the numbered construction stages as executable research scripts under `pipeline/`, move tests and current documentation into conventional top-level locations, and remove superseded prototype artifacts from the current tree. A standard-library release builder streams the locked JSONL into deterministic gzip shards and emits a manifest; an independent verifier reconstructs and audits the release before GitHub publication.

**Tech Stack:** Python 3 standard library, `unittest`, deterministic gzip/JSONL packaging, Git, GitHub CLI.

## Global Constraints

- Use `/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`; do not use Conda Python.
- Preserve the locked benchmark byte stream with SHA-256 `1cfd0334255266e6b8d4c234c615ade42b40c91bb86cb7c061a285261c363cb4`.
- Require 15,528 unique samples, 56,044 parent memories, and 78,734 atomic memories.
- Keep each tracked release shard below 50 MiB and every tracked file below GitHub's 100 MB hard limit.
- Create a private GitHub repository named `memcalib`; do not publish the release publicly.
- Do not add a repository-wide data or code license in this phase.
- Do not include API keys, raw source downloads, API responses, runtime logs, or large construction intermediates.
- Defer model evaluation implementation until repository publication is complete.

---

### Task 1: Deterministic Release Builder And Verifier

**Files:**
- Create: `tools/build_release.py`
- Create: `tools/verify_release.py`
- Create: `tests/tools/test_release_packaging.py`

**Interfaces:**
- Consumes: locked benchmark JSONL, benchmark summary, generation run lock, selected provenance manifests, audit HTML, and statistics HTML.
- Produces: `build_release(source: Path, release_dir: Path, *, shard_count: int, sample_size: int) -> dict[str, Any]` and `verify_release(release_dir: Path) -> dict[str, Any]`.

- [ ] **Step 1: Write failing tests for deterministic shards and reconstruction**

Create fixture records with parent blocks and atomic memories. Test that two builds produce identical gzip bytes, that concatenated decompressed shards equal the source bytes, and that manifest hashes match.

```python
def test_release_shards_are_deterministic_and_reconstruct_source(self):
    first = self.build_release(self.source, self.work / "first", shard_count=2, sample_size=2)
    second = self.build_release(self.source, self.work / "second", shard_count=2, sample_size=2)
    self.assertEqual(first["source_sha256"], second["source_sha256"])
    self.assertEqual(self.shard_bytes(first), self.shard_bytes(second))
    self.assertEqual(self.source.read_bytes(), self.reconstructed(first))
```

- [ ] **Step 2: Write failing tests for tamper detection and benchmark counts**

```python
def test_verify_release_rejects_modified_shard(self):
    manifest = self.build_release(self.source, self.release, shard_count=2, sample_size=2)
    shard = self.release / manifest["files"]["data_shards"][0]["path"]
    shard.write_bytes(shard.read_bytes() + b"tamper")
    with self.assertRaisesRegex(ValueError, "sha256"):
        self.verify_release(self.release)
```

- [ ] **Step 3: Run focused tests and verify RED**

```bash
PY=/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
PYTHONPATH=. "$PY" -m unittest tests/tools/test_release_packaging.py
```

Expected: import failure because `tools/build_release.py` and `tools/verify_release.py` do not exist.

- [ ] **Step 4: Implement streaming deterministic packaging**

Implement these functions in `tools/build_release.py`. The shard writer uses exact row targets and deterministic gzip headers:

```python
def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@contextmanager
def deterministic_gzip_writer(path: Path) -> Iterator[BinaryIO]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw_handle:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            compresslevel=9,
            fileobj=raw_handle,
            mtime=0,
        ) as gzip_handle:
            yield gzip_handle


def shard_row_targets(total_rows: int, shard_count: int) -> list[int]:
    quotient, remainder = divmod(total_rows, shard_count)
    return [quotient + (index < remainder) for index in range(shard_count)]


def write_shards(source: Path, output_dir: Path, shard_count: int) -> list[dict[str, Any]]:
    total_rows = sum(1 for line in source.open("rb") if line.strip())
    targets = shard_row_targets(total_rows, shard_count)
    metadata = []
    with source.open("rb") as source_handle:
        for index, target in enumerate(targets):
            path = output_dir / f"memcalib-v0.1-{index:05d}-of-{shard_count:05d}.jsonl.gz"
            with deterministic_gzip_writer(path) as output_handle:
                for _ in range(target):
                    line = source_handle.readline()
                    if not line:
                        raise ValueError("source ended before declared shard boundary")
                    output_handle.write(line)
            metadata.append({
                "path": path.name,
                "rows": target,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })
        if source_handle.read(1):
            raise ValueError("source contains rows beyond declared shard boundaries")
    return metadata
```

`count_release_records(source)` performs a separate streaming pass and computes sample, parent, atom, label, source, topic, mixed-parent, and Hard-A counts. `select_review_sample(source, sample_size)` maintains bounded deterministic priority reservoirs keyed by `(source_dataset, source_topic, has_mixed_parent)`, merges at most four candidates per stratum, greedily maximizes uncovered label and Hard-A features, and fills remaining positions from a 300-record global stable-hash reservoir. The top-level `build_release` function combines these results with copied review/provenance files and writes the final manifest only after all output hashes are known.

- [ ] **Step 5: Implement independent release verification**

`tools/verify_release.py` must verify manifest and file hashes before decompression, stream JSON parsing, unique IDs, field structure, counts, reconstructed byte hash, and expected lineage.

```python
EXPECTED = {
    "samples": 15528,
    "parent_memories": 56044,
    "atomic_memories": 78734,
    "source_sha256": "1cfd0334255266e6b8d4c234c615ade42b40c91bb86cb7c061a285261c363cb4",
}
```

- [ ] **Step 6: Run focused tests and commit**

```bash
PYTHONPATH=. "$PY" -m unittest tests/tools/test_release_packaging.py
git add tools tests/tools
git commit -m "Add deterministic MemCalib release tooling"
```

### Task 2: Repository Path Migration

**Files:**
- Rename: `med_rpeval_pipeline/` to `pipeline/`
- Move: `pipeline/test_*.py` to `tests/pipeline/`
- Move: `pipeline/audit_samples/test_manual_review_html.py` to `tests/pipeline/test_manual_review_html.py`
- Modify: all moved tests, `.gitignore`, pipeline documentation, script path constants, and checked-in manifests that serve as release provenance.

**Interfaces:**
- Consumes: the existing executable stage scripts and tests.
- Produces: a neutral `pipeline/` CLI surface with local working data still resolved as `pipeline/data/`.

- [ ] **Step 1: Capture the baseline test result**

```bash
PYTHONPATH=med_rpeval_pipeline "$PY" -m unittest discover -s med_rpeval_pipeline -p 'test_*.py'
```

Expected: 77 tests pass.

- [ ] **Step 2: Rename the pipeline directory and move tests**

Use `git mv` for tracked files. Keep numbered stage scripts, `utils.py`, `prompts/`, `config.json`, and `requirements.txt` directly under `pipeline/`. Retain ignored local working files physically under `pipeline/data/`.

- [ ] **Step 3: Update imports and path references**

Moved tests resolve scripts from the repository root:

```python
REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_DIR = REPO_ROOT / "pipeline"
SCRIPT = PIPELINE_DIR / "11_post_crk2_generation.py"
```

Update `.gitignore` patterns from `med_rpeval_pipeline/data/` to `pipeline/data/`. Replace current documentation commands and source-path strings without modifying historical hash values stored as data.

- [ ] **Step 4: Run all tests from the new structure**

```bash
PYTHONPATH=pipeline "$PY" -m unittest discover -s tests -p 'test_*.py'
```

Expected: all existing and release-tool tests pass.

- [ ] **Step 5: Commit the path migration**

```bash
git add -A
git commit -m "Reorganize the MemCalib construction pipeline"
```

### Task 3: Build The MemCalib v0.1 Release

**Files:**
- Create: `release/memcalib-v0.1/manifest.json`
- Create: `release/memcalib-v0.1/data/*.jsonl.gz`
- Create: `release/memcalib-v0.1/samples/memcalib-v0.1-sample-100.jsonl`
- Move/copy tracked release review, statistics, summary, and provenance files into `release/memcalib-v0.1/`.

**Interfaces:**
- Consumes: `pipeline/data/crk2_canonical_memory_benchmark_en_15528.jsonl` and the locked formal artifacts.
- Produces: a self-contained private-review release with no dependency on ignored intermediates.

- [ ] **Step 1: Run the release builder with the designated runtime**

```bash
"$PY" tools/build_release.py \
  --source pipeline/data/crk2_canonical_memory_benchmark_en_15528.jsonl \
  --release-dir release/memcalib-v0.1 \
  --shards 2 \
  --sample-size 100
```

- [ ] **Step 2: Verify shard sizes and ordinary Git compatibility**

```bash
find release/memcalib-v0.1 -type f -size +50M -print
```

Expected: no output. If a shard exceeds 50 MiB, rebuild with three shards and record `shard_count=3` in the manifest.

- [ ] **Step 3: Run independent release verification**

```bash
"$PY" tools/verify_release.py --release-dir release/memcalib-v0.1
```

Expected: status `passed`, 15,528 samples, 56,044 parents, 78,734 atoms, and the locked reconstructed SHA-256.

- [ ] **Step 4: Commit the release package**

```bash
git add release/memcalib-v0.1
git commit -m "Package the MemCalib v0.1 review release"
```

### Task 4: Documentation And Current-Tree Cleanup

**Files:**
- Create: `README.md`
- Create: `DATA_CARD.md`
- Create: `NOTICE.md`
- Create: `docs/benchmark-schema.md`
- Create: `docs/construction-pipeline.md`
- Create: `docs/repository-layout.md`
- Create: `docs/sources/chatdoctor-healthcaremagic.md`
- Create: `docs/sources/meddialog.md`
- Move: current research design documents under `docs/archive/construction-designs/` where appropriate.
- Remove: superseded tracked prototype JSONL/HTML/CSV outputs and stale generation results from the current tree.

**Interfaces:**
- Consumes: locked summary, analysis report, pipeline README, source cards, and approved design.
- Produces: a reviewer-first repository entry point with one unambiguous release.

- [ ] **Step 1: Write the root README and data card**

Document MemCalib's A/B/C capability definition, block-facing/atom-evaluated protocol, v0.1 statistics, five-minute verification workflow, repository map, current medical-domain scope, and deferred evaluation status.

- [ ] **Step 2: Write schema, construction, source, and notice documents**

Record upstream identifiers and licensing facts. Explicitly state that ChatDoctor-HealthCareMagic has no license in its current dataset card and that this private review release is not cleared for public redistribution.

- [ ] **Step 3: Remove obsolete tracked artifacts**

Use `git rm` only for tracked superseded outputs. Do not delete ignored full source files or local API intermediates needed for provenance. Keep the current release, the formal analysis report, locked manifests, prompts, tests, and construction scripts.

- [ ] **Step 4: Verify documentation links and tracked-file inventory**

```bash
git ls-files | sort
git ls-files -z | xargs -0 du -h | sort -h | tail -30
```

Require one obvious release directory and no tracked file above 100 MB.

- [ ] **Step 5: Commit documentation and cleanup**

```bash
git add -A
git commit -m "Document the MemCalib benchmark release"
```

### Task 5: Final Local Verification

**Files:**
- Modify generated manifest only if verification identifies a deterministic metadata defect.

**Interfaces:**
- Consumes: complete reorganized repository.
- Produces: verified clean commit ready for private publication.

- [ ] **Step 1: Run the complete test suite**

```bash
PYTHONPATH=pipeline "$PY" -m unittest discover -s tests -p 'test_*.py'
```

- [ ] **Step 2: Run release verification and secret scanning**

```bash
"$PY" tools/verify_release.py --release-dir release/memcalib-v0.1
git grep -n -I -E 'DASHSCOPE_API_KEY=.*|BAILIAN_API_KEY=.*|sk-[A-Za-z0-9_-]{16,}' -- . || true
```

Environment-variable names in documentation are allowed; credential values are not.

- [ ] **Step 3: Verify Git state and release size**

```bash
git diff --check
git status --short
git count-objects -vH
find release/memcalib-v0.1 -type f -size +50M -print
```

- [ ] **Step 4: Commit any final deterministic corrections**

```bash
git add -A
git commit -m "Finalize the MemCalib private review repository"
```

Skip this commit when the working tree is already clean.

### Task 6: Create And Verify The Private GitHub Repository

**Files:**
- No repository content changes expected.

**Interfaces:**
- Consumes: verified local `main` commit and authenticated GitHub CLI session.
- Produces: private GitHub repository URL and pushed default branch.

- [ ] **Step 1: Confirm GitHub identity without exposing credentials**

```bash
gh auth status
gh api user --jq .login
```

- [ ] **Step 2: Fast-forward local main**

```bash
git checkout main
git merge --ff-only codex/memcalib-repository
```

- [ ] **Step 3: Create the private repository and push main**

```bash
gh repo create memcalib --private --source=. --remote=origin --push
```

If `memcalib` already exists under the authenticated account, stop and report the collision rather than modifying an unrelated repository.

- [ ] **Step 4: Verify remote visibility, default branch, and commit**

```bash
gh repo view --json nameWithOwner,visibility,defaultBranchRef,url
git rev-parse HEAD
git ls-remote --heads origin main
```

Expected: repository `memcalib`, visibility `PRIVATE`, default branch `main`, and matching local/remote commit hashes.
