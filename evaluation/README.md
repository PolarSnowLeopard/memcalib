# MemCalib 评测实验

本目录保存 MemCalib v0.1 的确定性评测协议、提示词、运行脚本和聚合结果。首轮验证从正式数据中锁定 500 条样本，其中 Representative panel 350 条，Diagnostic panel 150 条。所有样本永久留出，不进入训练集。

## 实验设计

- 五个回答模型：Qwen3.7-Max、Qwen3.6-Flash、DeepSeek-V4-Pro、DeepSeek-V4-Flash、Kimi-K2.6。
- 每个模型分别运行 `full_memory` 与 `no_memory` 条件，共生成 5,000 条回答。
- 主 Judge 为 Qwen3.7-Plus，对全部回答评分。
- 复核 Judge 为 DeepSeek-V4-Pro 和 Kimi-K2.6，对 1,000 条分层回答独立评分。
- 人工复核包包含 60 条预先随机抽样和 40 条诊断性抽样。

模型接收非原子 `memory_blocks`。Judge 使用隐藏的原子记忆、A/B/C 标签和逐原子 rubric，分别判断应抑制的信息、可有限使用的信息以及控制回答的信息。

当前评测协议采用有序使用等级 v2。主指标为 Full-memory 条件下的 OPB 错误率、UPB 错误率及二者抵抗能力的调和平均。No-memory 条件作为反事实诊断，用于估计记忆诱发的 OPB 和记忆减少的 UPB。完整定义见 [有序记忆使用评测协议](../docs/evaluation_protocol_v2.md)。

## 当前结论

按 v2 指标向后计算，五个模型的 OPB 错误率为 0.215 至 0.277，UPB 错误率为 0.187 至 0.245，调和总分为 0.753 至 0.770。模型呈现出不同的方向性权衡：部分模型更容易过度结合记忆，另一些模型更容易忽略必要记忆。五个模型在加入记忆后均显著降低 UPB，同时也产生额外 OPB。

双 Judge 在 5,062 个 v1 原子 verdict 上的 exact agreement 为 0.876，Cohen κ 为 0.840。现有模型回答无需重跑，但 v1 Judge 没有输出精确的预测使用等级，因此当前 OPB/UPB 可以作为上、下三角聚合基线，无法恢复完整 3×3 混淆矩阵。正式 v2 结果需要使用 ordered-usage-v2 Judge 对现有回答重新评分。100 条人工复核完成前，不将该结果表述为最终有效性结论。

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

## v2 Judge 重评

现有 5,000 条模型回答可以直接复用。生成 v2 Judge 请求时必须使用独立运行目录，避免覆盖 v1 审计记录：

```bash
PYTHONPATH=. python3 evaluation/scripts/prepare_judge_requests.py \
  --config evaluation/configs/memcalib-ordered-v2-500.json \
  --answers evaluation/runs/memcalib-v0.1-500/answers \
  --output-dir evaluation/runs/memcalib-ordered-v2-500/requests/judges \
  --manifest evaluation/releases/memcalib-ordered-v2-500/judge-request.manifest.json
```

该命令仅生成请求，不调用 API。正式重评应把主 Judge、复核 Judge、归一化结果、指标和人工复核包全部写入 `memcalib-ordered-v2-500` 对应目录。

## v2 校准状态

ordered-usage-v2 已在 100 条配对回答上完成双 Judge 校准。主 Judge 和复核 Judge 均覆盖 516 个原子，全部原子可以构造完整混淆矩阵。有序等级 exact agreement 为 0.851，线性加权 Cohen κ 为 0.788，`scorable` 一致率为 1.000，整体自动门槛通过。

按回答模型切片后，DeepSeek-V4-Flash 的 exact agreement 为 0.796、线性加权 κ 为 0.679，低于校准阈值，已标记为人工复核重点。主 Judge 的 contradiction 标记率为 3.88%，复核 Judge 为 0.78%，同样需要检查正例口径。正式 5,000+1,000 条 v2 重评应在 30 条人工校准复核完成后启动。

- `releases/memcalib-ordered-v2-500/calibration-summary.json`：自动校准结果与分层一致性。
- `releases/memcalib-ordered-v2-500/calibration-human-review-30.html`：逐条人工校准复核页面。页面以英文原文为正式依据，并提供完整中文辅助译文；每条回答按原子记忆独立填写实际 A/B/C 使用强度，再给出整条审查结论。
- `releases/memcalib-ordered-v2-500/calibration-human-review-30.translations-zh.jsonl`：30 条校准样本的逐字段中文辅助译文，不参与正式指标计算。

## v2.1 Judge 协议

`ordered-usage-v2.1` 明确将纠正、反驳和警告视为可能的记忆使用，并按其影响范围区分 B 与 C；同时将事实冲突和约束违反拆成两个辅助字段。旧 v2 配置、提示词和结果继续保留以支持复现。完整定义见 [v2.1 评测协议](../docs/evaluation_protocol_v2.1.md)。

## v2.1 全量正式评测

正式评测集由 15,528 条英文构建结果经过父记忆规范化和问题精确去重得到，共保留 15,526 条样本、56,031 条模型可见记忆和 78,726 条隐藏原子标注。每个回答模型在 `full_memory` 条件下覆盖全部样本，共生成 77,630 条正式回答。500 条配对集继续用于 Full/No-memory 反事实协议验证，不与全量排行榜口径混合。

主 Judge 对全部 77,630 条回答进行评审；复核集按回答模型、来源数据集、主题和原子数分层抽取，每模型 500 条，共 2,500 条。复核子集上的有序等级 exact agreement 为 0.814，线性加权 Cohen κ 为 0.752。完整结果位于：

- `releases/memcalib-v0.1-full-15526/`：锁定的数据清单、样本 ID 和确定性 gzip 发布包；
- `releases/memcalib-ordered-v2.1-full-15526/metrics.json`：原子级混淆矩阵、OPB、UPB、H、2,000 次样本聚类 bootstrap 置信区间和 Judge 一致性；
- `releases/memcalib-ordered-v2.1-full-15526/report.html`：中文可视化报告；
- `configs/memcalib-ordered-v2.1-full-15526.json`：模型、条件、Judge 和复核抽样配置。

当前有效性状态为 `provisionally_supported_with_caveat`。五模型 H 分数跨度为 0.0275，单一总分区分度有限；标签正确率最大跨度为 0.124，OPB 与 UPB 的模型排序也明显不同。后续论文实验应同时报告 H、OPB、UPB、完整混淆矩阵和置信区间，并补充人工 Judge 验证。

## 多领域试点评测

`memcalib-ordered-v2.1-multidomain-pilot-200` 用于检验同一套原子记忆标注与有序使用评测协议能否迁移到通用对话和 Coding 场景。该内部诊断集固定包含 100 条通用对话样本和 100 条 Coding 样本。五个回答模型均运行 `full_memory` 与 `no_memory` 条件，共 2,000 条回答；主 Judge 评审全部回答，两个复核 Judge 按模型、条件、领域、主题和原子数分层复核 500 条回答。

完整流程包含回答生成、缺失与截断重试、Judge 结构化输出修复、原子级 OPB/UPB/H 聚合和 HTML 报告生成。使用非 Conda Python 启动：

```bash
PYTHON_BIN=/path/to/python3 \
  zsh evaluation/scripts/run_multidomain_pilot_200.sh
```

锁定输入位于 `releases/memcalib-ordered-v2.1-multidomain-pilot-200/`，API 原始输出和日志位于被 Git 忽略的 `runs/memcalib-ordered-v2.1-multidomain-pilot-200/`。该试验用于协议和数据质量诊断，不替代正式排行榜结果。
