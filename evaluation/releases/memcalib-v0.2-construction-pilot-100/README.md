# MemCalib construction-v2 pilot (100 records)

This directory contains the locked offline protocol and provenance for the 100-record repair pilot. It does not contain API responses and does not modify the MemCalib v0.1 release.

- [`protocol.html`](protocol.html): Chinese visual review of the revised labels, hard gates, and staged admission flow.
- [`generation-input.manifest.json`](generation-input.manifest.json): selected source IDs, distributions, parameters, and SHA-256 lineage.
- [`../../../docs/crk2-v2-construction-protocol.md`](../../../docs/crk2-v2-construction-protocol.md): formal Chinese protocol.

The generated request file remains under `pipeline/data/` and is excluded from Git. Recreate it with the non-Conda Python runtime:

```bash
PY=/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
$PY pipeline/29_prepare_crk2_v2_generation.py \
  --manifest evaluation/releases/memcalib-v0.2-construction-pilot-100/generation-input.manifest.json
```

The locked pilot contains 50 records from each existing medical source. The API construction and independent QC stages have not yet been run in this release state.
