# MemCalib v2.4.1：DeepSeek-V4-Pro Judge 三轮 Non-Think 评测

2 个回答模型在同一组锁定的 1,500 条样本上独立调用 3 次；本次评测条件为 full_memory。所有主判分都由 DeepSeek-V4-Pro 在关闭 thinking 的条件下独立完成。下表是各轮 Full-memory 的均值；`+/-` 后为总体标准差（population SD）。

| 模型键 | 模型 | SCS | sOPB | sUPB | Any OPB | Any UPB | Exact | 原子 H |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ministral3-8b-instruct-2512-bf16-local-vllm | ministral3-8b-instruct-2512-bf16-local-vllm | 30.41% +/- 0.13 pp | 59.12% +/- 0.06 pp | 24.10% +/- 0.22 pp | 75.62% +/- 0.03 pp | 37.00% +/- 0.28 pp | 14.84% +/- 0.21 pp | 84.56% +/- 0.17 pp |
| qwen35-35b-a3b-local-vllm | qwen35-35b-a3b-local-vllm | 24.59% +/- 0.12 pp | 67.74% +/- 0.16 pp | 18.55% +/- 0.26 pp | 83.20% +/- 0.14 pp | 29.82% +/- 0.52 pp | 10.13% +/- 0.16 pp | 86.85% +/- 0.09 pp |

每轮原始值、均值、总体标准差、最小值和最大值见 `aggregate-metrics.json` 与 `aggregate-metrics.csv`。
