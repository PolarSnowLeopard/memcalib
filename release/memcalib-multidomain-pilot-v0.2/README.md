# MemCalib 多领域试验集 v0.2

本目录用于内部研究审阅，验证既有 MemCalib 构建流程能否从医学问答扩展到通用对话与 coding 场景。当前版本包含通用对话 100 条、coding 100 条，尚未并入正式 benchmark，也不用于报告最终模型结果。

## 数据来源

| 领域 | 数据源 | 许可证 | 试验集数量 |
|---|---|---|---:|
| 通用对话 | OpenAssistant OASST1 | Apache-2.0 | 100 |
| Coding | Magicoder OSS-Instruct 75K | MIT（数据卡声明） | 100 |

构建流程依次执行源数据规范化、确定性质量过滤、近重复去除、主题与难度分层采样、LLM 语义质检、strict-only 准入、英文非原子记忆构造、隐藏原子拆分与 A/B/C 标注、rubric 生成、连续证据子串校验和定向修复。题面中直接包含完整参考解法的 coding 样本被排除。

## 审阅入口

- [通用对话分层审查队列（35 条）](review/general-review-queue-35.html)
- [Coding 分层审查队列（50 条）](review/coding-review-queue-50.html)
- [通用对话 100 条审阅页](review/general-audit-100.html)
- [Coding 100 条审阅页](review/coding-audit-100.html)
- [分层审查队列清单](metadata/review-queue-manifest.json)
- [最终机器验证结果](metadata/validation.json)
- [发布文件哈希](release-manifest.json)

优先审阅两份分层队列。页面按“一页一个样本”展示，使用 `←/→` 或 `K/J` 切换样本。每条样本同时展示入队依据、原始问题、去背景化后的当前问题、模型可见的非原子记忆块、隐藏原子记忆、A/B/C 标签与完整 judge rubric。选择结果会自动保存在当前浏览器，并可通过“导出 JSON”生成结构化标注文件。

## 试验结果

| 统计项 | 通用对话 | Coding |
|---|---:|---:|
| 最终样本 | 100 | 100 |
| 原子记忆 | 393 | 372 |
| A / B / C | 131 / 130 / 132 | 109 / 53 / 210 |
| 父记忆块 | 316 | 344 |
| 非原子父记忆块 | 71（22.5%） | 28（8.1%） |
| 含非原子父记忆的样本 | 55 | 23 |
| 经过定向证据修复的样本 | 12 | 52 |
| 最终结构/证据验证错误 | 0 | 0 |

Coding 的 B 标签比例、非原子父记忆比例与混合标签父记忆比例均明显低于通用对话。这可能反映 coding 任务中接口契约和实现约束通常具有控制性，也说明当前单一 coding 指令数据源的任务形态偏窄。该分布应作为扩大数据源前的重点审查项；后续需要补充带真实仓库、issue、测试与多轮修改上下文的 coding 数据。

## 文件说明

- `data/*-hidden-construction-100.jsonl`：内部构造审计数据，包含参考答案、隐藏原子标签和 rubric，不可直接作为模型输入发布。
- `review/*.html`：人工质量审阅页面。
- `review/*-review-queue-*.jsonl`：分层人工审查队列及其入队信号。
- `review/*-review-queue-*.csv`：可离线填写或复核的 parent-memory 级标注表。
- `metadata/*-source-selection.json`：确定性筛选、去重和分层采样统计。
- `metadata/*-semantic-qc.json`：语义质检及重试后的分布。
- `metadata/*-admission.json`：strict-only 自适应准入记录。
- `metadata/*-construction-summary.json`：最终构造统计。
- `metadata/validation.json`：样本数、唯一 ID、许可证、结构、证据 grounding 和参考答案重合审计结果。
- `metadata/review-queue-manifest.json`：分层审查规则、随机种子、覆盖分布及输出哈希。

## 当前限制

该版本每个新领域仅使用一个数据源。通用对话中的复杂样本数量有限；coding 数据主要由合成指令构成，真实仓库上下文、跨文件依赖和测试执行尚未覆盖。参考答案只用于源任务质量核验，但隐藏构造文件仍保留参考答案以便审计，因此公开发布前需要生成不含答案与隐藏标签的 model-facing 分片。
