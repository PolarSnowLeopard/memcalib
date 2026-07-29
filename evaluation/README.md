# MemCalib Evaluation

评测目录分为当前版本、历史归档和本地运行区：

```text
evaluation/current/v2.4/   当前配置、锁定发布包与分析
evaluation/archive/        v0.1-v2.3 历史快照
evaluation/scripts/        当前与历史共享的可复现工具
evaluation/prompts/        Judge 提示词
evaluation/templates/      报告模板
evaluation/runs/           Git 忽略的本地请求、回答、Judge 输出与日志
```

## 当前入口

- [v2.4 评测总览](current/v2.4/README.md)
- [494 条完全配对九模型结果](current/v2.4/releases/memcalib-v24-multidomain-494-nine-models-complete-case/README.md)
- [中文三层样本级主报告](current/v2.4/analyses/three-layer-metrics/README.md)
- [候选指标与诊断](current/v2.4/analyses/candidate-metrics/README.md)
- [样本级分数与分布](current/v2.4/analyses/sample-level/README.md)

当前报告采用 `SCS(0.5)`、`sOPB/sUPB(0.5)` 和
`Any-OPB/Any-UPB` 三层样本级口径。原子级 H、MCC、Kappa、CVaR、
PMU、Rasch、pairwise 和 Pareto 作为补充诊断。

## 中间结果

每次运行在 `evaluation/runs/<run>/` 保存：

| 路径 | 内容 |
|---|---|
| `requests/answers/` | full/no-memory 请求和输入指纹 |
| `answers/` | 原始回答、失败、重试和完整性报告 |
| `requests/judges/` | 主/副 Judge 请求及抽样 ID |
| `api/` | Judge 原始响应、失败和结构重试 |
| `judgments/` | 规范化逐原子判定、invalid 和合并结果 |
| `workflow.status` | 阶段状态 |

该目录不推送远程，也不进入合作者数据 ZIP。远程只保存锁定样本、聚合指标、报告和 manifest。

## 历史边界

[历史评测索引](archive/README.md)中的结果使用不同数据版本、抽样、模型快照、thinking 设置或 Judge 配置，不能与 v2.4 拼成同一排行榜。历史 manifest 的路径是生成时快照；归档不会改写其内容。

## 测试

```bash
PY=/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
PYTHONPATH=. "$PY" -m unittest discover -s tests/evalbench -p 'test_*.py'
```

分析器不会重新调用模型。重新发起请求必须使用新的运行目录，禁止覆盖既有审计。
