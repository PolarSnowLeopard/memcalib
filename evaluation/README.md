# MemCalib evaluation

本目录保存 MemCalib 的锁定评测样本、配置、聚合指标、可视化报告和可复现分析工具。当前主要入口是 MemCalib v2.3 同一批 500 条样本上的九模型思考评测与非思考对照；v2.1 同样本实验、v2.2 的 100 条 Codex answer-only pilot、v2.0、v0.1 和早期 Judge 校准均作为历史结果保留。

## v2.3 九模型思考与非思考对照

从 v2.3 最终 15,000 条中锁定 500 条，领域 health/general/coding 为 250/125/125，难度 level 1/2/3 为 125/250/125。两套运行使用完全相同的模型输入文件；八个百炼模型只切换回答侧 thinking，Codex GPT-5.6 Sol 始终使用 `reasoning_effort=none`，并复用同一批回答作为重复 Judge 控制。Judge 模型、提示词、关闭 thinking 的设置和 450 条分层复核设计保持一致。

| 模型 | H 非思考 | H 思考 | Delta H |
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

两套运行均完成 9,000/9,000 回答、9,000/9,000 主 Judge 和 450/450 副 Judge，定向结构重试后 residual invalid=0。思考/非思考主副 Judge Cohen kappa 分别为 0.9210/0.9259。八个百炼模型的 H 变化中位数为 +0.0168，但 OPB、UPB、CVaR 和 PMU 并非一致改善；完整解释见[同样本比较](analyses/memcalib-v23-thinking-vs-nonthinking/README.md)。

v2.3 采样时优先保留了 388 个 v2.1 查询/来源 ID，以增加问题层面的可比性。该数字不是相同 benchmark 行数：对应的 388 条 v2.3 `memory_blocks` 全部重建，和 v2.1 相同的 `memory_blocks`、完整模型输入行均为 0。

- [v2.3 thinking release](releases/memcalib-v23-multidomain-500-nine-models/README.md)
- [v2.3 non-thinking release](releases/memcalib-v23-multidomain-500-nonthinking-nine-models/README.md)
- [thinking candidate metrics](analyses/memcalib-v23-multidomain-500-nine-models-candidate-metrics/README.md)
- [non-thinking candidate metrics](analyses/memcalib-v23-multidomain-500-nonthinking-nine-models-candidate-metrics/README.md)
- [thinking versus non-thinking comparison](analyses/memcalib-v23-thinking-vs-nonthinking/README.md)
- [sample-level OPB/UPB and SCS distributions](analyses/memcalib-v23-sample-level-calibration/README.md)
- [Qwen3.5-35B-A3B base/SFT 集群 vLLM 评测说明](cluster/memcalib-v23-sft-vllm-500/README.md)
- [Qwen3.5-35B-A3B base/SFT 496 条严格配对结果](releases/memcalib-v23-sft-base-full-only-paired/README.md)

样本级分析不再让一条样本的每个原子分别占模型级权重。每条回答先累积有序过用/少用错误预算；`SCS(0.5)` 对一个单级错误计 0.5、两个单级错误或一个 A/C 两级错误计 0.25，再对 500 条样本等权平均。思考模式下 SCS(0.5) 范围为 0.257–0.427，任意 OPB 样本率为 49.0%–81.8%，任意 UPB 样本率为 30.8%–58.0%。该分析同时保留 `rho=0.25/0.5/0.75`、完整错误预算分布、三档负载分层和非思考对照。

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

## v2.1 思考模式八模型诊断

在下方锁定的同一批 500 条 v2.1 样本上，七个已有百炼模型全部以
`enable_thinking=true` 重新回答，并新增 GLM-5.2。Codex 不在本轮重跑范围内。
每个模型分别运行 full-memory 和 no-memory，共 8,000 条回答；全部回答均有
非空 reasoning、唯一请求 ID、`finish_reason=stop`，且无残余结构 invalid。
回答 temperature=0、默认最大输出 8,192 tokens；Judge 继续关闭 thinking，
避免同时改变回答模型与评分模型两个实验变量。

### 思考模式 full-memory 结果

| 模型 | OPB↓ | UPB↓ | H↑ |
|---|---:|---:|---:|
| Kimi-K2.6 | 0.307 | 0.207 | 0.740 |
| Qwen3.5-35B-A3B | 0.347 | 0.181 | 0.727 |
| GLM-5.2 | 0.372 | 0.156 | 0.720 |
| DeepSeek-V4-Pro | 0.402 | 0.137 | 0.707 |
| Qwen3.6-Flash | 0.384 | 0.189 | 0.700 |
| DeepSeek-V4-Flash | 0.384 | 0.193 | 0.699 |
| Qwen3.7-Max | 0.432 | 0.127 | 0.689 |
| Qwen3-8B | 0.304 | 0.339 | 0.678 |

### 思考模式 no-memory 对照

| 模型 | OPB↓ | UPB↓ | H↑ |
|---|---:|---:|---:|
| GLM-5.2 | 0.054 | 0.904 | 0.174 |
| Qwen3.7-Max | 0.063 | 0.906 | 0.171 |
| DeepSeek-V4-Pro | 0.051 | 0.907 | 0.170 |
| Qwen3.6-Flash | 0.058 | 0.912 | 0.161 |
| Qwen3.5-35B-A3B | 0.054 | 0.914 | 0.157 |
| DeepSeek-V4-Flash | 0.045 | 0.915 | 0.156 |
| Kimi-K2.6 | 0.047 | 0.915 | 0.156 |
| Qwen3-8B | 0.031 | 0.934 | 0.124 |

对七个共享模型做同样本配对比较后，开启 thinking 的 full-memory H 变化为：
Qwen3-8B +0.045、Qwen3.5-35B-A3B +0.042、Qwen3.6-Flash +0.011、
DeepSeek-V4-Flash +0.008、DeepSeek-V4-Pro +0.007、Kimi-K2.6
-0.003、Qwen3.7-Max -0.007。thinking 并非统一增益，常见变化是 OPB 与
UPB 之间的偏差方向重新平衡。

同一批 8,000 条主 Judge 结果还完整重算了候选指标：MinCalib、算术/几何/
乘积/soft-min 综合分、balanced accuracy、macro F1、MCC、未加权/线性/二次
Kappa、NMI、Cramér V、有序距离、严重错误、CVaR90/95、PMU 权重敏感性、
28 组配对胜率、Bradley–Terry、双维 Rasch 1PL、Pareto 和 2,000 次样本聚类
bootstrap。H 的八模型范围为 0.062；MCC、二次 Kappa、PMU(1)、MinCalib
的范围分别为 0.137、0.138、0.126、0.124。H 排名前三为 Kimi、
Qwen3.5-35B-A3B、GLM-5.2；CVaR90 则为 Qwen3.5-35B-A3B、GLM-5.2、
Kimi，说明尾部风险与总体方向平均不能互相替代。

主 Judge 仍为 `qwen3.7-plus`，覆盖 8,000 条回答；DeepSeek-V4-Pro 和
Kimi-K2.6 分层复核 400 条回答。在 1,493 个双判原子上，总体 exact
agreement=0.914、Cohen κ=0.886；有序使用等级 exact agreement=0.884、
线性加权 κ=0.840。全部结构 invalid 经定向重试后为 0。

GLM-5.2 的 1,000 条回答中有 2 条 no-memory 请求在多次无界重试中无法正常
终止，最终使用供应商支持的 `thinking_budget=8192`，仍保持 thinking
开启；两条均正常结束并在 release 中单独记录哈希与合并审计。Qwen3-4B
及 `qwen3-4b-instruct-2507` 对两套凭据均无可用在线推理端点，因此未以其他
模型代替，也没有结果分数。

- [`thinking eight-model README`](releases/memcalib-v21-multidomain-500-thinking-eight-models/README.md)：完整配置、结果、思考前后差值和限制；
- [`thinking eight-model report`](releases/memcalib-v21-multidomain-500-thinking-eight-models/report.html)：可视化报告；
- [`thinking audit`](releases/memcalib-v21-multidomain-500-thinking-eight-models/thinking-audit.json)：逐模型、逐条件 reasoning 与 finish-reason 审计；
- [`metrics.json`](releases/memcalib-v21-multidomain-500-thinking-eight-models/metrics.json)：机器可读完整指标和 Judge 一致性。
- [`thinking candidate metric study`](analyses/memcalib-v21-multidomain-500-thinking-candidate-metrics/README.md)：扩展指标、置信区间、配对、Rasch 与 Pareto；
- [`thinking tail/Pareto/rank diagnostics`](analyses/memcalib-v21-multidomain-500-thinking-candidate-metrics/candidate-metric-diagnostics.html)：尾部风险与跨指标排名图。

## v2.1 非思考基线与 Codex 诊断

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
- [`tail/Pareto/rank diagnostics`](analyses/memcalib-v21-multidomain-500-candidate-metrics/candidate-metric-diagnostics.html)：CVaR 尾部曲线、OPB–UPB Pareto 平面和跨指标名次变化；
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

- [`v2.3 thinking nine-model release`](releases/memcalib-v23-multidomain-500-nine-models/README.md)：当前 500 条、九模型思考模式主评测；
- [`v2.3 non-thinking nine-model release`](releases/memcalib-v23-multidomain-500-nonthinking-nine-models/README.md)：完全相同 v2.3 输入上的非思考对照；
- [`v2.3 thinking versus non-thinking`](analyses/memcalib-v23-thinking-vs-nonthinking/README.md)：同样本 Delta H、OPB、UPB、MinCalib、MCC、CVaR 与 PMU；
- [`thinking candidate metric study`](analyses/memcalib-v21-multidomain-500-thinking-candidate-metrics/README.md)：思考模式八模型扩展候选指标；
- [`memcalib-v21-multidomain-500-thinking-eight-models/README.md`](releases/memcalib-v21-multidomain-500-thinking-eight-models/README.md)：七个共享模型思考模式重评与新增 GLM-5.2；
- [`memcalib-v21-multidomain-500-thinking-eight-models/report.html`](releases/memcalib-v21-multidomain-500-thinking-eight-models/report.html)：思考模式八模型 full/no-memory 可视化报告；
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
