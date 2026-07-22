# MemCalib v2.3 人工审阅样例

这组 30 条 JSONL 用于快速人工审阅最终 v2.3 数据格式与内容，不用于估计总体比例。

- memcalib-v23-review-sample-30.model-facing.jsonl：模型实际看到的字段，适合先检查问题与记忆块是否自然。
- memcalib-v23-review-sample-30.full.jsonl：完整审查记录，包含隐藏原子、A/B/C 标签、动作、证据、构建与独立质检信息。
- memcalib-v23-review-sample-30.manifest.json：抽样方法、分层覆盖、文件哈希与样本 ID。

## 抽样覆盖

- 领域：health_seed / general / coding 各 10 条。
- 难度：level_1 / level_2 / level_3 = 9 / 12 / 9。
- Hard A：五个家族各 6 条。
- 独立质检：每个领域至少包含一条 review，其余为 strict_pass。
- 抽样在每个“领域 × Hard A 家族 × 难度”单元内按固定种子的 SHA-256 排序，因此可复现。

正式总体分布请以以下文件为准：

- pipeline/data/multidomain/full-v2/revision-composite-blocks-v23/release/memcalib_v23_multidomain_benchmark_15000.statistics.json
- docs/reports/memcalib-v23-composite-block-revision.html
