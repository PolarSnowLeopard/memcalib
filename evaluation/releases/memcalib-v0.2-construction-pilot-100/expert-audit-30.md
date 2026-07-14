# MemCalib v0.2 专家协议验收（30 条）

> 这是风险富集压力审查，覆盖全部 QC reject、correct-action 和 strict-pass 多原子 parent；不能把结果直接外推为 100 条总体缺陷率。

## 结论

- Accept: 2
- Revise: 28
- Reject: 0
- Strict-pass 压力样本非直接可用率: 19/21 (90.5%)
- QC reject 记录级误拒绝率: 0/9 (0.0%)
- QC reject 理由完全一致率: 6/9 (66.7%)

## 逐条结论

| # | ID | 原 QC | 专家结论 | 主要问题 |
|---:|---|---|---|---|
| 1 | `crk2_v2_raw_75fde6e8a080b15a` | reject | **revise** | atomicity, domain_validity |
| 2 | `crk2_v2_raw_61d6eb00fc3ead91` | reject | **revise** | atomicity |
| 3 | `crk2_v2_raw_c8cb3196613c5f4a` | reject | **revise** | query_isolation, counterfactual |
| 4 | `crk2_v2_raw_c40752621dc51bdd` | reject | **revise** | domain_validity, rubric_objectivity |
| 5 | `crk2_v2_raw_7d9177752d7618aa` | reject | **revise** | atomicity, label_action, domain_validity |
| 6 | `crk2_v2_raw_5d038a548ddf8731` | reject | **revise** | atomicity, label_action |
| 7 | `crk2_v2_raw_a4e55eeb7d269253` | reject | **revise** | query_isolation, counterfactual, domain_validity |
| 8 | `crk2_v2_raw_9461d255ce2a44ec` | reject | **revise** | query_isolation, atomicity, rubric_objectivity |
| 9 | `crk2_v2_raw_26c6fbefc9522523` | reject | **revise** | evidence_grounding, label_action |
| 10 | `crk2_v2_raw_2cdd1fd7311f47f1` | strict_pass | **revise** | atomicity, domain_validity, label_action |
| 11 | `crk2_v2_raw_b9734bd71ff351b9` | strict_pass | **revise** | atomicity, domain_validity |
| 12 | `crk2_v2_raw_8df210a8dc7022be` | strict_pass | **accept** | none |
| 13 | `crk2_v2_raw_bff211b8a4c49473` | strict_pass | **accept** | none |
| 14 | `crk2_v2_raw_f1454195874f9b4d` | strict_pass | **revise** | atomicity, label_action, domain_validity |
| 15 | `crk2_v2_raw_38852650a3c9c7e2` | strict_pass | **revise** | atomicity, domain_validity, rubric_objectivity |
| 16 | `crk2_v2_raw_892d28bf65cd4adc` | strict_pass | **revise** | label_action, domain_validity |
| 17 | `crk2_v2_raw_e5e4f4f171248f99` | strict_pass | **revise** | domain_validity, label_action |
| 18 | `crk2_v2_raw_fa6fbd9026903b86` | strict_pass | **revise** | atomicity, label_action, domain_validity |
| 19 | `crk2_v2_raw_d18fd83d9be88b1e` | strict_pass | **revise** | atomicity, label_action, counterfactual |
| 20 | `crk2_v2_raw_457919ed1e0c113b` | strict_pass | **revise** | label_action, domain_validity |
| 21 | `crk2_v2_raw_7db9e3b4698c8c4c` | strict_pass | **revise** | atomicity, label_action, counterfactual, domain_validity |
| 22 | `crk2_v2_raw_5d7477a5bb17e3e3` | strict_pass | **revise** | domain_validity, label_action |
| 23 | `crk2_v2_raw_455c75ba8b8059f4` | strict_pass | **revise** | atomicity, label_action, domain_validity |
| 24 | `crk2_v2_raw_ded7c07dc153f3ab` | strict_pass | **revise** | query_isolation, domain_validity |
| 25 | `crk2_v2_raw_5940c488293cec2b` | strict_pass | **revise** | domain_validity, label_action |
| 26 | `crk2_v2_raw_38798fb3a9647cfa` | strict_pass | **revise** | atomicity |
| 27 | `crk2_v2_raw_df3ce1d2f6c1b6b5` | strict_pass | **revise** | domain_validity, label_action, rubric_objectivity |
| 28 | `crk2_v2_raw_001e72470aed7f30` | strict_pass | **revise** | label_action, hard_a_validity |
| 29 | `crk2_v2_raw_ffbaee05ebc61e61` | strict_pass | **revise** | atomicity, domain_validity |
| 30 | `crk2_v2_raw_406d142298ad0341` | strict_pass | **revise** | atomicity, hard_a_validity |

## 协议决策

当前 v0.2 不能直接冻结并扩展。优先修订原子边界、反事实可归因性、医学/领域正确性与 hard-A 零足迹验证，再用同一 100 条候选重建并重复独立 QC 和 30 条压力审查。
