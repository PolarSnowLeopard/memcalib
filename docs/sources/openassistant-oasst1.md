# OpenAssistant OASST1

- Upstream dataset: `OpenAssistant/oasst1`
- Domain in MemCalib: general dialogue
- Upstream license: Apache-2.0
- Source unit: an English user turn, its preceding conversation path, and a positively reviewed assistant reply
- Dataset card: <https://huggingface.co/datasets/OpenAssistant/oasst1>
- Paper: <https://arxiv.org/abs/2304.07327>

The pilot excludes records detected as primarily medical or coding tasks so that domain-level analysis remains interpretable. Deleted, negatively reviewed, non-English, incomplete, and structurally invalid messages are excluded before deterministic MemCalib quality filtering. The current question remains the source task, while earlier turns are retained as auditable source context from which realistic stored memories may be derived.

Raw Parquet snapshots remain local under `pipeline/data/raw_sources/` and are not committed.
