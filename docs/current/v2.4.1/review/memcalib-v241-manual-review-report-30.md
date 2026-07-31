# MemCalib v2.4.1 评测前人工抽样审查

## 审查结论

在启动模型评测前，从最终 15,000 条候选集中固定种子、分层抽取 30 条，由人工逐条阅读问题、参考答案、全部记忆块、原子标签/动作和评分要求。

- 抽样规模：30 条，占完整数据集 0.20%
- 领域：coding 24 条、health_seed 3 条、general 3 条
- 构建分层：人工收尾 9 条、对齐修复 9 条、coding 对照 6 条、health 对照 3 条、general 对照 3 条
- 首轮严格判定：通过 18 条、需澄清 3 条、不通过 9 条
- 修正记录：12 条，其中 1 条领域错误记录被替换，11 条完成监督或参考答案修正
- 修正后第二轮判定：30/30 通过
- 修正后 coding 原子/rubric 确定性对齐告警：0
- 修正后样本内 A 原子全文出现在参考答案：0

本报告是评测前的人工质量门，不代表对 15,000 条进行了逐条人工标注。其作用是检验主要构建分支是否存在可观察的系统性错误，并在启动昂贵评测前阻断明显缺陷。

## 审查标准

每条样本按以下六个方面检查：

1. **领域适配**：coding 必须是软件工程、程序行为、系统设计或代码理解任务，不能仅因来源站点而把非软件任务归入 coding。
2. **问题可回答性**：问题必须能从自然语言直接回答，不依赖实际执行代码才能判分，也不能缺失决定结论的必要条件。
3. **B/C 落实**：每个 B/C 原子的同原子信息都应在参考答案中得到明确、适度、可观察的使用；C 必须能够控制结论或关键行为。
4. **A 零足迹**：A 原子不能独立改变答案的结论、步骤、术语、格式或额外约束。若答案中的相同信息由问题本身明确提供，则必须避免造成无法判定来源的冲突。
5. **事实与安全性**：技术机制应正确；医疗回答不得因旧诊断而忽略新危险信号，也不得给出不充分的自我处理建议。
6. **块与原子一致性**：自然语言记忆块必须覆盖其声明的原子，原子文本、标签、动作、rubric 和参考答案不得互相矛盾。

## 逐条结果

| # | 样本 ID | 分层 | 复核结论 | 审查要点 |
|---:|---|---|---|---|
| 1 | `crk2_v2_raw_coding_e19cebbe74362259` | 人工收尾 | 通过（替换后） | 替换原非软件人体工学样本。新样本是 CI 硬件选型；C 控制三人团队规模，B 提供 PHP 工作负载，A 不影响答案。19 个原子、6 个自然语言记忆块。 |
| 2 | `crk2_v2_raw_coding_d99669074e4dded8` | 人工收尾 | 通过 | 时间边界、NetworkX 环境和秒制浮点返回合同明确；未采用 A 中指定的 `time.perf_counter()`。 |
| 3 | `crk2_v2_raw_coding_cbb6ed3c5c7a0b34` | 人工收尾 | 通过 | SAN 约束控制虚拟化评估，历史口述仅作为待核实线索；未引入 A 中的灾备审批要求。 |
| 4 | `crk2_v2_raw_coding_e688bbbdd3e5967b` | 人工收尾 | 通过 | 正确区分 Hibernate/JDBC 与原始文件，XML 偏好和表单展示需求均落实；未引入 XSD 要求。 |
| 5 | `crk2_v2_raw_coding_47e9eabff7ae07f7` | 人工收尾 | 通过 | 明确纠正“首个用户触发”和“阻塞请求”两项 C 错误记忆，并覆盖生命周期、重叠和失败处理。 |
| 6 | `crk2_v2_raw_coding_55d32777c2f91f3e` | 人工收尾 | 通过 | 组件共享状态、数据驱动组合、编译依赖和 unity build 影响均有对应监督；未受 UML 格式偏好影响。 |
| 7 | `crk2_v2_raw_coding_657e634457cdb2cf` | 人工收尾 | 通过 | 保留函数接口并解释 n-back 配对；短输入返回 0，未采用 A 中错误的 `ValueError` 要求。 |
| 8 | `crk2_v2_raw_coding_698941cbf11a4ea7` | 人工收尾 | 通过（修正后） | 首轮参考答案主动提到“不使用下划线”，形成 Hard A 足迹；已删除该对比，只保留问题规格给出的连字符行为。 |
| 9 | `crk2_v2_raw_coding_355b91459e361b52` | 人工收尾 | 通过 | DSE 表示、目标日期、epoch、日序和时区假设完整；ISO 8601 偏好未进入答案。 |
| 10 | `crk2_v2_raw_coding_041ea662e9263b06` | 对齐修复 | 通过（修正后） | 首轮虽写出 1M/10M 规模，却仍建议全量两两斥力。已改为稀疏边、Barnes-Hut/四叉树近似、阻尼和非收敛处理。 |
| 11 | `crk2_v2_raw_coding_13086accc2e0781e` | 对齐修复 | 通过 | 构建命令、退出状态、`target/apple-client-1.0.jar` 和失败反馈明确；未采用 `dist/` 的 A 约束。 |
| 12 | `crk2_v2_raw_coding_60a8ef449a904d6e` | 对齐修复 | 通过 | 空 Transaction ID、`validateTID` 和预期异常类型一致，旧“返回 false”记忆未影响答案。 |
| 13 | `crk2_v2_raw_coding_9f2a5d792f26fc2a` | 对齐修复 | 通过（修正后） | 首轮答案无必要地提到 changelist，触及 A。已删除该足迹，并保留模板文件、未版本化本地配置和 `svn:ignore` 排除约束。 |
| 14 | `crk2_v2_raw_coding_0ef9607a46af8054` | 对齐修复 | 通过（修正后） | 首轮原子写“GCC+同一 shell”，rubric 却要求 `uname` 且禁止提 GCC。已把原子收窄为共享 POSIX shell/`uname`，并同步块、rubric 和答案。 |
| 15 | `crk2_v2_raw_coding_7e63b37eb0ad0395` | 对齐修复 | 通过 | 位掩码包含判断准确；未引入局部权限继承或可访问性错误消息要求。 |
| 16 | `crk2_v2_raw_coding_3e4cb4e775ad6b4b` | 对齐修复 | 通过 | Android 行视图标签、`ItemInfo` 和 Intent key `equipment` 一致；Parcelable 偏好未进入答案。 |
| 17 | `crk2_v2_raw_coding_f25ba482ae108e63` | 对齐修复 | 通过 | 按精度需求、数组带宽和混合类型转换选择 float/double；未采用 GPU 类比格式偏好。 |
| 18 | `crk2_v2_raw_coding_431f2228ca2fb941` | 对齐修复 | 通过 | J2ME、ProGuard 和厂商材料偏差均落实；格式偏好未改变技术结论。 |
| 19 | `crk2_v2_raw_coding_ce439ac2342e5ac6` | coding 对照 | 通过（修正后） | 首轮错误声称 WinForms 需要 `DataBind`，并错误描述自动列行为。已改为 DataTable 或 BindingSource+DataMember 的正确绑定机制。 |
| 20 | `crk2_v2_raw_coding_b4c6fd3607809601` | coding 对照 | 通过（澄清后） | 补全资源定位、批准的解析类、均值/最大波长计算、元组顺序和缺失/空数据失败行为。 |
| 21 | `crk2_v2_raw_coding_93e41677e7c5b270` | coding 对照 | 通过 | `VoucherData` 必选/可选字段边界明确，未擅自加入重试策略。 |
| 22 | `crk2_v2_raw_coding_0f25f1dbb4e56078` | coding 对照 | 通过（澄清后） | 补充 Linux 上 `os.path` 的 POSIX 语义、`ntpath` 和 Python 字符串反斜杠表示，避免把 `\t` 误作路径字符。 |
| 23 | `crk2_v2_raw_coding_6ba0fd0fc1be141d` | coding 对照 | 通过 | 输入尺寸/缓冲区、纹理 ID 和 OpenGL 错误检查均覆盖；德语注释偏好未进入答案。 |
| 24 | `crk2_v2_raw_coding_db2be6712d26ab79` | coding 对照 | 通过（修正后） | “失败时返回错误字符串”由题面明确要求，却同时被标为 Hard A，导致不可判定。已删除冲突 A，保留成功路径 B。 |
| 25 | `crk2_v2_raw_6a85c11f9300952b` | health 对照 | 通过（修正后） | 首轮忽略水疱/出血和全身皮疹，仅建议氧化锌。已补充婴儿鉴别、感染/病毒可能、淋巴结解释和明确就医红旗。 |
| 26 | `crk2_v2_raw_83d0ec64551f902a` | health 对照 | 通过（修正后） | 首轮未使用皮肤癌家族史。已同时纳入家族史、1 型糖尿病、感染鉴别、皮肤镜/活检和紧急信号。 |
| 27 | `crk2_v2_raw_b040afe7f3baaf55` | health 对照 | 通过 | 蜘蛛暴露、咬痕、神经系统和全身症状共同支持急诊建议；保险文档格式偏好未进入答案。 |
| 28 | `crk2_v2_raw_general_12a12f3253775f4d` | general 对照 | 通过（修正后） | 首轮完全未使用 B 中的辛辣顾虑。已保留优质 kebab 推荐，并加入 `acısız`、酱汁另放和现场确认辣度建议。 |
| 29 | `crk2_v2_raw_general_13249bbbed9b7521` | general 对照 | 通过 | 程序员远程工作场景支持人体工学鼠标建议；未采用“仅轻量游戏鼠标”的 A 偏好。 |
| 30 | `crk2_v2_raw_general_171746e01800472e` | general 对照 | 通过 | PDF/JPEG/PNG 三种格式及用途完整；叙事段落格式偏好未改变答案结构。 |

## 修复类型汇总

| 修复类型 | 数量 | 说明 |
|---|---:|---|
| 领域错误替换 | 1 | 移除 standing-desk 人体工学题，换入有完整署名的软件工程 CI 题 |
| 原子/rubric 同步 | 1 | 修正共享 shell 原子与 `uname` rubric 的语义错位 |
| 冲突 Hard A 删除 | 1 | 删除题面已规定、却被标作 A 的失败返回行为 |
| 参考答案修正 | 9 | 包括 A 足迹、不可扩展算法、技术错误、遗漏的 B/C、医疗安全和个性化缺失 |

## 产物

- 人工审查样本：`docs/current/v2.4.1/review/memcalib-v241-manual-review-sample-30.jsonl`
- 抽样清单：`docs/current/v2.4.1/review/memcalib-v241-manual-review-sample-30.manifest.json`
- 修复审计：`pipeline/data/multidomain/full-v2/revision-coding-text-observable-v24/v241/audit/memcalib_v241_manual_review_gate.audit.jsonl`
- 修正后完整数据：`pipeline/data/multidomain/full-v2/revision-coding-text-observable-v24/v241/release/memcalib_v241_multidomain_benchmark_15000.jsonl`

评测启动条件是：本报告的第二轮 30/30 通过、完整 release 仍保持 15,000 条及既定领域配额、coding 确定性原子/rubric 对齐告警为 0。当前这些条件均已满足。
