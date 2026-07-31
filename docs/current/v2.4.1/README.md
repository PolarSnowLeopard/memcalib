# MemCalib v2.4.1 数据与质检入口

v2.4.1 是对 v2.4 质量事件的纠正发布。当前完整数据、训练准备和论文分析应以 v2.4.1 为准；v2.4 仅用于复现问题发现和修复历史。

## 发布范围

- 15,000 条英文样本；
- health_seed / general / coding = 7,500 / 3,750 / 3,750；
- 74,800 个模型可见自然语言记忆块；
- 234,220 个隐藏评分原子；
- A / B / C = 197,510 / 18,943 / 17,767；
- 3 个预定义难度层级；
- coding 问题使用自然语言实现规划、行为预测、代码理解或调试诊断，避免以不可执行的代码文本作为唯一判分依据。

权威数据：

```text
pipeline/data/multidomain/full-v2/revision-coding-text-observable-v24/v241/
  release/memcalib_v241_multidomain_benchmark_15000.jsonl
```

SHA-256：

```text
8bc18ae468e1ab1d41ffa4556c6e042a62538eca01e97029db94f850c2c46dc4
```

## 纠正流程

1. 对原子文本、问题、参考答案和 rubric 执行确定性对齐审计。
2. 对可自动修复项进行锁定表面改写、问题修复或监督修复。
3. 用两个独立 Judge 复核修复结果，仅接纳双重严格通过项。
4. 对少量残余项进行逐条人工收尾，并保留修复渠道与变更审计。
5. 重新合并 15,000 条发布数据，验证 ID、顺序、领域配额、块结构和标签动作约束。
6. 在评测前进行固定种子、风险分层的 30 条人工逐样本审查。
7. 对人工发现的问题完成修正后，重新抽样并进行第二轮逐条复核。

## 人工门禁

[30 条人工审查报告](review/memcalib-v241-manual-review-report-30.md)记录了每一条样本的判断依据：

- 首轮：18 通过、3 需澄清、9 不通过；
- 修正：12 条，其中 1 条领域错误记录被替换；
- 第二轮：30/30 通过；
- 修正后 coding 原子/rubric 确定性告警：0；
- 修正后抽样中 A 原子全文进入参考答案：0。

机器可读材料：

- [30 条完整监督样本](review/memcalib-v241-manual-review-sample-30.jsonl)
- [抽样与发布哈希清单](review/memcalib-v241-manual-review-sample-30.manifest.json)

该门禁只能证明抽样覆盖的高风险构建分支在修正后未再暴露同类问题，不能替代对 15,000 条逐条人工标注。

## 评测口径

论文与训练对齐的主评测口径为 **Non-thinking**。八个百炼模型关闭 thinking，Codex 固定为 `reasoning_effort=none`。入口见：

- [v2.4.1 评测总览](../../../evaluation/current/v2.4.1/README.md)
- [样本级三层主指标](../../../evaluation/current/v2.4.1/analyses/sample-level-nonthinking/README.md)
- [候选指标与诊断](../../../evaluation/current/v2.4.1/analyses/candidate-metrics-nonthinking/README.md)

## 使用边界

完整数据含多个上游公开数据源，公开再分发前仍需单独完成许可证、署名、隐私、PII 和敏感内容审查。内部训练或合作者审阅也应保存发布 SHA-256，避免把冻结的 v2.4 与当前 v2.4.1 混用。
