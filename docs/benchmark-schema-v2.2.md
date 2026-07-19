# MemCalib v2.2 Benchmark Schema

MemCalib v2.2 separates the model-facing retrieval unit from the hidden
evaluation unit:

- an answer model receives the current question and 3–20 visible memory
  blocks;
- each visible block maps to one or more hidden atomic memories;
- every hidden atom has an expected influence level, action, evidence, and
  instance-specific rubric;
- the Judge scores realized atom-level influence rather than treating an
  entire visible block as uniformly relevant.

This design preserves the non-atomic form returned by realistic memory
systems while retaining precise supervision for over-use and under-use.

## 1. Record structure

Each JSONL row is one benchmark record. The main fields are:

| Field | Meaning |
| --- | --- |
| `id` | Unique benchmark record identifier |
| `source_id` | Unique normalized source-unit identifier |
| `domain` | `health_seed`, `general`, or `coding` |
| `source_dataset` | Upstream dataset lineage |
| `source_topic` | Normalized topic stratum |
| `question` | Current user question |
| `memory_blocks` | Ordered model-facing retrieval units |
| `memories` | Hidden atomic memories and supervision |
| `atom_pair_relations` | Pairwise atomic independence or relation audit |
| `longtail_independent_qc` | Independent semantic QC decision and audit |

The answer model should not receive hidden labels, atomic rubrics, evidence
audits, or QC metadata.

## 2. Long-tail visible-block distribution

Let \(K_i\) be the number of visible memory blocks in record \(i\). The
release contains 15,000 records and enforces:

```text
K_i in {3, ..., 20}
```

The exact distribution is:

| Blocks per record | Records |
| ---: | ---: |
| 3 | 4,200 |
| 4 | 3,600 |
| 5 | 2,700 |
| 6 | 1,800 |
| 7 | 1,052 |
| 8 | 600 |
| 9 | 376 |
| 10 | 224 |
| 11 | 148 |
| 12 | 104 |
| 13 | 76 |
| 14 | 44 |
| 15 | 32 |
| 16 | 20 |
| 17 | 12 |
| 18 | 4 |
| 19 | 4 |
| 20 | 4 |

This gives:

- 82.0% of records with 3–6 blocks;
- 15.01% with 7–10 blocks;
- 2.99% with 11–20 blocks;
- mean 4.9867 blocks per record;
- median 4 blocks per record.

The same proportional distribution is enforced within each domain, so block
load is not confounded with domain.

## 3. Decomposable blocks

For a record with \(K_i\) visible blocks, the required number of multi-atom
blocks is:

```text
M_i = ceil(K_i / 2)
```

Therefore every record has at least half of its visible blocks decomposable
into multiple independently scored atoms. Across the full release:

| Quantity | Count |
| --- | ---: |
| Visible memory blocks | 74,800 |
| Multi-atom visible blocks | 41,700 |
| Multi-atom block share | 55.75% |
| Hidden atomic memories | 118,819 |

Each atom identifier appears in exactly one visible block, and every atom
referenced by a visible block exists exactly once in `memories`.

## 4. Ordered influence labels

Each hidden atom has a target influence level \(u^*\):

| Label | Action | Required answer behavior |
| --- | --- | --- |
| A | `ignore` | Leave no atom-specific content, presentation, implementation, or safety footprint |
| B | `apply` or `correct` | Use as supporting context, or explicitly correct a wrong, unsafe, or stale memory |
| C | `apply` or `correct` | Treat as a controlling constraint, or explicitly correct it when required |

Wrong, unsafe, stale, or superseded memories are never encoded as `A +
correct`. They are represented as `B + correct` or `C + correct`, according
to how strongly the correction should control the answer.

## 5. Canonical Hard A and auxiliary retrieval noise

Every record preserves one canonical Hard A atom in its own singleton visible
block. The five canonical failure mechanisms are exactly balanced:

1. factual-judgment pollution;
2. scope overreach;
3. current-evidence conflict;
4. profile/style near-neighbor;
5. untriggered preference.

Additional A atoms simulate realistic same-user retrieval noise. They are
separate from canonical Hard A and use three families:

1. cross-domain episode;
2. non-task profile detail;
3. unrelated physical-artifact preference.

Auxiliary atoms within one multi-atom block share a coherent scene, but each
states a distinct atomic proposition. They must remain absent from the answer
both individually and collectively.

## 6. Model-facing projection

A minimal answer-model input is:

```json
{
  "id": "record identifier",
  "question": "current question",
  "memory_blocks": [
    {
      "parent_memory_id": "visible block identifier",
      "text": "model-visible non-atomic memory block"
    }
  ]
}
```

The authoritative dataset keeps richer block metadata and hidden atom
annotations for reproducibility. Training or answer-generation code should
construct an explicit model-facing projection instead of exposing the full
row.

## 7. Judge-facing projection

The Judge receives:

- the current question;
- the model answer;
- hidden atomic memories;
- expected label and action;
- construction target;
- counterfactual contract;
- usage rubric;
- atom-to-block mapping.

The core directional errors are:

```text
over-use  = realized influence > expected influence
under-use = realized influence < expected influence
```

Scoring is atom-level even when several atoms appeared to the answer model as
one visible block.

## 8. Release invariants

A v2.2 release must satisfy all of the following:

1. exactly 15,000 unique record IDs and source IDs;
2. exact domain quotas of 7,500 / 3,750 / 3,750;
3. exact 3–20 block long-tail distribution;
4. exactly `ceil(K/2)` multi-atom blocks in every record;
5. bijective atom-to-visible-block mapping;
6. one singleton canonical Hard A block per record;
7. exact five-family canonical Hard A balance;
8. only legal A/B/C action combinations;
9. complete Stack Exchange attribution for admitted records;
10. deterministic structural pass and independent semantic QC admission.
