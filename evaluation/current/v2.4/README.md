# MemCalib v2.4 Evaluation

本目录是当前 v2.4 的唯一评测入口。旧数据版本和旧实验位于 [`evaluation/archive/`](../../archive/)。

## 锁定实验

v2.4 从锁定的 500 条分层样本开始，对全部 125 条 coding 输入替换为自然语言实现规划、行为预测或调试诊断。GLM-5.2 no-memory 有 6 条持续长度终止，因此正式比较使用所有 18 个模型-条件桶共同完成的 494 条样本：

```text
494 samples × 9 models × 2 conditions = 8,892 answers
```

主 Judge 8,892/8,892、副 Judge 450/450；结构重试后 residual invalid=0。八个百炼回答模型开启 thinking，Codex GPT-5.6 Sol 使用 `reasoning_effort=none`，Judge 关闭 thinking。

## 当前产物

配置：

- [`memcalib-v24-multidomain-500-nine-models.json`](configs/memcalib-v24-multidomain-500-nine-models.json)
- [`memcalib-v24-multidomain-494-nine-models-complete-case.json`](configs/memcalib-v24-multidomain-494-nine-models-complete-case.json)

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
