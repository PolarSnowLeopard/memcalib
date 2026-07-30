# MemCalib 与五项高度相关工作的详细比较

> 调研快照：2026-07-15  
> 比较对象：RPEval、BenchPreS、StratMem-Bench、OP-Bench、MemSyco-Bench  
> 目的：澄清这些工作分别评估什么、是否包含外部记忆系统、规范标签与实际行为如何测量，以及 MemCalib 真正可成立的差异化位置。

## 1. 核心结论

这五项工作不应被简单写成五个并列的“选择性记忆 benchmark”。它们位于不同的系统层次，并且对“记忆使用正确性”的定义不同：

- **OP-Bench**：研究加入外部记忆系统后，整个 personalized agent 是否出现无关个性化、谄媚和跨问题重复。
- **MemSyco-Bench**：直接比较外部 Agent Memory 系统，进一步区分检索失败与“已经检索到、但在推理和决策中用错”，重点研究 memory-induced sycophancy。
- **BenchPreS**：在固定 persistent profile 已经提供给模型的条件下，研究表达偏好是否符合当前收件人和正式沟通规范。
- **RPEval**：在固定偏好记忆已经提供给模型的条件下，研究偏好对当前用户意图应当被 Ignore、Support 还是 Dominate。
- **StratMem-Bench**：在一个未标注的候选记忆池已经提供给模型的条件下，研究模型能否选择并自然整合 must、nice 和 irrelevant memories。
- **MemCalib**：在模型只能看到非原子记忆块的条件下，以隐藏原子监督判断每个原子在回答中产生的实际影响强度是否达到规范等级。

因此，MemCalib 最稳妥的定位不是“首次研究记忆应不应该使用”，也不是“首次采用三级使用标签”，而是：

> **在给定非原子记忆块的受控条件下，对块内隐藏原子进行双向、有序的实际影响校准。**

这一定位强调的是三个此前通常被分开处理的设计同时成立：

1. 模型侧输入是现实记忆系统可能返回的自然语言复合块，而非已经拆好的 gold atoms；
2. 评估侧保留逐原子的规范等级与实例化 rubric；
3. 对每个原子同时恢复实际 A/B/C 影响等级，从而形成逐原子的规范—实际有序混淆矩阵。

## 2. 首先区分两个系统层次

### 2.1 端到端外部记忆系统评测

这一层不假设“正确记忆已经给到模型”，而是让外部记忆框架处理历史对话、构建 memory bank、检索候选内容，再由 backbone model 生成回答。因此最终错误可能来自：

- 记忆抽取或压缩错误；
- 记忆更新、覆盖或失效管理错误；
- 检索遗漏；
- 检索了语义相关但决策上不适用的信息；
- 检索正确，但生成模型错误赋予记忆过高决策权。

**OP-Bench 和 MemSyco-Bench 属于这一层。**其中 MemSyco-Bench 对 retrieval failure 与 post-retrieval misuse 的分解最明确。

### 2.2 给定记忆后的使用校准

这一层把检索结果视为已知输入，主要隔离和测量生成模型的下游使用行为。它回答的是：

- 面对已经进入上下文的记忆，模型能否判断适用性？
- 记忆应当被忽略、局部支持还是主导？
- 模型是否在回答中真正按要求使用？
- 使用方式是否自然、是否产生过度或不足？

**RPEval、BenchPreS、StratMem-Bench 和当前 MemCalib 属于这一层。**

这一划分非常重要：MemCalib 当前不能直接声称自己评估“记忆系统是否会检索错误”，因为它主要测量给定记忆后的影响校准；但它能以更细的原子级监督隔离 post-retrieval use error。

## 3. 核心维度对比

这六项工作都以 benchmark 为核心贡献。✅ 表示该维度被正式纳入任务、标注或指标；× 表示没有作为独立评价维度。

| Benchmark | 外部记忆系统 | 判断是否应使用 | 三级使用强度 | 原子 / item 级监督 | 非原子输入 | 同时测过度与不足 | 多种记忆语义类型（事实 / 偏好 / 约束等） |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| RPEval | × | ✅ | ✅ | ✅ | × | ✅ | × |
| BenchPreS | × | ✅ | × | ✅ | × | ✅ | × |
| StratMem-Bench | × | ✅ | ✅ | ✅ | × | ✅ | × |
| OP-Bench | ✅ | ✅ | × | × | × | × | × |
| MemSyco-Bench | ✅ | ✅ | × | × | × | ✅ | ✅ |
| **MemCalib** | × | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

> **在给定记忆后的使用校准上，MemCalib 覆盖最全面：它同时具备三级强度、原子级监督、非原子输入、双向偏差，并统一覆盖事实、偏好、约束等多种记忆语义类型。**

唯一需要保留的限定是：OP-Bench 和 MemSyco-Bench 评估完整外部记忆系统；MemCalib 当前评估的是记忆进入上下文之后，模型是否用得合度。

## 4. RPEval：形式化与错误矩阵最接近

[RPEval](https://arxiv.org/abs/2601.16621) 的核心问题是：偏好记忆如何影响对当前用户意图的理解。它将每个 preference–query pair 标为：

- **Ignore**：偏好不能改善当前回答，甚至可能误导当前任务；
- **Support**：偏好可以提高回答质量，但不是必须遵循的硬条件；
- **Dominate**：偏好必须严格遵循，否则会产生事实性错误或强烈用户拒绝。

例如，“喜欢辣味”对餐厅推荐可以是 Support，“素食者”对餐厅推荐可以是 Dominate，而二者对天气查询都应当是 Ignore。

### 4.1 它实际覆盖了什么

RPEval 先建立原子 preference–query 标注，再通过两类扩展构造更真实的输入：

- 将显式偏好转换为多轮对话中的隐式偏好；
- 将单偏好扩展为多偏好设置，包括全部无关偏好的 Ignore-All，以及相关偏好与无关干扰项混合的 Leave-K-Out。

评估包含两个层次：

1. **Discriminative setting**：让模型直接预测每条偏好的 Ignore / Support / Dominate。
2. **Generative setting**：让模型生成回答，再判断是否与整组 intent labels 对齐，并对 Filter Bubble、RII、UPB、Low Feasibility 和 Verbose Generation 打严重度分。

因此，不能把 RPEval 简化成“只预测使用策略”。它已经直接评估生成回答，并明确提出了三级策略错误矩阵和用户可感知的错误 taxonomy。

### 4.2 与 MemCalib 的实质重叠

- 都认为记忆的作用不是简单 use/not-use，而是存在 Ignore、Support、Dominate 三种规范强度；
- 都在原子信息层定义 gold role；
- 都承认过度使用和使用不足是两个方向；
- RPEval 的 FB、RII、UPB 与 MemCalib 的 OPB、RII、UPB 有直接概念重叠。

因此，MemCalib 不应把三级角色、双向偏差意识或原子偏好标注本身作为首创。

### 4.3 MemCalib 可成立的差异

- RPEval 聚焦偏好对用户意图的作用；MemCalib 试图覆盖事实、偏好、约束和安全敏感信息。
- RPEval 的多偏好通常仍以可区分条目提供；MemCalib 强调一个模型可见的复合块内部包含多个隐藏原子。
- RPEval 的生成 Judge 主要报告整体严格匹配、匹配条数和错误严重度；MemCalib 对每个原子显式恢复实际 A/B/C，并与该原子的规范 A/B/C 直接对齐。
- MemCalib 因而可以构造完整的逐原子规范—实际有序混淆矩阵，而不是仅判断回答总体是否符合预期策略。

最合适的写法是：RPEval 建立了偏好利用的三级规范与双向错误分析，MemCalib 将这一问题推进到复合、异质记忆输入下的逐原子实际影响校准。

## 5. BenchPreS：正式沟通中的情境性偏好门控

[BenchPreS](https://arxiv.org/abs/2603.16557) 以 persistent memory 为应用背景，但它**不评估外部记忆系统的检索、存储或更新**。论文明确说明其聚焦最终生成阶段，不覆盖 retrieval 或 external tools。

它给模型一个固定用户 profile，并测试其中的表达偏好在当前第三方正式沟通中是否适用。数据包含 10 个用户 profile 和 39 个 recipient–task 情境，覆盖金融、就业等五类正式沟通领域。偏好类型主要包括：

- role；
- style；
- tone；
- markers，例如 emoji；
- nickname。

例如，用户平时喜欢幽默、emoji 或活泼语气，并不意味着这些偏好应该出现在写给法院职员、税务人员或招生委员会的正式文本中。

### 5.1 评测机制

BenchPreS 通过人工标注为每个 context–preference pair 给出 Apply / Suppress gold label。生成后，再逐属性检测回答是否体现该偏好，并报告：

- **Misapplication Rate (MR)**：本应抑制却被错误应用；
- **Appropriate Application Rate (AAR)**：本应应用且正确应用。

这意味着它已经具备“逐属性规范标签 + 逐属性实际使用检测”，不能只概括为一个粗粒度二值 benchmark。

### 5.2 与 MemCalib 的实质重叠

- 都研究进入上下文的长期用户信息是否应该影响当前回答；
- 都将规范适用性落实到具体属性或原子，而非只评价整段回答是否个性化；
- 都同时暴露错误应用和未应用之间的权衡。

### 5.3 MemCalib 可成立的差异

- BenchPreS 的规范来源主要是社会与制度沟通规范；MemCalib 的规范来源更广，包括事实正确性、任务约束、偏好适用性和安全边界。
- BenchPreS 的实际检测是 applied/not-applied，无法区分偏好只影响局部表达，还是已经不当地控制核心结论。
- BenchPreS 没有专门测试一个自然语言父记忆内部存在多个不同使用等级的情况。
- MemCalib 的三级实际影响可捕捉“允许轻微润色，却被升级为核心限制”一类二值检测难以表达的错误。

反过来，BenchPreS 的人工 gold 构建更值得重视：它通过人工标注和歧义过滤限制文化与社会规范上的边界案例。MemCalib 若大量依赖自动构建和 LLM Judge，需要更强的人类一致性证据。

## 6. StratMem-Bench：候选记忆池中的选择与整合

[StratMem-Bench](https://arxiv.org/abs/2604.26243) 从 LoCoMo 构造虚拟角色对话。每个样本向模型提供：persona、dialogue history、当前 query，以及一个不带标签的 memory pool。模型直接看到所有候选 memory items，但看不到它们的功能角色，因此该 benchmark 同样不评估外部 retriever，而是评估给定候选池之后的选择与生成。

每条记忆被标注为：

- **must**：满足当前信息需求所必需，遗漏会造成错误或幻觉；
- **nice**：并非正确性所必需，但可增加个性化、共情、背景或社会连贯性；
- **irr**：不服务当前沟通目标，加入后会造成跑题或不合时宜。

### 6.1 它不只是一个二值 benchmark

回答端首先逐条判断某个 memory item 是否被使用，这一步是二值的；但整体评测还包括：

- **Strict Memory Compliance (SMC)**：使用全部 must、在存在 nice 时至少使用一条 nice、完全不使用 irr；
- **Memory Integration Quality (MIQ)**：以 1–5 分评价被选记忆是否自然、连贯地服务当前对话目标；
- **Proactive Enrichment Score (PES)**：使用 nice memory 主动丰富回答的倾向；
- **Conditional Irrelevance Rate (CIR)**：存在 nice memory 时错误加入 irr memory 的倾向。

因此，更准确的概括是：其单 item 使用检测是二值的，但同时显式评估了整合质量和主动丰富—风险规避之间的权衡。

### 6.2 与 MemCalib 的实质重叠

- 都超越事实回忆，直接研究响应生成中的策略性记忆使用；
- 都在同一输入中提供具有不同规范角色的多条信息；
- 都关心漏用必要信息、适当利用支持信息和抑制无关信息；
- 都使用隐藏标签，模型在生成时看不到 must/nice/irr 或 A/B/C。

### 6.3 MemCalib 可成立的差异

- StratMem 的候选记忆已经切成独立短 item；MemCalib 的原子边界在模型输入中不可见，多个原子被包装在自然语言父记忆里。
- StratMem 的 must/nice/irr 是功能角色，回答端逐 item 的直接观测仍是 used/not-used；MemCalib 的实际行为本身也是 A/B/C 有序强度。
- StratMem 的 nice 是集合级软目标：通常至少选择一条 nice 即可，并不要求每条 nice 都产生特定强度的影响；MemCalib 对每个 B 原子分别判断是否保持局部、受限的支持作用。
- StratMem 更强调角色对话自然性和整合质量；MemCalib 更强调细粒度方向性归因。

最清楚的区别是：

> StratMem-Bench 测量跨独立 memory items 的 selection and integration；MemCalib 测量复合 memory block 内部的 atomic disentanglement and influence calibration。

## 7. OP-Bench：端到端过度个性化诊断

[OP-Bench](https://arxiv.org/abs/2601.13722) 是端到端 memory-augmented agent 评测。它从 LoCoMo 长期对话中抽取用户 profile 和主题，构造 1,700 个专门诱发过度个性化的问题，并比较多个 LLM 与多个 memory-augmentation methods 的组合。

它定义三类过度个性化：

- **Irrelevance**：当前问题不需要个性化，却强行引用用户记忆或画像；
- **Sycophancy**：为了迎合用户记忆、观点或价值而牺牲事实性和客观性；
- **Repetition**：面对语义不同但相关的问题，反复调用相同记忆并产生高度相似的个性化回答。

### 7.1 它评估的是完整系统效应

OP-Bench 不只研究模型在固定记忆输入下如何生成，还比较无记忆 baseline 与不同记忆增强方案，并进一步分析：

- memory method 是否检索了无关记忆；
- 模型是否对检索结果赋予过高注意力；
- 记忆是否遮蔽当前 query 和正常推理；
- 在生成前增加 Self-ReCheck 过滤是否能缓解问题。

因此它的核心单位是“记忆系统 × backbone model × 最终失败类型”，而不是单条记忆原子的规范使用等级。

### 7.2 与 MemCalib 的关系

OP-Bench 为“记忆增强会系统性诱发过度个性化”提供了直接证据，这一风险动机与 MemCalib 高度一致。但两者的测量对象不同：

- OP-Bench 主要诊断过度方向，没有为每条记忆定义规范使用强度，也不对使用不足进行统一的对称建模；
- MemCalib 固定给定记忆输入，从而更容易把过度或不足追溯到具体隐藏原子；
- OP-Bench 能观察 retrieval 和 downstream use 的共同系统结果，MemCalib 当前不能直接定位检索阶段错误。

还应避免混淆 OP-Bench 的 Repetition 与 RPEval/MemCalib 的 RII：

- OP-Bench Repetition 偏向跨多个相关问题反复调用相同记忆、产生相似响应；
- RII 偏向单次回答中错误地同时包含一般内容与偏好内容，或把本应处于 A/C 极端的使用策略落在中间。

## 8. MemSyco-Bench：外部 Agent Memory 系统与后检索决策校准

[MemSyco-Bench](https://arxiv.org/abs/2607.01071) 是此次比较中必须新增的工作。它研究 **memory-induced sycophancy**：历史用户信念、偏好或过去决策被外部记忆系统重新检索后，在当前任务中获得了不应有的证据地位或决策权。

与传统 prompt 内谄媚不同，这种影响有三个特点：

- 来源不是当前问题中的显式用户立场，而是跨会话返回的历史记忆；
- 错误不只表现为语言上的同意，还可能表现为把记忆当事实证据、越过适用范围、压过客观证据或继续使用已经失效的旧偏好；
- 同一错误记忆可能长期保存并反复影响后续决策。

### 8.1 它确实直接评估外部记忆系统

MemSyco-Bench 的实验同时包含：

- NoMemory；
- RawDialogue / Full Dialog；
- NaiveRAG；
- Mem0；
- A-Mem；
- LightMem；
- MemGPT；
- MemoryBank；
- SuperMemory。

官方仓库报告共 **1,550 个最终样本**，包括四个 300 样本任务和一个 350 样本任务，并提供统一的记忆构建、检索、生成与 Judge 管线。[官方仓库](https://github.com/XMUDeepLIT/MemSyco-Bench)

所以，你之前所说的“偏向评估外部记忆系统”准确对应 MemSyco-Bench，而不是 BenchPreS。

### 8.2 五类任务覆盖“何时用”和“如何用”

MemSyco-Bench 通过五种 memory-decision schemas 定义记忆在当前任务中的决策边界：

1. **Objective Fact Judgment**：历史记忆即使熟悉或语义相关，也不能被当作客观事实证据。
2. **Contextual Scope Control**：某一偏好或习惯只在原有适用范围内有效，不能无条件迁移到其他对象、团队或约束。
3. **Memory-Evidence Conflict**：用户记忆与当前可验证证据冲突时，必须让证据优先。
4. **Valid Memory Selection**：偏好已经被更新、反转或替代时，应选择当前有效记忆，避免旧记忆污染。
5. **Personalized Memory Use**：当推荐、建议或主观选择确实需要个性化时，应正确使用有效偏好，而不是一律忽略记忆。

前三类主要测“记忆不应获得决定权”，后两类主要测“应该选择哪条有效记忆，以及是否真正用于个性化”。因此它并非只测过度方向，也包含有用记忆未被正确使用的能力侧评估。

### 8.3 指标与错误归因

它对所有任务报告 Generation Accuracy，并针对不同类别报告：

- **Sycophancy Rate**：在记忆不应主导时，回答是否沿着 memory-misleading direction 输出；
- **Correct Memory Use**：需要个性化时，是否真正使用有效记忆；
- **Outdated Memory Use**：偏好已更新后，是否仍然受旧记忆支配。

更关键的是，它把 retrieval 与 answer correctness 组合成 R+/A+、R+/A−、R−/A+、R−/A− 四种状态，从而区分：

- 没检索到需要的信息，因此答错；
- 已经检索到充分信息，但仍在生成或决策阶段用错。

论文报告，在重点分析的 Mem0、A-Mem 和 LightMem 上，约 61%–62% 的错误发生在相关信息已经被检索到之后。这说明现有外部记忆系统的问题不只是 recall 不足，还包括 memory-to-policy conversion、证据仲裁、适用范围判断和时序更新失败。

### 8.4 与 OP-Bench 的区别

两者都属于端到端外部记忆系统评测，但重点不同：

- OP-Bench 的风险 taxonomy 更宽，包括无关个性化、谄媚和跨问题重复；
- MemSyco-Bench 集中研究“历史记忆在当前决策中获得错误权威”，但对事实证据、适用范围、冲突、更新和有效个性化拆得更细；
- OP-Bench 强调记忆引入后的整体退化、注意力劫持和过滤缓解；
- MemSyco-Bench 更明确地区分 retrieval failure 与 post-retrieval decision failure。

### 8.5 与 MemCalib 的实质重叠

MemSyco-Bench 对 MemCalib 的贡献主张形成了比 OP-Bench 更直接的压力：

- 它已经明确提出“when and how retrieved memories should influence decisions”；
- 它不只覆盖偏好，还覆盖客观事实、范围限制、证据冲突、记忆更新和有效个性化；
- 它既包含应当抑制记忆的任务，也包含应当使用有效记忆的任务；
- 它使用实例级 rubric 规定记忆应有的决策角色和 memory-aligned failure direction。

因此，加入 MemSyco-Bench 后，MemCalib 更不适合声称：

- 首次研究记忆何时应该或不应该影响回答；
- 首次同时覆盖事实与偏好记忆的合理使用；
- 首次同时研究错误使用和有用记忆未被使用；
- 首次把检索后的记忆使用视为独立问题。

### 8.6 MemCalib 仍可成立的差异

MemSyco-Bench 的监督主要位于任务和场景层：每个 schema 规定正确答案、记忆应承担的决策角色以及错误方向。它没有对模型看到的每个复合记忆块拆出多个隐藏原子，也没有对每个原子同时恢复实际 A/B/C 影响等级。

因此二者的关系可以准确表述为：

> MemSyco-Bench 提供端到端系统有效性与 retrieval/use 错误归因；MemCalib 提供受控给定记忆条件下更细的逐原子、有序影响测量。

MemSyco-Bench 更接近真实部署链路，MemCalib 的优势则应是测量分辨率和归因粒度。二者是互补关系，而不是简单的覆盖范围竞争。

## 9. 加入 MemSyco-Bench 后，MemCalib 应如何重新定位

### 9.1 不再足够的差异点

以下表述单独使用时已经不足以区分 MemCalib：

- “超越事实回忆，评估记忆是否应该使用”；
- “同时关注过度使用和使用不足”；
- “采用 Ignore / Support / Dominate 三级标签”；
- “进行原子级标注”；
- “覆盖事实和偏好等异质记忆”；
- “研究检索后记忆如何影响下游回答”；
- “通过实例 rubric 描述记忆在当前任务中的作用”。

这些元素分别已被 RPEval、BenchPreS、StratMem-Bench 和 MemSyco-Bench 覆盖。

### 9.2 最强差异应落在表示层与测量层的组合

MemCalib 最有辨识度的设计仍然是：

1. **Model-facing representation**：模型看到的是自然语言非原子父记忆，而不是经过 gold 拆分的独立原子列表。
2. **Hidden atomic supervision**：评估端知道父记忆包含哪些原子，并允许同一父块内部出现不同规范角色。
3. **Ordered observed influence**：实际行为不是简单 detected/not-detected，而是逐原子的 A/B/C 影响等级。
4. **Symmetric directional attribution**：规范等级和实际等级处于同一有序空间，可直接定位过度与不足，并保留完整混淆模式。
5. **Instance-specific observable rubric**：每个原子的抽象等级被翻译为当前问题中可观察的正确使用、过度使用和不足使用行为。

这里真正重要的不是任何一个单独元素，而是它们的组合。尤其是以下案例，是现有邻近工作相对难以直接表达的：

> 一个模型可见的总结块同时包含事实、偏好和限制。其中某条事实与当前问题无关，应保持 A；某条偏好只允许局部影响表达或排序，应保持 B；某条安全或硬约束必须控制核心建议，应达到 C。模型可能引用了整块，却只对其中一部分赋予正确权重。

BenchPreS 能判断若干属性是否被应用，StratMem 能判断独立 items 是否被选择，RPEval 能给独立偏好分配三级角色，MemSyco-Bench 能判断端到端系统是否让历史记忆获得错误决策权；但 MemCalib 的目标是进一步判断同一可见复合块内部每个隐藏原子的实际影响是否恰好达到规范强度。

## 10. 推荐的 related-work 组织方式

论文中不宜继续按“哪篇最接近”简单排列。更清晰的结构是分成两层。

### 10.1 System-level memory risk benchmarks

- **OP-Bench**：证明外部记忆增强会诱发无关个性化、谄媚和重复，并分析 retrieval 与 memory over-attention。
- **MemSyco-Bench**：进一步以五类决策任务比较真实外部记忆框架，区分 retrieval failure 与 retrieved-but-misused failure。

这两篇说明：部署中的错误来自完整 memory pipeline，不能只看 recall。

### 10.2 Controlled post-retrieval memory-use benchmarks

- **BenchPreS**：逐偏好属性评价正式沟通中的 apply/suppress。
- **RPEval**：逐偏好标注 Ignore/Support/Dominate，并以错误 taxonomy 评价偏好对用户意图的合理影响。
- **StratMem-Bench**：逐 memory item 标注 must/nice/irr，并评价选择、主动丰富与整合质量。
- **MemCalib**：在复合记忆输入下，将评价单位推进到隐藏原子，并在规范端和实际端使用同一个有序影响空间。

这样组织后，MemCalib 既不会与端到端系统 benchmark 混为一谈，也不会低估后三项工作已经提供的细粒度监督。

## 11. 可直接用于论文的中文总结段落

近期研究已从长期记忆的存储与检索能力推进到记忆对下游回答的适当影响。系统层面的 OP-Bench 比较多种记忆增强方案，揭示无关个性化、谄媚与重复等端到端失效；MemSyco-Bench 进一步以事实判断、适用范围、证据冲突、记忆更新和有效个性化五类任务评估外部 Agent Memory 系统，并区分检索失败与检索成功后的决策误用。在给定记忆的受控设置下，BenchPreS 逐属性评价正式沟通中的偏好应用与抑制，RPEval 为偏好—问题对标注 Ignore、Support 和 Dominate 并分析双向使用错误，StratMem-Bench 则区分 required、supportive 与 irrelevant memory items，并评价记忆选择和整合质量。不同于上述工作，MemCalib 不将模型输入预先简化为独立、带原子边界的记忆条目，而是保留现实记忆系统可能返回的非原子总结块，同时在评估端维护隐藏原子命题、逐原子规范等级和实例化 rubric。通过在同一 A/B/C 有序空间中比较每个原子的规范影响与实际影响，MemCalib 旨在测量同一可见记忆块内部的差异化使用，并对过度使用和使用不足进行细粒度方向性归因。

## 12. 可直接用于论文的英文定位段落

Recent work has shifted long-term memory evaluation from storage and retrieval toward the appropriateness of memory influence on downstream responses. At the system level, OP-Bench diagnoses irrelevance, sycophancy, and repetition across memory-augmented agents, while MemSyco-Bench evaluates external agent-memory systems across factual judgment, scope control, evidence conflict, memory updates, and valid personalization, explicitly separating retrieval failures from post-retrieval misuse. Under controlled, given-memory settings, BenchPreS measures attribute-level preference application and suppression in formal communication, RPEval assigns Ignore, Support, and Dominate roles to preference–query pairs, and StratMem-Bench evaluates the selection and integration of required, supportive, and irrelevant memory items. MemCalib differs in the joint design of its representation and measurement layers: models receive realistic non-atomic memory blocks, whereas evaluation retains hidden atomic propositions, instance-specific usage rubrics, and ordered target roles. By recovering the realized influence of each atom in the same ordered space, MemCalib measures within-block differential use and attributes both over-use and under-use at the atomic level.

## 13. 主张边界

### 可以强调

- 面向非原子长期记忆输入的隐藏原子级有序影响校准；
- 模型输入粒度与评估监督粒度的显式分离；
- 同一可见父块内部混合 A/B/C 规范角色；
- 对每个原子同时建模规范等级和实际影响等级；
- 在统一有序混淆矩阵中对 OPB 与 UPB 进行方向性归因；
- 与端到端 memory-system benchmark 互补的 post-retrieval diagnostic protocol。

### 应避免

- 首个研究记忆何时应该使用的 benchmark；
- 首个三级记忆使用 benchmark；
- 首个兼顾过度个性化与个性化不足的 benchmark；
- 首个原子级记忆适用性 benchmark；
- 首个研究检索后错误使用的 benchmark；
- 首个覆盖事实、偏好、约束或更新冲突的合理记忆使用 benchmark；
- 直接声称优于端到端外部记忆系统评测，而未增加 retrieval-aware track。

## 14. 对实验设计的直接启示

新增 MemSyco-Bench 后，MemCalib 最值得补强的实验不是继续扩大抽象标签解释，而是证明其细粒度协议确实提供了额外诊断能力：

1. 单独报告 mixed-label parent blocks，证明同一块内部差异化使用比独立 atom 输入更难；
2. 对比二值 used/not-used 与三级 actual influence，展示哪些错误只有有序影响标签能够发现；
3. 报告逐原子的规范—实际混淆矩阵，而不只给聚合 H 分数；
4. 增加一个 retrieval-aware track，把不同外部记忆系统返回的块输入 MemCalib，从而区分 retrieval、representation 和 downstream influence 三类错误；
5. 在人工验证中分别测量原子边界、规范等级、实际影响等级和 Judge rubric 的一致性；
6. 加入事实证据冲突、适用范围变化和旧偏好更新等案例，以正面回应 MemSyco-Bench 已经覆盖的决策场景。

## 参考文献与原始资源

- Feng et al. [How Does Personalized Memory Shape LLM Behavior? Benchmarking Rational Preference Utilization in Personalized Assistants](https://arxiv.org/abs/2601.16621). 2026.
- Yoon et al. [BenchPreS: A Benchmark for Context-Aware Personalized Preference Selectivity of Persistent-Memory LLMs](https://arxiv.org/abs/2603.16557). 2026.
- Wu et al. [StratMem-Bench: Evaluating Strategic Memory Use in Virtual Character Conversation Beyond Factual Recall](https://arxiv.org/abs/2604.26243). ACL 2026.
- Hu et al. [OP-Bench: Benchmarking Over-Personalization for Memory-Augmented Personalized Conversational Agents](https://arxiv.org/abs/2601.13722). 2026.
- Xiang et al. [MemSyco-Bench: Benchmarking Sycophancy in Agent Memory](https://arxiv.org/abs/2607.01071). 2026.
- [MemSyco-Bench official repository](https://github.com/XMUDeepLIT/MemSyco-Bench).
