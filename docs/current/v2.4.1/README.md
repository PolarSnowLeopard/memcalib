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
f76b9d6b1d07c6e27e975562ce5b05a338a6d59f093674eea947d65e74e59f50
```

每个父块同时保存正式评测使用的流畅 `memory_text` 和按原子 ID、原始文本及锁定顺序确定性生成的 `atomic_concat_text`。训练分区中有 11,892 条双严格监督写入同一 canonical JSONL 的顶层 `sft_supervision`；108 条未通过监督门禁的训练记录不含该字段，3,000 条 test 均不含该字段。拼接公式、反事实按 ID 删除规则和 teacher-forced 比较契约见：

- [训练字段、直接拼接与反事实契约](training-fields.md)

## 正式数据划分

v2.4.1 不设置独立 dev 集。15,000 条数据被确定性划分为三个互斥的顶层分区：

| 分区 | 数量 | health_seed | general | coding | 预定用途 |
|---|---:|---:|---:|---:|---|
| `sft_cold_start` | 4,000 | 2,000 | 1,000 | 1,000 | SFT 冷启动 |
| `rl` | 8,000 | 4,000 | 2,000 | 2,000 | 后续强化学习 |
| `test` | 3,000 | 1,500 | 750 | 750 | 只用于测试 |

`test` 进一步提供两个互斥子集，但它们不是新的顶层分区：

- `test_eval`：最终发布并反复使用的 1,500 条 benchmark Test，领域为 750 / 375 / 375；
- `test_remaining`：其余 1,500 条测试样本。

新的 `test_eval` 完整保留历史 500 条评测样本作为有序锚点，再按固定种子补充 1,000 条。扩展选择在领域、难度、标签/纠正动作组合、来源和原子数量层面分层，并保证 1,500 条归一化最终问题文本全部唯一。正式 Full-memory、Non-Think 评测现已完成 6 个百炼模型、3 个公司统一推理平台模型和 2 个本地 vLLM 基线；所有模型均独立生成三轮，并由关闭 thinking 的 DeepSeek-V4-Pro 判分。

划分使用固定种子，并在领域、难度、标签/纠正动作组合、来源和原子数量层面保持分层。相同最终问题文本必须整体进入同一分区；三大分区之间的记录 ID、来源身份、原始问题和最终问题精确重叠均为 0。历史训练 pilot 中有 1 条与固定 test 样本共享完全相同的问题，因此按防泄漏规则移入 test；其余 499 条保留在 SFT 冷启动集。

本地 JSONL：

```text
pipeline/data/multidomain/full-v2/revision-coding-text-observable-v24/v241/release/splits/
  sft_cold_start_4000.jsonl
  rl_8000.jsonl
  test_3000.jsonl
  test_eval_1500.jsonl
  test_remaining_1500.jsonl
  test_eval_anchor_500.jsonl
```

可复现控制文件、ID 清单、分布统计和各文件 SHA-256 见：

- [v2.4.1 划分 manifest](../../../sft/releases/memcalib-v241-sft4000-rl8000-test3000/split-manifest.json)

划分脚本只按 ID 原样分流记录，不给记录新增 split 字段，也不修改问题、记忆块、原子、rubric、参考答案或训练监督。

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

论文与训练对齐的主评测口径为 **Non-thinking**。正式 1,500 条评测使用锁定样本、统一提示词和三轮独立生成；Judge 为关闭 thinking 的 DeepSeek-V4-Pro。入口见：

- [v2.4.1 评测总览](../../../evaluation/current/v2.4.1/README.md)
- [正式九模型三轮聚合结果](../../../evaluation/current/v2.4.1/analyses/memcalib-v241-benchmark1500-nine-models-nonthinking-full-memory-three-seeds/aggregate/README.md)
- [本地 vLLM 两模型三轮聚合结果](../../../evaluation/current/v2.4.1/analyses/memcalib-v241-local-baselines-1500-nonthinking-vllm/aggregate/README.md)
- [样本级三层主指标](../../../evaluation/current/v2.4.1/analyses/sample-level-nonthinking/README.md)
- [候选指标与诊断](../../../evaluation/current/v2.4.1/analyses/candidate-metrics-nonthinking/README.md)

## 使用边界

完整数据含多个上游公开数据源，公开再分发前仍需单独完成许可证、署名、隐私、PII 和敏感内容审查。内部训练或合作者审阅也应保存发布 SHA-256，避免把冻结的 v2.4 与当前 v2.4.1 混用。
