# Manual Quality Review Guide

Generated with seed `20260706` from existing `verified_records.jsonl` and `verified_rejected.jsonl`.

Files:
- `manual_quality_review_samples.csv`: spreadsheet-friendly review sheet with blank columns for manual labels.
- `manual_quality_review_samples.jsonl`: same samples with full nested record structure.
- `manual_quality_review_summary.json`: counts by bucket/source/topic/language.

Recommended review labels:
- `pass`: usable as-is.
- `minor_fix`: usable after small wording or label correction.
- `major_fix`: core question/preference/label problem; should be regenerated or edited.
- `drop`: unsafe, medically implausible, leaked, duplicate, or not aligned with the source.

Suggested `review_issue_types` values:
- `question_not_decontextualized`
- `question_preference_leakage`
- `source_task_drift`
- `wrong_u_star`
- `unnatural_preference`
- `medical_inaccuracy`
- `unsafe_personalization`
- `language_inconsistent`
- `duplicate_or_near_duplicate`
- `too_much_synthetic_context`
- `other`

Checklist per row:
1. Does `question` preserve the original medical task while removing personal facts that are in `preferences`?
2. Does each preference represent one clear, plausible fact or preference?
3. Is each `u_star` correct under A=ignore, B=support, C=dominate?
4. Would using the C facts materially change triage, medication, testing, contraindications, or safety threshold?
5. Are A facts genuinely ignorable rather than medically necessary context?
6. Is the output language acceptable for the intended dataset?
7. Does the generated record remain faithful to `raw_question` and `doctor_answer` without inventing unsafe facts?

Sampling buckets:
{
  "verified_core_stratified": 51,
  "verified_topic_focus": 32,
  "verified_boundary_cases": 28,
  "verified_language_edge": 12,
  "verified_duplicate_question": 11,
  "verified_unusual_combos": 21,
  "rejected_leakage_calibration": 20,
  "rejected_label_calibration": 10,
  "rejected_parse_or_other": 10
}
