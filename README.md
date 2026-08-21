# MemCalib

**评测对话语言模型应当何时以及如何使用记忆。**

MemCalib 评测模型在回答新问题时，能否恰当地调节检索记忆或存储记忆对回答的影响。正式评测使用自然段形式的父记忆块；同一 canonical 记录还保存原子文本的确定性直接拼接视图，供句子级信用分配使用。评测端使用隐藏的原子级监督，判断每项信息应被抑制、有限使用，还是作为关键约束。

## 当前版本：v2.4.1

v2.4.1 是当前纠正后的数据版本。它针对人工发现的原子文本、问题、参考答案和 rubric 错位进行了全量对齐审计、双 Judge 修复、人工收尾和评测前人工门禁。v2.4 保留为质量事件审计版本，不再作为训练数据或论文主表来源。

| 统计项 | v2.4.1 |
|---|---:|
| 样本 | 15,000 |
| health / general / coding | 7,500 / 3,750 / 3,750 |
| 模型可见记忆块 | 74,800 |
| 每条样本可见记忆块 | 3–20，均值 4.9867 |
| 多原子可见块 | 59,801（79.95%） |
| 隐藏原子记忆 | 234,220 |
| 每条样本隐藏原子 | 6–63，均值 15.6147 |
| A / B / C 原子 | 197,510 / 18,943 / 17,767 |
| level 1 / 2 / 3 | 3,751 / 7,500 / 3,749 |
| SFT / RL / test | 4,000 / 8,000 / 3,000（无独立 dev） |
| 双严格 SFT 监督 | 11,892 / 12,000 训练样本 |
| 无监督训练样本 | 108（保留在 canonical，不进入 SFT baseline） |
| 固定评测子集 | test 内 1,500 条（保留历史 500 条锚点） |
| 评测前人工分层审查 | 首轮 18/30 通过；修正后 30/30 通过 |

能力标签描述记忆对当前回答的使用强度：

- **A - suppress：** 不应影响当前回答，对应 `ignore`。
- **B - bound：** 与问题相关，但只能有限使用。
- **C - control：** 必须实质性约束回答。

错误、过时或不安全但仍与问题相关的记忆由独立的 `memory_action=correct` 表示，可能属于 B 或 C；A 只允许 `ignore`，禁止 `A+correct`。

完整发布文件：

```text
pipeline/data/multidomain/full-v2/revision-coding-text-observable-v24/v241/
  release/memcalib_v241_multidomain_benchmark_15000.jsonl
```

发布 SHA-256：

```text
f76b9d6b1d07c6e27e975562ce5b05a338a6d59f093674eea947d65e74e59f50
```

## 当前入口

- [v2.4.1 数据、质检与人工门禁](docs/current/v2.4.1/README.md)
- [v2.4.1 正式划分、ID 清单与统计](sft/releases/memcalib-v241-sft4000-rl8000-test3000/split-manifest.json)
- [v2.4.1 正式 1,500 条 Benchmark Test 发布包](evaluation/current/v2.4.1/releases/memcalib-v241-benchmark-test-eval-1500/release-manifest.json)
- [v2.4.1 训练字段、直接拼接与反事实契约](docs/current/v2.4.1/training-fields.md)
- [30 条评测前逐样本人工审查报告](docs/current/v2.4.1/review/memcalib-v241-manual-review-report-30.md)
- [30 条完整监督审查样本](docs/current/v2.4.1/review/memcalib-v241-manual-review-sample-30.jsonl)
- [v2.4.1 非思考九模型评测](evaluation/current/v2.4.1/README.md)
- [正式 1,500 条九模型三轮 Non-Think 聚合结果](evaluation/current/v2.4.1/analyses/memcalib-v241-benchmark1500-nine-models-nonthinking-full-memory-three-seeds/aggregate/README.md)
- [正式九模型三轮聚合可视化表](evaluation/current/v2.4.1/analyses/memcalib-v241-benchmark1500-nine-models-nonthinking-full-memory-three-seeds/aggregate/three-repeat-summary.html)
- [本地 vLLM 两模型 1,500 条三轮 Non-Think 聚合结果](evaluation/current/v2.4.1/analyses/memcalib-v241-local-baselines-1500-nonthinking-vllm/aggregate/README.md)
- [本地 vLLM 两模型三轮聚合可视化表](evaluation/current/v2.4.1/analyses/memcalib-v241-local-baselines-1500-nonthinking-vllm/aggregate/three-repeat-summary.html)
- [中文样本级三层主指标、公式与区间](evaluation/current/v2.4.1/analyses/three-layer-metrics-nonthinking/README.md)
- [机器生成的样本级分布明细](evaluation/current/v2.4.1/analyses/sample-level-nonthinking/README.md)
- [原子级候选指标与诊断图](evaluation/current/v2.4.1/analyses/candidate-metrics-nonthinking/README.md)
- [v2.4 质量事件报告](docs/current/v2.4/reports/memcalib-v24-data-quality-incident.md)
- [SFT 数据构建入口](sft/README.md)

## 当前评测摘要

正式 `test_eval` 已扩展并锁定为 1,500 条，领域为 health_seed/general/coding = 750/375/375；它保留原 500 条评测集作为可追溯锚点，新增 1,000 条，并保证归一化问题文本无重复。正式评测覆盖 6 个百炼模型、3 个公司统一推理平台模型和 2 个本地 vLLM 基线；主口径均为 Full-memory、Non-Think、三轮独立生成，Judge 为关闭 thinking 的 DeepSeek-V4-Pro。

正式 1,500 条上的九个远程推理模型三轮结果如下（数值为百分数，`±` 后为总体标准差百分点）：

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

三个公司统一推理平台模型与六个百炼模型使用同一锁定样本、提示词、三轮种子和 Judge 协议。原计划的 Claude Opus 5 在 415 条有效回答后被平台访问策略阻断；这些结果只保留为失败审计，正式评测改用 Claude Sonnet 4.6 并从零完成三轮，未将两个 Claude 模型混合统计。九模型三轮共完成 40,500/40,500 条主 Judge 和 675/675 条分层副 Judge，定向重试后 API 失败与结构 invalid 均为 0。

两个本地 vLLM 基线使用相同评测设置，但与九个远程推理模型分表报告：

| Model | SCS ↑ | Exact ↑ | sOPB ↓ | sUPB ↓ | Any-OPB ↓ | Any-UPB ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Qwen3.5-35B-A3B (Local vLLM) | 24.59±0.12 | 10.13±0.16 | 67.74±0.16 | **18.55±0.26** | 83.20±0.14 | **29.82±0.52** |
| Ministral-3-8B-Instruct-2512 (Local vLLM) | **30.41±0.13** | **14.84±0.21** | **59.12±0.06** | 24.10±0.22 | **75.62±0.03** | 37.00±0.28 |

三轮共完成 9,000 条主 Judge 和 150 条分层副 Judge，Judge API 失败与结构 invalid 均为 0。Qwen3.5-35B-A3B 第三轮有 1 条上游回答生成失败；该样本未被删除，而是按预注册失败策略保留在分母中并计为任务质量 0、全部目标原子预测为 A。

以下结果仅是扩展前 494 个完全配对 ID 上的历史 Non-thinking 九模型实验，不是新 1,500 条 benchmark 的分数。该历史实验在同一批样本上独立评测三轮，每轮均包含 Full-memory 与 No-memory：每轮 8,892 个回答，三轮共 26,676 个回答。八个百炼模型关闭 thinking，Codex GPT-5.6 Sol 使用 `reasoning_effort=none`。三轮所有主判分均由关闭 thinking 的 DeepSeek-V4-Pro 完成，共 26,676/26,676；另有 1,350 条同 Judge 分层复判。

主报告采用三层样本级口径：

- 总体主指标：`SCS(0.5)`；
- 方向主指标：`sOPB(0.5)` 与 `sUPB(0.5)`；
- 事件率护栏：`Any-OPB` 与 `Any-UPB`。

下表报告历史 494 条实验中三轮 Full-memory 的均值与三轮总体标准差（`均值 ± SD`）：

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

原子级 H、MinCalib、MCC、Kappa、CVaR、PMU、Rasch、pairwise 和 Pareto 仅作为补充诊断，不替代三层样本级主口径。

## 数据与交付

完整 15,000 条数据、API 构建审计和模型/Judge 中间结果位于 Git 忽略的本地目录。远程仓库保存可复现代码、提示词、测试、schema、报告、小型审阅样本和锁定评测发布包；凭据不进入仓库或交付文件。

评测发布包位于：

```text
evaluation/current/v2.4.1/releases/
  memcalib-v241-multidomain-494-nine-models-nonthinking/
  memcalib-v241-nonthinking-nine-models-deepseek-v4-pro-judge-three-repeats/
```

## 仓库结构

```text
docs/current/v2.4.1/        当前数据文档与人工审查
docs/current/v2.4/          已冻结的质量事件审计版本
evaluation/current/v2.4.1/ 当前非思考主评测、指标和发布包
evaluation/current/v2.4/   已冻结的旧数据评测
evaluation/archive/        更早评测归档
pipeline/                  构建阶段、提示词和本地工作区
sft/                       SFT 构建与实验
tools/                     发布、打包与验证工具
tests/                     流水线和发布工具测试
```

## 验证

```bash
PY=/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
PYTHONPATH=. $PY -m unittest discover -s tests -p 'test_*.py'
```
