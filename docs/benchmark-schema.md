# MemCalib Benchmark Schema

## Evaluation Boundary

MemCalib separates what the answer model sees from what the evaluator sees.

### Model-facing input

- `question`
- ordered `memory_blocks[].memory_text`

### Hidden evaluation data

- `memories[]` atomic annotations
- A/B/C labels
- construction targets
- usage rubrics
- source evidence and construction audit

An evaluation implementation must not expose hidden atomic labels or rubrics to the answer model.

## Top-Level Record

| Field | Type | Role |
|---|---|---|
| `id` | string | stable sample ID |
| `domain` | string | current source-domain marker |
| `source_dataset` | string | upstream dataset identifier |
| `source_record_id` | string | upstream/normalized lineage |
| `source_topic` | string | stratification topic |
| `question` | string | decontextualized current query |
| `memory_blocks` | array | model-facing realistic memories |
| `memories` | array | hidden atomic annotations |
| `composition` | object | sample-level label structure |
| `qc` | object | construction quality gates |
| `construction_audit` | object | prompt, source, and generation lineage |
| `raw_query` | string | retained source question for audit |
| `doctor_answer` | string | retained source answer for audit |

## Parent Memory Block

A parent memory block represents the unit stored or returned by a realistic memory system. It can contain multiple closely related facts.

Important fields:

- `parent_memory_id`: stable parent identifier;
- `memory_text`: third-person canonical memory shown to the answer model;
- `raw_evidence`: retained source evidence;
- `source`: source class for the parent content;
- `atom_count`: number of hidden atoms;
- `parent_label_mode`: `homogeneous` or `mixed`;
- `parent_label_set`: sorted labels represented by its atoms.

Mixed parents are intentional diagnostic cases. They test whether a model can use one fact from a block while suppressing or bounding another related fact.

## Atomic Memory

Each entry in `memories` corresponds to one independently judgeable proposition.

| Field | Meaning |
|---|---|
| `atom_id` | unique atom identifier |
| `parent_memory_id` | link to model-facing block |
| `atom_index`, `atom_count` | location inside parent |
| `text` | canonical atomic memory |
| `evidence` | retained supporting evidence |
| `atomic_predicate` | normalized proposition |
| `derivation` | explicit, inferred, or synthetic |
| `source` | `from_question`, `from_answer`, or `synthetic_hard_a` |
| `memory_type` | fixed memory category |
| `u_star` | A, B, or C use label |
| `hard_a_family` | synthetic negative family where applicable |
| `construction_target` | intended answer-level role |
| `usage_rubric` | observable judge contract |

## A/B/C Semantics

### A: irrelevant or forbidden

The response should not reveal an unsupported influence from the atom. Correct behavior normally leaves no observable footprint. Typical failures include importing the memory as a fact, inventing a restriction, expanding a risk, or allowing an unrelated preference to shape the answer.

### B: supporting and bounded

The atom may improve relevance or personalization, but it must remain local and subordinate to the current task. Typical failures are overexpansion, converting support into a hard constraint, or allowing the memory to dominate the answer.

### C: controlling or required

The atom must alter the answer's core conclusion, recommendation, or constraint. Ignoring it makes the response incomplete, unsafe, or inapplicable.

## Usage Rubric

Common rubric fields include:

- `expected_answer_behavior`
- `memory_usage_weight`
- `validity_scope`
- `correct_use`
- `under_use`
- `over_use`
- `forbidden_memory_role`
- `failure_direction`
- `observable_checks`

Label-specific fields add controlling factors, allowed maximum footprint, contamination signals, or missing-memory failure descriptions. Rubrics are intended to support structured response evaluation; they are not gold model responses.

## Structural Invariants

- sample IDs are unique;
- every atom links to one parent in the same record;
- `atom_count` agrees with the number of linked atoms;
- parent label sets equal the labels of linked atoms;
- A/B/C labels map to `none`, `supporting`, and `controlling` rubric weights;
- fixed source and memory-type enums are respected;
- generated benchmark fields are English in v0.1;
- raw evidence may retain original source wording.

