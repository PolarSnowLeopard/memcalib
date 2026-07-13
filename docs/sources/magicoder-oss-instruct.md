# Magicoder OSS-Instruct 75K

- Upstream dataset: `ise-uiuc/Magicoder-OSS-Instruct-75K`
- Domain in MemCalib: coding assistance
- Upstream dataset-card license: MIT
- Source unit: a coding problem and its reference solution
- Dataset card: <https://huggingface.co/datasets/ise-uiuc/Magicoder-OSS-Instruct-75K>
- Paper: <https://arxiv.org/abs/2312.02120>

The coding problem supplies explicit project, runtime, interface, or implementation constraints that may be transformed into stored memory. The reference solution is used only to establish task coherence and source quality; the multidomain construction prompt prohibits copying implementation details from the solution into model-facing memory.

The pilot rejects tasks whose problem text contains a near-complete copy of the reference solution. This prevents task correctness from becoming a copying exercise.

Raw JSONL snapshots remain local under `pipeline/data/raw_sources/` and are not committed. Before a public full release, the project will additionally audit provenance and licensing of source code snippets that were used upstream to synthesize the instructions.
