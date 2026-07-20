# MemCalib

**评测对话语言模型应当何时以及如何使用记忆。**

MemCalib 用于评测模型在回答新问题时，能否恰当地调节检索记忆或存储记忆对回答的影响。模型接收符合真实记忆系统形态的非原子记忆块；评测端使用隐藏的原子级标注，判断各项信息应被抑制、仅作为有限支持，还是作为控制回答的关键约束。

## 当前版本

MemCalib v2.2 是当前供论文合作者内部审阅和训练使用的多领域版本。最终发布集包含 15,000 条英文记录，严格按照 health、general、coding 三个领域的预定配额选取；其中 14,973 条为 strict pass，27 条为不改变标签或答案足迹边界的 non-blocking review，reject 和 invalid 均未进入发布集。

v2.2 将每条记录的模型可见记忆扩展为 3–20 块的长尾分布：82.0% 的记录包含 3–6 块，15.01% 包含 7–10 块，2.99% 包含 11–20 块。对包含 K 个可见块的任一记录，恰有 `ceil(K/2)` 个块可拆成多个独立评分原子，因此不是只在全局平均上满足“至少一半可拆解”。每个领域采用相同比例的块数分布，避免领域与上下文负载混杂。canonical Hard A 仍保持独立单原子块，按五种失败机制构造，每类恰好 3,000 条。

| 统计项 | 数量 |
|---|---:|
| 样本 | 15,000 |
| health / general / coding | 7,500 / 3,750 / 3,750 |
| 每条模型可见记忆块 | 3–20（均值 4.9867，中位数 4） |
| 模型可见记忆块 | 74,800 |
| 多原子可见块 | 41,700（55.75%） |
| 隐藏原子记忆 | 118,819 |
| A / B / C 原子记忆 | 82,171 / 19,032 / 17,616 |
| strict / review / reject / invalid | 14,973 / 27 / 0 / 0 |
| 五类 Hard A | 各 3,000 |
| 数据源 | 8 |
| 完整署名的 Stack Exchange 记录 | 805 |

## 能力定义

- **A - suppress（抑制）：** 该记忆不应影响当前回答，对应 `ignore` 动作。
- **B - bound（有限使用）：** 该记忆与问题相关，但只能作为有限支持，不能不受约束地控制回答。
- **C - control（控制）：** 该记忆必须实质性地约束回答内容或主要建议。

A/B/C 描述的是记忆对当前回答的**使用强度**，并不直接等同于“错误/正确”。错误、过时或不安全但仍与问题相关的记忆通过独立的 `memory_action=correct` 标记，可能属于 B 或 C；A 原子只允许 `ignore`，禁止 `A+correct`。模型输入中呈现的是 `memory_blocks`，评测使用隐藏的 `memories` 数组及原子级 rubric，因此可以分别测量“不该用却用了”的 OPB 和“该用却没用”的 UPB。

## 研究定位

[StratMem-Bench](https://arxiv.org/abs/2604.26243) 在 657 个虚拟角色场景中独立评测了必要记忆、支持性记忆和无关记忆。MemCalib 不将这种三分类相关性划分本身作为创新点。其主要贡献包括：面向模型输入记忆块、面向评测使用原子标注的协议；符合真实系统形态的非原子记忆；用于判定记忆使用不足与过度使用的原子级 rubric；以及规模更大且可复现的数据构建流程。

## 五分钟快速审阅

v2.2 审阅入口：

- [v2.2 15,000 条数据交付说明](docs/MEMCALIB_V22_COAUTHOR_HANDOFF.md)
- [v2.2 数据结构与长尾约束](docs/benchmark-schema-v2.2.md)
- [v2.2 长尾修订与质检报告](docs/reports/memcalib-v22-longtail-revision.html)
- [v2.1 基础集完整构建与质检方法报告](docs/reports/memcalib-v21-dataset-construction-methodology.html)
- [v2.1 思考模式八模型同样本评测](evaluation/releases/memcalib-v21-multidomain-500-thinking-eight-models/)
- [v2.1 八模型同样本抽样评测](evaluation/releases/memcalib-v21-multidomain-500-eight-models/)
- [v2.0 历史七模型抽样评测报告](evaluation/releases/memcalib-v2-multidomain-500-seven-models/report.html)
- [Qwen3.5-35B-A3B 增量评测审计](evaluation/releases/memcalib-v2-multidomain-500-qwen35/README.md)
- [Qwen3-8B 增量评测报告](evaluation/releases/memcalib-v2-multidomain-500-qwen3-8b/report.html)

以下命令用于验证历史 v0.1 仓库内发布包。使用当前工作区指定的非 Conda Python 运行时，或任意带有标准库的 Python 3.11 及以上版本：

```bash
PY=/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3

$PY tools/verify_release.py --release-dir release/memcalib-v0.1
```

验证脚本会检查发布包中每个文件的哈希，按顺序重建两个压缩分片，解析全部记录，检查 ID 唯一性，重新计算 benchmark 统计量，并验证锁定的源文件 SHA-256。

如需重建未压缩的 JSONL 文件：

```bash
gzip -cd \
  release/memcalib-v0.1/data/memcalib-v0.1-00000-of-00002.jsonl.gz \
  release/memcalib-v0.1/data/memcalib-v0.1-00001-of-00002.jsonl.gz \
  > memcalib-v0.1.jsonl

shasum -a 256 memcalib-v0.1.jsonl
# 1cfd0334255266e6b8d4c234c615ade42b40c91bb86cb7c061a285261c363cb4
```

审阅入口：

- [发布包说明](release/memcalib-v0.1/README.md)
- [100 条样本审阅页面](release/memcalib-v0.1/review/memcalib-v0.1-audit-100.html)
- [完整统计分析报告](release/memcalib-v0.1/reports/memcalib-v0.1-statistics.html)
- [数据卡](DATA_CARD.md)
- [v2.2 Benchmark 数据结构](docs/benchmark-schema-v2.2.md)
- [v2.1 历史 Benchmark 数据结构](docs/benchmark-schema.md)
- [数据构建流程](docs/construction-pipeline.md)

## 仓库结构

```text
pipeline/                 可复现的数据构建阶段与提示词
release/memcalib-v0.1/   已锁定的内部审阅数据版本
evaluation/releases/     评测发布包、指标、manifest 与 HTML 报告
tools/                    确定性发布包构建与验证工具
tests/                    流水线与发布工具测试
docs/                     数据结构、方法、数据来源与归档设计文档
```

大体积源数据、API 请求与响应、运行日志和构建中间产物保存在本地 `pipeline/data/` 目录中，不纳入 Git 版本控制。

## 构建与评测进展

v2.2 继承 v2.1 锁定的 15,000 条来源谱系、问题、真实原子、A/B/C 标签与 canonical Hard A，不重新抽样基础记录。在此基础上，按领域内相同比例分配 3–20 块长尾负载，重新组合真实原子，并添加同用户、跨场景、零答案足迹的辅助 A 记忆。每条记录先通过确定性结构门，再由独立模型逐原子、逐块和全局检查；失败项只做定向重试或带前后哈希的局部修复。v2.1 的完整基础构建见[基础集方法报告](docs/reports/memcalib-v21-dataset-construction-methodology.html)，v2.2 的增量流程与精确统计见[长尾修订报告](docs/reports/memcalib-v22-longtail-revision.html)。

v2.1 模型比较从最终 15,000 条数据中按正式领域比例、来源、主题和原子数确定性抽取 500 条样本，其中 health 250、general 125、coding 125。八个模型分别运行 full-memory 与 no-memory 两个配对条件，共 8,000 条回答；主 Judge 评审全部回答，复核 Judge 对 400 条分层样本进行跨模型家族复核。每个模型在每个条件下均得到 500 条有效回答。Codex 使用 `gpt-5.6-sol`、`reasoning_effort=none`，每个回答采用独立临时会话、空工作区和只读沙箱；1,000 条回答均无 reasoning token、工具调用或截断。

协议采用 `ordered-usage-v2.1`，以 OPB 错误率、UPB 错误率及两个方向抵抗能力的调和平均 H 作为主指标。以下为当前 v2.1 抽样结果：

**Full-memory 主结果**

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

**No-memory 对照结果**

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

No-memory 是同一批问题在不提供记忆块时的反事实基线，不是独立排行榜。各模型几乎不会过度使用不存在的记忆，因此 OPB 很低；但无法获得 B/C 原子承载的必要信息，因此 UPB 普遍超过 0.90。八个模型在 full-memory 下均显著降低 UPB。Qwen3-8B 的 OPB 较低但 UPB 达到 0.452，表现为更保守、同时对相关记忆利用不足。

八模型在 full-memory 下的宏平均 H 从 0.633 到 0.745，显示模型间存在稳定的“利用相关记忆”和“拒绝不该使用的记忆”权衡。Codex 与 Kimi 的 bootstrap 区间高度重叠；宏平均 H 下 Codex 高 0.0026，而按合作者提出的微平均方向错误定义，Kimi 的 H=0.751、Codex=0.748，次序反转。因此只能报告二者总体接近、偏差方向不同，不能宣称 Codex 显著领先。当前结果属于 500 条内部诊断，不应解释为 15,000 条全量公开 leaderboard，人工验证仍待扩展。

### 思考模式八模型重评

同一批 500 条锁定样本上，七个百炼模型全部开启 thinking 重新评测，并新增 GLM-5.2；Codex 不在本轮重跑范围。8 个模型、full/no-memory 两个条件共 8,000 条回答全部完成，均有非空 reasoning、唯一请求 ID 和 `finish_reason=stop`。Judge 配置保持不变且关闭 thinking，以隔离回答侧 thinking 的影响。

| 模型 | Full-memory OPB↓ | Full-memory UPB↓ | Full-memory H↑ |
|---|---:|---:|---:|
| Kimi-K2.6 | 0.307 | 0.207 | 0.740 |
| Qwen3.5-35B-A3B | 0.347 | 0.181 | 0.727 |
| GLM-5.2 | 0.372 | 0.156 | 0.720 |
| DeepSeek-V4-Pro | 0.402 | 0.137 | 0.707 |
| Qwen3.6-Flash | 0.384 | 0.189 | 0.700 |
| DeepSeek-V4-Flash | 0.384 | 0.193 | 0.699 |
| Qwen3.7-Max | 0.432 | 0.127 | 0.689 |
| Qwen3-8B | 0.304 | 0.339 | 0.678 |

七个共享模型相对非思考基线的 H 变化范围为 -0.007 到 +0.045，说明 thinking 不产生统一增益，更多表现为 OPB/UPB 偏差方向的重新平衡。复核 Judge 在 1,493 个原子上的总体 exact agreement=0.914、κ=0.886。GLM-5.2 有 2 条 no-memory 请求使用供应商支持的受限 thinking budget 完成，已单列审计。Qwen3-4B 对当前两套凭据均没有可用在线推理端点，因此没有静默替换，也未加入结果表。完整结果、no-memory 对照、思考前后差值和中间结果保存边界见[思考模式八模型说明](evaluation/releases/memcalib-v21-multidomain-500-thinking-eight-models/README.md)及[可视化报告](evaluation/releases/memcalib-v21-multidomain-500-thinking-eight-models/report.html)。

### 候选综合指标与尾部风险诊断

为检查 H 的数值区分度和排序稳健性，同一批 500 条样本、8 个模型和 8,000 条主 Judge 结果还计算了 MinCalib、算术/几何/乘积及 soft-min 综合分、balanced accuracy、macro F1、MCC、Kappa、NMI、有序距离与严重错误、样本级 CVaR、配对胜率、Bradley–Terry、双维 Rasch 及 PMU 权重敏感性。正式 H 定义没有因此改变；这些候选指标用于揭示不同聚合口径下的排序变化，而不是事后选择最有利的排行榜。

CVaR90 先在每条 full-memory 样本内计算归一化有序误差，再对误差最高的 10% 样本取平均，因此衡量的是尾部失败，不是总体平均表现。它与 H 使用不同的聚合单位和评估子集，模型次序不完全一致是预期现象。完整公式、置信区间和解释边界见[候选指标研究](evaluation/analyses/memcalib-v21-multidomain-500-candidate-metrics/README.md)；[尾部、Pareto 与名次诊断图](evaluation/analyses/memcalib-v21-multidomain-500-candidate-metrics/candidate-metric-diagnostics.html)可直接在浏览器中打开。

### Judge 配置与稳定性

全部 8,000 条回答由 `qwen3.7-plus` 按 `ordered-usage-v2.1` 协议进行主评审，temperature 为 0 且关闭 thinking。另有 400 条回答按回答模型、full/no-memory 条件、来源、主题和原子数分层抽取，交给不同模型家族独立复核：`deepseek-v4-pro` 复核 300 条回答，`kimi-k2.6` 复核 100 条回答。

相对主 Judge，1,494 个复核原子的总体 exact agreement 为 0.902、Cohen κ 为 0.868；有序 A/B/C 等级 exact agreement 为 0.865、线性加权 κ 为 0.808。DeepSeek 与 Kimi 复核分别得到 κ=0.869 和 κ=0.863。主 Judge 的 8,000 条和复核 Judge 的 400 条结构化判定均覆盖完整，残余 invalid 为 0。该结果支持模型间判定稳定性，但不替代盲法人工专家验证。

`qwen3.8-max` 在 2026-07-20 使用两套百炼凭据做了关闭 thinking 的[可用性预检](evaluation/releases/memcalib-v21-multidomain-500-qwen38-max/README.md)，两套凭据均返回 HTTP 404 `model_not_found`；百炼公开模型目录当时也未列出该模型 ID。因此没有发起 500 条正式评测，也没有将其加入结果表。

### 中间结果与保存边界

模型请求、模型原始回答、Judge 请求、Judge 原始 API 输出、规范化逐原子判定，以及失败、重试和日志均保存在本地 `evaluation/runs/<run>/`。其中 `requests/answers/` 保存回答请求，`answers/` 保存模型回答，`requests/judges/` 保存 Judge 请求，`api/` 保存原始 Judge 输出，`judgments/` 保存结构化后的有效/无效判定。

`evaluation/runs/` 被 Git 忽略，也不进入协作者数据 ZIP。远程仓库的 `evaluation/releases/<release>/` 保存锁定输入映射、行数和 SHA-256 manifest、聚合指标与 HTML 报告，使结果可核对但不分发大体积原始响应。如需异机复算或长期归档，必须单独备份对应 `evaluation/runs/` 目录，并继续排除 API Key。

实验说明见 [evaluation/README.md](evaluation/README.md)，正式协议见 [v2.1 评测协议](docs/evaluation_protocol_v2.1.md)。当前 v2.1 的完整混淆矩阵、置信区间和领域结果见 [v2.1 八模型报告](evaluation/releases/memcalib-v21-multidomain-500-eight-models/report.html)；Codex 的单模型控制与审计见 [Codex 评测说明](evaluation/releases/memcalib-v21-multidomain-500-codex/README.md)。v2.0 历史结果保留在[旧版七模型报告](evaluation/releases/memcalib-v2-multidomain-500-seven-models/report.html)中。历史 v0.1 的 15,526 条全量评测仍保留在[原全量报告](evaluation/releases/memcalib-ordered-v2.1-full-15526/report.html)中。

## 发布与许可状态

本仓库仅用于论文合作者内部研究审阅。v2.2 沿用 v2.1 的 8 个来源；每条记录保存来源、split、license 和可用的署名元数据。医学来源中的 `lavita/ChatDoctor-HealthCareMagic-100k` 数据卡未注明许可证，因此 7,500 条 health 数据当前仍记为 license unknown。Stack Exchange 入选记录均完成 CC-BY-SA-4.0 署名补全。完整数据尚不具备公开再分发条件，公开发布前仍需完成权利、PII 和敏感内容审查。

数据来源署名与权利状态详见 [NOTICE.md](NOTICE.md)。当前内部审阅版本未对仓库整体授予代码或数据许可证。
