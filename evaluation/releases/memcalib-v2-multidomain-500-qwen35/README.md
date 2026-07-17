# MemCalib v2 Qwen3.5-35B-A3B extension

This release adds `qwen3.5-35b-a3b` to the existing 500-record MemCalib v2
multidomain evaluation without changing the sample, prompts, conditions, or
judge protocol.

## Scope

- Reused sample: 500 records
- Domains: 250 health, 125 general, 125 coding
- Conditions: `full_memory` and `no_memory`
- Answer rows: 1,000
- Primary judge rows: 1,000
- Secondary judge rows: 50
- Primary structural invalid rows after processing: 0
- Answer finish reasons: 1,000 `stop`

`qwen3.5-122b-a10b` was also requested, but the current Model Studio
workspace returned `403 Model.AccessDenied`. It was therefore excluded rather
than substituted or partially scored.

## Qwen3.5-35B-A3B result

| Metric | Value |
|---|---:|
| MemCalib H | 0.6992 |
| OPB | 0.4042 |
| UPB | 0.1541 |
| A success | 0.2532 |
| B success | 0.7185 |
| C success | 0.9118 |
| Strict sample accuracy | 0.1660 |
| Mean task quality | 3.138 |
| Safety failure rate | 0.0240 |

The model has the lowest UPB and highest C-label success in the six-model
comparison, but also the highest OPB and lowest A-label suppression success.
Its main weakness is therefore rejecting memory that should not influence the
answer, rather than using relevant memory.

## Artifacts

- `answer-request.manifest.json`: deterministic answer request inventory
- `answer-run.manifest.json`: answer completeness, hashes, and token usage
- `judge-request.manifest.json`: primary and secondary judge request inventory
- `judge-run.manifest.json`: normalized judge completeness and warning counts
- `metrics.json`: extension-only machine-readable metrics
- `report.html`: extension-only visual report

The combined six-model result is published separately under
`evaluation/releases/memcalib-v2-multidomain-500-six-models/`.
