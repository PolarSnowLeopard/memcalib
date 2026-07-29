# CRK-2 v2 pilot: preliminary audit of 9 QC rejects

This is a preliminary consistency audit of the independent Kimi QC output. It does not replace the human annotations collected in `review.html`.

| Record | Preliminary assessment | Main reason |
|---|---|---|
| `crk2_v2_raw_75fde6e8a080b15a` | likely QC false positive | The QC field says `label_action_validity=fail`, while its own reason concludes that B + `correct` is valid and observable. |
| `crk2_v2_raw_c40752621dc51bdd` | likely QC false positive | The QC reason again concludes that B + `correct` is valid, but emits `fail`. |
| `crk2_v2_raw_61d6eb00fc3ead91` | construction issue | Two atoms combine multiple pathologies or symptoms. The QC query-relation enum is inconsistent with its prose, but the atomicity failure is independently sufficient. |
| `crk2_v2_raw_c8cb3196613c5f4a` | construction issue | Aspirin use is already recoverable from the model-facing question, violating query-memory isolation. |
| `crk2_v2_raw_7d9177752d7618aa` | label/content issue | The claimed causal link from osteoporosis medication to hypercalcemia, renal workup, and secondary hypertension is medically weak; C/apply is not defensible without revision. |
| `crk2_v2_raw_5d038a548ddf8731` | construction issue | One atom combines forearm lesions, ear sores, and oral burning, which are independently judgeable symptom groups. |
| `crk2_v2_raw_a4e55eeb7d269253` | counterfactual issue | Recurrence is already stated in the question, so the claimed memory-specific B deltas are not credible. |
| `crk2_v2_raw_9461d255ce2a44ec` | construction issue | Maltese/English-language information leaks into the question and the atom combines nationality with language proficiency. |
| `crk2_v2_raw_26c6fbefc9522523` | evidence/derivation issue | A general laboratory warning was incorrectly converted into a factual user history of monoclonal-antibody treatment. |

The provisional recommendation is to recover the first two records only after human confirmation, and to revise or exclude the remaining seven. This would yield up to 93 usable records from the pilot, subject to a stratified audit of the 91 strict-pass records.
