# MemCalib v2.4.1 训练字段与衍生视图

## 单一权威数据

v2.4.1 只维护一份 15,000 条 canonical JSONL。评测、SFT、RL 和句子级信用分配所需格式均从该文件确定性导出，不再维护内容可能漂移的第二套数据。

每个父记忆块同时保存两种表示：

| 字段 | 含义 | 用途 |
|---|---|---|
| `memory_blocks[].memory_text` | 经流畅度改写的自然语言父块 | 正式 benchmark、标准 SFT baseline |
| `memory_blocks[].atomic_concat_text` | 原子文本按锁定顺序直接拼接的父块 | 句子级信用分配、原子删除反事实 |

训练分区中的双严格通过样本还包含顶层 `sft_supervision`，其中 `response` 是监督回答。test 分区不含该字段。

## 原子直接拼接

对样本 $x$，记原子集合为 $A_x$。每个原子 $a$ 有唯一标识 $id(a)$、原文 $t(a)$ 和唯一父块。父块 $p$ 保存有序原子标识序列：

$$
I(p) = \bigl(i_1, i_2, \ldots, i_k\bigr).
$$

定义 $\operatorname{strip}$ 为只删除字符串首尾空白，$\Vert_{\text{space}}$ 为使用一个 ASCII 空格连接。原子拼接文本为：

$$
T(p) =
\operatorname{strip}\bigl(t(A_x[i_1])\bigr)
\mathbin{\Vert_{\text{space}}}
\cdots
\mathbin{\Vert_{\text{space}}}
\operatorname{strip}\bigl(t(A_x[i_k])\bigr).
$$

这里不调用模型，不摘要、不润色、不增加衔接词，也不根据文本相似度去重。`atomic_concat_text` 必须逐字符等于 $T(p)$。

构造方法侧模型输入时，按 `memory_blocks` 的原顺序输出：

```text
Potentially relevant memory:
1. <第一个父块的 T(p)>
2. <第二个父块的 T(p)>

Current query:
<当前问题>
```

多个父块不合并。父块内部原子顺序只由 `atom_ids` 决定。

## 原子删除反事实

给定要删除的原子 ID 集合 $D$，父块 $p$ 的保留序列为：

$$
I_D(p) = \bigl(i \in I(p) \mid i \notin D\bigr),
$$

并使用与原始视图完全相同的规则重建：

$$
T_D(p) =
\mathop{\Vert_{\text{space}}}_{i \in I_D(p)}
\operatorname{strip}\bigl(t(A_x[i])\bigr).
$$

若 $I_D(p)$ 为空，则省略整个父块；否则父块位置、剩余原子身份、文本和相对顺序不变。删除操作只比较 `atom_id`，因此即使两个原子的文本逐字符相同，也只删除 $D$ 中指定的原子。

反事实信用分配复用同一条已生成回答 $y$，比较完整输入与删原子输入下的 teacher-forced 概率；不得为反事实输入重新生成回答：

$$
\Delta_D(x,y)
=
\log P_\theta\!\left(y \mid x, M\right)
-
\log P_\theta\!\left(y \mid x, M \setminus D\right).
$$

## 强制不变量

任何训练视图或反事实生成前必须验证：

1. 样本内 `atom_id` 唯一且非空；
2. 样本内父块 `parent_memory_id` 唯一且非空；
3. 每个原子恰好属于一个父块，原子声明的父 ID 与父块一致；
4. 每个父块的 `atom_ids` 非空、无重复、无未知 ID；
5. 所有原子均被父块引用一次，不能遗漏或重复引用；
6. `atomic_concat_text` 与公式定义逐字符一致；
7. 反事实删除集合不能包含未知 ID。

任一条件不满足即停止，不做容错猜测或文本级模糊匹配。

## SFT 监督范围

12,000 条训练分区样本均完成教师回答和双 Judge 审查。准入要求两个独立 Judge 同时严格通过原子使用、任务质量、安全和约束检查。

| 状态 | 数量 | canonical 处理 |
|---|---:|---|
| 双严格通过 | 11,892 | 写入 `sft_supervision` |
| 单 Judge review | 7 | 不写入监督 |
| reject | 101 | 不写入监督 |
| test | 3,000 | 不写入监督 |

被排除的 108 条仍保留在完整 benchmark 及其既定 SFT/RL 顶层分区中，只是不进入 SFT baseline 的监督导出。全部教师回答、Judge 输出和排除原因保留在本地审计目录。

标准 SFT baseline 从 12,000 条训练 ID 中导出 11,892 条 fluent-memory 样本；方法训练可从同一 canonical 记录导出 11,892 条 atomic-concat 样本。两者共享完全相同的监督回答，只有模型可见父块表示不同。

## 当前校验结果

- canonical：15,000 条、74,800 个父块、234,220 个原子；
- 训练监督：11,892 条；
- 无监督训练记录：108 条；
- test 监督泄漏：0；
- fluent Swift：11,892 条，只有 assistant 消息参与 loss；
- atomic-concat Swift：11,892 条，只有 assistant 消息参与 loss；
- canonical SHA-256：`f76b9d6b1d07c6e27e975562ce5b05a338a6d59f093674eea947d65e74e59f50`。
