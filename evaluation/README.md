# MemCalib 评测实验

本目录保存 MemCalib v0.1 的确定性评测协议、提示词、运行脚本和聚合结果。首轮验证从正式数据中锁定 500 条样本，其中 Representative panel 350 条，Diagnostic panel 150 条。所有样本永久留出，不进入训练集。

## 实验设计

- 五个回答模型：Qwen3.7-Max、Qwen3.6-Flash、DeepSeek-V4-Pro、DeepSeek-V4-Flash、Kimi-K2.6。
- 每个模型分别运行 `full_memory` 与 `no_memory` 条件，共生成 5,000 条回答。
- 主 Judge 为 Qwen3.7-Plus，对全部回答评分。
- 复核 Judge 为 DeepSeek-V4-Pro 和 Kimi-K2.6，对 1,000 条分层回答独立评分。
- 人工复核包包含 60 条预先随机抽样和 40 条诊断性抽样。

模型接收非原子 `memory_blocks`。Judge 使用隐藏的原子记忆、A/B/C 标签和逐原子 rubric，分别判断应抑制的信息、可有限使用的信息以及控制回答的信息。

## 当前结论

五个模型的 Full-memory 宏平均分为 0.662 至 0.689，单一总分的模型区分度有限。A/B/C 标签级最大分差为 0.107，能够揭示不同的记忆使用能力结构。五个模型在 B、C 标签上均获得正向配对增益，同时均出现明显的 A 类污染效应。

双 Judge 在 5,062 个原子判定上的 exact agreement 为 0.876，Cohen κ 为 0.840。自动检查因此给出“初步支持（有限制）”：benchmark 能稳定诊断记忆使用不足与过度使用，但不应仅依赖一个总分排列当前强模型。100 条人工复核完成前，不将该结果表述为最终有效性结论。

## 关键文件

- `configs/memcalib-v0.1-500.json`：锁定的实验配置。
- `releases/memcalib-v0.1-500/model-facing.jsonl`：模型可见评测输入。
- `releases/memcalib-v0.1-500/hidden-evaluation.jsonl`：隐藏原子标注与 rubric。
- `releases/memcalib-v0.1-500/metrics.json`：完整聚合指标。
- `releases/memcalib-v0.1-500/report.html`：中文可视化结果报告。
- `releases/memcalib-v0.1-500/human-review-100.html`：逐条人工复核页面，支持方向键翻页与导出标注。
- `releases/memcalib-v0.1-500/*.manifest.json`：选择、请求、回答运行与 Judge 运行清单。

API 请求、模型原始回答、Judge 原始输出和日志位于本地 `evaluation/runs/`，默认不提交 Git。发布目录中的清单记录其数量、哈希和归一化过程。

## 复现聚合分析

请使用系统 Python 或项目指定的独立 Python 运行时，避免依赖 Conda：

```bash
PYTHONPATH=. python3 evaluation/scripts/finalize_answer_run.py
PYTHONPATH=. python3 evaluation/scripts/finalize_judge_run.py
PYTHONPATH=. python3 evaluation/scripts/analyze_evaluation.py
PYTHONPATH=. python3 evaluation/scripts/build_human_review.py
```

上述命令需要本地 `evaluation/runs/` 中已有完整 API 输出。重新发起 API 请求时，密钥通过被 Git 忽略的 `.env.local` 注入，不写入配置、脚本或运行清单。
