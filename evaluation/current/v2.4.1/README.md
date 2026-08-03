# MemCalib v2.4.1 Evaluation

本目录是纠正后 v2.4.1 的当前评测入口。主口径为 **Non-thinking**，与训练设置一致；不与冻结的 v2.4 结果混表。

## 当前主实验：DeepSeek-V4-Pro Judge 三轮 Non-Think

- 样本：同一组 494 个完全配对 ID；
- 领域：health_seed 250、general 125、coding 119；
- 条件：每轮均包含 Full-memory 与 No-memory；
- 回答：每轮 `494 × 9 × 2 = 8,892`，三轮 26,676；
- 八个百炼回答模型：thinking 关闭；
- Codex GPT-5.6 Sol：`reasoning_effort=none`；
- 主 Judge：DeepSeek-V4-Pro，thinking 关闭，每轮 8,892，三轮 26,676；
- 同 Judge 分层复判：每轮 450，三轮 1,350；
- 凭据隔离：所有百炼回答与 Judge 只使用第二个 broad key，不使用 fast key。

三轮都重新调用回答模型和 Judge，不跨轮复用结果。每轮回答、主判分和复判均达到完整覆盖；三轮各有 1 条初始结构无效判分，经定向重试后 residual invalid=0。主 Judge 请求不向 Judge 暴露回答模型身份。

## 三轮主结果

下表是 Full-memory 样本级三层指标的 `三轮均值 ± 三轮总体标准差`：

| 模型 | SCS↑ | sOPB↓ | sUPB↓ | Any-OPB↓ | Any-UPB↓ | Exact↑ |
|---|---:|---:|---:|---:|---:|---:|
| Codex GPT-5.6 Sol | **48.80% ± 0.78** | **29.48% ± 0.59** | 28.45% ± 0.72 | **42.17% ± 0.48** | 43.86% ± 1.54 | **30.09% ± 1.10** |
| Kimi-K2.6 | 37.72% ± 0.96 | 50.76% ± 0.46 | 20.54% ± 0.89 | 65.45% ± 0.50 | 32.32% ± 1.54 | 21.79% ± 0.91 |
| GLM-5.2 | 36.31% ± 1.02 | 48.42% ± 0.58 | 23.58% ± 0.83 | 62.82% ± 0.50 | 35.96% ± 1.59 | 19.84% ± 1.59 |
| DeepSeek-V4-Flash | 33.60% ± 0.37 | 50.85% ± 0.96 | 27.00% ± 0.56 | 67.34% ± 1.50 | 41.90% ± 0.57 | 15.92% ± 0.53 |
| Qwen3.7-Max | 33.43% ± 0.80 | 50.35% ± 1.07 | 28.71% ± 0.59 | 66.53% ± 1.57 | 43.25% ± 0.67 | 16.94% ± 0.50 |
| Qwen3-8B | 32.40% ± 0.44 | 32.91% ± 0.85 | 46.54% ± 0.43 | 45.88% ± 1.70 | 62.82% ± 0.58 | 15.59% ± 0.83 |
| DeepSeek-V4-Pro | 31.24% ± 1.32 | 59.39% ± 0.64 | 20.86% ± 1.52 | 75.64% ± 0.10 | 33.27% ± 2.07 | 15.32% ± 1.06 |
| Qwen3.6-Flash | 26.92% ± 0.28 | 64.86% ± 0.19 | **18.63% ± 0.69** | 79.96% ± 0.17 | **29.96% ± 1.01** | 12.89% ± 0.25 |
| Qwen3.5-35B-A3B | 26.78% ± 0.50 | 64.87% ± 0.42 | 19.50% ± 0.83 | 80.23% ± 0.50 | 31.65% ± 1.74 | 11.81% ± 0.76 |

不要用单一综合数替代方向性分析：SCS 是总体主指标；sOPB/sUPB 保留错误方向和累积强度；Any-OPB/Any-UPB 是事件覆盖率护栏。

### 三轮产物

- [三轮专用配置](configs/memcalib-v241-multidomain-494-nine-models-nonthinking-deepseek-v4-pro-judge.json)
- [聚合结果与三轮稳定性](analyses/memcalib-v241-nonthinking-nine-models-deepseek-v4-pro-judge-three-repeats/aggregate/README.md)
- [聚合机器可读指标](analyses/memcalib-v241-nonthinking-nine-models-deepseek-v4-pro-judge-three-repeats/aggregate/aggregate-metrics.json)
- [聚合可视化表](analyses/memcalib-v241-nonthinking-nine-models-deepseek-v4-pro-judge-three-repeats/aggregate/three-repeat-summary.html)
- [三轮逐轮指标与报告](releases/memcalib-v241-nonthinking-nine-models-deepseek-v4-pro-judge-three-repeats/)

## 历史单轮 Qwen3.7-Plus Judge 实验

- 样本：494 个完全配对 ID；
- 领域：health_seed 250、general 125、coding 119；
- 条件：full-memory 与 no-memory；
- 回答：494 × 9 × 2 = 8,892；
- 八个百炼回答模型：thinking 关闭；
- Codex GPT-5.6 Sol：`reasoning_effort=none`；
- 主 Judge：Qwen3.7-Plus，thinking 关闭；
- 副 Judge：DeepSeek-V4-Pro 350 条、Kimi-K2.6 100 条，thinking 关闭。

回答和 Judge 均使用请求指纹进行精确复用；不匹配或缺失项才重新运行。v2.4.1 最终完成主 Judge 8,892/8,892、副 Judge 450/450。主 Judge 初次结构无效 25 条，第一轮修复 24 条，第二轮修复 1 条；副 Judge 结构修复 1 条，最终 residual invalid=0。

## 历史单轮结果

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
