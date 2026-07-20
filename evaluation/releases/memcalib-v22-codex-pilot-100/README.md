# MemCalib v2.2 Codex answer-only pilot

This internal diagnostic evaluates one reproducible Codex configuration on a
locked 100-record MemCalib v2.2 sample. It is a pilot, not a 15,000-record
leaderboard result and not directly comparable with the v2.1 seven-model table.

## Evaluated configuration

- Interface: Codex CLI non-interactive `exec`
- CLI version: `codex-cli 0.145.0-alpha.18`
- Model: `gpt-5.6-sol`
- Reasoning effort: `medium`
- Session policy: one fresh ephemeral session per answer
- Workspace: a newly created empty temporary directory
- Sandbox: read-only
- User configuration and project rules: disabled
- Tools: forbidden by the answer protocol and audited from the JSON event stream
- Output: a schema-constrained object containing only the answer text

All 200 formal calls completed without a failed request, truncated response, or
tool event. The model received only the answer-system instruction, the current
query, and, in the full-memory condition, the ordered visible memory blocks.
Hidden atoms, A/B/C labels, actions, rubrics, source answers, and construction
audit fields were not model-facing.

## Locked sample

The sample was selected deterministically from the SHA-256-locked 15,000-record
v2.2 release with seed `20260720`. Domain and long-tail block-count margins were
fixed before model inference:

| Dimension | Locked counts |
|---|---:|
| Health / general / coding | 50 / 25 / 25 |
| 3-4 / 5-6 / 7-10 / 11-20 visible blocks | 52 / 30 / 15 / 3 |
| Current-evidence / factual-pollution / profile-neighbor / scope-overreach / untriggered-preference Hard A | 22 / 21 / 21 / 19 / 17 |

All eight v2.2 source datasets are represented. The exact ordered sample ID
digest is
`0a2e367397788e5fdd0e6c2468f9912d6702695bc7269d0e9d09cc4ed2cb04a9`.
The 100 records contain 793 hidden scoring atoms: 550 A, 111 B, and 132 C.

## Primary results

The existing `ordered-usage-v2.1` judge protocol was reused without changing
its prompt or normalization logic. The primary table uses the repository's
label-macro directional rates so that the result follows the existing report
contract.

| Condition | OPB error ↓ | UPB error ↓ | H ↑ | A success | B success | C success | Strict sample accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|
| Full memory | 0.057 | 0.239 | 0.842 | 0.922 | 0.622 | 0.864 | 0.320 |
| No memory | 0.005 | 0.914 | 0.158 | 0.991 | 0.081 | 0.091 | 0.030 |

Paired full-minus-no-memory atom success changed by `-0.069` for A, `+0.541`
for B, and `+0.773` for C. In directional terms, visible memory reduced UPB by
`0.675` while inducing `0.053` additional OPB. This is the expected central
tradeoff: the memories make the answer substantially more responsive to B/C
facts, but also cause some irrelevant A content to enter the response.

Clustered 2,000-replicate bootstrap intervals for the full-memory result are:

| Metric | Estimate | 95% CI |
|---|---:|---:|
| OPB error | 0.057 | [0.037, 0.079] |
| UPB error | 0.239 | [0.182, 0.300] |
| H | 0.842 | [0.803, 0.878] |

## Micro-average sensitivity check

The coauthor-proposed micro definition pools directional mistakes before
division:

```text
OPB_micro = (A->B + A->C + B->C) / (gold A + gold B)
UPB_micro = (B->A + C->A + C->B) / (gold B + gold C)
```

Using the same primary-judge confusion matrix:

| Condition | OPB micro ↓ | UPB micro ↓ | H micro ↑ |
|---|---:|---:|---:|
| Full memory | 0.071 | 0.230 | 0.842 |
| No memory | 0.008 | 0.914 | 0.159 |

The macro and micro H values are nearly identical in this pilot. The directional
components differ modestly because the sample contains many more A atoms than
B or C atoms. The machine-readable `metrics.json` retains the established
macro protocol; this table is an explicitly labeled sensitivity analysis.

## Domain and context-length diagnostics

| Domain | Full-memory OPB ↓ | Full-memory UPB ↓ | Full-memory H ↑ | Strict sample accuracy |
|---|---:|---:|---:|---:|
| Health | 0.046 | 0.257 | 0.836 | 0.420 |
| General | 0.076 | 0.216 | 0.848 | 0.200 |
| Coding | 0.049 | 0.235 | 0.848 | 0.240 |

| Visible blocks | Samples | Atoms | Full-memory OPB ↓ | Full-memory UPB ↓ | Full-memory H ↑ |
|---|---:|---:|---:|---:|---:|
| 3-4 | 52 | 297 | 0.079 | 0.304 | 0.793 |
| 5-6 | 30 | 253 | 0.068 | 0.150 | 0.889 |
| 7-10 | 15 | 183 | 0.028 | 0.167 | 0.897 |
| 11-20 | 3 | 60 | 0.009 | 0.450 | 0.707 |

The 11-20 block row has only three samples and must not be interpreted as a
stable context-length estimate. It confirms that the protocol executes on the
long tail, but a larger panel is required for a reliable scaling curve.

## Judge stability

The primary judge was `qwen3.7-plus` on all 200 answers. A 40-answer sample,
locked before seeing primary-judge outputs, was independently judged by
`deepseek-v4-pro`, covering 325 atoms.

| Agreement view | N | Exact agreement | Kappa |
|---|---:|---:|---:|
| Overall verdict | 325 | 0.982 | 0.964 |
| Ordered A/B/C usage | 325 | 0.972 | 0.935, linear weighted |

Both judges produced structurally valid output on the first pass. Seven primary
rows and one secondary row contain auxiliary evidence/confidence warnings;
these do not remove or alter the ordered usage prediction.

## Artifacts

- `release-manifest.json`: exact sample inputs, distributions, privacy contract,
  ordered ID digest, and artifact hashes.
- `answer-request.manifest.json`: 200 answer request fingerprints.
- `answer-run.manifest.json`: complete answer counts, response lengths, token
  usage, model identity, and output hashes.
- `judge-request.manifest.json`: primary and preselected secondary judge inputs.
- `judge-run.manifest.json`: normalized judge coverage and warning counts.
- `metrics.json`: confusion matrices, macro metrics, paired effects, bootstrap
  intervals, domain panels, and judge agreement.
- `report.html`: self-contained visual report.

Raw answer events, model responses, judge API responses, failures, and
normalized atom-level judgments remain under
`evaluation/runs/memcalib-v22-codex-pilot-100/`. That directory is intentionally
excluded from Git and must be transferred separately when row-level
reaggregation or forensic review is required.

The analyzer's generic validity block expects a multi-model experiment and
therefore labels this single-model pilot `needs_review`. Its model-count checks
are not evidence of missing Codex results: all requested answers and judgments
are complete. Human answer-level validation remains pending.
