# MemCalib v2 Data Card

## Dataset Summary

MemCalib v2 is a 15,000-record English dataset for studying calibrated use of retrieved conversational memory. Each record contains a current question, realistic non-atomic memory blocks shown to the answer model, and hidden atomic annotations that specify both expected influence strength and expected action.

The release is restricted to private coauthor research review and controlled internal training. It is not cleared for public redistribution.

## Benchmark Task

Given a question and stored memory blocks, generate a useful response that:

1. ignores memories that should not affect the current task;
2. uses supporting memories only within their valid scope;
3. lets controlling memories materially constrain the answer;
4. explicitly corrects relevant memories that are wrong, stale, or unsafe when the annotation requires correction.

The answer model sees parent memory blocks, not hidden atoms or rubrics. Evaluation is performed at atomic granularity.

## Dataset Composition

| Unit | Count |
|---|---:|
| Records | 15,000 |
| Health / general / coding | 7,500 / 3,750 / 3,750 |
| Model-facing memory blocks | 51,970 |
| Hidden atomic memories | 53,318 |
| Strict pass / non-blocking review | 14,906 / 94 |
| Upstream datasets | 8 |

### Atomic labels and actions

| Label | Meaning | Count |
|---|---|---:|
| A | no observable influence; suppress | 16,640 |
| B | bounded supporting influence | 19,060 |
| C | controlling or materially constraining influence | 17,618 |

A/B/C encode usage strength, not truthfulness. The independent `memory_action` field encodes direction:

| Action | Meaning | Count |
|---|---|---:|
| `ignore` | leave no atom-specific footprint | 16,640 |
| `apply` | use the memory within its assigned scope | 36,351 |
| `correct` | explicitly correct relevant wrong/stale/unsafe content | 327 |

Allowed combinations are A+ignore, B+apply/correct, and C+apply/correct. A+correct is forbidden.

### Source distribution

| Domain | Source | Records | Recorded release license |
|---|---|---:|---|
| health | OpenMed/MedDialog | 3,793 | unknown in v2 release metadata |
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
- model-facing `question` and `memory_blocks`;
- hidden atomic `memories`, including `u_star`, `memory_action`, counterfactual contracts, and rubrics;
- deterministic construction QC, independent semantic QC, and final release-admission decisions;
- retained source question, answer, context, sampling, and semantic-admission audit.

See [the benchmark schema](docs/benchmark-schema.md) for the detailed contract.

## Construction And Quality Control

The final release was produced through:

1. source rights/attribution review, normalization, quality filtering, and exact/near deduplication;
2. domain/source/topic/difficulty stratified candidate selection;
3. grounded semantic source-QA admission;
4. over-generated memory construction with atomic labels, actions, evidence, counterfactual contracts, and rubrics;
5. deterministic schema, label-action, evidence-grounding, isolation, observability, and pairwise-independence validation;
6. targeted repair of only failed records, preserving all successful records and audit history;
7. independent semantic QC and targeted correction of a detected query-leakage failure mode;
8. strict-first selection to exact domain quotas, with only explicitly non-blocking review records eligible as capacity fallback.

No reject or invalid record entered the final 15,000. Full stage counts and repair-loop details are documented in the [construction methodology report](docs/reports/memcalib-v2-dataset-construction-methodology.html).

## Intended Uses

- evaluating over-use and under-use of conversational memory;
- supervised or preference/reward-model research using the hidden atomic contracts;
- controlled ablations by domain, source, label, action, memory type, and QC status;
- judge calibration and analysis of realistic non-atomic retrieval units.

Researchers using records for training must keep any benchmark evaluation split disjoint and must not expose hidden labels or rubrics to an answer model being evaluated.

## Out-Of-Scope Uses

- clinical decision support, diagnosis, or treatment recommendation;
- estimating real-world user, disease, or programming-task prevalence;
- treating source answers or generated annotations as factual gold standards;
- public redistribution without a separate rights, attribution, privacy, and sensitive-content review.

## Known Limitations

- The health subset has unresolved redistribution and privacy risk; all 7,500 health records are conservatively treated as license unknown in the v2 release metadata.
- Source answers and model-generated annotations may be inaccurate even after structural and semantic QC.
- Independent QC is model-assisted. A systematic query-leakage failure was detected and repaired, but this does not replace blinded expert annotation.
- Only 327 atoms require `correct`; conclusions about correction behavior have wider uncertainty than A/B/C aggregate results.
- Each record includes a synthetic hard-A, which strengthens over-use testing but introduces a construction prior.
- The 94 non-blocking review records should remain explicitly marked; strict-only sensitivity analysis uses 14,906 records.

## Maintenance And Versioning

The release manifest, package manifest, statistics, and SHA-256 hashes are the source of truth. Any content change requires a new version and new hashes. Evaluations must reference the exact dataset digest, sample manifest, protocol version, and model snapshot.

The historical v0.1 medical-only release and its 15,526-record evaluation remain archived under `release/memcalib-v0.1/` and `evaluation/releases/memcalib-ordered-v2.1-full-15526/`.
