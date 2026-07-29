# Repository Layout

## Current v2.4

| Path | Purpose |
|---|---|
| `docs/current/v2.4/` | Current schema, handoff, QC report, and review samples |
| `evaluation/current/v2.4/` | Current configs, locked evaluation releases, and analyses |
| `pipeline/current/v2.4/` | Index of active numbered construction stages |
| `pipeline/data/multidomain/full-v2/revision-coding-text-observable-v24/` | Ignored local 15k dataset, API audit, and handoff ZIP |

The complete dataset is intentionally local because it is large and contains
construction intermediates. `tools/package_memcalib_v24_handoff.py` builds the
deterministic DingTalk-ready coauthor ZIP.

## Historical Archive

| Path | Purpose |
|---|---|
| `docs/archive/versions/` | v2.0-v2.3 reviewer-facing documentation |
| `docs/archive/construction-designs/` | Early construction proposals |
| `docs/archive/plans/` | Historical implementation plans |
| `evaluation/archive/` | v0.1-v2.3 configs, releases, analyses, and cluster notes |
| `release/archive/` | Early repository-tracked release packages |
| `pipeline/archive/` | Lineage boundary for numbered stages 00-101 |

Historical machine manifests retain their creation-time paths. The archive
move does not rewrite those snapshots or their content hashes.

## Stable Executable Interfaces

`pipeline/` keeps numbered scripts in one flat namespace because stage numbers
and sibling imports are part of the reproducible command interface. Current
v2.4 uses stages 102-110; earlier stages remain executable lineage, not current
review entry points.

`evaluation/scripts/`, `evaluation/prompts/`, and `evaluation/templates/` are
shared executable code. Current shell wrappers target
`evaluation/current/v2.4/`; historical wrappers target `evaluation/archive/`.

## Local Data and Credentials

`pipeline/data/`, `evaluation/runs/`, raw source snapshots, API requests,
responses, logs, and large intermediates are ignored. They are not renamed by
repository cleanup, so resumability and local audit trails remain intact.

The repository never searches user home directories for API keys. Credentials
are read only from environment variables at execution time.
