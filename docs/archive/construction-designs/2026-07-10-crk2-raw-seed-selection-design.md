# CRK-2 Raw Seed Selection Design

## Objective

Insert a formal, reproducible raw-seed selection stage between source normalization and LLM benchmark construction. The stage must select high-quality, memory-bearing source questions without using benchmark labels or generated benchmark outputs.

The first validation run selects 100 seeds from the full locally available source pool. The same code and fixed configuration must support later targets of 10,000 or more records.

## Considered Approaches

1. Pure random or topic-balanced sampling is simple, but it cannot establish that selected questions contain usable personal context or substantive answers.
2. LLM-only screening offers semantic flexibility, but it adds model variance, cost, and a second prompt-dependent annotation stage before construction.
3. Deterministic hard filtering, interpretable scoring, deduplication, and stratified quality-first selection provide an auditable base layer. LLM construction and later QC remain responsible for semantic atomization and A/B/C labels.

The third approach is selected. Its rules are source-independent where possible, while medical marker families are explicit because the current two sources are medical QA datasets.

## Data Flow

The pipeline has four distinct data states:

1. `normalized_raw_full.jsonl`: every source record that passes technical schema and broad length checks. No source cap or random sampling is applied.
2. `crk2_raw_quality_audit.jsonl`: every normalized record with extracted quality features, score components, rejection reasons, and duplicate status.
3. `crk2_raw_eligible_pool.jsonl`: records that pass hard filters, deduplication, and the minimum quality score.
4. `crk2_selected_raw_seeds_<N>.jsonl`: the deterministic source/topic/complexity-stratified selection passed to CRK-2 generation.

Each run also writes `crk2_raw_selection_<N>.manifest.json`, containing parameters, version identifiers, input/output hashes, rejection counts, score summaries, duplicate statistics, and distributions before and after selection.

## Eligibility Rules

A record is technically valid only when its identifier, source, question, and answer are present; lengths and token counts fall within configured bounds; English alphabetic coverage is sufficient for the current sources; and the text is not dominated by boilerplate or repeated noise.

A construction candidate must contain at least one observable memory-signal family. Signal families cover personal entities, temporal history, conditions, treatments, measurements, exposures or events, preferences or constraints, and symptom course. This requirement excludes generic knowledge questions that provide no plausible stored memory.

Exact duplicates are grouped by canonicalized question text. Near duplicates are proposed by deterministic word-shingle signatures and confirmed by a fixed Jaccard-similarity threshold. The highest-scoring record represents each duplicate group; ties are broken by stable identifier.

## Quality Score

The score is an integer from 0 to 100 and is the sum of four inspectable components:

- question informativeness: amount of usable context without rewarding unbounded length;
- answer substance: non-boilerplate answer content and actionable or explanatory markers;
- memory suitability: a saturating score for the presence of one or more observable memory-signal families, kept separate from seed complexity;
- text cleanliness and coherence: language coverage, sentence structure, and absence of noise.

Every component and matched signal family is written into the quality audit record. The score is a preselection device, not a benchmark quality label and not a proxy for model performance.

## Stratified Selection

Selection is hierarchical. The target is first divided as evenly as capacity permits across source datasets. Within each source, topic quotas are proportional to the square root of eligible topic counts, which increases rare-topic representation without exhausting very small strata. Within each source-topic stratum, configured seed-complexity proportions are applied.

Seed complexity is an observable construction proxy derived from context length, number of memory-signal families, and explicit relations. It is named `simple`, `medium`, or `complex`; it must not be reported as final benchmark difficulty. Within each stratum, records are sampled without replacement using a seeded exponential quality weight. This preserves a strong preference for higher scores without collapsing the selected set onto the longest records in every stratum. Any unfilled quota is filled from the remaining quality-weighted order within the same source, then globally.

Near-duplicate groups use greedy representative assignment in descending quality order. A record is assigned only when it directly meets the similarity threshold against a retained representative; similarity chains cannot merge records that do not directly satisfy the threshold.

## Audit Interface

The 100-seed validation run produces one local HTML page with one sample visible at a time. Arrow keys switch samples. Each sample shows the source question, source answer, score components, matched memory signals, source/topic/complexity stratum, eligibility decision, and selection rationale. The page is read-only because this stage validates deterministic selection rules rather than collecting benchmark annotations.

## Reproducibility Contract

Changing any hard-filter threshold, scoring weight, signal pattern, deduplication threshold, stratum weight, seed, or source input creates a distinct run manifest. The manifest records schema and scoring versions plus SHA-256 hashes of the input, selector script, configuration, and outputs. A selected dataset is reproducible only when these values match.

## Validation

Unit tests cover feature extraction, hard rejection, score boundaries, exact and near duplicate handling, deterministic tie-breaking, source quotas, topic smoothing, complexity allocation, manifest hashes, and one-sample HTML navigation. The local 100-seed run additionally checks row counts, unique identifiers, rejection rates, score distributions, and selected distributions by source, topic, and seed complexity.
