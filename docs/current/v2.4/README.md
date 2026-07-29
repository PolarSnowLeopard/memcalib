# MemCalib v2.4 文档入口

本目录只保存当前 v2.4 的审阅文档和小型样本，不混入旧版本材料。

## 数据与方法

- [合作者交付说明](MEMCALIB_V24_COAUTHOR_HANDOFF.md)
- [数据结构、字段与不变量](benchmark-schema-v2.4.md)
- [coding 文本可观测性全量迭代与质检](reports/memcalib-v24-coding-text-observability.md)

## 人工审阅

- [3 条中文分层样本](samples/memcalib-v24-coding-review-sample-3-zh.md)
- [30 条分层样本说明](samples/memcalib-v24-coding-review-sample-30.README.md)
- [30 条完整监督 JSONL](samples/memcalib-v24-coding-review-sample-30.full.jsonl)
- [30 条模型可见 JSONL](samples/memcalib-v24-coding-review-sample-30.model-facing.jsonl)
- [抽样 manifest](samples/memcalib-v24-coding-review-sample-30.manifest.json)

## 边界

完整 15,000 条数据位于 Git 忽略的本地构建目录，不在本目录复制。当前评测结果统一从[评测入口](../../../evaluation/current/v2.4/README.md)访问。v2.0-v2.3 文档统一从[历史版本索引](../../archive/versions/README.md)访问。
