# MemCalib ordered-usage-v2.1 全量结果

该目录包含五个回答模型在 15,526 条正式样本上的聚合结果。

- `metrics.json`：五模型原子级 A/B/C 混淆矩阵、OPB、UPB、H、分层指标、2,000 次样本聚类 bootstrap 置信区间和双 Judge 一致性。
- `report.html`：面向论文合作者的中文可视化报告。
- `judge-request.manifest.json`：77,630 条主评审与 2,500 条分层复核请求清单。
- `judge-run.manifest.json`：归一化 Judge 结果的数量、哈希和输出质量摘要。

当前有效性结论为 `provisionally_supported_with_caveat`。主指标应同时报告 OPB、UPB 和 H；不建议只依据 H 形成模型能力结论。
