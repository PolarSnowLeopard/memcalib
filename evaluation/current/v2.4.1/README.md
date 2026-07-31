# MemCalib v2.4.1 Evaluation

本目录是纠正后 v2.4.1 的当前评测入口。主口径为 **Non-thinking**，与训练设置一致；不与冻结的 v2.4 结果混表。

## 锁定实验

- 样本：494 个完全配对 ID；
- 领域：health_seed 250、general 125、coding 119；
- 条件：full-memory 与 no-memory；
- 回答：494 × 9 × 2 = 8,892；
- 八个百炼回答模型：thinking 关闭；
- Codex GPT-5.6 Sol：`reasoning_effort=none`；
- 主 Judge：Qwen3.7-Plus，thinking 关闭；
- 副 Judge：DeepSeek-V4-Pro 350 条、Kimi-K2.6 100 条，thinking 关闭。

回答和 Judge 均使用请求指纹进行精确复用；不匹配或缺失项才重新运行。v2.4.1 最终完成主 Judge 8,892/8,892、副 Judge 450/450。主 Judge 初次结构无效 25 条，第一轮修复 24 条，第二轮修复 1 条；副 Judge 结构修复 1 条，最终 residual invalid=0。

## 主结果

样本级三层主口径：

| 模型 | SCS↑ | sOPB↓ | sUPB↓ | Any-OPB↓ | Any-UPB↓ | Exact↑ |
|---|---:|---:|---:|---:|---:|---:|
| Codex GPT-5.6 Sol | **40.4%** | **33.8%** | 36.0% | **46.0%** | 53.6% | **21.5%** |
| Kimi-K2.6 | 30.3% | 55.3% | **27.8%** | 69.0% | 43.7% | 14.6% |
| GLM-5.2 | 30.1% | 53.7% | 29.5% | 67.4% | 43.9% | 15.0% |
| Qwen3-8B | 26.7% | 38.6% | 49.6% | 51.2% | 67.6% | 10.3% |
| Qwen3.7-Max | 26.6% | 54.2% | 35.6% | 68.4% | 54.0% | 10.5% |
| DeepSeek-V4-Flash | 24.9% | 63.0% | 28.2% | 77.1% | 44.9% | 10.5% |
| DeepSeek-V4-Pro | 24.1% | 64.2% | 28.0% | 78.7% | 44.3% | 10.5% |
| Qwen3.5-35B-A3B | 21.5% | 67.9% | 27.4% | 81.0% | **43.1%** | 8.7% |
| Qwen3.6-Flash | 21.3% | 68.6% | 27.7% | 82.6% | 44.3% | 8.1% |

不要仅用一个综合数解释模型行为。SCS 是总体主指标；sOPB/sUPB 保留错误方向和累积强度；Any-OPB/Any-UPB 只作为事件覆盖面护栏。

## 产物

- [评测配置](configs/memcalib-v241-multidomain-494-nine-models-nonthinking.json)
- [锁定发布包](releases/memcalib-v241-multidomain-494-nine-models-nonthinking/)
- [可视化评测报告](releases/memcalib-v241-multidomain-494-nine-models-nonthinking/report.html)
- [中文样本级三层主指标、公式与区间](analyses/three-layer-metrics-nonthinking/README.md)
- [机器生成的样本级指标、区间和分布](analyses/sample-level-nonthinking/README.md)
- [样本级分布图](analyses/sample-level-nonthinking/sample-level-score-distributions.html)
- [候选指标与稳健性分析](analyses/candidate-metrics-nonthinking/README.md)
- [尾部、Pareto 与排名诊断图](analyses/candidate-metrics-nonthinking/candidate-metric-diagnostics.html)

模型回答、Judge 原始输出、结构重试和规范化判断保存在本地运行目录：

```text
evaluation/runs/memcalib-v241-multidomain-494-nine-models-nonthinking/
```

该目录默认不进入 Git；发布目录保存锁定样本、manifest、指标与可审阅报告。
