# OpenMed/MedDialog

## Upstream Record

- Identifier: `OpenMed/MedDialog`
- URL: https://huggingface.co/datasets/OpenMed/MedDialog
- Records reported by the local dataset card: 251,731
- Main fields: `patient_message`, `doctor_response`, `dialogue_context`
- Declared license: Apache-2.0
- Upstream source named by the card: `ruslanmv/ai-medical-chatbot`

## Use In MemCalib

MemCalib uses patient messages as source questions and doctor responses as retained construction evidence. The formal release contains 7,763 samples from this source after deterministic filtering, deduplication, semantic QA, strict admission, and construction QC.

## Risks

The source answers vary in quality and are not clinical reference standards. Medical text may contain sensitive information, inaccurate advice, or outdated recommendations. MemCalib does not endorse the source answers and does not use them as gold final responses.

