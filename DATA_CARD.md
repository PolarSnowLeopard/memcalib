# MemCalib v2.4 Data Card

## Dataset Summary

MemCalib v2.4 is a 15,000-record English dataset for studying calibrated use
of retrieved conversational memory. Each record contains a current question,
3–20 natural-language memory blocks shown to an answer model, and hidden
atomic annotations that specify expected influence strength, action, evidence,
counterfactual behavior, and observable grading criteria.

The release is restricted to private coauthor research review and controlled
internal training. It is not cleared for public redistribution.

## Benchmark Task

Given a question and stored memory blocks, generate a useful response that:

1. ignores memories that should leave no answer footprint;
2. uses supporting memories only within their valid scope;
3. lets controlling memories materially constrain the answer;
4. explicitly corrects relevant memories that are wrong, stale, or unsafe when
   correction is required.

The answer model sees natural paragraphs, not atom boundaries, labels, or
rubrics. Evaluation is performed at atomic granularity.

## Dataset Composition

| Unit | Count |
|---|---:|
| Records | 15,000 |
| Health / general / coding | 7,500 / 3,750 / 3,750 |
| Model-facing memory blocks | 74,800 |
| Multi-atom blocks | 59,800 (79.95%) |
| Blocks with at least three atoms | 48,548 (64.90%) |
| Hidden atomic memories | 234,221 |
| Atoms per record | 6–63 (mean 15.6147, median 14) |
| Atoms per block | 1–20 |
| Difficulty level 1 / 2 / 3 | 3,751 / 7,500 / 3,749 |
| v2.3 block-QC strict / review | 13,923 / 1,077 |
| v2.4 coding independent-QC strict / manual adjudication | 3,735 / 15 |
| Upstream datasets | 8 |

The visible-block count retains the v2.2 long-tail distribution. v2.3 adds an
independent atom-count long tail inside blocks. Every multi-atom block is
rendered as one natural paragraph without visible numbering or atom-boundary
markers. The canonical Hard A remains a singleton block. v2.4 keeps those
memories locked and revises all coding tasks for answer-text observability.

### Atomic labels and actions

| Label | Meaning | Count |
|---|---|---:|
| A | no observable influence; suppress | 197,573 |
| B | bounded supporting influence | 19,032 |
| C | controlling or materially constraining influence | 17,616 |

| Label-action | Meaning | Count |
|---|---|---:|
| A + `ignore` | leave no atom-specific footprint | 197,573 |
| B + `apply` | use as bounded support | 18,899 |
| B + `correct` | correct relevant content with bounded influence | 133 |
| C + `apply` | materially constrain the answer | 17,422 |
| C + `correct` | explicitly correct a controlling wrong/stale/unsafe memory | 194 |

A/B/C encode usage strength, not truthfulness. Allowed combinations are
A+ignore, B+apply/correct, and C+apply/correct. A+correct is forbidden. v2.3
adds 115,402 auxiliary atoms, all of which are A+ignore; original v2.2 atoms,
labels, actions, questions, and source lineage are locked.

### Three difficulty strata

Difficulty is determined from hidden atoms per noncanonical block:

- **level 1:** no noncanonical block exceeds four atoms and at most one exceeds
  two atoms;
- **level 2:** the largest noncanonical block contains three to seven atoms;
- **level 3:** at least one noncanonical block contains eight or more atoms, or
  at least two contain five or more atoms.

The global target is approximately 25% / 50% / 25%, allocated separately
within each domain. The one-record rounding difference is recorded in release
statistics.

### Hard A families

Each record contains exactly one canonical Hard A atom. The five mechanisms
remain exactly balanced at 3,000 records each:

1. factual-judgment pollution;
2. scope overreach;
3. current-evidence conflict;
4. profile/style near-neighbor;
5. untriggered preference.

Hard A atoms may be surface-related but cannot change the conclusion,
prioritization, evidence weighting, recommendation, or wording in an
atom-specific way. Wrong, stale, or unsafe content that should be corrected is
represented as B/C+correct, not Hard A.

### Source distribution

| Domain | Source | Records | Recorded release license |
|---|---|---:|---|
| health | OpenMed/MedDialog | 3,793 | unknown in release metadata |
| health | lavita/ChatDoctor-HealthCareMagic-100k | 3,707 | unknown |
| general | HuggingFaceH4/ultrachat_200k | 2,377 | MIT |
| general | OpenAssistant/oasst1 | 470 | Apache-2.0 |
| general | OpenAssistant/oasst2 | 903 | Apache-2.0 |
| coding | ise-uiuc/Magicoder-OSS-Instruct-75K | 2,771 | MIT |
| coding | codeparrot/apps | 174 | MIT |
| coding | HuggingFaceH4/stack-exchange-preferences | 805 | CC-BY-SA-4.0 |

All selected Stack Exchange records have complete author attribution metadata.
Source proportions are benchmark coverage choices, not estimates of natural
traffic.

## Record Structure

Important top-level groups include:

- stable record, source, split, topic, domain, and license lineage;
- model-facing `question` and ordered `memory_blocks`;
- hidden atomic `memories`, including label, action, evidence,
  counterfactual contract, and usage rubric;
- pairwise atom relations and atom-to-block membership;
- v2.1 construction, v2.2 block-layout, v2.3 expansion/rewrite provenance, and
  v2.4 coding text-observability provenance;
- deterministic construction QC, independent semantic QC, targeted repair,
  and final release adjudication.

See [the v2.4 benchmark schema](docs/current/v2.4/benchmark-schema-v2.4.md) for the detailed
contract.

## Construction and Quality Control

The release was produced through five versioned layers.

### Source-to-benchmark foundation

1. normalize eight public sources; filter language, length, noise, and exact or
   near duplicates;
2. sample by domain, source, topic, and construction difficulty;
3. run grounded semantic source-QA admission and complete Stack Exchange
   attribution;
4. over-generate 18,000 benchmark candidates from 8,500 health, 4,750 general,
   and 4,750 coding seeds;
5. assign hidden atoms, A/B/C labels, actions, evidence, pair relations,
   counterfactuals, and rubrics;
6. run deterministic validation, targeted repair, independent QC, and
   exact-quota selection.

### v2.1 controlled block foundation

v2.1 locked the 15,000 questions and source-grounded supervision, reconstructed
the controlled grounded/Hard-A interface, balanced the five Hard-A families,
and resolved all records through deterministic validation and cross-family QC.

### v2.2 visible-block long tail

v2.2 retained all v2.1 supervision while expanding each record to 3–20 visible
blocks. The block-count distribution is identical by domain, and the canonical
Hard A remains a singleton.

### v2.3 atom-count long tail and natural surface form

1. assign one of three difficulty levels and a deterministic target atom count
   to every block;
2. generate only auxiliary A+ignore atoms, with original atoms and supervision
   locked;
3. validate schema, IDs, counts, block membership, atom independence, and
   canonical Hard-A preservation;
4. independently rewrite each multi-atom set as one natural paragraph, without
   access to labels or the current question;
5. validate atom coverage, critical values, single-paragraph form, and absence
   of visible boundaries;
6. independently judge every added atom and every visible block with a
   different model family;
7. regenerate only rejected records, re-run rewriting and QC, and retain all
   failed attempts and hashes;
8. complete a four-record residual tail through explicit, field-level human
   audit: two single-atom content repairs and two omitted-check completions;
9. admit exactly 15,000 strict/review records and exclude all reject/invalid
   records.

The detailed flow, counts, formulas, and repair boundaries are in the
[v2.3 construction report](docs/archive/versions/v2.3/reports/memcalib-v23-composite-block-revision.html).

### v2.4 coding answer-text observability

1. retain all 3,750 coding IDs, sources, memory blocks, atoms, labels, and
   actions;
2. rewrite every coding question into natural-language implementation
   planning, behavior prediction, or debugging diagnosis;
3. rebuild coding reference answers and atom rubrics so every scored behavior
   is decidable from answer text without program execution;
4. reject questions that partly or fully reveal any hidden atom value;
5. retry only failed IDs and freeze successful records;
6. admit 3,735 independent-QC strict records and separately mark 15
   record-level manual adjudications;
7. restore exact v2.3 order and validate the complete 15,000-record release.

All 3,750 coding questions changed and contain the natural-language-only
contract. Coding questions and reference answers contain zero code fences. The
complete protocol and iteration counts are in the
[v2.4 coding revision report](docs/current/v2.4/reports/memcalib-v24-coding-text-observability.md).

## Intended Uses

- evaluating over-use and under-use of conversational memory;
- supervised or preference/reward-model research using hidden atomic contracts;
- controlled ablations by domain, source, label, action, memory type, Hard-A
  family, difficulty stratum, block size, and QC path;
- judge calibration and analysis of realistic non-atomic retrieval units.

Researchers using records for training must keep benchmark evaluation splits
disjoint and must not expose hidden labels or rubrics to an answer model being
evaluated.

## Out-of-Scope Uses

- clinical decision support, diagnosis, or treatment recommendation;
- estimating real-world user, disease, or programming-task prevalence;
- treating source answers or generated annotations as factual gold standards;
- public redistribution without rights, attribution, privacy, and
  sensitive-content review.

## Known Limitations

- The health subset has unresolved redistribution and privacy risk; all 7,500
  health records are conservatively treated as license unknown.
- Source answers and model-generated annotations may remain inaccurate after
  structural and semantic QC.
- Independent QC is model-assisted. The 1,077 v2.3 block-QC review records are
  admitted boundary cases without hard failures, not human-confirmed strict
  cases.
- Four v2.3 residual records and 15 v2.4 coding residual records received
  explicit human completion or adjudication. All paths are separately marked
  and audited, but this does not replace a blinded expert study.
- Only 327 atoms require `correct`, so conclusions about correction behavior
  have wider uncertainty than aggregate A/B/C results.
- v2.3 increases context complexity synthetically while preserving a fixed set
  of questions and original scored atoms; it does not evaluate retrieval
  itself.
- v2.4 changes every coding question and rubric. Existing v2.3 model answers,
  Judge outputs, and scores are not valid v2.4 results and must be regenerated.

## Maintenance and Versioning

The release manifest, statistics, package manifest, and SHA-256 hashes are the
source of truth. Any content change requires a new version and new hashes.
Evaluations must reference the exact dataset digest, sample manifest, protocol
version, answer-model snapshot, and judge configuration.

Historical v2.1, v2.2, and v2.3 artifacts remain available for audit but must
not be combined with v2.4 metrics. The medical-only v0.1 release remains
archived under `release/archive/memcalib-v0.1/`.
