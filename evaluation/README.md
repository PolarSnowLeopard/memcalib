# MemCalib evaluation

本目录保存 MemCalib 的锁定评测输入、配置、聚合指标、审查页面和可复现分析工具。默认入口是最终多领域 v2 数据上的 500 条六模型配对诊断；v0.1、早期 ordered-usage 校准和 200 条多领域试验均作为历史归档保留。

## 当前 v2 诊断

从最终 15,000 条发布数据中按正式领域比例和来源分布确定性抽取 500 条：health 250、general 125、coding 125。六个回答模型分别运行 full-memory 和 no-memory 条件，共形成 6,000 条配对回答。主 Judge 覆盖全部回答，复核 Judge 按模型分层复核 300 条。

回答模型只接收当前问题和非原子 `memory_blocks`。Judge 使用隐藏原子、A/B/C 规范使用等级、`memory_action` 和逐原子 rubric。A/B/C 表示影响强度；`ignore`、`apply`、`correct` 表示处置方向。错误、过时或不安全但相关的记忆可以是 B/C + `correct`，A 始终要求 `ignore`。

正式协议为 [`ordered-usage-v2.1`](../docs/evaluation_protocol_v2.1.md)。主指标使用 full-memory 条件：

- OPB：实际使用高于规范等级的宏平均错误率，越低越好；
- UPB：实际使用低于规范等级的宏平均错误率，越低越好；
- H：抵抗 OPB 与 UPB 能力的调和平均，越高越好；
- full/no-memory 配对差异：用于诊断记忆引入的过度使用和记忆缓解的使用不足。

| 模型 | OPB↓ | UPB↓ | H↑ |
|---|---:|---:|---:|
| Kimi-K2.6 | 0.317 | 0.207 | 0.734 |
| Qwen3.7-Max | 0.345 | 0.179 | 0.728 |
| DeepSeek-V4-Pro | 0.368 | 0.183 | 0.713 |
| Qwen3.6-Flash | 0.392 | 0.159 | 0.706 |
| DeepSeek-V4-Flash | 0.387 | 0.182 | 0.701 |
| Qwen3.5-35B-A3B | 0.404 | 0.154 | 0.699 |

复核的整体 exact agreement 为 0.936，Cohen kappa 为 0.915；有序使用等级 exact agreement 为 0.898，线性加权 kappa 为 0.868。该 500 条实验用于内部诊断和流程验证，不应表述为 15,000 条全量公开排行榜。

## Judge 配置与跨模型稳定性

- 主 Judge：`qwen3.7-plus`，覆盖全部 6,000 条回答；
- 复核 Judge `deepseek-v4-pro`：200 条分层回答、761 个原子；
- 复核 Judge `kimi-k2.6`：100 条分层回答、372 个原子；
- 生成参数：temperature=0、thinking=false；
- 分层维度：回答模型、full/no-memory 条件、来源、主题和原子数。

在 1,133 个双重判定原子上，总体 exact agreement 为 0.936、Cohen kappa 为 0.915；有序 A/B/C exact agreement 为 0.898、线性加权 kappa 为 0.868。按复核模型分别计算，DeepSeek 的 kappa 为 0.926，Kimi 的 kappa 为 0.893。因此当前稳定性不是同一模型的重复自评，而是 Qwen 主 Judge 与两个不同模型家族之间的一致性；它仍不能替代盲法人工专家标注。

## 中间结果与审计保留

每次运行在 `evaluation/runs/<run>/` 下保留以下中间结果：

| 路径 | 内容 |
|---|---|
| `requests/answers/` | full/no-memory 模型请求及输入指纹 |
| `answers/` | 模型原始回答、失败、重试、截断与完整性报告 |
| `requests/judges/` | 主 Judge 和复核 Judge 请求及抽样 ID |
| `api/` | Judge 原始 API 响应、失败与结构重试 |
| `judgments/` | 规范化逐原子有效判定、invalid 和合并结果 |
| `workflow.status` / `workflow.completed` | 阶段状态与完成时间 |

这些原始中间结果保存在本机，但 `evaluation/runs/` 被 Git 忽略，不推送远程仓库，也不进入协作者数据 ZIP。远程 `evaluation/releases/<release>/` 只保存锁定配置、输入/输出行数、SHA-256、运行 manifest、聚合 `metrics.json` 和 `report.html`。因此远程材料可以审计结果口径和完整性；若要在另一台机器上重新聚合逐条结果，仍需单独传输对应的 `evaluation/runs/`，并确保不包含任何凭据。

## 当前结果入口

- [`memcalib-v2-multidomain-500-six-models/report.html`](releases/memcalib-v2-multidomain-500-six-models/report.html)：六模型可视化报告；
- [`memcalib-v2-multidomain-500-six-models/metrics.json`](releases/memcalib-v2-multidomain-500-six-models/metrics.json)：机器可读指标、混淆矩阵、置信区间和分层结果；
- [`memcalib-v2-multidomain-500-qwen35/README.md`](releases/memcalib-v2-multidomain-500-qwen35/README.md)：Qwen3.5-35B-A3B 增量运行、完整性与审计说明；
- [`memcalib-v2-multidomain-500-qwen35/`](releases/memcalib-v2-multidomain-500-qwen35/)：该模型的锁定输入映射、指标和 manifest。

发布目录只保存核对聚合结果所需的锁定输入映射、manifest、指标和报告；凭据不写入配置、脚本或清单。

## 聚合复现

在已有完整本地运行产物时，使用项目指定的非 Conda Python：

```bash
PY=/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
PYTHONPATH=. "$PY" evaluation/scripts/analyze_evaluation.py \
  --config evaluation/configs/memcalib-v2-multidomain-500-qwen35.json
PYTHONPATH=. "$PY" -m unittest discover -s tests/evalbench -p 'test_*.py'
```

分析器以锁定 manifest 和归一化 Judge 结果为输入，不重新调用模型。重新发起模型请求必须使用新的运行目录，不能覆盖既有审计。

## 历史归档

- `memcalib-ordered-v2.1-full-15526/`：v0.1 医学数据上的 15,526 条五模型全量评测；
- `memcalib-ordered-v2-500/`：早期 ordered-usage Judge 校准与人工审查材料；
- `memcalib-ordered-v2.1-multidomain-pilot-200/`：100 general + 100 coding 的跨领域试验；
- `memcalib-v0.1-500/`：最早 500 条五模型验证。

这些归档的样本、数据版本和评测口径与最终 v2 不同。论文引用时必须同时报告数据版本、样本 manifest、评测协议版本和模型快照，不能将历史结果与当前六模型结果混为同一排行榜。
