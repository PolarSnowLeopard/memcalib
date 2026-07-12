# MemCalib

**评测对话语言模型应当何时以及如何使用记忆。**

MemCalib 用于评测模型在回答新问题时，能否恰当地调节检索记忆或存储记忆对回答的影响。模型接收符合真实记忆系统形态的非原子记忆块；评测端使用隐藏的原子级标注，判断各项信息应被抑制、仅作为有限支持，还是作为控制回答的关键约束。

## 当前版本

MemCalib v0.1 是供论文合作者内部审阅的私有版本，基于两个英文医学问答数据源构建。该版本用于验证 benchmark 的数据构建流程与评测表示形式，目前尚不足以支持对通用对话场景的结论。

| 统计项 | 数量 |
|---|---:|
| 样本 | 15,528 |
| 原始记忆块 | 56,044 |
| 原子记忆 | 78,734 |
| 含混合标签的记忆块 | 7,963（14.2%） |
| A / 无关原子记忆 | 22,722 |
| B / 支持性原子记忆 | 25,783 |
| C / 控制性原子记忆 | 30,229 |
| 数据源 | 2 |
| 医学主题 | 12 |

## 能力定义

- **A - suppress（抑制）：** 该记忆不应在回答中留下缺乏依据的影响。
- **B - bound（有限使用）：** 该记忆可以为回答提供支持，但不应控制回答或导致内容过度扩展。
- **C - control（控制）：** 该记忆必须实质性地约束回答内容或主要建议。

模型输入中呈现的是 `memory_blocks`。评测使用隐藏的 `memories` 数组，其中每条原子记忆均包含 A/B/C 标签、构造目标以及可观测的 judge rubric。该设计在保留真实非原子记忆输入形态的同时，支持细粒度的错误诊断。

## 研究定位

[StratMem-Bench](https://arxiv.org/abs/2604.26243) 在 657 个虚拟角色场景中独立评测了必要记忆、支持性记忆和无关记忆。MemCalib 不将这种三分类相关性划分本身作为创新点。其主要贡献包括：面向模型输入记忆块、面向评测使用原子标注的协议；符合真实系统形态的非原子记忆；用于判定记忆使用不足与过度使用的原子级 rubric；以及规模更大且可复现的数据构建流程。

## 五分钟快速审阅

使用当前工作区指定的非 Conda Python 运行时，或任意带有标准库的 Python 3.11 及以上版本：

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
tools/                    确定性发布包构建与验证工具
tests/                    流水线与发布工具测试
docs/                     数据结构、方法、数据来源与归档设计文档
```

大体积源数据、API 请求与响应、运行日志和构建中间产物保存在本地 `pipeline/data/` 目录中，不纳入 Git 版本控制。

## 构建与评测进展

当前构建流程包括确定性源数据过滤、去重、候选样本分层选择、源问答语义质检、英文记忆构造、原子信息拆分、A/B/C 标注、原子级 rubric 生成和结构化质量检查。

首轮回答级验证已经完成。实验锁定了 500 条分层样本，并在 Full-memory 与 No-memory 配对条件下评测五个代表性模型，共生成 5,000 条回答和 6,000 条自动 Judge 结果。双 Judge 在 5,062 个原子判定上的 exact agreement 为 0.876，Cohen κ 为 0.840。

当前证据初步支持 benchmark 的诊断能力：五个模型在 B/C 标签上均表现出正向记忆增益，同时均存在 A 类过度结合；标签级能力差异明显。五个模型的综合分差仅为 0.027，因此当前版本更适合比较细粒度错误结构，单一总分的模型区分度有限。完成 100 条人工复核后再形成最终有效性结论。实验说明见 [evaluation/README.md](evaluation/README.md)，可视化结果见 [500 条验证报告](evaluation/releases/memcalib-v0.1-500/report.html)。

## 发布与许可状态

本仓库仅用于论文合作者内部研究审阅。`OpenMed/MedDialog` 声明采用 Apache-2.0 许可；`lavita/ChatDoctor-HealthCareMagic-100k` 的数据卡未注明许可证。因此，当前数据分片尚不具备公开再分发条件。公开发布前还需完成个人身份信息（PII）与敏感内容审查。

数据来源署名与权利状态详见 [NOTICE.md](NOTICE.md)。当前内部审阅版本未对仓库整体授予代码或数据许可证。
