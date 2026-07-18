# MemCalib evaluation

本目录保存 MemCalib 的锁定评测样本、配置、聚合指标、可视化报告和可复现分析工具。当前默认入口是 MemCalib v2.1 的 500 条七模型配对诊断；v2.0、v0.1、早期 Judge 校准和跨领域 pilot 均作为历史归档保留。

## 当前 v2.1 七模型诊断

从 SHA-256 为
`bd45f77534351cd096476080096ce9ba6250a375941a171ab561ad78704bed44`
的 15,000 条 v2.1 发布集中确定性抽取 500 条：

- health 250、general 125、coding 125；
- 按领域、来源、主题和原子数分层；
- 固定随机种子 `20260719`；
- 有序样本 ID 摘要
  `92292219c596e790720456754376354be30c5954bf7875085594fbce40c52d29`。

七个回答模型分别运行 full-memory 和 no-memory 条件，共形成 7,000
条配对回答。每个模型、每个条件均完整得到 500 条有效回答。回答模型只接收当前问题和非原子 `memory_blocks`，不接收隐藏原子标签、动作或 rubric。

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
| Qwen3-8B | 0.024 | 0.944 | 0.105 |

No-memory 使用同一批问题但不提供记忆块，因此不是独立排行榜。低 OPB
说明模型不会误用不存在的记忆，高 UPB 则说明 B/C 原子承载的信息无法被恢复。七个模型在 full-memory 下均显著降低 UPB。Qwen3-8B 的 OPB
较低但 UPB 明显较高，表现为更保守但对相关记忆利用不足。

该 500 条实验用于内部诊断和流程验证，不应表述为 15,000 条全量公开排行榜。

## Judge 配置与跨模型稳定性

- 主 Judge：`qwen3.7-plus`，覆盖全部 7,000 条回答；
- 复核 Judge `deepseek-v4-pro`：250 条分层回答；
- 复核 Judge `kimi-k2.6`：100 条分层回答；
- 复核抽样按回答模型、full/no-memory 条件、来源、主题和原子数分层；
- 所有调用均使用 temperature=0、thinking=false。

在 1,309 个双重判定原子上：

| 一致性口径 | Exact agreement | Kappa |
|---|---:|---:|
| 总体判定 | 0.898 | 0.864 |
| 有序使用等级 | 0.861 | 0.804（线性加权） |
| DeepSeek 复核 | 0.898 | 0.864 |
| Kimi 复核 | 0.899 | 0.863 |

主 Judge 的 7,000 条规范化判定和复核 Judge 的 350 条判定均覆盖完整，结构性 invalid 经定向重试后为 0。主 Judge 有 510
条、复核 Judge 有 31 条带辅助警告，主要是 Judge 给出的 evidence quote
未能逐字定位或 confidence 格式归一化；这些警告不等于缺少原子使用等级，完整计数保存在 `metrics.json` 和 judge-run manifest
中。模型间一致性支持当前自动评测的稳定性，但不能替代盲法人工专家标注。

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

- [`memcalib-v21-multidomain-500-seven-models/README.md`](releases/memcalib-v21-multidomain-500-seven-models/README.md)：本次运行摘要；
- [`memcalib-v21-multidomain-500-seven-models/report.html`](releases/memcalib-v21-multidomain-500-seven-models/report.html)：七模型 full/no-memory 可视化报告；
- [`memcalib-v21-multidomain-500-seven-models/metrics.json`](releases/memcalib-v21-multidomain-500-seven-models/metrics.json)：机器可读指标、混淆矩阵、置信区间和分层结果；
- [`memcalib-v21-multidomain-500-seven-models/release-manifest.json`](releases/memcalib-v21-multidomain-500-seven-models/release-manifest.json)：样本来源、分布和内容哈希。

## 聚合复现

在已有完整本地运行产物时，使用项目指定的非 Conda Python：

```bash
PY=/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
RUN=evaluation/runs/memcalib-v21-multidomain-500-seven-models
REL=evaluation/releases/memcalib-v21-multidomain-500-seven-models

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

- `memcalib-v2-multidomain-500-seven-models/`：v2.0 七模型 500 条历史结果；
- `memcalib-v2-multidomain-500-qwen35/`：v2.0 Qwen3.5-35B-A3B 增量审计；
- `memcalib-v2-multidomain-500-qwen3-8b/`：v2.0 Qwen3-8B 增量审计；
- `memcalib-ordered-v2.1-full-15526/`：v0.1 医学数据上的 15,526 条五模型全量评测；
- `memcalib-ordered-v2-500/`：早期 ordered-usage Judge 校准；
- `memcalib-ordered-v2.1-multidomain-pilot-200/`：100 general + 100 coding 跨领域试验；
- `memcalib-v0.1-500/`：最早 500 条五模型验证。

历史结果的数据版本、样本和评测口径不同。论文引用必须同时报告数据版本、样本 manifest、协议版本、回答模型快照和 Judge
配置，不得将历史结果与 v2.1 混为同一排行榜。
