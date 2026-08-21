# MemCalib v2.4.1 Evaluation

本目录是纠正后 v2.4.1 的当前评测入口。主口径为 **Non-thinking**，与训练设置一致；不与冻结的 v2.4 结果混表。

## 正式 Benchmark Test：1,500 条

正式发布评测集现已从历史 500 条扩展为 1,500 条，领域为 health_seed/general/coding = 750/375/375。原 500 条完整保留为有序锚点，新增 1,000 条；归一化问题文本无重复，且该 1,500 条与 SFT、RL 分区均无重叠。数据发布包见 [`releases/memcalib-v241-benchmark-test-eval-1500/`](releases/memcalib-v241-benchmark-test-eval-1500/)。

正式 1,500 条上的评估已完成 6 个百炼模型、3 个公司统一推理平台模型及 2 个本地 vLLM 基线。远程推理模型与本地 vLLM 基线分表报告；后续 494 条三轮九模型结果只用于保留历史实验记录，不能当作新正式 benchmark 的得分。

## 正式 1,500 条九模型结果

- 模型：6 个百炼模型，以及 GPT-5.6-SOL、Claude Sonnet 4.6、Gemini 3.5 Flash；
- 条件：Full-memory、Non-Think，每个模型在种子 42/43/44 下各生成一次；
- 主 Judge：DeepSeek-V4-Pro，关闭 thinking；
- 覆盖：三轮主 Judge `40,500/40,500`，分层副 Judge `675/675`；
- 定向重试后 Judge API 失败：0；结构 invalid：0。

| Model | SCS ↑ | Exact ↑ | sOPB ↓ | sUPB ↓ | Any-OPB ↓ | Any-UPB ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Qwen3.8-Max | 34.22±0.52 | 17.80±0.48 | 50.11±0.33 | 27.46±0.32 | 66.09±0.51 | 41.16±0.21 |
| Kimi-K2.6 | 35.54±0.18 | 20.00±0.28 | 53.83±0.19 | 19.94±0.60 | 68.67±0.63 | 31.56±0.98 |
| DeepSeek-V4-Flash-0731 | 33.72±0.76 | 16.96±0.93 | 55.64±1.08 | 20.86±0.59 | 73.31±1.01 | 32.64±0.76 |
| GLM-5.2 | 34.40±0.45 | 18.20±0.61 | 52.13±0.42 | 23.42±0.31 | 67.53±0.88 | 35.73±0.71 |
| Qwen3.5-35B-A3B | 24.78±0.43 | 10.47±0.48 | 67.55±0.65 | **19.04±0.63** | 83.07±0.63 | **30.47±1.00** |
| Qwen3-8B | 31.84±0.09 | 15.56±0.30 | **34.68±0.33** | 46.57±0.12 | **48.22±0.68** | 62.47±0.29 |
| GPT-5.6-SOL | **46.25±0.60** | **28.40±0.85** | 38.45±0.15 | 22.92±0.40 | 53.33±0.45 | 35.82±0.51 |
| Claude Sonnet 4.6 | 36.44±0.34 | 19.09±0.33 | 48.89±0.62 | 24.77±0.37 | 65.40±0.77 | 37.93±0.38 |
| Gemini 3.5 Flash | 34.96±0.53 | 17.96±0.58 | 51.65±0.45 | 24.73±0.14 | 68.27±0.38 | 37.69±0.25 |

数值是百分数三轮均值，`±` 后为总体标准差（百分点）。公司统一推理平台模型使用与百炼模型相同的锁定样本、提示词、三轮种子和 Judge 协议。原计划的 Claude Opus 5 在获得 415 条有效回答后被平台访问策略阻断；其输出只保留为失败审计，正式表格中的 Claude 结果全部来自从零完成三轮的 Sonnet 4.6。

- [九模型聚合说明](analyses/memcalib-v241-benchmark1500-nine-models-nonthinking-full-memory-three-seeds/aggregate/README.md)
- [九模型聚合 JSON](analyses/memcalib-v241-benchmark1500-nine-models-nonthinking-full-memory-three-seeds/aggregate/aggregate-metrics.json)
- [九模型三轮可视化表](analyses/memcalib-v241-benchmark1500-nine-models-nonthinking-full-memory-three-seeds/aggregate/three-repeat-summary.html)
- [九模型逐轮发布产物](releases/memcalib-v241-benchmark1500-nine-models-nonthinking-full-memory-three-seeds/)

## 正式 1,500 条本地 vLLM 基线

- 模型：Qwen3.5-35B-A3B、Ministral-3-8B-Instruct-2512；
- 条件：Full-memory、Non-Think，每个模型在种子 42/43/44 下各生成一次；
- 主 Judge：DeepSeek-V4-Pro，关闭 thinking；
- 覆盖：三轮主 Judge `9,000/9,000`，分层副 Judge `150/150`；
- Judge API 失败：0；结构 invalid：0；
- 回答生成失败：Qwen3.5-35B-A3B 第三轮 1 条，按固定失败策略保留在分母中。

| Model | SCS ↑ | Exact ↑ | sOPB ↓ | sUPB ↓ | Any-OPB ↓ | Any-UPB ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Qwen3.5-35B-A3B (Local vLLM) | 24.59±0.12 | 10.13±0.16 | 67.74±0.16 | **18.55±0.26** | 83.20±0.14 | **29.82±0.52** |
| Ministral-3-8B-Instruct-2512 (Local vLLM) | **30.41±0.13** | **14.84±0.21** | **59.12±0.06** | 24.10±0.22 | **75.62±0.03** | 37.00±0.28 |

数值是百分数三轮均值，`±` 后为总体标准差（百分点）。本地基线的逐轮指标、聚合机器可读结果和 HTML 表格见：

- [聚合说明](analyses/memcalib-v241-local-baselines-1500-nonthinking-vllm/aggregate/README.md)
- [聚合 JSON](analyses/memcalib-v241-local-baselines-1500-nonthinking-vllm/aggregate/aggregate-metrics.json)
- [三轮可视化表](analyses/memcalib-v241-local-baselines-1500-nonthinking-vllm/aggregate/three-repeat-summary.html)
- [逐轮发布产物](releases/memcalib-v241-local-baselines-1500-nonthinking-vllm/)

## 历史主实验：DeepSeek-V4-Pro Judge 三轮 Non-Think

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
- [Qwen3-8B 自定义 checkpoint 集群评测（494 条、Non-Think）](cluster/memcalib-v241-qwen3-8b-checkpoints-494/README.md)
- [Qwen3-8B v2.4.1 三训练视图对比（485 条、Full-memory）](analyses/qwen3-8b-three-checkpoints-485-primary/README.md)
- [原始 Qwen3-8B 与三训练视图严格同 prompt 对比（485 条、全部主指标）](analyses/qwen3-8b-four-model-current-prompt-485-primary/README.md)
- [原始 Qwen3-8B 的 Qwen3.7-Plus / DeepSeek-V4-Pro 全覆盖 Judge 稳定性对比](analyses/qwen3-8b-original-current-prompt-485-deepseek-v4-pro-judge/README.md)
- [旧 prompt 原始 Qwen3-8B 近似对比（历史产物）](analyses/qwen3-8b-four-model-485-primary/README.md)

模型回答、Judge 原始输出、结构重试和规范化判断保存在本地运行目录：

```text
evaluation/runs/memcalib-v241-multidomain-494-nine-models-nonthinking/
```

该目录默认不进入 Git；发布目录保存锁定样本、manifest、指标与可审阅报告。
