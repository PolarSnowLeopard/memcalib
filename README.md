# MemCalib

**评测对话语言模型应当何时以及如何使用记忆。**

MemCalib 用于评测模型在回答新问题时，能否恰当地调节检索记忆或存储记忆对回答的影响。模型接收符合真实记忆系统形态的非原子记忆块；评测端使用隐藏的原子级标注，判断各项信息应被抑制、仅作为有限支持，还是作为控制回答的关键约束。

## 当前版本

MemCalib v2.3 是当前供论文合作者内部审阅和训练使用的多领域版本。最终发布集包含 15,000 条英文记录，严格按照 health、general、coding 三个领域的预定配额选取；其中 13,923 条为 strict pass，1,077 条为没有硬失败的 review，reject 和 invalid 均未进入发布集。

v2.3 在 v2.2 的 3–20 个模型可见记忆块长尾基础上，进一步把每个块扩展到 1–20 个隐藏原子，并把多原子块统一改写为不显示原子边界的自然段落。全量数据分为三档难度：level 1 / 2 / 3 分别为 3,751 / 7,500 / 3,749 条，并在每个领域内按 25% / 50% / 25% 近似精确分配。canonical Hard A 继续保持独立单原子块；v2.2 的问题、来源、真实原子、A/B/C 标签和动作全部锁定，v2.3 只增加零答案足迹的 `A+ignore` 辅助原子。

| 统计项 | 数量 |
|---|---:|
| 样本 | 15,000 |
| health / general / coding | 7,500 / 3,750 / 3,750 |
| 每条模型可见记忆块 | 3–20（均值 4.9867，中位数 4） |
| 模型可见记忆块 | 74,800 |
| 多原子可见块 | 59,800（79.95%） |
| 至少 3 个原子的可见块 | 48,548（64.90%） |
| 隐藏原子记忆 | 234,221 |
| 每条记录隐藏原子 | 6–63（均值 15.6147，中位数 14） |
| A / B / C 原子记忆 | 197,573 / 19,032 / 17,616 |
| strict / review / reject / invalid | 13,923 / 1,077 / 0 / 0 |
| level 1 / 2 / 3 | 3,751 / 7,500 / 3,749 |
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

v2.3 审阅入口：

- [v2.3 15,000 条数据交付说明](docs/MEMCALIB_V23_COAUTHOR_HANDOFF.md)
- [v2.3 数据结构、三档难度与原子长尾约束](docs/benchmark-schema-v2.3.md)
- [v2.3 完整构建与质检流程报告](docs/reports/memcalib-v23-composite-block-revision.html)
- [v2.3 最终集机器可读统计](pipeline/data/multidomain/full-v2/revision-composite-blocks-v23/release/memcalib_v23_multidomain_benchmark_15000.statistics.json)
- [v2.3 30 条分层人工审阅样例](docs/samples/memcalib-v23-review-sample-30.README.md)
- [v2.3 九模型思考模式评测](evaluation/releases/memcalib-v23-multidomain-500-nine-models/)
- [v2.3 九模型非思考对照](evaluation/releases/memcalib-v23-multidomain-500-nonthinking-nine-models/)
- [v2.3 思考/非思考同样本比较](evaluation/analyses/memcalib-v23-thinking-vs-nonthinking/)
- [v2.3 三层样本级指标完整汇总](evaluation/analyses/memcalib-v23-three-layer-metrics/README.md)
- [v2.3 SFT 数据拆分与 500 条目标生成 pilot](sft/README.md)
- [v2.3 Qwen3.5-35B-A3B Base/SFT 严格配对评测](evaluation/releases/memcalib-v23-sft-base-full-only-paired/README.md)
- [v2.2 历史长尾块交付说明](docs/MEMCALIB_V22_COAUTHOR_HANDOFF.md)
- [v2.2 历史数据结构与块数长尾约束](docs/benchmark-schema-v2.2.md)
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
- [v2.3 Benchmark 数据结构](docs/benchmark-schema-v2.3.md)
- [v2.2 历史 Benchmark 数据结构](docs/benchmark-schema-v2.2.md)
- [v2.1 历史 Benchmark 数据结构](docs/benchmark-schema.md)
- [数据构建流程](docs/construction-pipeline.md)

## 仓库结构

```text
pipeline/                 可复现的数据构建阶段与提示词
release/memcalib-v0.1/   已锁定的内部审阅数据版本
evaluation/releases/     评测发布包、指标、manifest 与 HTML 报告
sft/                     SFT 拆分清单、目标生成配置与确定性转换工具
tools/                    确定性发布包构建与验证工具
tests/                    流水线与发布工具测试
docs/                     数据结构、方法、数据来源与归档设计文档
```

大体积源数据、API 请求与响应、运行日志和构建中间产物保存在本地 `pipeline/data/` 目录中，不纳入 Git 版本控制。

## 构建与评测进展

v2.3 继承 v2.2 锁定的 15,000 条来源谱系、问题、真实原子、A/B/C 标签、动作、块数长尾与 canonical Hard A，不重新抽样基础记录。新增阶段先按三档难度为每个非 Hard-A 块分配 1–20 个原子目标，再生成同用户、块内连贯、对当前问题零答案足迹的辅助 `A+ignore` 原子；随后由独立阶段把完整原子集合改写成自然段落，隐藏数字分隔和原子边界。扩展、改写和独立 QC 分别使用独立请求与指纹，失败项只做定向重建或带前后哈希的最小局部修复。完整流程和精确计数见[v2.3 构建报告](docs/reports/memcalib-v23-composite-block-revision.html)；v2.1 基础构建与 v2.2 块数长尾仍分别保留在[基础集方法报告](docs/reports/memcalib-v21-dataset-construction-methodology.html)和[长尾修订报告](docs/reports/memcalib-v22-longtail-revision.html)中。

### v2.3 九模型同样本评测

当前 v2.3 评测从最终 15,000 条中锁定 500 条，按 health/general/coding=250/125/125 和难度 level 1/2/3=125/250/125 精确分层。八个百炼模型分别运行思考与非思考回答；Codex GPT-5.6 Sol 固定为 `reasoning_effort=none`，并在非思考运行中复用完全相同的回答作为重复 Judge 控制。两套运行各有 9,000 条回答、9,000 条主 Judge 和 450 条跨家族复核 Judge，结构重试后残余 invalid 均为 0。

| 模型 | 非思考 H | 思考 H | Delta H |
|---|---:|---:|---:|
| Qwen3-8B | 0.657 | 0.760 | +0.103 |
| GLM-5.2 | 0.839 | 0.872 | +0.033 |
| Qwen3.7-Max | 0.838 | 0.870 | +0.032 |
| DeepSeek-V4-Pro | 0.842 | 0.859 | +0.018 |
| DeepSeek-V4-Flash | 0.834 | 0.850 | +0.016 |
| Qwen3.5-35B-A3B | 0.849 | 0.853 | +0.004 |
| Qwen3.6-Flash | 0.836 | 0.837 | +0.001 |
| Kimi-K2.6 | 0.837 | 0.828 | -0.009 |
| Codex GPT-5.6 Sol control | 0.797 | 0.801 | +0.004 |

上表的原子宏平均 H 作为历史结果和原子级诊断保留。当前样本级主报告改为三层口径：总体主指标 `SCS(0.5)`；方向主指标 `sOPB/sUPB(0.5)=mean_s(1-0.5^directional_budget_s)`；事件率护栏 `Any-OPB/Any-UPB`。三个层次都对样本等权，但分别回答总体可靠性、方向错误强度和错误覆盖面，内部使用的 A 子类型不进入公开指标。完整公式、20 个 Full-memory 配置、18 个 No-memory 配置、2,000 次样本 bootstrap 区间和配对差值见[三层指标完整汇总](evaluation/analyses/memcalib-v23-three-layer-metrics/README.md)；逐难度、逐领域和错误预算分布见[样本级明细](evaluation/analyses/memcalib-v23-sample-level-calibration/README.md)。

在八个百炼模型上，Think 相对 Non-Think 的 SCS 平均变化为 +0.005、中位变化为 +0.001，只有 4/8 改善；sUPB 平均下降 0.039，但 sOPB 平均上升 0.028。这说明思考模式主要把错误从少用方向移向过用方向，而不是稳定提高整条回答的总体可靠性。Any-UPB 有 6/8 改善、Any-OPB 只有 3/8 改善，与方向主指标的趋势一致。Codex 两侧复用相同回答，其小幅差值只反映重复 Judge 波动。原子级 OPB/UPB、MinCalib、MCC、Kappa、CVaR、PMU、Rasch、pairwise 与 Pareto 仍见[v2.3 思考/非思考比较](evaluation/analyses/memcalib-v23-thinking-vs-nonthinking/README.md)、[思考模式候选指标](evaluation/analyses/memcalib-v23-multidomain-500-nine-models-candidate-metrics/README.md)和[非思考候选指标](evaluation/analyses/memcalib-v23-multidomain-500-nonthinking-nine-models-candidate-metrics/README.md)。

### v2.3 SFT pilot：Base 与 SFT 严格配对评测

Qwen3.5-35B-A3B Base 与 MemCalib SFT 合并模型通过同一套 vLLM 非思考配置在锁定的 v2.3 500 条 pilot 上生成回答。两侧各得到 498 条有效 Full-memory 回答；由于缺失集合不同，最终只比较共同完成的 496 条，不补跑缺失项。992 条主 Judge 与 50 条分层副 Judge 均完整，4 条主 Judge 结构问题经定向重试后 residual invalid=0；893 个双判原子的有序等级 exact agreement=0.966、线性加权 κ=0.921。

| 指标 | Base | SFT |
|---|---:|---:|
| OPB↓ | 0.104 | **0.029** |
| UPB↓ | **0.201** | 0.284 |
| H↑ | **0.845** | 0.824 |
| MCC↑ | 0.557 | **0.752** |
| 严格样本准确率↑ | 0.107 | **0.387** |
| SCS(0.5)↑ | 0.235 | **0.570** |
| CVaR90↓ | 0.359 | **0.197** |

SFT 明显降低了过用和严重有序错误，但同时增加了相关记忆使用不足，因此 H 小幅下降，而 MCC、Kappa、整条样本严格正确率和尾部风险显著改善。按同样本有序损失，SFT 在 371 条上更好、78 条持平、47 条更差，含平局胜率为 0.827；Base-SFT 平均损失差为 0.0804，样本聚类 bootstrap 95% 区间为 [0.0709, 0.0896]。在三层样本级口径下，`SCS(0.5)` 从 0.235 提升到 0.570，sOPB 从 0.687 降到 0.159，sUPB 则从 0.229 升到 0.324；Any-OPB 从 83.3% 降至 24.2%，Any-UPB 从 37.1% 升至 50.4%。该结果应解释为“总体错误显著减少但存在更强 under-use 偏置”，不能只用 H 或任一单指标概括。由于没有生成 No-memory 回答，PMU 等反事实指标不可计算。完整结果见[评测发布说明](evaluation/releases/memcalib-v23-sft-base-full-only-paired/README.md)、[候选指标研究](evaluation/analyses/memcalib-v23-sft-base-full-only-paired-candidate-metrics/README.md)、[样本级明细](evaluation/analyses/memcalib-v23-sft-base-full-only-paired-sample-level/README.md)和[三层指标完整汇总](evaluation/analyses/memcalib-v23-three-layer-metrics/README.md)。

采样 manifest 中的 388 表示与 v2.1 共享的查询/来源 ID，不表示数据行相同：这 388 条问题文本相同，但 `memory_blocks` 相同数为 0，完整模型输入行相同数也为 0。v2.1 与 v2.3 不是同一套 benchmark 数据，跨版本结果不得作为严格同样本回答模式对照。

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

思考模式结果也已完整重算候选指标，包括 MinCalib、MCC、各类 Kappa、NMI、Cramér V、有序严重度、CVaR90/95、PMU 权重敏感性、28 组配对胜率、Bradley–Terry、双维 Rasch 1PL、Pareto 和 2,000 次样本聚类 bootstrap。H 的八模型范围只有 0.062，而 MCC、二次 Kappa、PMU(1)、MinCalib 的范围分别为 0.137、0.138、0.126、0.124。H 排名前三为 Kimi、Qwen3.5-35B-A3B、GLM-5.2；CVaR90 前三则为 Qwen3.5-35B-A3B、GLM-5.2、Kimi。完整表格见[思考模式候选指标研究](evaluation/analyses/memcalib-v21-multidomain-500-thinking-candidate-metrics/README.md)，图形诊断见[尾部、Pareto 与名次图](evaluation/analyses/memcalib-v21-multidomain-500-thinking-candidate-metrics/candidate-metric-diagnostics.html)。

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

本仓库仅用于论文合作者内部研究审阅。v2.3 沿用 v2.1 的 8 个来源；每条记录保存来源、split、license 和可用的署名元数据。医学来源中的 `lavita/ChatDoctor-HealthCareMagic-100k` 数据卡未注明许可证，因此 7,500 条 health 数据当前仍记为 license unknown。Stack Exchange 入选记录均完成 CC-BY-SA-4.0 署名补全。完整数据尚不具备公开再分发条件，公开发布前仍需完成权利、PII 和敏感内容审查。

数据来源署名与权利状态详见 [NOTICE.md](NOTICE.md)。当前内部审阅版本未对仓库整体授予代码或数据许可证。
