# MemCalib v2.1 Benchmark Schema

MemCalib v2.1 keeps the model-facing retrieval unit separate from the hidden
evaluation unit. The answer model sees two realistic memory blocks, while the
Judge and training pipeline use the atom-level supervision retained inside the
record.

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

Every v2.1 record has exactly two model-facing blocks:

1. a composite real-memory block containing all source-grounded atoms for the
   record; and
2. a synthetic Hard A block containing one plausible but non-actionable atom.

Consequently, the 15,000-record release contains 30,000 visible blocks. Exactly
15,000 blocks are multi-atom blocks, so the visible-block multi-atom rate is
50%, and every record contains one decomposable block.

## Atomic Memory

Each `memories[]` entry is one independently judgeable proposition.

| Field group | Representative fields | Meaning |
|---|---|---|
| identity/linkage | `memory_id`, `atom_id`, `parent_memory_id`, `atom_index`, `atom_count` | stable identity and parent position |
| proposition | `text`, `atomic_predicate`, `evidence`, `derivation`, `source` | normalized content and grounding |
| taxonomy | `memory_type`, `subtype`, `hard_a_family`, `query_relation` | diagnostic categorization |
| normative target | `u_star`, `memory_action`, `label_reason` | expected influence strength and direction |
| answer contract | `construction_target`, `counterfactual_contract`, `usage_rubric` | observable expected behavior |

The final release contains 53,316 hidden atoms: 38,316 source-grounded atoms
and 15,000 synthetic Hard A atoms. A record contains between 3 and 8 atoms
after the two blocks are atomized.

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

## Hard A Families

Hard A is not a generic off-topic distractor. It is close enough to tempt a
model, but it must leave no atom-specific footprint in the answer. v2.1
contains five balanced mechanisms:

| Family | Construction principle | Why the correct target is A |
|---|---|---|
| factual judgment pollution | a nearby fact or judgment is introduced without establishing that it applies to the current case | topical proximity is not case applicability |
| scope overreach | a valid statement from a broader, narrower, or adjacent scope is presented as if transferable | the required scope bridge is absent |
| current evidence conflict | a plausible prior claim conflicts with stronger evidence explicitly available in the current question | current evidence defeats reliance on the memory |
| profile/style near-neighbor | a profile or style fact belongs to a similar but different user, task, or context | entity or context identity is not established |
| untriggered preference | a real-looking preference is supplied without the condition that would activate it | the trigger is absent from the current request |

Each family contributes exactly 3,000 records. Within every family, the locked
domain allocation is 1,500 health, 750 general, and 750 coding.

## Quality-Control Layers

- `semantic_qc` and `semantic_admission` establish that the upstream source unit is coherent and constructible.
- `qc` contains record-level atomicity, evidence grounding, label-action consistency, query isolation, observability, rubric objectivity, and pairwise-independence gates.
- `deterministic_qc` records the final machine-checkable construction decision and lexical-overlap audit.
- `independent_qc` records atom checks, pair checks, issues, reasons, and the independent semantic decision.
- `release_admission` records the final strict decision and the exact domain target.

## Structural Invariants

- record IDs and source IDs are unique in the final release;
- every record has exactly two visible blocks: one source-grounded composite
  block and one one-atom Hard A block;
- every record contains at least two source-grounded atoms, so the composite
  block is genuinely decomposable;
- exactly 50% of visible blocks are multi-atom blocks;
- every atom links to exactly one block in the same record;
- block `atom_ids`, atom positions, and counts are mutually consistent;
- evidence is grounded according to the locked source-substring policy;
- A is always paired with `ignore`; B/C are paired with `apply` or `correct`;
- wrong, stale, or unsafe content that needs an explicit correction is B/C +
  `correct`, never A + `correct`;
- the five Hard A families are exactly balanced globally and proportionally
  balanced within each domain;
- deterministic QC must pass for every released record;
- independent semantic QC must resolve to `strict_pass` for every released
  record; review, reject, and invalid states are excluded;
- generated benchmark fields are English, while retained raw evidence may preserve source wording;
- the final release contains exactly 15,000 records in the locked 7,500/3,750/3,750 domain allocation.

Aggregate counts and content hashes are recorded in the v2.1 release stats,
manifest, and package manifest under
`pipeline/data/multidomain/full-v2/revision-composite-harda/`.
