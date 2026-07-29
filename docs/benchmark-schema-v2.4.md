# MemCalib v2.4 Benchmark Schema

MemCalib v2.4 is a coding text-observability revision of the locked v2.3
multidomain release. It keeps the same 15,000 record IDs, ordering, domains,
sources, visible memory blocks, hidden memory atoms, A/B/C labels, and memory
actions. It revises all 3,750 coding tasks so that model behavior can be judged
from natural-language answers rather than by executing generated code.

## Release Composition

| Domain | Records |
|---|---:|
| health_seed | 7,500 |
| general | 3,750 |
| coding | 3,750 |
| **Total** | **15,000** |

The health and general records are semantically unchanged from v2.3. Every
coding record passes through the v2.4 revision protocol.

## Model-Facing Fields

The evaluated model receives:

| Field | Meaning |
|---|---|
| `id` | Stable record identifier |
| `domain` | `health_seed`, `general`, or `coding` |
| `question` | Current task |
| `memory_blocks` | Retrieved natural-language memory blocks |

For coding records, `question` always ends with a task-family-specific contract
requiring a natural-language answer and prohibiting executable code and code
blocks. Exact externally visible names, configuration keys, status values, and
error messages must still be stated literally when they are relevant.

## Coding Task Families

| Family | Intended answer |
|---|---|
| `implementation_plan` | Step-by-step natural-language implementation plan |
| `behavior_prediction` | Natural-language explanation of expected behavior |
| `debugging_diagnosis` | Diagnosis and corrected behavior in natural language |

The final coding distribution is:

| Family | Records |
|---|---:|
| implementation planning | 1,879 |
| behavior prediction | 1,141 |
| debugging diagnosis | 730 |

These families are construction strata. They are visible through the wording
of the task, but they are not model-quality labels and do not change the public
A/B/C evaluation protocol.

## Hidden Supervision

The evaluator additionally receives hidden fields:

| Field | Meaning |
|---|---|
| `source_answer` | Natural-language reference answer |
| `memories` | Hidden atomic memories and A/B/C labels |
| `construction_target` | Intended task role of one atom |
| `counterfactual_contract` | Expected answer change if the atom is available |
| `usage_rubric` | Answer-text checks for correct use, under-use, and over-use |
| `coding_text_observability_revision` | Revision lineage and locked fingerprints |
| `v24_coding_admission` | Final admission channel and decision |

The A/B/C semantics are unchanged:

- **A / ignore:** the atom must have no legitimate answer footprint;
- **B / apply or correct:** the atom provides bounded support;
- **C / apply or correct:** the atom controls a material part of the answer.

An incorrect, unsafe, or obsolete memory that must be corrected remains B or C
with `memory_action=correct`. `A+correct` is forbidden.

## Answer-Text Observability

Each B/C atom has one or more minimal evidence strings. Every string must occur
verbatim in the hidden natural-language reference answer. Each atom also has at
least two observable checks that refer to answer text, not runtime behavior.

An A atom must satisfy both:

1. its counterfactual answer delta is `none`;
2. its minimal evidence list is empty.

The current question is independently checked against every hidden atom. If it
partly or fully supplies an atom's value, the record is rejected because the
memory contribution would not be identifiable.

## Admission Channels

| Channel | Records | Meaning |
|---|---:|---|
| independent QC strict | 3,735 | Independent Judge accepted all record- and atom-level checks |
| manual adjudication | 15 | Residual records were rewritten one by one and passed the same deterministic validators |

Manual records are explicitly marked and are not represented as independent
Judge outputs. Their audit stores the prior failure reasons, rationale, source
fingerprint, output fingerprint, and confirmation that memory labels and
actions were not changed.

## Release Invariants

A v2.4 release is valid only if all of the following hold:

1. exactly 15,000 unique record IDs are present in v2.3 order;
2. domain counts equal 7,500 / 3,750 / 3,750;
3. exactly all 3,750 source coding IDs are revised;
4. every coding question has the natural-language-only contract;
5. coding questions and reference answers contain no code fences;
6. visible memory blocks are byte-for-byte structurally unchanged;
7. atom IDs, atom text, order, parent IDs, A/B/C labels, and actions are locked;
8. every B/C evidence string occurs in the reference answer;
9. every A atom has zero answer footprint;
10. every coding record has an explicit, auditable admission channel;
11. health and general content is unchanged apart from the release schema tag.

The authoritative release SHA-256 is:

```text
377770f0048114db4cf40e95783f05789f1a024d1e6c90ff77881e170c0e111b
```
