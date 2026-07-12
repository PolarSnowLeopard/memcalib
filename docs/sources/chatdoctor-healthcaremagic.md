# lavita/ChatDoctor-HealthCareMagic-100k

## Upstream Record

- Identifier: `lavita/ChatDoctor-HealthCareMagic-100k`
- URL: https://huggingface.co/datasets/lavita/ChatDoctor-HealthCareMagic-100k
- Records reported by the dataset card: 112,165
- Format: Parquet
- Main fields: `instruction`, `input`, `output`
- Associated paper: https://arxiv.org/abs/2303.14070

## Use In MemCalib

MemCalib normalizes the patient-style input as a source question and the output as retained source answer evidence. The formal release contains 7,765 samples from this source after deterministic filtering, deduplication, semantic QA, strict admission, and construction QC.

## Rights And Risk Status

The current upstream dataset card does not specify a license. MemCalib does not infer redistribution permission from public availability. Derived release data is restricted to private co-author review until rights are clarified.

The source contains real-world-style medical narratives and may include sensitive or identifying details. Public release requires a dedicated PII and sensitive-content audit.

