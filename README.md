# MemCalib

**评测对话语言模型应当何时以及如何使用记忆。**

MemCalib 评测模型在回答新问题时，能否恰当地调节检索记忆或存储记忆对回答的影响。模型接收自然段形式的非原子记忆块；评测端使用隐藏的原子级监督，判断每项信息应被抑制、有限使用，还是作为关键约束。

## 当前版本：v2.4

v2.4 是当前唯一活跃的数据版本。它锁定 v2.3 的 15,000 条记录、领域配额、ID、顺序、来源、记忆块和 A/B/C 监督，只重建全部 3,750 条 coding 记录的问题、自然语言参考答案和 answer-text rubric。coding 任务改为实现规划、行为预测或调试诊断，Judge 无需执行代码即可核验记忆使用。

| 统计项 | v2.4 |
|---|---:|
| 样本 | 15,000 |
| health / general / coding | 7,500 / 3,750 / 3,750 |
| 模型可见记忆块 | 74,800 |
| 每条样本可见记忆块 | 3–20，均值 4.9867 |
| 多原子可见块 | 59,800（79.95%） |
| 隐藏原子记忆 | 234,221 |
| A / B / C 原子 | 197,573 / 19,032 / 17,616 |
| level 1 / 2 / 3 | 3,751 / 7,500 / 3,749 |
| coding 独立 QC strict / 人工裁决 | 3,735 / 15 |

能力标签描述记忆对当前回答的使用强度：

- **A - suppress：** 不应影响当前回答，对应 `ignore`。
- **B - bound：** 与问题相关，但只能有限使用。
- **C - control：** 必须实质性约束回答。

错误、过时或不安全但仍与问题相关的记忆由独立的 `memory_action=correct` 表示，可能属于 B 或 C；A 只允许 `ignore`，禁止 `A+correct`。

## 当前入口

所有 v2.4 Git 跟踪内容集中在以下两个入口：

- [v2.4 数据、结构、质检与审阅文档](docs/current/v2.4/README.md)
- [v2.4 评测配置、发布结果与指标分析](evaluation/current/v2.4/README.md)

常用文档：

- [合作者交付说明](docs/current/v2.4/MEMCALIB_V24_COAUTHOR_HANDOFF.md)
- [数据结构与约束](docs/current/v2.4/benchmark-schema-v2.4.md)
- [3,750 条 coding 全量迭代与质检报告](docs/current/v2.4/reports/memcalib-v24-coding-text-observability.md)
- [3 条中文分层审阅样本](docs/current/v2.4/samples/memcalib-v24-coding-review-sample-3-zh.md)
- [30 条机器可读审阅样本](docs/current/v2.4/samples/memcalib-v24-coding-review-sample-30.README.md)
- [九模型 494 条完全配对评测](evaluation/current/v2.4/releases/memcalib-v24-multidomain-494-nine-models-complete-case/README.md)
- [中文三层样本级指标、公式与图表](evaluation/current/v2.4/analyses/three-layer-metrics/README.md)

## 当前评测摘要

v2.4 九模型评测使用 494 个共同样本、full-memory/no-memory 配对条件和相同 Judge 配置。主 Judge 8,892/8,892、副 Judge 450/450；结构重试后 residual invalid=0。主报告采用三层样本级口径：

- 总体主指标：`SCS(0.5)`；
- 方向主指标：`sOPB(0.5)` 与 `sUPB(0.5)`；
- 事件率护栏：`Any-OPB` 与 `Any-UPB`。

| 模型 | SCS↑ | sOPB↓ | sUPB↓ | Any-OPB↓ | Any-UPB↓ | Exact↑ |
|---|---:|---:|---:|---:|---:|---:|
| Codex GPT-5.6 Sol | **39.8%** | **38.5%** | 33.7% | **52.6%** | 51.4% | **21.9%** |
| Kimi-K2.6 | 32.3% | 53.3% | 28.9% | 67.0% | 44.1% | 18.0% |
| Qwen3-8B | 30.4% | 47.0% | 39.6% | 59.9% | 59.3% | 15.0% |
| DeepSeek-V4-Flash | 28.6% | 60.9% | 24.9% | 75.9% | 39.9% | 14.2% |
| Qwen3.6-Flash | 27.9% | 60.9% | 27.0% | 74.5% | 42.3% | 15.4% |
| GLM-5.2 | 25.9% | 64.7% | 22.2% | 78.1% | 36.4% | 11.7% |
| DeepSeek-V4-Pro | 24.4% | 67.8% | 20.9% | 81.4% | 33.4% | 11.7% |
| Qwen3.5-35B-A3B | 21.0% | 70.0% | 26.1% | 84.4% | 41.1% | 8.5% |
| Qwen3.7-Max | 20.7% | 71.8% | **19.9%** | 86.0% | **32.4%** | 6.7% |

原子级 H、MinCalib、MCC、Kappa、CVaR、PMU、Rasch、pairwise 和 Pareto 仅作为补充诊断，见[候选指标报告](evaluation/current/v2.4/analyses/candidate-metrics/README.md)。

## 数据与交付

完整 15,000 条 v2.4 数据和 API 构建审计位于本机忽略目录：

```text
pipeline/data/multidomain/full-v2/revision-coding-text-observable-v24/
```

远程仓库只保存可复现代码、提示词、测试、schema、报告、小型审阅样本和锁定评测发布包。合作者完整数据包由以下工具确定性构建：

```bash
PY=/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
$PY tools/package_memcalib_v24_handoff.py
```

默认 ZIP 输出为：

```text
pipeline/data/multidomain/full-v2/revision-coding-text-observable-v24/handoff/MemCalib-v2.4-coauthor-20260729.zip
```

## 仓库结构

```text
docs/current/v2.4/          当前数据文档、报告与审阅样本
docs/archive/              v2.0-v2.3 文档和设计归档
evaluation/current/v2.4/   当前评测配置、发布包和分析
evaluation/archive/        历史评测配置、发布包、分析与集群说明
pipeline/                  稳定编号的构建阶段、提示词和本地工作区
release/archive/           早期仓库内锁定发布包
sft/                       历史 v2.3 SFT 实验线
tools/                     发布、打包与验证工具
tests/                     流水线和发布工具测试
```

详细边界见[仓库布局说明](docs/repository-layout.md)。旧版本不得作为当前入口或与 v2.4 混合排名；历史索引见[文档归档](docs/archive/versions/README.md)和[评测归档](evaluation/archive/README.md)。

## 验证

```bash
PY=/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
$PY -m unittest discover -s tests -p 'test_*.py'
```

大体积源数据、API 请求与响应、运行日志和中间产物均不进入 Git。凭据只从环境变量读取，不保存在仓库或交付包中。
