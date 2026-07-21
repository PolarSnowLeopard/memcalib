# MemCalib v2.1 Construction Pipeline

> This document preserves the v2.1 foundation lineage. The current v2.3
> release freezes this foundation and applies the v2.2 long-tail block revision
> plus the v2.3 composite-atom and natural-paragraph revision. See the
> [complete v2.3 methodology report](reports/memcalib-v23-composite-block-revision.html)
> and [v2.3 schema](benchmark-schema-v2.3.md) for the current release contract.

## End-to-End Overview

```text
8 public-source snapshots
  -> rights, attribution, schema, language, and quality screening
  -> exact and near deduplication
  -> domain/source/topic/difficulty stratified source sampling
  -> grounded source-QA semantic admission
  -> strict-only admission and Stack Exchange attribution completion
  -> 18,000 over-generated benchmark candidates
  -> deterministic validation, targeted repairs, independent QC
  -> exact-quota 15,000-record v2 foundation
  -> v2.1 two-block reconstruction
  -> five-family balanced Hard A construction
  -> full deterministic validation
  -> full independent QC, targeted semantic repair, second-family review
  -> direct audited repair of the 93-record tail
  -> 15,000-record strict-only v2.1 release
```

The pipeline separates source eligibility, benchmark construction, deterministic validation, independent semantic QC, and release selection. A record cannot skip a gate. Repairs operate only on failed IDs, successful outputs remain frozen, and every overwritten fingerprint retains an audit trail.

## 1. Source Preparation

Eight upstream datasets cover health, general dialogue, and coding:

| Domain | Sources | Role |
|---|---|---|
| Health | MedDialog; ChatDoctor-HealthCareMagic | symptom, medication, chronic-condition, and care-seeking questions |
| General | UltraChat 200K; OASST1; OASST2 | explanation, planning, writing, household, communication, and productivity tasks |
| Coding | Magicoder OSS Instruct; APPS; Stack Exchange Preferences | implementation, debugging, algorithms, APIs, systems, testing, and code review |

Records are normalized to a common source unit while preserving dataset, split, source ID, license metadata, context, question, answer, topic, and available attribution.

Deterministic filters remove unusable schemas, unsuitable language or length, severe noise, low-information units, exact duplicates, and near duplicates. Candidate selection is stratified rather than proportional to raw source volume:

1. allocate capacity across domains and sources;
2. smooth topic capacity so a large source topic cannot dominate;
3. target a low/medium/high construction-difficulty mixture;
4. rank deterministically within each stratum by quality and a seeded stable hash.

For a stratum \(h\) with \(N_h\) eligible records and a domain target \(n_d\), its initial proportional quota is:

```text
raw_quota(h) = n_d * N_h / sum_j(N_j)
```

Integer quotas are produced with largest-remainder allocation, then adjusted only when a cell lacks capacity. The result is a capability-coverage distribution, not an estimate of natural user traffic.

## 2. Grounded Source Admission

The source semantic gate checks whether the retained question, answer, and context are coherent, answerable, sufficiently informative, non-trivial, and supported by quoted evidence. Structural output failures are retried only for the affected IDs; valid decisions remain frozen.

The general/coding source run processed 34,150 candidates. After targeted structural retries:

| Quantity | Count |
|---|---:|
| Resolved source-QA decisions | 33,574 |
| Residual invalid | 576 |
| Strict general capacity | 4,901 |
| Strict coding capacity before attribution filtering | 5,020 |
| Stack Exchange records missing complete attribution | 67 |
| Strict coding capacity after attribution filtering | 4,953 |
| Final strict general / coding admission | 4,750 / 4,750 |

No capacity was moved between domains and no review item was promoted to fill a quota. The 9,500 admitted general/coding units were combined with 15,577 previously admitted health units, producing 25,077 construction seeds.

## 3. v2 Foundation Construction

Construction over-generates 18,000 records to leave capacity for downstream rejection:

| Domain | Construction requests |
|---|---:|
| health | 8,500 |
| general | 4,750 |
| coding | 4,750 |
| **Total** | **18,000** |

For each seed, the constructor produces model-facing memory text and hidden atomic propositions. Every atom receives:

- normative influence strength A, B, or C;
- an independent `ignore`, `apply`, or `correct` action;
- source-grounded evidence or an explicit synthetic derivation;
- a counterfactual behavior contract;
- an observable usage rubric;
- pairwise relations needed to identify overlap or dependence.

The source answer supports construction coherence but is not treated as factual gold. It cannot be silently converted into an unsupported memory.

Deterministic validators check schema, identity, enum values, evidence grounding, label-action compatibility, question isolation, rubric observability, and pairwise independence. Model-based repair is applied only to the residual set. The v2 foundation then passes an independent semantic QC and exact-domain-quota selection, yielding 15,000 source-aligned records.

## 4. v2.1 Memory Interface Revision

The v2.1 revision keeps each foundation record's source lineage and question but replaces the memory interface.

### 4.1 Two visible blocks

For each record with real atoms \(r_1,\ldots,r_k\), where \(k \ge 2\):

```text
visible_block_1 = numbered composition of r_1 ... r_k
visible_block_2 = one synthetic Hard A atom
hidden_atoms    = r_1 ... r_k plus Hard A
```

The first block must be coherent, exactly cover the real atoms, add no new proposition, and remain recoverable into the original atomic units. The second block must contain exactly one Hard A atom. Therefore:

```text
visible blocks              = 2 * 15,000 = 30,000
multi-atom visible blocks   = 1 * 15,000 = 15,000
multi-atom visible share    = 15,000 / 30,000 = 0.5
records with multi-atom     = 15,000 / 15,000 = 1.0
```

### 4.2 A/B/C and action semantics

The normative labels describe how much influence a memory should have on the current answer:

- **A, suppress:** zero answer footprint; action must be `ignore`.
- **B, bound:** relevant but limited support; action is `apply` or `correct`.
- **C, control:** materially controls or constrains the answer; action is `apply` or `correct`.

Truthfulness and influence are separate. A wrong, stale, or unsafe memory that must be corrected is B/C+correct, not A. A+correct is invalid.

### 4.3 Five Hard A mechanisms

The colleague-provided Hard A design is represented as five mechanisms:

| Family | Construction boundary |
|---|---|
| Factual judgment pollution | profile/belief information appears relevant but cannot alter an objective judgment |
| Scope overreach | a fact valid in another scope cannot be generalized to the current task |
| Current evidence conflict | older memory is superseded by stronger current evidence and must not control the answer |
| Profile/style near-neighbor | a nearby user/style fact lacks decision authority for this query |
| Untriggered preference | a genuine preference is not activated by the current task |

Every Hard A must be surface-relevant enough to create a realistic temptation, yet have no legitimate answer footprint. The release fixes each family at exactly 3,000 records:

```text
health:  1,500 per family
general:   750 per family
coding:    750 per family
global:  3,000 per family
```

## 5. Deterministic Reconstruction Gate

All 15,000 records were reconstructed. The first pass accepted 14,923 and rejected 77:

| Reconstruction stage | Submitted | Accepted | Residual |
|---|---:|---:|---:|
| Initial v2.1 reconstruction | 15,000 | 14,923 | 77 |
| Targeted deterministic repair | 77 | 77 | 0 |
| **Resolved v2.1 candidates** |  | **15,000** | **0** |

Checks included:

- source and record identity preservation;
- exact two-block structure;
- composite coverage and no-new-proposition constraints;
- one and only one Hard A per record;
- family allocation and domain balance;
- label-action legality;
- evidence-substring grounding;
- query isolation and pairwise independence;
- non-empty, objective, atom-specific grading rubrics.

## 6. Independent QC and Iterative Repair

An independent judge received the question, visible blocks, hidden atoms, evidence, family contract, and rubric, but not the construction decision. It evaluated composite correctness, atom validity, label/action fit, observability, Hard A family membership, no-footprint behavior, and release suitability.

After retrying 15 structurally malformed judge outputs, the first complete decision set was:

| Decision | Count |
|---|---:|
| Strict | 14,140 |
| Review | 296 |
| Reject | 564 |
| Invalid | 0 |

The 860 non-strict records were separated by failure type:

- 461 records had repairable Hard-A-specific semantic issues;
- 423 records contained non-Hard-A or multi-cause disputes and were deferred rather than rewritten by the same repair prompt;
- the sets overlap because one record can carry multiple failure reasons.

All 461 Hard-A repair requests returned structurally valid records. Fresh independent QC accepted 412 as strict, placed 7 in review, and rejected 42. Overlaying only those updated fingerprints produced:

| State after targeted semantic repair | Strict | Review | Reject |
|---|---:|---:|---:|
| Full 15,000-record pool | 14,552 | 303 | 145 |

The 423 deferred records were then judged by a second model family. Its local decisions were 369 strict, 10 review, 26 reject, and 18 structurally invalid. Only valid fresh decisions were overlaid; invalid decisions retained their previous audited state. The resulting pool was:

| State after second-family adjudication | Strict | Review | Reject |
|---|---:|---:|---:|
| Full 15,000-record pool | 14,907 | 22 | 71 |

## 7. Direct Repair of the 93-Record Tail

The remaining 93 non-strict records were small enough for direct record-level repair rather than another broad generation round. The repair was constrained to four audited operations:

| Operation | Affected records/actions |
|---|---:|
| Repair a real atom while preserving source support | 59 |
| Replace Hard A with a same-family zero-footprint atom | 47 |
| Remove an unsupported atom | 2 |
| Add a formal deterministic proof record | 16 |

Counts overlap because a record may need more than one operation. Each edit refreshed evidence spans, recomputed record fingerprints, rebuilt composite text, and reran the original deterministic validators.

Only changed fingerprints were sent for fresh cross-family QC. Across the final versions:

| Tail adjudication | Count |
|---|---:|
| Both judges strict | 79 |
| One judge strict, one non-strict, deterministic manual tiebreak | 14 |
| Both judges non-strict | 0 |

The 14 tiebreaks were not silently promoted. Each has both judge outputs, reasons, deterministic validation results, and an explicit manual adjudication record. This produced 15,000 computed strict records.

## 8. Release Invariants

Release succeeds only if every assertion below is true:

```text
assert records == unique_record_ids == unique_source_ids == 15,000
assert domain_counts == {health: 7,500, general: 3,750, coding: 3,750}
assert visible_blocks == 30,000
assert multi_atom_visible_blocks == 15,000
assert every_record_has_one_multi_atom_block
assert hard_a_family_counts == 3,000 for every family
assert all_records_are_strict
assert reject == review == invalid == 0
assert stack_exchange_attribution_complete == 805
assert request_and_record_fingerprints_match
```

Final atomic composition:

| Quantity | Count |
|---|---:|
| Hidden atoms | 53,316 |
| Real atoms | 38,316 |
| Synthetic Hard A atoms | 15,000 |
| A / B / C | 16,668 / 19,032 / 17,616 |
| `correct` atoms | 327 |
| Mean / median atoms per record | 3.5544 / 3 |

## 9. Reproducibility and Audit Boundary

Deterministic stages reproduce exactly from the same source snapshots, configuration, seed, and implementation. Model-dependent construction and QC may vary under mutable provider aliases, so canonical artifacts are the locked JSONL plus manifests and SHA-256 hashes.

The local audit tree retains:

- source admission, exclusions, and attribution cache;
- every request, response, failure, retry, and structural invalid;
- deterministic validator outcomes;
- old and new record fingerprints for repair overlays;
- independent judge raw outputs and normalized decisions;
- direct-repair actions and tiebreak evidence;
- release statistics and review HTML.

Credentials never enter artifacts. Raw API responses and large intermediate files remain local and are excluded from the coauthor package. The shareable package contains the locked dataset, manifest, statistics, review pages, data card, handoff notes, and methodology report.

For a readable paper-oriented treatment with diagrams and pseudocode, see the [MemCalib v2.1 construction methodology report](reports/memcalib-v21-dataset-construction-methodology.html).

## Historical Versions

The previous v2.0 release had 14,906 strict and 94 non-blocking review records with a different visible-block layout. Its dataset and model-evaluation results are retained for audit but are not current v2.1 statistics. The medical-only v0.1 pipeline and 200-record multi-domain pilot remain historical artifacts.

## Current V2.3 Revision

The v2.2 revision expanded each record from two visible blocks to a fixed,
domain-balanced 3-20 block long-tail allocation while preserving questions,
lineage, original atoms, labels, actions, and canonical Hard A. The v2.3
revision keeps those block counts and expands each block to 1-20 hidden atoms.
Added atoms are auxiliary `A+ignore` only, and no record-level total-atom cap is
imposed. Multi-atom blocks are rewritten as natural paragraphs, then checked by
an independent atom-, block-, and record-level judge.

The final v2.3 release has:

| Quantity | Count |
|---|---:|
| Records | 15,000 |
| Visible blocks | 74,800 |
| Multi-atom blocks | 59,800 |
| Blocks with at least three atoms | 48,548 |
| Hidden atoms | 234,221 |
| Level 1 / 2 / 3 | 3,751 / 7,500 / 3,749 |
| Strict / review / reject / invalid | 13,923 / 1,077 / 0 / 0 |

The complete end-to-end source, sampling, construction, repair, and QC history
is documented in the v2.3 methodology report linked at the top of this file.
