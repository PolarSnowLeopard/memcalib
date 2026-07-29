# MemCalib v2.4 Locked 500-Sample Release

This directory contains the original stratified 500-sample v2.4 evaluation
projection used to prepare answer requests:

- health / general / coding: 250 / 125 / 125;
- the same locked IDs as the v2.3 pilot;
- all 125 coding inputs replaced by v2.4 natural-language tasks;
- hidden and model-facing JSONL plus deterministic gzip copies;
- sample, request, and release manifests.

Six GLM-5.2 no-memory answers repeatedly ended by length. The official
nine-model comparison therefore uses the common 494-sample subset in
[`../memcalib-v24-multidomain-494-nine-models-complete-case/`](../memcalib-v24-multidomain-494-nine-models-complete-case/).

This 500-sample directory is retained as the locked parent sample and exclusion
audit source. It is not an alternative leaderboard.
