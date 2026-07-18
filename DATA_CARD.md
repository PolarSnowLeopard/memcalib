# MemCalib v2.1 Data Card

## Dataset Summary

MemCalib v2.1 is a 15,000-record English dataset for studying calibrated use of retrieved conversational memory. Each record contains a current question, two realistic memory blocks shown to the answer model, and hidden atomic annotations that specify expected influence strength, action, evidence, counterfactual behavior, and observable grading criteria.

The release is restricted to private coauthor research review and controlled internal training. It is not cleared for public redistribution.

## Benchmark Task

Given a question and stored memory blocks, generate a useful response that:

1. ignores memories that should leave no answer footprint;
2. uses supporting memories only within their valid scope;
3. lets controlling memories materially constrain the answer;
4. explicitly corrects relevant memories that are wrong, stale, or unsafe when correction is required.

The answer model sees model-facing blocks, not hidden atoms or rubrics. Evaluation is performed at atomic granularity.

## Dataset Composition

| Unit | Count |
|---|---:|
| Records | 15,000 |
| Health / general / coding | 7,500 / 3,750 / 3,750 |
| Model-facing memory blocks | 30,000 |
| Multi-atom model-facing blocks | 15,000 (50.0%) |
| Records containing a multi-atom block | 15,000 (100%) |
| Hidden atomic memories | 53,316 |
| Strict / review / reject / invalid | 15,000 / 0 / 0 / 0 |
| Upstream datasets | 8 |

Every record has exactly two visible memory blocks:

- one `composite_grounded` block containing all source-grounded real atoms for that record;
- one single-atom synthetic Hard A block designed to look superficially usable while remaining normatively unusable.

The composite block contains at least two hidden real atoms. This enforces the intended benchmark distinction between realistic non-atomic retrieval units shown to the model and atomic annotations used for evaluation.

### Atomic labels and actions

| Label | Meaning | Count |
|---|---|---:|
| A | no observable influence; suppress | 16,668 |
| B | bounded supporting influence | 19,032 |
| C | controlling or materially constraining influence | 17,616 |

A/B/C encode usage strength, not truthfulness. The independent `memory_action` field encodes direction:

| Label-action | Meaning | Count |
|---|---|---:|
| A + `ignore` | leave no atom-specific footprint | 16,668 |
| B + `apply` | use as bounded support | 18,899 |
| B + `correct` | correct relevant content with bounded influence | 133 |
| C + `apply` | materially constrain the answer | 17,422 |
| C + `correct` | explicitly correct a controlling wrong/stale/unsafe memory | 194 |

Allowed combinations are A+ignore, B+apply/correct, and C+apply/correct. A+correct is forbidden. In particular, an incorrect memory that must be corrected is B or C, not A.

### Hard A families

Each record contains exactly one synthetic Hard A atom. The five mechanisms are exactly balanced globally and within every domain.

| Family | Intended failure test | Total | Health | General | Coding |
|---|---|---:|---:|---:|---:|
| `factual_judgment_pollution` | a profile fact or prior belief biases an objective judgment | 3,000 | 1,500 | 750 | 750 |
| `scope_overreach` | a valid fact from another scope is extended beyond its authority | 3,000 | 1,500 | 750 | 750 |
| `current_evidence_conflict` | older memory competes with stronger current evidence but must not control | 3,000 | 1,500 | 750 | 750 |
| `profile_style_near_neighbor` | a nearby profile/style fact appears relevant but has no decision authority | 3,000 | 1,500 | 750 | 750 |
| `untriggered_preference` | a genuine preference is not triggered by the current task | 3,000 | 1,500 | 750 | 750 |

Hard A atoms must satisfy zero-footprint behavior: they may be surface-related, but cannot change the conclusion, prioritization, evidence weighting, recommendation, or wording in an atom-specific way. Wrong, stale, or unsafe content that should be corrected is excluded from Hard A and represented as B/C+correct.

### Source distribution

| Domain | Source | Records | Recorded release license |
|---|---|---:|---|
| health | OpenMed/MedDialog | 3,793 | unknown in v2.1 release metadata |
| health | lavita/ChatDoctor-HealthCareMagic-100k | 3,707 | unknown |
| general | HuggingFaceH4/ultrachat_200k | 2,377 | MIT |
| general | OpenAssistant/oasst1 | 470 | Apache-2.0 |
| general | OpenAssistant/oasst2 | 903 | Apache-2.0 |
| coding | ise-uiuc/Magicoder-OSS-Instruct-75K | 2,771 | MIT |
| coding | codeparrot/apps | 174 | MIT |
| coding | HuggingFaceH4/stack-exchange-preferences | 805 | CC-BY-SA-4.0 |

All 805 selected Stack Exchange records have complete author attribution metadata. Source proportions are deliberate benchmark coverage choices, not estimates of natural traffic.

## Record Structure

Important top-level groups include:

- stable record, source, split, topic, domain, and license lineage;
- model-facing `question` and two `memory_blocks`;
- hidden atomic `memories`, including label, action, evidence, counterfactual contract, and usage rubric;
- pairwise atom relations and composite-block atom membership;
- deterministic construction QC, independent semantic QC, targeted-repair provenance, and final release adjudication;
- retained source question, answer, context, sampling, and source-admission audit.

See [the benchmark schema](docs/benchmark-schema.md) for the detailed contract.

## Construction and Quality Control

The release was produced through two linked layers.

### Source-to-benchmark foundation

1. inspect source rights and attribution, normalize schemas, filter language/length/noise, and remove exact and near duplicates;
2. sample by domain, source, topic, and construction difficulty rather than raw source volume;
3. run grounded semantic source-QA admission and complete Stack Exchange attribution;
4. over-generate 18,000 benchmark candidates from 8,500 health, 4,750 general, and 4,750 coding seeds;
5. assign hidden atoms, A/B/C labels, actions, evidence, pair relations, counterfactuals, and rubrics;
6. run deterministic validation, targeted repair, independent QC, and exact-quota selection to form the 15,000-record v2 foundation.

### v2.1 structural revision

1. reconstruct all 15,000 records into exactly one multi-atom grounded block and one single Hard A block;
2. enforce an exact 3,000-per-family allocation for the five Hard A mechanisms;
3. accept 14,923 records in the initial deterministic pass and repair only the remaining 77;
4. run independent QC on all 15,000 records, structurally retrying only malformed outputs;
5. repair 461 Hard-A-specific semantic failures and independently recheck them;
6. send 423 unresolved non-Hard-A disputes to a second model family;
7. directly repair and audit the remaining 93 records, then rejudge only changed fingerprints with two independent judges;
8. admit 79 tail records by dual strict consensus and 14 by explicit deterministic manual tiebreak where one judge was strict, the other was non-strict, and the full validator suite passed;
9. revalidate all 15,000 records and enforce exact domain, family, structure, attribution, and uniqueness invariants.

No reject, review, or invalid record entered the final release. Full counts, repair boundaries, formulas, pseudocode, and diagrams are documented in the [v2.1 construction methodology report](docs/reports/memcalib-v21-dataset-construction-methodology.html).

## Intended Uses

- evaluating over-use and under-use of conversational memory;
- supervised or preference/reward-model research using hidden atomic contracts;
- controlled ablations by domain, source, label, action, memory type, Hard A family, and QC path;
- judge calibration and analysis of realistic non-atomic retrieval units.

Researchers using records for training must keep benchmark evaluation splits disjoint and must not expose hidden labels or rubrics to an answer model being evaluated.

## Out-of-Scope Uses

- clinical decision support, diagnosis, or treatment recommendation;
- estimating real-world user, disease, or programming-task prevalence;
- treating source answers or generated annotations as factual gold standards;
- public redistribution without a separate rights, attribution, privacy, and sensitive-content review.

## Known Limitations

- The health subset has unresolved redistribution and privacy risk; all 7,500 health records are conservatively treated as license unknown in the release metadata.
- Source answers and model-generated annotations may be inaccurate even after structural and semantic QC.
- Independent QC is model-assisted. The 93-record tail received explicit deterministic repair and cross-family rejudging, but this does not replace blinded expert annotation.
- Only 327 atoms require `correct`; conclusions about correction behavior have wider uncertainty than aggregate A/B/C results.
- Every record contains one synthetic Hard A, which strengthens over-use testing but introduces a known construction prior.
- A fixed two-block interface is useful for controlled evaluation but does not cover all retrieval-system layouts.

## Maintenance and Versioning

The release manifest, statistics, package manifest, and SHA-256 hashes are the source of truth. Any content change requires a new version and new hashes. Evaluations must reference the exact dataset digest, sample manifest, protocol version, answer-model snapshot, and judge configuration.

The historical v2.0 dataset and seven-model evaluation remain available for audit but must not be combined with v2.1 metrics. The medical-only v0.1 release and its 15,526-record evaluation remain archived under `release/memcalib-v0.1/` and `evaluation/releases/memcalib-ordered-v2.1-full-15526/`.
