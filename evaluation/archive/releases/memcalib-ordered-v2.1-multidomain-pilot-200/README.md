# MemCalib 多领域试点评测集

本目录锁定 `ordered-usage-v2.1` 多领域内部诊断评测所需的 200 条样本，其中通用对话和 Coding 各 100 条。它用于验证原子记忆标注、A/B/C 有序使用等级、OPB/UPB 指标及配对反事实评测在非医学场景中的适用性。

- `model-facing.jsonl`：回答模型可见的非原子记忆与问题，不包含答案、原子标签或 rubric。
- `hidden-evaluation.jsonl`：Judge 和聚合分析使用的隐藏原子标注与 rubric。
- `release-manifest.json`：源数据、样本顺序、发布文件和配置的数量与 SHA-256 哈希。
- `answer-request.manifest.json`：5 个模型、2 个条件产生的 2,000 条回答请求清单。
- `metrics.json` 与 `report.html`：流程完成后生成的原子级指标和可视化报告。

本发布集状态为 `internal_diagnostic`。人工数据审查完成前，不应将结果表述为正式多领域排行榜结论。
