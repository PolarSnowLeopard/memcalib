# MemCalib v0.2 专家协议验收（30 条）

> 这是风险富集审查，覆盖全部 QC reject、correct-action 和 strict-pass 多原子 parent。最终结论采用实用验收门槛；非阻断问题保留为改进建议，不能把结果直接外推为 100 条总体缺陷率。

## 结论

- Accept: 19
- Revise: 11
- Reject: 0
- Strict-pass 压力样本非直接可用率: 6/21 (28.6%)
- QC reject 记录级误拒绝率: 4/9 (44.4%)
- QC reject 理由完全一致率: 6/9 (66.7%)

## 逐条结论

| # | ID | 原 QC | 专家结论 | 观察项 / 阻断问题 |
|---:|---|---|---|---|
| 1 | `crk2_v2_raw_75fde6e8a080b15a` | reject | **accept** | atomicity, domain_validity |
| 2 | `crk2_v2_raw_61d6eb00fc3ead91` | reject | **accept** | atomicity |
| 3 | `crk2_v2_raw_c8cb3196613c5f4a` | reject | **revise** | query_isolation, counterfactual |
| 4 | `crk2_v2_raw_c40752621dc51bdd` | reject | **accept** | domain_validity, rubric_objectivity |
| 5 | `crk2_v2_raw_7d9177752d7618aa` | reject | **revise** | atomicity, label_action, domain_validity |
| 6 | `crk2_v2_raw_5d038a548ddf8731` | reject | **accept** | atomicity, label_action |
| 7 | `crk2_v2_raw_a4e55eeb7d269253` | reject | **revise** | query_isolation, counterfactual, domain_validity |
| 8 | `crk2_v2_raw_9461d255ce2a44ec` | reject | **revise** | query_isolation, atomicity, rubric_objectivity |
| 9 | `crk2_v2_raw_26c6fbefc9522523` | reject | **revise** | evidence_grounding, label_action |
| 10 | `crk2_v2_raw_2cdd1fd7311f47f1` | strict_pass | **accept** | atomicity, domain_validity, label_action |
| 11 | `crk2_v2_raw_b9734bd71ff351b9` | strict_pass | **accept** | atomicity, domain_validity |
| 12 | `crk2_v2_raw_8df210a8dc7022be` | strict_pass | **accept** | none |
| 13 | `crk2_v2_raw_bff211b8a4c49473` | strict_pass | **accept** | none |
| 14 | `crk2_v2_raw_f1454195874f9b4d` | strict_pass | **accept** | atomicity, label_action, domain_validity |
| 15 | `crk2_v2_raw_38852650a3c9c7e2` | strict_pass | **accept** | atomicity, domain_validity, rubric_objectivity |
| 16 | `crk2_v2_raw_892d28bf65cd4adc` | strict_pass | **revise** | label_action, domain_validity |
| 17 | `crk2_v2_raw_e5e4f4f171248f99` | strict_pass | **revise** | domain_validity, label_action |
| 18 | `crk2_v2_raw_fa6fbd9026903b86` | strict_pass | **revise** | atomicity, label_action, domain_validity |
| 19 | `crk2_v2_raw_d18fd83d9be88b1e` | strict_pass | **accept** | atomicity, label_action, counterfactual |
| 20 | `crk2_v2_raw_457919ed1e0c113b` | strict_pass | **accept** | label_action, domain_validity |
| 21 | `crk2_v2_raw_7db9e3b4698c8c4c` | strict_pass | **accept** | atomicity, label_action, counterfactual, domain_validity |
| 22 | `crk2_v2_raw_5d7477a5bb17e3e3` | strict_pass | **revise** | domain_validity, label_action |
| 23 | `crk2_v2_raw_455c75ba8b8059f4` | strict_pass | **accept** | atomicity, label_action, domain_validity |
| 24 | `crk2_v2_raw_ded7c07dc153f3ab` | strict_pass | **accept** | query_isolation, domain_validity |
| 25 | `crk2_v2_raw_5940c488293cec2b` | strict_pass | **revise** | domain_validity, label_action |
| 26 | `crk2_v2_raw_38798fb3a9647cfa` | strict_pass | **accept** | atomicity |
| 27 | `crk2_v2_raw_df3ce1d2f6c1b6b5` | strict_pass | **revise** | domain_validity, label_action, rubric_objectivity |
| 28 | `crk2_v2_raw_001e72470aed7f30` | strict_pass | **accept** | label_action, hard_a_validity |
| 29 | `crk2_v2_raw_ffbaee05ebc61e61` | strict_pass | **accept** | atomicity, domain_validity |
| 30 | `crk2_v2_raw_406d142298ad0341` | strict_pass | **accept** | atomicity, hard_a_validity |

## 协议决策

当前流程总体可用，无需重建全部 100 条。先定向修复 11 条存在阻断问题的样本，再进行一次轻量抽查即可冻结本轮试点；其余严格审查观察项作为后续版本优化建议，不阻止当前样本使用。
