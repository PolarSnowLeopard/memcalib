# MemCalib v2.4 coding alignment quality incident

Status: **open; v2.4 coding labels and evaluation results are provisional**

## What failed

Human review found that some coding records do not preserve the semantic
alignment among the atomic memory, rewritten natural-language question,
reference answer, and atom-specific rubric.

Confirmed failure modes include:

1. **Cross-atom rubric assignment.** A rubric is attached to the wrong atom. In
   one confirmed record, the Django atom is scored against the browser-game
   context while the browser-game atom is scored against Django.
2. **Unsupported answer requirements.** A rubric introduces a conclusion not
   entailed by its atom. In one confirmed record, a LAMP-stack atom is used to
   require Route53, Linode, and Dynadot.
3. **Question leakage.** The rewritten question supplies an atom-specific value
   that is still marked as absent from the query.
4. **B-to-C magnitude drift.** Rewriting can promote bounded supporting context
   into a core task requirement while retaining label B.

These failures directly affect atom-level OPB/UPB judgments and therefore the
sample-level and aggregate evaluation metrics.

## Deterministic screen

The first repository audit was run over the complete 15,000-record v2.4 release,
with semantic-alignment checks applied to all 3,750 coding records.

| Check | Result |
|---|---:|
| Coding records screened | 3,750 |
| Records flagged for semantic review | 376 |
| Flagged-record rate | 10.03% |
| Flagged B/C atoms | 434 |
| Probable cross-atom rubric swaps | 100 |
| Rubrics introducing unsupported marked identifiers | 83 |
| Very low atom-to-rubric lexical support | 206 |
| Query/rubric leakage candidates | 132 |
| Current 494-sample main evaluation rows flagged | 15 |
| Flagged share of the 494-sample evaluation | 3.04% |

The 10.03% value is a candidate-review rate, not a final semantic error rate.
The screen establishes a reproducible candidate set; unflagged records are not
automatically proven correct.

Audit artifacts:

- `pipeline/data/multidomain/full-v2/revision-coding-text-observable-v24/audit/memcalib_v24_atom_alignment.summary.json`
- `pipeline/data/multidomain/full-v2/revision-coding-text-observable-v24/audit/memcalib_v24_atom_alignment.flagged.jsonl`
- `pipeline/110_audit_memcalib_v24_atom_alignment.py`

## Root cause

The v2.4 coding rewrite asked the generator to preserve existing labels and
actions, but the structural validator checked atom-ID coverage, copied labels,
reference-answer string presence, and output shape. It did not verify that each
required answer element was entailed by the same atom.

The independent QC prompt nominally rejudged labels, but did not require an
explicit cross-atom attribution comparison. This allowed fluent explanations
to justify a swapped rubric. Label locking also made it too easy to defend a B
label after the rewritten task had made that fact central.

## Impact and use policy

- The v2.4 15,000-record release remains preserved for reproducibility.
- Existing Think and Non-thinking evaluations remain preserved as incident
  evidence, but must not be used as final paper results.
- The Non-thinking run remains the intended primary evaluation mode after the
  data is corrected; Think remains supplementary.
- No corrected release may reuse answer or Judge output for a row whose
  question, reference answer, rubric, or label changes.

## Remediation gate

The corrected release must satisfy all of the following:

1. Full 3,750-record coding semantic audit, not only repair of known examples.
2. Every required answer element is attributable to exactly one scored atom and
   is directly entailed by that atom.
3. No question supplies any B/C atom-specific value.
4. B remains bounded supporting influence; C remains controlling influence.
5. Failed rows are repaired and then independently re-audited.
6. Deterministic alignment checks report no blocking cross-atom swaps,
   unsupported identifiers, or query leakage.
7. A human review sample explicitly over-samples B atoms and all repaired rows.
8. The corrected release receives a new immutable manifest and evaluation; old
   and corrected metrics are never mixed.
