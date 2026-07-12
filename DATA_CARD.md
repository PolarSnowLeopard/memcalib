# MemCalib v0.1 Data Card

## Dataset Summary

MemCalib is a benchmark for calibrated use of conversational memory. Each record contains a current query, realistic parent memory blocks shown to the answer model, and hidden atomic annotations used for evaluation. Atomic memories are labeled according to how strongly they should influence the response.

Version `v0.1` contains 15,528 English medical-domain records derived from public QA sources. It is a private research review release and is not cleared for public redistribution.

## Benchmark Task

Given a question and a collection of stored memory blocks, generate a useful response that:

1. does not introduce content from contextually irrelevant memories;
2. uses supporting memories only within their valid scope;
3. incorporates controlling memories when omission would make the response incomplete, unsafe, or inapplicable.

Parent blocks may contain multiple related atomic facts with different A/B/C roles. The answer model is evaluated at atomic granularity without receiving those hidden labels.

MemCalib is related to StratMem-Bench (arXiv:2604.26243), which also distinguishes required, supportive, and irrelevant memory. The current release should not be cited as originating that three-way distinction. Its distinct evaluation representation uses non-atomic model-facing blocks, hidden atomic labels, and per-atom observable rubrics at 15,528-sample scale.

## Dataset Composition

| Unit | Count |
|---|---:|
| Samples | 15,528 |
| Parent memory blocks | 56,044 |
| Atomic memories | 78,734 |
| Mixed-label parent blocks | 7,963 |

### Atomic labels

| Label | Meaning | Count |
|---|---|---:|
| A | irrelevant or forbidden to use | 22,722 |
| B | supporting, with bounded influence | 25,783 |
| C | controlling or required | 30,229 |

### Source distribution

| Source | Samples |
|---|---:|
| `lavita/ChatDoctor-HealthCareMagic-100k` | 7,765 |
| `OpenMed/MedDialog` | 7,763 |

The near-equal source distribution is an explicit benchmark coverage choice and does not estimate the natural prevalence of either source.

### Topic coverage

The release covers 12 automatically assigned medical topic groups: acute symptoms, cardiovascular health, chronic disease, digestive health, general/other, medication and treatment, mental health and sleep, neurology, pediatrics, pregnancy and reproductive health, respiratory/ENT, and skin/allergy.

## Record Structure

Important top-level fields include:

- `id`: stable benchmark sample identifier;
- `source_dataset`, `source_record_id`, `source_topic`: source lineage;
- `question`: decontextualized model-facing query;
- `memory_blocks`: model-facing stored memory blocks;
- `memories`: hidden atomic annotations and rubrics;
- `composition`: aggregate sample composition;
- `qc`: construction-stage quality gates;
- `construction_audit`: generation and source lineage;
- `raw_query`, `doctor_answer`: retained source evidence for audit, not model-facing benchmark input.

See [docs/benchmark-schema.md](docs/benchmark-schema.md) for the detailed contract.

## Construction Process

1. Normalize all locally available records from the two sources.
2. Apply deterministic schema, language, length, noise, and quality filters.
3. Remove exact and near-duplicate source questions.
4. Select a balanced candidate pool by source, topic, and construction complexity.
5. Apply a grounded semantic source QA gate.
6. Construct English parent memories, atomic memories, A/B/C labels, targets, and rubrics with a locked LLM prompt.
7. Reject malformed or out-of-schema records and run benchmark-level structural QC.

The final release contains 15,528 accepted records from 15,577 strict-pass source records admitted to construction. The complete lineage and hashes are included under `release/memcalib-v0.1/provenance/`.

## Quality Checks

Every released record passed construction checks for:

- atomic decomposition;
- duplicate control;
- question-memory leakage;
- Hard-A target consistency;
- rubric objectivity;
- English generated-field language;
- fixed memory source, type, and label enums.

The release verifier independently checks all file hashes, JSON parsing, ID uniqueness, reconstructed source hash, and aggregate counts.

## Intended Uses

- evaluating memory-aware answer generation;
- diagnosing under-use and over-use at atomic granularity;
- comparing model behavior across label, memory type, topic, Hard-A family, and mixed-parent subsets;
- judge calibration and rubric-based reward modeling research;
- studying the gap between realistic memory blocks and atomic evaluation units.

## Out-of-Scope Uses

- clinical decision support or medical diagnosis;
- estimating real-world disease or demographic prevalence;
- claiming general-domain dialogue coverage from v0.1;
- treating source doctor answers or LLM annotations as verified medical truth;
- public redistribution before rights and privacy review is complete.

## Known Limitations

### Domain concentration

Both v0.1 sources are medical QA datasets. The topic diversity is intra-domain. General conversational memory claims require additional non-medical sources.

### LLM-generated annotations

Memory blocks, atomic decompositions, labels, and rubrics are generated through a fixed LLM construction process and rule validation. A 100-sample human review found the quality suitable for continued development, but a publication-grade stratified double-annotation study has not yet been completed.

### Response-level validity

The release has not yet been calibrated against a representative set of model responses. Counterfactual answer pairs, dual-judge agreement, and human response adjudication remain pending.

### Source quality and medical safety

Public medical QA text may contain inaccurate, incomplete, outdated, or unsafe advice. Source answers are retained for construction audit and are not reference-standard clinical responses.

### Privacy and sensitive content

The source datasets contain real-world-style medical questions and may contain names, locations, dates, or other personal details. No claim of complete de-identification is made. A dedicated PII and sensitive-content audit is required before public release.

### Rights status

`OpenMed/MedDialog` declares Apache-2.0. The current `lavita/ChatDoctor-HealthCareMagic-100k` dataset card does not state a license. MemCalib v0.1 is therefore restricted to private co-author review while redistribution rights are resolved.

## Maintenance And Versioning

The release manifest is the source of truth for file hashes, counts, and lineage. Any content change requires a new release version and new hashes. Generated model evaluations must reference the exact release manifest SHA-256 and fixed model snapshots.
