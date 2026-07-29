# MemCalib v2.3 Benchmark Schema

MemCalib v2.3 separates the model-facing retrieval unit from the hidden
evaluation unit:

- an answer model receives the current question and 3–20 visible memory blocks;
- each visible block maps to 1–20 hidden atomic memories;
- multi-atom blocks are rendered as natural paragraphs with no visible atom
  numbering or boundary markers;
- every hidden atom retains an expected influence level, action, evidence,
  counterfactual contract, and instance-specific rubric;
- the Judge scores realized atom-level influence rather than assigning one
  relevance label to an entire block.

## 1. Record structure

Each JSONL row is one benchmark record. The principal fields are:

| Field | Meaning |
|---|---|
| `id` | Unique benchmark record identifier |
| `source_id` | Unique normalized source-unit identifier |
| `domain` | `health_seed`, `general`, or `coding` |
| `source_dataset` | Upstream dataset lineage |
| `source_topic` | Normalized topic stratum |
| `question` | Current user question |
| `memory_blocks` | Ordered model-facing retrieval units |
| `memories` | Hidden atomic memories and supervision |
| `atom_pair_relations` | Pairwise atomic relation audit |
| `composite_block_revision` | v2.3 difficulty, expansion, and rewrite provenance |
| `v23_independent_qc` | Final independent atom/block QC decision and audit |

The answer model must not receive hidden labels, actions, rubrics, evidence,
pairwise audits, or QC metadata.

## 2. Model-facing block

A model-facing block has a stable block ID and one natural-language paragraph:

```json
{
  "parent_memory_id": "v22_grounded_01",
  "memory_text": "One natural paragraph containing all hidden propositions.",
  "surface_form": "natural_paragraph"
}
```

The authoritative row also stores hidden `atom_ids` and rewrite provenance.
These fields are for evaluation and audit, not answer-model input.

## 3. Hidden atomic memory

Each hidden atom contains at least:

```json
{
  "atom_id": "stable atom identifier",
  "parent_memory_id": "owning visible block",
  "text": "one independently meaningful proposition",
  "u_star": "A | B | C",
  "memory_action": "ignore | apply | correct",
  "counterfactual_contract": {},
  "usage_rubric": {}
}
```

Atom-to-block membership is bijective: each atom occurs in exactly one block,
every block atom exists exactly once in `memories`, and block order is stable.

## 4. Ordered influence labels

| Label | Legal actions | Required answer behavior |
|---|---|---|
| A | `ignore` | Leave no atom-specific content, framing, implementation, format, or safety footprint |
| B | `apply`, `correct` | Use as bounded support, or correct it without letting it dominate |
| C | `apply`, `correct` | Let it materially constrain the answer, or explicitly correct a controlling error |

Truthfulness and influence strength are separate. Wrong, unsafe, stale, or
superseded memories that require correction are B/C+correct. A+correct is
forbidden.

## 5. Visible-block and atom-count long tails

Let `K_i` be the visible-block count of record `i`, and `N_i,b` the hidden atom
count of block `b`.

```text
3 <= K_i <= 20
1 <= N_i,b <= 20
```

The v2.2 block-count distribution is retained exactly:

```text
3:4200, 4:3600, 5:2700, 6:1800,
7:1052, 8:600, 9:376, 10:224,
11:148, 12:104, 13:76, 14:44,
15:32, 16:20, 17:12, 18:4, 19:4, 20:4
```

The v2.3 atom-count distribution is:

| Atoms/block | Blocks | Atoms/block | Blocks |
|---:|---:|---:|---:|
| 1 | 15,000 | 11 | 280 |
| 2 | 11,252 | 12 | 286 |
| 3 | 33,448 | 13 | 56 |
| 4 | 1,956 | 14 | 51 |
| 5 | 3,817 | 15 | 40 |
| 6 | 3,722 | 16 | 41 |
| 7 | 3,751 | 17 | 42 |
| 8 | 288 | 18 | 45 |
| 9 | 318 | 19 | 45 |
| 10 | 312 | 20 | 50 |

Across the full release:

| Quantity | Count |
|---|---:|
| Visible blocks | 74,800 |
| Multi-atom blocks | 59,800 |
| Blocks with at least three atoms | 48,548 |
| Hidden atoms | 234,221 |
| Atoms per record | 6–63; mean 15.6147; median 14 |

There is no per-record total atom cap. The cap applies only to one block.

## 6. Three difficulty strata

Difficulty is assigned from noncanonical block atom counts. The canonical Hard
A singleton is excluded from the rule.

```text
level_1:
  max block size <= 4
  and at most one noncanonical block has more than 2 atoms

level_2:
  3 <= max block size <= 7

level_3:
  max block size >= 8
  or at least two noncanonical blocks have at least 5 atoms
```

The release contains 3,751 / 7,500 / 3,749 records in levels 1 / 2 / 3.
Allocation is performed independently within each domain using a deterministic
largest-remainder rule.

## 7. Locked and added content

v2.3 locks all v2.2 questions, source lineage, original atoms, labels, actions,
block IDs, and the canonical Hard A. It adds 115,402 auxiliary atoms under the
following contract:

- label/action is always A+ignore;
- no legitimate answer footprint for the current question;
- no explicit correction requirement;
- one independently meaningful proposition;
- same-user plausibility and block coherence;
- no duplication, entailment, or contradiction with neighboring atoms.

The canonical Hard A remains the only controlled Hard-A factor and remains a
singleton block.

## 8. Model-facing projection

Training or answer generation should construct an explicit projection:

```json
{
  "id": "record identifier",
  "question": "current question",
  "memory_blocks": [
    {
      "parent_memory_id": "visible block identifier",
      "memory_text": "natural model-visible paragraph"
    }
  ]
}
```

Do not pass the authoritative full row directly to an answer model unless the
training objective explicitly requires hidden targets.

## 9. Judge-facing projection

The Judge receives the question, candidate answer, hidden atoms, target labels
and actions, counterfactual contracts, usage rubrics, and atom-to-block mapping.
Core directional errors are:

```text
over-use  = realized influence > expected influence
under-use = realized influence < expected influence
```

Scoring remains atom-level even when many atoms appeared in one paragraph.

## 10. Release invariants

A v2.3 release must satisfy all of the following:

1. exactly 15,000 unique record IDs and source IDs;
2. domain quotas 7,500 / 3,750 / 3,750;
3. exact v2.2 visible-block long-tail distribution;
4. 1–20 atoms per block and no per-record atom cap;
5. exact three-level domain-stratified difficulty quotas;
6. bijective atom-to-block mapping;
7. one singleton canonical Hard A per record;
8. original v2.2 atoms and supervision preserved;
9. all v2.3 auxiliary atoms encoded as A+ignore;
10. every multi-atom block rendered as one natural paragraph;
11. complete Stack Exchange attribution for admitted records;
12. final independent QC decision is strict_pass or review;
13. no reject, invalid, or deterministic violation enters release.

The authoritative uncompressed release digest is:

```text
e86d79545b44344b44337d8f9502dc69880daeb18c6513784344e33a06de8773
```
