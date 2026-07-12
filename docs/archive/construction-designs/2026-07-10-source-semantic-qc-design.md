# Source QA Semantic QC Design

## Objective

Evaluate whether each record in the fixed 30,000-record source candidate pool is suitable for CRK-2 construction. The semantic gate must detect complete but incoherent questions, irrelevant or non-substantive answers, unavailable memory evidence, corrupted source text, and clear medical safety or factual hazards that deterministic rules cannot assess reliably.

The intended final benchmark contains approximately 15,000 usable records. Semantic admission therefore remains adaptive to observed semantic-QC and CRK-2 construction pass rates rather than fixing an arbitrary reject count in advance.

## Considered Policies

1. A single automatic pass/reject judge is inexpensive but makes borderline decisions irreversible and weakens the methodological account.
2. Two full independent judgments for all 30,000 records improve agreement measurement but double cost and can over-reject when both judges share model biases.
3. An adaptive cascade applies one grounded judgment to all records, routes uncertain cases to review, permanently excludes explicit rejects, and uses uncertain cases only when the strict-pass pool cannot support the final target. This policy is selected.

## Judgment Schema

The judge returns one object with schema version `crk2-source-semantic-qc-v1`. It evaluates six dimensions:

- `question_completeness`: the user task is complete, interpretable, and answerable from the displayed text;
- `answer_relevance`: the answer directly addresses the central user task and does not respond to a different condition or request;
- `answer_substantiveness`: the answer contains an explanation, recommendation, clarification, or actionable next step beyond greetings and referral boilerplate;
- `memory_extractability`: the question contains at least one explicit user-specific fact that can be stored without inference;
- `text_integrity`: the question and answer are not truncated, concatenated from unrelated records, or corrupted beyond interpretation;
- `safety_plausibility`: the answer contains no clear dangerous instruction, direct contradiction, or obviously implausible medical claim. Medical uncertainty alone is not a reject.

Each dimension has `label` in `{pass, reject, uncertain}`, an exact `evidence` quote, and a concise `reason`. Question evidence must be quoted from `raw_question`; answer relevance, substance, and safety evidence must be quoted from `doctor_answer`. The model also returns `overall_verdict`, `reject_reasons`, and `confidence`.

## Deterministic Post-Validation

The postprocessor verifies the schema, enum values, required dimensions, internal verdict consistency, and evidence grounding. A citation may contain one contiguous source span or multiple exact source spans joined by an ellipsis; multiple spans must occur in source order. Unicode spacing and quotation-mark serialization are normalized, while semantic paraphrases remain invalid. Invalid model outputs are not classified as data rejects; they are written to a retry file.

A record is `strict_pass` only when all six dimensions are `pass` and the overall verdict is `pass`. A record is `review` when no dimension is `reject` and at least one dimension is `uncertain`. A record is `reject` when any dimension is `reject` or the overall verdict is `reject`.

Explicit rejects are never automatically rescued. Review records may be judged again or manually reviewed when needed for target capacity. Safety uncertainty follows the review path; only an explicit safety rejection is automatically excluded.

## Adaptive Capacity Rule

Let the final benchmark target be \(N=15{,}000\). Let \(p_g^L\) be the lower 95% Wilson confidence bound of the CRK-2 construction-and-post-QC pass rate measured on a calibrated pilot. The semantic gate must admit

\[
N_{\mathrm{admit}} = \left\lceil \frac{N}{p_g^L} \right\rceil
\]

source records. The lower confidence bound prevents a small optimistic pilot from underestimating the required reserve.

If the strict-pass pool contains at least \(N_{\mathrm{admit}}\) records, all review records remain excluded from construction. Otherwise, review records receive a second judgment or manual review and accepted records are added until \(N_{\mathrm{admit}}\) is reached. Explicit rejects never enter this recovery path. If strict and reviewed records remain insufficient, additional candidates are sampled from the fixed eligible pool under the same source/topic/complexity policy.

The admitted subset is selected under the fixed source, topic, and seed-complexity policy. Capacity is therefore assessed jointly with distribution coverage; a numerically sufficient pool should not erase a source or difficulty stratum through quality filtering.

## Calibration Run

The first run uses 100 records selected from the 30,000-record pool with source, topic, and seed-complexity coverage. It estimates strict-pass, review, reject, invalid-output, and dimension-level failure rates. A one-sample-per-page HTML audit exposes source text, every dimension, exact evidence, reasons, and the deterministic final state.

No 30,000-record API run begins until the 100-record rubric output has been inspected and the schema version is fixed.

The completed 100-record calibration produced 68 strict passes, 22 review records, 10 explicit rejects, and no invalid outputs after deterministic evidence validation. The strict-pass rate was 0.68, with a lower 95% Wilson bound of 0.583. A 100/100 construction-and-post-QC pilot yields \(N_{\mathrm{admit}}=15{,}577\), so the observed calibration suggests that a 30,000-record pool has sufficient strict-pass capacity, subject to the full-run distribution check.

## Reproducibility

Request and result manifests record the parent candidate-pool hash, prompt hash, configuration hash, model parameters, request fingerprints, schema version, fixed seed, selected IDs, and output hashes. The final dataset records whether each admitted source was a strict pass or a reviewed pass.
