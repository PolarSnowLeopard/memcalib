# MemCalib evaluation

本目录保存 MemCalib 的锁定评测样本、配置、聚合指标、可视化报告和可复现分析工具。当前跨模型默认入口是 MemCalib v2.1 的 500 条八模型配对诊断；另有一项 MemCalib v2.2 的 100 条 Codex answer-only 配对 pilot。v2.0、v0.1、早期 Judge 校准和跨领域 pilot 均作为历史归档保留。

## v2.2 Codex answer-only pilot

从当前 15,000 条 v2.2 长尾发布集中确定性抽取 100 条，覆盖
health/general/coding=50/25/25、全部 8 个来源、全部 5 类 Hard A，以及
3–4/5–6/7–10/11–20 四档可见块数。评测配置为
`codex-cli 0.145.0-alpha.18`、`gpt-5.6-sol`、medium reasoning；每个回答使用
独立 ephemeral 会话、空临时目录和只读沙箱，禁用用户配置与项目规则，并从
Codex JSON 事件流审计工具调用。

200 条 full/no-memory 回答全部完成，0 失败、0 截断、0 工具事件。主
Judge `qwen3.7-plus` 覆盖全部回答，`deepseek-v4-pro` 对预锁定的 40 条回答
进行复核：

| 条件 | OPB↓ | UPB↓ | H↑ |
|---|---:|---:|---:|
| Full memory | 0.057 | 0.239 | 0.842 |
| No memory | 0.005 | 0.914 | 0.158 |

325 个双判原子的有序等级 exact agreement 为 0.972，线性加权
κ=0.935。按合作者提出的微平均方向错误定义复算，full-memory
OPB/UPB/H=0.071/0.230/0.842，整体结论不变。该实验规模只有 100 条，不能
与下方 v2.1 八模型 500 条表直接排名比较。

- [`memcalib-v22-codex-pilot-100/README.md`](releases/memcalib-v22-codex-pilot-100/README.md)：配置、锁样、宏/微指标、分层诊断和限制；
- [`memcalib-v22-codex-pilot-100/report.html`](releases/memcalib-v22-codex-pilot-100/report.html)：可视化报告；
- [`memcalib-v22-codex-pilot-100/metrics.json`](releases/memcalib-v22-codex-pilot-100/metrics.json)：机器可读混淆矩阵、置信区间和 Judge 一致性。

## 当前 v2.1 八模型诊断

从 SHA-256 为
`bd45f77534351cd096476080096ce9ba6250a375941a171ab561ad78704bed44`
的 15,000 条 v2.1 发布集中确定性抽取 500 条：

- health 250、general 125、coding 125；
- 按领域、来源、主题和原子数分层；
- 固定随机种子 `20260719`；
- 有序样本 ID 摘要
  `92292219c596e790720456754376354be30c5954bf7875085594fbce40c52d29`。

八个回答模型分别运行 full-memory 和 no-memory 条件，共形成 8,000
条配对回答。每个模型、每个条件均完整得到 500 条有效回答。回答模型只接收当前问题和非原子 `memory_blocks`，不接收隐藏原子标签、动作或 rubric。原七模型结果没有重跑；Codex 作为第八个模型按唯一回答 ID 合并。

正式协议为
[`ordered-usage-v2.1`](../docs/evaluation_protocol_v2.1.md)。A/B/C
表示规范影响强度；`ignore`、`apply`、`correct` 表示处置方向。错误、过时或不安全但相关的记忆可以是 B/C + `correct`，A 始终要求
`ignore`。

主指标使用 full-memory 条件：

- OPB：实际使用高于规范等级的宏平均错误率，越低越好；
- UPB：实际使用低于规范等级的宏平均错误率，越低越好；
- H：抵抗 OPB 与 UPB 能力的调和平均，越高越好。

### Full-memory 主结果

| 模型 | OPB↓ | UPB↓ | H↑ |
|---|---:|---:|---:|
| Codex GPT-5.6 Sol | 0.212 | 0.294 | 0.745 |
| Kimi-K2.6 | 0.311 | 0.196 | 0.742 |
| DeepSeek-V4-Pro | 0.383 | 0.193 | 0.699 |
| Qwen3.7-Max | 0.384 | 0.201 | 0.696 |
| DeepSeek-V4-Flash | 0.393 | 0.199 | 0.691 |
| Qwen3.6-Flash | 0.394 | 0.201 | 0.689 |
| Qwen3.5-35B-A3B | 0.414 | 0.176 | 0.685 |
| Qwen3-8B | 0.251 | 0.452 | 0.633 |

### No-memory 反事实基线

| 模型 | OPB↓ | UPB↓ | H↑ |
|---|---:|---:|---:|
| DeepSeek-V4-Flash | 0.047 | 0.902 | 0.177 |
| DeepSeek-V4-Pro | 0.052 | 0.907 | 0.170 |
| Qwen3.7-Max | 0.057 | 0.910 | 0.164 |
| Kimi-K2.6 | 0.048 | 0.913 | 0.160 |
| Qwen3.5-35B-A3B | 0.055 | 0.913 | 0.159 |
| Qwen3.6-Flash | 0.065 | 0.915 | 0.155 |
| Codex GPT-5.6 Sol | 0.024 | 0.918 | 0.151 |
| Qwen3-8B | 0.024 | 0.944 | 0.105 |

No-memory 使用同一批问题但不提供记忆块，因此不是独立排行榜。低 OPB
说明模型不会误用不存在的记忆，高 UPB 则说明 B/C 原子承载的信息无法被恢复。八个模型在 full-memory 下均显著降低 UPB。Qwen3-8B 的 OPB
较低但 UPB 明显较高，表现为更保守但对相关记忆利用不足。

该 500 条实验用于内部诊断和流程验证，不应表述为 15,000 条全量公开排行榜。

Codex 使用 `gpt-5.6-sol`、`reasoning_effort=none`，每题独立
ephemeral 会话、空临时工作区和只读沙箱，禁用用户配置与项目规则，并审计
事件流。1,000 条回答均为 0 reasoning token、0 工具事件、0 截断。Codex
仍带固定系统上下文，且 CLI 不暴露与百炼完全相同的 temperature/max-token
控制，因此该行应称为“Codex GPT-5.6 Sol answer-only 配置”，不能表述为
OpenAI API 裸模型结果。

宏平均 H 下 Codex=0.745、Kimi=0.742，二者 95% bootstrap 区间高度重叠。
按合作者提出的微平均方向错误定义，Codex 的 OPB/UPB/H=0.200/0.297/0.748，
Kimi=0.294/0.198/0.751，名次反转。因此合理结论是两者总体接近、方向偏差
不同，而不是 Codex 显著排名第一。

### 候选综合指标研究

同一批 8,000 条主 Judge 结果还计算了 MinCalib、算术/几何/乘积与 soft-min
综合分、balanced accuracy、macro F1、multiclass MCC、未加权/线性/二次
Kappa、NMI、Cramér V、有序距离和严重错误、样本级 CVaR、PMU 权重敏感性、
28 组配对胜率、Bradley–Terry 能力，以及过用/少用双维 Rasch 1PL。正式 H
定义没有因此改变。

- [`candidate metric study`](analyses/memcalib-v21-multidomain-500-candidate-metrics/README.md)：可读汇总、公式边界与全部主要表格；
- [`candidate-metrics.csv`](analyses/memcalib-v21-multidomain-500-candidate-metrics/candidate-metrics.csv)：模型级横向比较；
- [`candidate-metrics.json`](analyses/memcalib-v21-multidomain-500-candidate-metrics/candidate-metrics.json)：完整指标、bootstrap 区间、pairwise、Rasch 和 Pareto 结果。

## Judge 配置与跨模型稳定性

- 主 Judge：`qwen3.7-plus`，覆盖全部 8,000 条回答；
- 复核 Judge `deepseek-v4-pro`：300 条分层回答；
- 复核 Judge `kimi-k2.6`：100 条分层回答；
- 复核抽样按回答模型、full/no-memory 条件、来源、主题和原子数分层；
- 所有调用均使用 temperature=0、thinking=false。

在 1,494 个双重判定原子上：

| 一致性口径 | Exact agreement | Kappa |
|---|---:|---:|
| 总体判定 | 0.902 | 0.868 |
| 有序使用等级 | 0.865 | 0.808（线性加权） |
| DeepSeek 复核 | 0.902 | 0.869 |
| Kimi 复核 | 0.899 | 0.863 |

主 Judge 的 8,000 条规范化判定和复核 Judge 的 400 条判定均覆盖完整，结构性 invalid 经定向重试后为 0。辅助警告主要是 Judge 给出的 evidence quote
未能逐字定位或 confidence 格式归一化；这些警告不等于缺少原子使用等级，完整计数保存在 `metrics.json` 和 judge-run manifest
中。模型间一致性支持当前自动评测的稳定性，但不能替代盲法人工专家标注。

`qwen3.8-max` 也做了可用性预检。2026-07-20 两套百炼凭据均返回 HTTP
404 `model_not_found`，官方公开文本模型目录当时也没有列出该 ID，因此未生成
正式回答，也未把它加入结果表。

## 中间结果与审计保留

每次运行在 `evaluation/runs/<run>/` 下保留：

| 路径 | 内容 |
|---|---|
| `requests/answers/` | full/no-memory 模型请求及输入指纹 |
| `answers/` | 模型原始回答、失败、重试、截断与完整性报告 |
| `requests/judges/` | 主 Judge 和复核 Judge 请求及抽样 ID |
| `api/` | Judge 原始 API 响应、失败与结构重试 |
| `judgments/` | 规范化逐原子有效判定、invalid 和合并结果 |
| `workflow.status` / `workflow.completed` | 阶段状态与完成时间 |

这些原始中间结果保存在本机，但 `evaluation/runs/` 被 Git
忽略，不推送远程仓库，也不进入协作者数据 ZIP。远程
`evaluation/releases/<release>/` 保存锁定样本、输入/输出行数、SHA-256
manifest、聚合 `metrics.json` 和 `report.html`。若要在另一台机器上重新聚合逐条结果，需单独传输对应的 `evaluation/runs/`，并继续排除凭据。

## 当前结果入口

- [`memcalib-v21-multidomain-500-eight-models/README.md`](releases/memcalib-v21-multidomain-500-eight-models/README.md)：同一样本八模型摘要、宏/微口径和公平性限制；
- [`memcalib-v21-multidomain-500-eight-models/report.html`](releases/memcalib-v21-multidomain-500-eight-models/report.html)：八模型 full/no-memory 可视化报告；
- [`memcalib-v21-multidomain-500-eight-models/metrics.json`](releases/memcalib-v21-multidomain-500-eight-models/metrics.json)：机器可读指标、混淆矩阵、置信区间和分层结果；
- [`memcalib-v21-multidomain-500-eight-models/release-manifest.json`](releases/memcalib-v21-multidomain-500-eight-models/release-manifest.json)：样本、模型、完整性和内容哈希；
- [`memcalib-v21-multidomain-500-codex/README.md`](releases/memcalib-v21-multidomain-500-codex/README.md)：Codex 单模型受控配置与审计；
- [`memcalib-v21-multidomain-500-qwen38-max/README.md`](releases/memcalib-v21-multidomain-500-qwen38-max/README.md)：`qwen3.8-max` 两套凭据的不可用预检，不含正式评测分数。

## 聚合复现

在已有完整本地运行产物时，使用项目指定的非 Conda Python：

```bash
PY=/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
RUN=evaluation/runs/memcalib-v21-multidomain-500-eight-models
REL=evaluation/releases/memcalib-v21-multidomain-500-eight-models

PYTHONPATH=. "$PY" evaluation/scripts/analyze_evaluation.py \
  --primary "$RUN/judgments/primary.valid.jsonl" \
  --secondary "$RUN/judgments/secondary.valid.jsonl" \
  --hidden "$REL/hidden-evaluation.jsonl" \
  --metrics "$REL/metrics.json" \
  --report "$REL/report.html"

PYTHONPATH=. "$PY" -m unittest discover -s tests/evalbench -p 'test_*.py'
```

分析器不重新调用模型。重新发起模型请求必须使用新的运行目录，不能覆盖既有审计。

## 历史归档

- `memcalib-v21-multidomain-500-seven-models/`：当前八模型结果所复用的未改动七模型基线；
- `memcalib-v2-multidomain-500-seven-models/`：v2.0 七模型 500 条历史结果；
- `memcalib-v2-multidomain-500-qwen35/`：v2.0 Qwen3.5-35B-A3B 增量审计；
- `memcalib-v2-multidomain-500-qwen3-8b/`：v2.0 Qwen3-8B 增量审计；
- `memcalib-ordered-v2.1-full-15526/`：v0.1 医学数据上的 15,526 条五模型全量评测；
- `memcalib-ordered-v2-500/`：早期 ordered-usage Judge 校准；
- `memcalib-ordered-v2.1-multidomain-pilot-200/`：100 general + 100 coding 跨领域试验；
- `memcalib-v0.1-500/`：最早 500 条五模型验证。

历史结果的数据版本、样本和评测口径不同。论文引用必须同时报告数据版本、样本 manifest、协议版本、回答模型快照和 Judge
配置，不得将历史结果与 v2.1 混为同一排行榜。
