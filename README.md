# MemCalib

**评测对话语言模型应当何时以及如何使用记忆。**

MemCalib 评测模型在回答新问题时，能否恰当地调节检索记忆或存储记忆对回答的影响。模型接收自然段形式的非原子记忆块；评测端使用隐藏的原子级监督，判断每项信息应被抑制、有限使用，还是作为关键约束。

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
8bc18ae468e1ab1d41ffa4556c6e042a62538eca01e97029db94f850c2c46dc4
```

## 当前入口

- [v2.4.1 数据、质检与人工门禁](docs/current/v2.4.1/README.md)
- [30 条评测前逐样本人工审查报告](docs/current/v2.4.1/review/memcalib-v241-manual-review-report-30.md)
- [30 条完整监督审查样本](docs/current/v2.4.1/review/memcalib-v241-manual-review-sample-30.jsonl)
- [v2.4.1 非思考九模型评测](evaluation/current/v2.4.1/README.md)
- [DeepSeek-V4-Pro Judge 三轮 Non-Think 聚合结果](evaluation/current/v2.4.1/analyses/memcalib-v241-nonthinking-nine-models-deepseek-v4-pro-judge-three-repeats/aggregate/README.md)
- [三轮聚合可视化表](evaluation/current/v2.4.1/analyses/memcalib-v241-nonthinking-nine-models-deepseek-v4-pro-judge-three-repeats/aggregate/three-repeat-summary.html)
- [中文样本级三层主指标、公式与区间](evaluation/current/v2.4.1/analyses/three-layer-metrics-nonthinking/README.md)
- [机器生成的样本级分布明细](evaluation/current/v2.4.1/analyses/sample-level-nonthinking/README.md)
- [原子级候选指标与诊断图](evaluation/current/v2.4.1/analyses/candidate-metrics-nonthinking/README.md)
- [v2.4 质量事件报告](docs/current/v2.4/reports/memcalib-v24-data-quality-incident.md)
- [SFT 数据构建入口](sft/README.md)

## 当前评测摘要

主口径为 **Non-thinking**，与训练设置一致。正式 `test_eval` 子集冻结 500 个历史评测 ID；当前跨模型主表采用其中 494 个完全配对 ID。九个模型在同一批样本上独立评测三轮，每轮均包含 Full-memory 与 No-memory：每轮 8,892 个回答，三轮共 26,676 个回答。八个百炼模型关闭 thinking，Codex GPT-5.6 Sol 使用 `reasoning_effort=none`。三轮所有主判分均由关闭 thinking 的 DeepSeek-V4-Pro 完成，共 26,676/26,676；另有 1,350 条同 Judge 分层复判。百炼回答与 Judge 全程只使用第二个、模型覆盖更广的 key，未占用用于训练的快速 key。

主报告采用三层样本级口径：

- 总体主指标：`SCS(0.5)`；
- 方向主指标：`sOPB(0.5)` 与 `sUPB(0.5)`；
- 事件率护栏：`Any-OPB` 与 `Any-UPB`。

下表报告三轮 Full-memory 的均值与三轮总体标准差（`均值 ± SD`）：

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
