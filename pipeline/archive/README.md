# Pipeline Lineage Archive

编号 00–101 的构建阶段是 v0.1-v2.3 的可复现谱系。为避免破坏阶段号、模块导入和旧命令，它们继续保留在 `pipeline/` 根目录，不做物理搬迁。

当前 v2.4 入口见 [`pipeline/current/v2.4/`](../current/v2.4/)。旧版本的面向审阅文档位于 [`docs/archive/versions/`](../../docs/archive/versions/)，历史评测位于 [`evaluation/archive/`](../../evaluation/archive/)。

这一安排把“当前版本发现入口”与“稳定可执行接口”分开：新工作只从 v2.4 索引开始，旧脚本仍可按原阶段号审计。
