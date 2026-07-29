# MemCalib Evaluation Archive

本目录保存 v0.1-v2.3 的评测快照：

- `configs/`：历史锁样和模型配置；
- `releases/`：锁定样本、聚合指标、报告和 manifest；
- `analyses/`：候选指标、样本级分布和思考模式比较；
- `cluster/`：v2.3 SFT 集群运行说明。

目录名保留数据版本和实验标识，可直接按版本搜索。不同目录可能使用不同数据、抽样、回答模型快照、thinking 设置、Judge 或指标定义，不得拼接成同一排行榜。

历史 JSON manifest 是生成时审计快照，其中的 `path` 字段保留迁移前路径，文件内容和哈希不因归档而重写。需要阅读时使用本目录的实际文件位置；需要新实验时从 [`evaluation/current/v2.4/`](../current/v2.4/) 开始。

本地原始请求、回答、Judge 输出和日志仍在 Git 忽略的 `evaluation/runs/`，未随跟踪产物迁移。
