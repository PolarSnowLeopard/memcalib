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
- [中文样本级三层主指标、公式与区间](evaluation/current/v2.4.1/analyses/three-layer-metrics-nonthinking/README.md)
- [机器生成的样本级分布明细](evaluation/current/v2.4.1/analyses/sample-level-nonthinking/README.md)
- [原子级候选指标与诊断图](evaluation/current/v2.4.1/analyses/candidate-metrics-nonthinking/README.md)
- [v2.4 质量事件报告](docs/current/v2.4/reports/memcalib-v24-data-quality-incident.md)
- [SFT 数据构建入口](sft/README.md)

## 当前评测摘要

主口径为 **Non-thinking**，与训练设置一致。评测锁定 v2.4 的 494 个完全配对 ID，并在纠正后的 v2.4.1 数据上重新生成受影响回答。八个百炼回答模型关闭 thinking；Codex GPT-5.6 Sol 使用 `reasoning_effort=none`。主 Judge 完成 8,892/8,892，副 Judge 完成 450/450；26 条主 Judge 结构错误经两轮定向重试后 residual invalid=0。

主报告采用三层样本级口径：

- 总体主指标：`SCS(0.5)`；
- 方向主指标：`sOPB(0.5)` 与 `sUPB(0.5)`；
- 事件率护栏：`Any-OPB` 与 `Any-UPB`。

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

原子级 H、MinCalib、MCC、Kappa、CVaR、PMU、Rasch、pairwise 和 Pareto 仅作为补充诊断，不替代三层样本级主口径。

## 数据与交付

完整 15,000 条数据、API 构建审计和模型/Judge 中间结果位于 Git 忽略的本地目录。远程仓库保存可复现代码、提示词、测试、schema、报告、小型审阅样本和锁定评测发布包；凭据不进入仓库或交付文件。

评测发布包位于：

```text
evaluation/current/v2.4.1/releases/
  memcalib-v241-multidomain-494-nine-models-nonthinking/
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
$PY -m unittest discover -s tests -p 'test_*.py'
```
