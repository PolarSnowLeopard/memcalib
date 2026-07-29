# MemCalib v2.4 coding review sample

This deterministic sample is intended for qualitative review of the complete
3,750-record coding revision.

- `memcalib-v24-coding-review-sample-30.model-facing.jsonl` contains exactly
  what an evaluated model receives: the natural-language coding question and
  visible memory blocks.
- `memcalib-v24-coding-review-sample-30.full.jsonl` additionally contains the
  hidden reference answer, atomic memories, A/B/C labels, actions, answer-text
  rubrics, revision provenance, and admission audit.
- `memcalib-v24-coding-review-sample-30.manifest.json` records the source
  release hash, exact IDs, deterministic sampling rule, strata, and output
  hashes.

The sample contains ten records from each task family: implementation planning,
behavior prediction, and debugging diagnosis. It also deliberately includes
one manually adjudicated record from each task family where that channel
exists. This slight oversampling of the 15-record manual residual makes the
exception path reviewable; it must not be used to estimate release prevalence.

All records still expose natural prose memory blocks to the model. Atomic
boundaries and labels are hidden supervision and are present only in the full
review file.
