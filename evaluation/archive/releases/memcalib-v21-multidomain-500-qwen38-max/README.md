# Qwen3.8-Max availability check

This directory records a model-availability preflight requested before adding
`qwen3.8-max` to the locked MemCalib v2.1 500-record comparison.

## Outcome

No formal evaluation was run. On 2026-07-20:

- the preferred Bailian credential returned HTTP 404 `model_not_found` for
  all four smoke requests;
- the fallback, broader-access Bailian credential returned the same HTTP 404
  error for one smoke request;
- both tests used `temperature=0`, `enable_thinking=false`, and the exact
  model ID `qwen3.8-max`;
- the public Bailian text-generation model catalog did not list that model ID.

The two credentials are not stored or identified in this release. Because the
model could not be resolved by either credential, no 500-record full-memory or
no-memory answers were submitted, no Judge calls were made, and no score was
added to the eight-model table.

## Reproducibility boundary

`answer-request.manifest.json` records the already prepared smoke and formal
request hashes. `availability-check.json` records only non-secret status codes
and counts. A future run should first repeat the smoke test with a newly
documented model ID or entitlement, then use a new run directory so this
failed preflight remains intact.

Public catalog checked:
<https://help.aliyun.com/zh/model-studio/text-generation-model/>.
