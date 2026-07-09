# Medical Public QA -> RPEval Pipeline

This folder converts downloaded public medical QA data into RPEval-style train/val/test records.

Input sources:
- `../MedDialog/train.json`
- `../MedDialog/validation.json`
- `../ChatDoctor-HealthCareMagic-100k/data/*.parquet`

Main output:
- `data/rpeval_med_public/rpeval_med_public_train.json`
- `data/rpeval_med_public/rpeval_med_public_val.json`
- `data/rpeval_med_public/rpeval_med_public_test.json`
- `data/rpeval_med_public/rpeval_med_public_audit.jsonl`

Open the HTML plan:

```bash
open docs/medical_public_rpeval_pipeline.html
```

The default pipeline now uses Bailian/DashScope OpenAI-compatible API calls with retry, rate limiting, and resume support:

```text
normalize public QA
  -> prepare generation requests
  -> Bailian API fact-relocation generation
  -> local post/validation
  -> prepare verifier requests
  -> Bailian API verification
  -> final local QA and split
```

Recommended target:
- sample up to 15,000 records from `OpenMed/MedDialog`
  - balanced 1:1 between MedDialog train and validation by default
  - balanced across coarse topics such as symptoms, medication/treatment, pregnancy/reproductive, pediatrics, chronic disease, etc.
- sample up to 15,000 records from `lavita/ChatDoctor-HealthCareMagic-100k`
  - balanced across the same coarse topics
- final split: 10,000 RL train, 4,000 SFT reserved, 500 test, and remaining high-quality data in `unused`

```bash
export DASHSCOPE_API_KEY=<your-key>

python3 00_normalize_sources.py
python3 01_prepare_generation.py
python3 06_run_bailian_api.py --input data/crawl_generation_input.jsonl --output data/crawl_generation_result.jsonl
python3 02_post_generation.py --input data/crawl_generation_result.jsonl
python3 03_prepare_verification.py
python3 06_run_bailian_api.py --input data/crawl_verify_input.jsonl --output data/crawl_verify_result.jsonl
python3 04_post_verification.py --input data/crawl_verify_result.jsonl
python3 05_build_splits.py --write-parquet
```
