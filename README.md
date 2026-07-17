# MemCalib

**评测对话语言模型应当何时以及如何使用记忆。**

MemCalib 用于评测模型在回答新问题时，能否恰当地调节检索记忆或存储记忆对回答的影响。模型接收符合真实记忆系统形态的非原子记忆块；评测端使用隐藏的原子级标注，判断各项信息应被抑制、仅作为有限支持，还是作为控制回答的关键约束。

## 当前版本

MemCalib v2 是当前供论文合作者内部审阅和训练使用的多领域版本。最终发布集包含 15,000 条英文记录，严格按照 health、general、coding 三个领域的预定配额选取；所有记录均通过确定性结构校验、证据 grounding、语义质量控制和独立模型复核。14,906 条为 strict pass，94 条为脚本明确允许的 non-blocking review，reject 和 invalid 均未进入最终数据。

| 统计项 | 数量 |
|---|---:|
| 样本 | 15,000 |
| health / general / coding | 7,500 / 3,750 / 3,750 |
| 模型可见记忆块 | 51,970 |
| 隐藏原子记忆 | 53,318 |
| A / B / C 原子记忆 | 16,640 / 19,060 / 17,618 |
| strict / non-blocking review | 14,906 / 94 |
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

v2 审阅入口：

- [15,000 条数据交付说明](docs/MEMCALIB_V2_COAUTHOR_HANDOFF.md)
- [完整构建与质检方法报告](docs/reports/memcalib-v2-dataset-construction-methodology.html)
- [六模型抽样评测报告](evaluation/releases/memcalib-v2-multidomain-500-six-models/report.html)
- [六模型机器可读指标](evaluation/releases/memcalib-v2-multidomain-500-six-models/metrics.json)
- [Qwen3.5-35B-A3B 增量评测审计](evaluation/releases/memcalib-v2-multidomain-500-qwen35/README.md)

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
- [Benchmark 数据结构](docs/benchmark-schema.md)
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

v2 构建流程包括数据源许可与署名审查、确定性清洗和去重、按领域/来源/主题分层抽样、源问答语义质检、英文记忆构造、原子化、A/B/C 使用强度与动作标注、证据逐字 grounding、确定性 validator、独立模型质检以及只针对失败项的定向修复。完整方法、阶段容量和审计闭环见[构建方法报告](docs/reports/memcalib-v2-dataset-construction-methodology.html)。

当前 v2 模型比较使用从最终 15,000 条数据中按正式领域比例和来源分布确定性抽取的 500 条样本，其中 health 250、general 125、coding 125。六个模型分别完成 full-memory 与 no-memory 两个配对条件，共 6,000 条回答；主 Judge 完成 6,000 条评审，复核 Judge 完成 300 条分层复核。

协议采用 `ordered-usage-v2.1`，以 OPB 错误率、UPB 错误率及两个方向抵抗能力的调和平均 H 作为主指标。v2 抽样结果如下：

| 模型 | OPB↓ | UPB↓ | H↑ |
|---|---:|---:|---:|
| Kimi-K2.6 | 0.317 | 0.207 | 0.734 |
| Qwen3.7-Max | 0.345 | 0.179 | 0.728 |
| DeepSeek-V4-Pro | 0.368 | 0.183 | 0.713 |
| Qwen3.6-Flash | 0.392 | 0.159 | 0.706 |
| DeepSeek-V4-Flash | 0.387 | 0.182 | 0.701 |
| Qwen3.5-35B-A3B | 0.404 | 0.154 | 0.699 |

六模型复核的整体 exact agreement 为 0.936，Cohen κ 为 0.915；有序使用等级 exact agreement 为 0.898，线性加权 κ 为 0.868。Qwen3.5-35B-A3B 的 UPB 最低、C 类使用正确率最高，但 OPB 最高、A 类抑制正确率最低，进一步显示模型间存在清晰的“利用相关记忆”和“拒绝不该使用的记忆”权衡。当前结果属于 500 条内部诊断，不应解释为 15,000 条全量公开 leaderboard，人工验证仍待扩展。

实验说明见 [evaluation/README.md](evaluation/README.md)，正式协议见 [v2.1 评测协议](docs/evaluation_protocol_v2.1.md)，完整混淆矩阵、置信区间和领域结果见 [v2 六模型报告](evaluation/releases/memcalib-v2-multidomain-500-six-models/report.html)。历史 v0.1 的 15,526 条全量评测仍保留在[原全量报告](evaluation/releases/memcalib-ordered-v2.1-full-15526/report.html)中。

## 发布与许可状态

本仓库仅用于论文合作者内部研究审阅。v2 使用 8 个来源；每条记录保存来源、split、license 和可用的署名元数据。医学来源中的 `lavita/ChatDoctor-HealthCareMagic-100k` 数据卡未注明许可证，因此 7,500 条 health 数据当前仍记为 license unknown。Stack Exchange 入选记录均完成 CC-BY-SA-4.0 署名补全。完整数据尚不具备公开再分发条件，公开发布前仍需完成权利、PII 和敏感内容审查。

数据来源署名与权利状态详见 [NOTICE.md](NOTICE.md)。当前内部审阅版本未对仓库整体授予代码或数据许可证。
