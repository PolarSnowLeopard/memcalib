# MemCalib v2.4 冻结审计入口

> **发布状态：已被 v2.4.1 取代。** coding 子集已确认存在原子记忆、改写问题、
> 参考答案和 rubric 的语义对齐错误；本目录只作为可复现审计材料。
> 当前数据与评测入口见 [v2.4.1](../v2.4.1/README.md)，问题背景见
> [质量事件报告](reports/memcalib-v24-data-quality-incident.md)。

本目录只保存当前 v2.4 的审阅文档和小型样本，不混入旧版本材料。

## 数据与方法

- [合作者交付说明](MEMCALIB_V24_COAUTHOR_HANDOFF.md)
- [数据结构、字段与不变量](benchmark-schema-v2.4.md)
- [coding 文本可观测性全量迭代与质检](reports/memcalib-v24-coding-text-observability.md)
- [v2.4 SFT 构建、固定切分与 Qwen3-8B 训练入口](../../../sft/README.md)
- [v2.4 评估结果与推理模式口径](../../../evaluation/current/v2.4/README.md)

当前论文与训练对齐的主评估口径为 **Non-thinking**。Think 结果作为补充分析单独报告；Codex GPT-5.6 Sol 固定为 `reasoning_effort=none`，不解释为两种模式下的独立重复实验。不同推理模式、单模型诊断和旧版本结果不得混表。

## 人工审阅

- [3 条中文分层样本](samples/memcalib-v24-coding-review-sample-3-zh.md)
- [30 条分层样本说明](samples/memcalib-v24-coding-review-sample-30.README.md)
- [30 条完整监督 JSONL](samples/memcalib-v24-coding-review-sample-30.full.jsonl)
- [30 条模型可见 JSONL](samples/memcalib-v24-coding-review-sample-30.model-facing.jsonl)
- [抽样 manifest](samples/memcalib-v24-coding-review-sample-30.manifest.json)

## 边界

完整 15,000 条数据位于 Git 忽略的本地构建目录，不在本目录复制。当前评测结果统一从[评测入口](../../../evaluation/current/v2.4/README.md)访问。v2.0-v2.3 文档统一从[历史版本索引](../../archive/versions/README.md)访问。
