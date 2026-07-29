# MemCalib v2.4 Pipeline Index

v2.4 的可复现构建阶段保留在 `pipeline/` 根目录，以维持稳定阶段号和 Python 导入路径：

| 阶段 | 作用 |
|---|---|
| 102 | 准备 3,750 条 coding 文本推理重写 |
| 103 | 结构化后处理与确定性 validator |
| 104–105 | 独立 QC 请求与后处理 |
| 106 | 构建 15,000 条完整 v2.4 |
| 107–108 | 有界本地修复与人工裁决 |
| 109 | 合并全部准入轮次并验证 3,750 条覆盖 |
| 110 | 导出确定性人工审阅样本 |

共享逻辑位于 `pipeline/memcalib_v24_coding_common.py`，提示词位于 `pipeline/prompts/`。完整方法见 [`docs/current/v2.4/reports/memcalib-v24-coding-text-observability.md`](../../../docs/current/v2.4/reports/memcalib-v24-coding-text-observability.md)。

本索引只定义当前版本边界，不复制脚本。大体积数据和 API 审计继续保存在 Git 忽略的 `pipeline/data/`。
