---
configs:
- config_name: default
  data_files:
  - split: train
    path: data/train-*
dataset_info:
  features:
  - name: instruction
    dtype: string
  - name: input
    dtype: string
  - name: output
    dtype: string
  splits:
  - name: train
    num_bytes: 126454896
    num_examples: 112165
  download_size: 70518148
  dataset_size: 126454896
---
# Dataset Card for "ChatDoctor-HealthCareMagic-100k"

[More Information needed](https://github.com/huggingface/datasets/blob/main/CONTRIBUTING.md#how-to-contribute-to-the-dataset-cards)