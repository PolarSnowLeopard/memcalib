# MemCalib v2 Construction Pipeline

## End-To-End Overview

```text
8 public-source snapshots
  -> rights, attribution, schema, language, and quality screening
  -> exact and near deduplication
  -> domain/source/topic/difficulty stratified sampling
  -> grounded semantic source-QA admission
  -> strict-only source admission and attribution completion
  -> 18,000 over-generated memory benchmark records
  -> deterministic validation and targeted repair loops
  -> independent semantic QC and failure-mode diagnosis
  -> targeted semantic/local repair with full audit retention
  -> strict-first exact-quota selection
  -> 15,000-record locked release
```

The pipeline separates source eligibility, benchmark construction, deterministic validation, independent semantic QC, and release selection. A record cannot skip a gate, and a later repair cannot silently overwrite earlier outputs or audit history.

## 1. Source Preparation

Eight upstream datasets cover health, general dialogue, and coding. Records are normalized to a common source unit while preserving dataset, split, source identifier, license metadata, context, question, answer, topic, and available attribution.

Deterministic filters remove unusable schemas, unsuitable language/length, severe noise, low-quality units, exact duplicates, and near duplicates. Candidate selection is stratified rather than proportional to raw source volume:

1. allocate capacity across domains and sources;
2. smooth topic capacity to avoid domination by the largest topics;
3. target a low/medium/high construction-difficulty mixture;
4. use deterministic quality-weighted ranking within each stratum.

This creates a capability-coverage distribution, not a natural user-traffic estimate.

## 2. Grounded Source Admission

The source semantic gate checks whether the question, answer, and retained context are coherent, answerable, sufficiently informative, non-trivial, and supported by quoted evidence. Structural failures are retried only for affected IDs; valid decisions remain frozen.

The general/coding source run processed 34,150 candidates. After targeted structural retries, 33,574 were resolved and 576 remained invalid. Strict capacity was sufficient for the locked admission of 4,750 general and 4,750 coding source units. Stack Exchange candidates additionally required complete author attribution; 67 incomplete candidates were excluded before final admission.

The 9,500 admitted general/coding units were combined with 15,577 previously admitted health units, creating 25,077 construction seeds.

## 3. Over-Generated Benchmark Construction

Construction draws 18,000 seeds to leave capacity for downstream rejection:

| Domain | Requests |
|---|---:|
| health | 8,500 |
| general | 4,750 |
| coding | 4,750 |

For each seed, the construction contract produces realistic parent memory blocks and hidden atomic propositions. Every atom receives:

- A/B/C normative influence strength;
- an independent `ignore`, `apply`, or `correct` action;
- source-grounded evidence or an explicit synthetic hard-A derivation;
- a counterfactual behavior contract;
- an observable usage rubric;
- pairwise relations needed to detect overlap or dependence.

The source answer supports construction coherence but is not treated as factual gold and cannot be silently converted into ungrounded memory content.

## 4. Deterministic Validation And Repair

Every constructed record must pass schema, enum, identity, atomicity, evidence-grounding, label-action, query-isolation, observability, rubric-objectivity, and pairwise-independence checks.

Repair loops operate only on the previous residual set. Accepted records are frozen, request/output fingerprints are checked, and every rejection remains auditable.

| Stage | Submitted | Newly accepted | Cumulative accepted | Residual |
|---|---:|---:|---:|---:|
| Initial construction | 18,000 | 6,888 | 6,888 | 11,112 |
| Targeted repair 1 | 11,112 | 6,038 | 12,926 | 5,074 |
| Targeted repair 2 | 5,074 | 800 | 13,726 | 4,274 |
| Targeted repair 3 | 4,274 | 233 | 13,959 | 4,041 |
| Strict local evidence repair | 4,041 | 1,624 | 15,583 | 2,417 |

The local repair was deliberately narrow: it could repair verbatim evidence grounding and an empty declared source, then had to pass the original validator suite. It could not rewrite semantic targets merely to obtain a pass.

## 5. Independent Semantic QC

Independent QC judges atom correctness, label/action consistency, observability, query leakage, pairwise overlap, and overall release suitability without relying on the construction decision.

The first independent pass exposed a systematic query-leakage failure mode: many otherwise valid atoms restated or entailed the current question. Because the failure was systematic, the pipeline did not relax the standard or admit rejects. It diagnosed representative examples, reconstructed affected semantic content, added qualified reserve records, and repeatedly recomputed the same independent QC contract. Only targeted IDs changed in each iteration.

The final candidate pool contained 16,195 independently classified records:

| Domain | Strict | Review | Reject | Invalid |
|---|---:|---:|---:|---:|
| health | 7,491 | 29 | 440 | 59 |
| general | 3,669 | 91 | 369 | 48 |
| coding | 3,746 | 19 | 230 | 4 |
| total | 14,906 | 139 | 1,039 | 111 |

## 6. Release Selection

Release selection is deterministic and domain-constrained:

```text
for domain in [health, general, coding]:
    take strict_pass records in locked priority order
    if strict capacity is insufficient:
        take only script-defined non-blocking review records
    never take reject or invalid records
assert exact domain quotas and global uniqueness
```

The final 15,000 records contain 14,906 strict passes and 94 non-blocking reviews, with exact quotas of 7,500 health, 3,750 general, and 3,750 coding. All 805 selected Stack Exchange records have complete attribution. The release contains 51,970 parent blocks and 53,318 atoms.

## 7. Reproducibility And Audit Boundary

Deterministic stages reproduce exactly from the same source snapshots, configuration, seed, and implementation. Model-dependent construction/QC may vary under mutable provider aliases, so canonical artifacts are the locked JSONL plus its manifests and hashes.

The release bundle records:

- dataset and compressed-file SHA-256 digests;
- exact domain/source/label/action distributions;
- request, output, and record fingerprints;
- source admission, deterministic QC, independent QC, repair, exclusion, and release decisions;
- record-level review HTML and a complete methodology report.

Raw API responses, credentials, and bulky retry logs are intentionally excluded from the handoff package but retained locally under the project's audit policy.

For the full source-by-source description, sampling equations, flow diagrams, repair rationale, and release invariants, see the [MemCalib v2 construction methodology report](reports/memcalib-v2-dataset-construction-methodology.html).

## Historical Versions

The medical-only v0.1 pipeline and 200-record multi-domain pilot remain reproducible historical artifacts. Their counts, source coverage, and quality gates must not be used as current v2 release statistics.
