---
language:
- en
license: apache-2.0
size_categories:
- 100K<n<1M
task_categories:
- text-generation
- question-answering
tags:
- medical
- dialogue
- doctor-patient
- healthcare
- openmed
- clinical
- question-answering
pretty_name: MedDialog
dataset_info:
  features:
  - name: patient_message
    dtype: string
  - name: doctor_response
    dtype: string
  - name: dialogue_context
    dtype: string
  splits:
  - name: train
    num_examples: 226557
  - name: validation
    num_examples: 25174
  config_names:
  - default
source_datasets:
- ruslanmv/ai-medical-chatbot
---

# MedDialog

A large-scale medical dialogue dataset containing ~252k patient-doctor conversation pairs for training and evaluating clinical dialogue systems.

## Dataset Description

| Property | Value |
|---|---|
| **Source** | [ruslanmv/ai-medical-chatbot](https://huggingface.co/datasets/ruslanmv/ai-medical-chatbot) |
| **License** | [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0) |
| **Language** | English |
| **Total examples** | 251,731 |
| **Train split** | 226,557 |
| **Validation split** | 25,174 |
| **Domain** | Clinical / General Medicine |

### Overview

MedDialog is designed for training language models to generate medically appropriate, empathetic, and safe doctor responses given a patient query. It covers a broad range of medical topics including symptoms, diagnoses, medications, procedures, and general health questions.

## Dataset Structure

### Fields

| Field | Type | Description |
|---|---|---|
| `patient_message` | `string` | The patient's description of symptoms or medical question |
| `doctor_response` | `string` | The doctor's response (ground truth reference) |
| `dialogue_context` | `string` | Additional context (reserved for multi-turn; empty in current version) |

### Statistics

| Metric | Patient Message | Doctor Response |
|---|---|---|
| Min length (chars) | 22 | 41 |
| Median length (chars) | 414 | 481 |
| Mean length (chars) | 492 | 546 |
| Max length (chars) | 2,500 | 2,500 |

## Example

**Patient:**
> I have been experiencing severe headaches for the past week, mostly in the morning. The pain is throbbing and located on the right side of my head. I also feel nauseous sometimes. What could be causing this?

**Doctor:**
> I understand how concerning persistent headaches can be, especially when accompanied by nausea. Based on your description of throbbing, one-sided pain with morning occurrence, this could potentially be migraines, though we'd need a proper evaluation to be sure.
>
> I'd recommend:
> 1. Keep a headache diary noting triggers, duration, and severity
> 2. Ensure you're staying hydrated and getting adequate sleep
> 3. Avoid known migraine triggers like bright lights or certain foods
>
> However, given the duration and severity, I strongly advise scheduling an appointment with your doctor for a proper examination.

## Data Processing

This dataset was derived from [ruslanmv/ai-medical-chatbot](https://huggingface.co/datasets/ruslanmv/ai-medical-chatbot) (257k raw examples) with the following processing steps:

1. **Field combination**: Merged `Description` and `Patient` fields into `patient_message`
2. **Quality filtering**: Removed examples with very short messages (<5 words patient, <10 words doctor)
3. **Redirect filtering**: Excluded entries where the doctor response was only a referral with no content
4. **Truncation**: Capped messages at 2,500 characters
5. **Split**: 90/10 train/validation split with random seed 42

## Usage

### Loading with `datasets`

```python
from datasets import load_dataset

ds = load_dataset("OpenMed/MedDialog")
train = ds["train"]
val = ds["validation"]

print(train[0]["patient_message"])
print(train[0]["doctor_response"])
```

### With Prime Intellect RL Environment

This dataset is used by the `maziyar/OpenMed_MedDialog` RL environment for training models via reinforcement learning with the following reward components:

| Component | Weight | Description |
|---|---|---|
| Response Quality | 35% | Relevance, helpfulness, medical appropriateness |
| Empathy & Communication | 25% | Patient-centered language, acknowledgment |
| Medical Content | 20% | Addresses symptoms/concerns with relevant information |
| Safety | 10% | Appropriate disclaimers, recommends professional consultation |
| Fluency | 10% | Coherent, well-structured responses |

```bash
prime env install maziyar/OpenMed_MedDialog
```

## License

This dataset is released under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0), inherited from the source dataset [ruslanmv/ai-medical-chatbot](https://github.com/ruslanmv/ai-medical-chatbot).

## Limitations and Ethical Considerations

- This dataset is intended for **research purposes only** and should not be used as a substitute for professional medical advice
- Doctor responses in the source data vary in quality and may contain inaccuracies
- The dataset reflects patterns from online medical Q&A platforms, which may not represent clinical best practices
- Models trained on this data should include appropriate disclaimers about the limitations of AI-generated medical advice

## Citation

If you use this dataset, please cite:

```bibtex
@dataset{openmed_meddialog_2026,
  title={MedDialog: A Medical Dialogue Dataset for Clinical Response Generation},
  author={OpenMed},
  year={2026},
  publisher={Hugging Face},
  url={https://huggingface.co/datasets/OpenMed/MedDialog}
}
```

## Part of OpenMed

This dataset is part of the [OpenMed](https://huggingface.co/OpenMed) collection of open medical NLP resources for research and development.
