# MemCalib v2 Benchmark Schema

## Evaluation Boundary

MemCalib strictly separates model-facing input from hidden supervision.

### Model-facing input

- `question`
- ordered `memory_blocks[].memory_text`

### Hidden evaluation and training supervision

- atomic `memories[]`;
- normative A/B/C use strength (`u_star`);
- `memory_action` (`ignore`, `apply`, or `correct`);
- counterfactual contracts and observable usage rubrics;
- source evidence, construction QC, independent QC, and release audit.

An answer-model evaluation must not expose hidden atoms, labels, actions, or rubrics to the answer model.

## Top-Level Record

| Field group | Representative fields | Role |
|---|---|---|
| identity | `id`, `schema_version`, `domain` | stable record identity and version |
| source lineage | `source_dataset`, `source_id`, `source_index`, `source_split`, `source_topic`, `source_license`, `source_metadata` | upstream provenance and attribution |
| model input | `question`, `memory_blocks` | visible benchmark input |
| hidden supervision | `memories`, `atom_pair_relations` | atomic targets and pairwise relations |
| source audit | `raw_query`, `source_answer`, `source_context`, `raw_selection` | retained construction evidence |
| source admission | `semantic_qc`, `semantic_admission` | grounded source-QA decision |
| benchmark QC | `qc`, `deterministic_qc`, `independent_qc` | construction and semantic quality gates |
| release | `accepted`, `release_admission`, `notes` | final inclusion state and review notes |

## Parent Memory Block

A parent block is the realistic unit returned by a memory system. It can contain multiple atomic propositions and is intentionally not reduced to one label.

| Field | Meaning |
|---|---|
| `parent_memory_id` | stable parent identifier |
| `memory_text` | canonical text shown to the answer model |
| `raw_evidence` | retained source evidence |
| `source` | parent content source class |
| `atom_ids` | hidden atoms linked to this block |
| `atomization_notes` | construction/audit note |

Mixed parent blocks test whether a model can use one proposition while suppressing, bounding, or correcting another proposition in the same retrieved unit.

## Atomic Memory

Each `memories[]` entry is one independently judgeable proposition.

| Field group | Representative fields | Meaning |
|---|---|---|
| identity/linkage | `memory_id`, `atom_id`, `parent_memory_id`, `atom_index`, `atom_count` | stable identity and parent position |
| proposition | `text`, `atomic_predicate`, `evidence`, `derivation`, `source` | normalized content and grounding |
| taxonomy | `memory_type`, `subtype`, `hard_a_family`, `query_relation` | diagnostic categorization |
| normative target | `u_star`, `memory_action`, `label_reason` | expected influence strength and direction |
| answer contract | `construction_target`, `counterfactual_contract`, `usage_rubric` | observable expected behavior |

## Label And Action Semantics

| Label | Normative influence |
|---|---|
| A | no observable atom-specific influence |
| B | bounded, local supporting influence |
| C | controlling or materially constraining influence |

The label does not encode truthfulness. Direction is encoded separately:

- `ignore`: leave no atom-specific footprint;
- `apply`: use the memory within its valid scope;
- `correct`: explicitly correct relevant wrong, stale, or unsafe content.

Allowed label-action pairs are:

```text
A -> ignore
B -> apply | correct
C -> apply | correct
```

For a `correct` atom, the actual-use Judge still assigns B or C according to how strongly the correction affects the answer.

## Quality-Control Layers

- `semantic_qc` and `semantic_admission` establish that the upstream source unit is coherent and constructible.
- `qc` contains record-level atomicity, evidence grounding, label-action consistency, query isolation, observability, rubric objectivity, and pairwise-independence gates.
- `deterministic_qc` records the final machine-checkable construction decision and lexical-overlap audit.
- `independent_qc` records atom checks, pair checks, issues, reasons, and the independent semantic decision.
- `release_admission` records strict/review eligibility and the exact domain target.

## Structural Invariants

- record IDs and source IDs are unique in the final release;
- every atom links to exactly one block in the same record;
- block `atom_ids`, atom positions, and counts are mutually consistent;
- evidence is grounded according to the locked source-substring policy;
- A is always paired with `ignore`; B/C are paired with `apply` or `correct`;
- deterministic QC must pass for every released record;
- release admission is either `strict_pass` or explicitly allowed non-blocking `review`;
- reject and invalid states are excluded;
- generated benchmark fields are English, while retained raw evidence may preserve source wording;
- the final release contains exactly 15,000 records in the locked 7,500/3,750/3,750 domain allocation.

Aggregate counts and content hashes are recorded in the release stats, manifest, and package manifest under `pipeline/data/multidomain/full-v2/`.
