# MemCalib 全量正式评测集

该目录锁定了 `full_memory` 正式评测使用的 15,526 条样本。数据由 15,528 条英文构建结果经过父记忆规范化、完整性校验和问题精确去重得到。

## 文件说明

- `model-facing.jsonl.gz`：模型可见输入，仅含问题、非原子记忆块和来源分层字段。
- `hidden-evaluation.jsonl.gz`：隐藏原子记忆、A/B/C 标签、rubric 与构建审计字段，不应提供给被评模型。
- `sample-ids.txt`：锁定的样本 ID 顺序。
- `excluded-exact-question-duplicates.jsonl`：被排除的 2 条精确问题重复记录。
- `release-manifest.json`：数据规模、分布、质量检查和文件 SHA-256。
- `answer-request.manifest.json`、`answer-run.manifest.json`：全量回答请求与完成清单。

压缩文件使用固定 gzip 时间戳生成。解压后文件的 SHA-256 应与 `release-manifest.json` 中对应未压缩条目一致：

```bash
gzip -cd hidden-evaluation.jsonl.gz | shasum -a 256
gzip -cd model-facing.jsonl.gz | shasum -a 256
```

正式指标和可视化报告位于 `../memcalib-ordered-v2.1-full-15526/`。原始 API 请求、回答、Judge 输出和重试审计文件保存在本地 `evaluation/runs/`，不纳入 Git。
