# MemCalib v2.4 Evaluation

> **Quality hold:** Human review found coding atom/question/reference/rubric
> alignment errors in the current v2.4 release. Existing Think and Non-thinking
> outputs are preserved but provisional and must not be cited as final paper
> results. See the
> [quality incident report](../../../docs/current/v2.4/reports/memcalib-v24-data-quality-incident.md).

本目录是当前 v2.4 的唯一评测入口。旧数据版本和旧实验位于 [`evaluation/archive/`](../../archive/)。

## 锁定实验

v2.4 从锁定的 500 条分层样本开始，对全部 125 条 coding 输入替换为自然语言实现规划、行为预测或调试诊断。GLM-5.2 no-memory 有 6 条持续长度终止，因此正式比较使用所有 18 个模型-条件桶共同完成的 494 条样本：

```text
494 samples × 9 models × 2 conditions = 8,892 answers
```

评估结果按推理模式分别汇总，不跨模式混算：

- **主口径：Non-thinking。** 与当前训练设置一致；八个百炼回答模型关闭 thinking，Codex GPT-5.6 Sol 固定使用 `reasoning_effort=none`。完整九模型 system-v2 评估正在生成，完成前不引用旧版或单模型结果代替。
- **补充口径：Think。** 八个百炼回答模型开启 thinking，Codex 仍固定使用 `reasoning_effort=none`，用于分析推理模式影响，不作为训练设置下的主排行榜。
- **单模型诊断：** Qwen3-8B 的既有 non-thinking 实验只用于诊断，不等同于完整九模型 Non-thinking 主评估。

旧 system prompt 下的九模型评估已完成主 Judge 8,892/8,892、副 Judge 450/450，结构重试后 residual invalid=0；新 system-v2 的 Think 与 Non-thinking 结果必须在各自运行完成后独立报告。

## 当前产物

配置：

- [`memcalib-v24-multidomain-500-nine-models.json`](configs/memcalib-v24-multidomain-500-nine-models.json)
- [`memcalib-v24-multidomain-494-nine-models-complete-case.json`](configs/memcalib-v24-multidomain-494-nine-models-complete-case.json)
- [`Qwen3-8B Base/SFT/方法模型 500 条配对评测配置`](configs/memcalib-v24-qwen3-8b-sft-500-vllm.json)
- [`system-v2 Non-thinking 九模型主评估配置`](configs/memcalib-v24-multidomain-494-nine-models-system-v2-nonthinking.json)

集群评测：

- [`Qwen3-8B Base/SFT/方法模型非思考 vLLM 运行包`](cluster/memcalib-v24-qwen3-8b-sft-500/README.md)

发布包：

- [原始 500 条运行发布包](releases/memcalib-v24-multidomain-500-nine-models/README.md)
- [494 条完全配对正式发布包](releases/memcalib-v24-multidomain-494-nine-models-complete-case/README.md)

分析：

- [中文三层样本级主报告](analyses/three-layer-metrics/README.md)
- [候选指标与诊断](analyses/candidate-metrics/README.md)
- [样本级分数与分布](analyses/sample-level/README.md)
- [尾部、Pareto 与名次诊断图](analyses/candidate-metrics/candidate-metric-diagnostics.html)

## 路径约定

当前脚本和文档使用本目录中的 canonical path。发布包内部分 manifest 还记录生成时路径；对当前 v2.4 产物，仓库清理已刷新可解析路径及其直接 SHA-256。历史 manifest 保持原样，见[归档说明](../../archive/README.md)。
