# Attribution And Rights Notice

MemCalib v2.3 is an internal research derivative of eight upstream datasets. The table below reports the metadata carried by the locked v2.3 release; it is an audit record, not a legal determination or a grant of redistribution rights.

| Domain | Upstream dataset | Upstream page | v2.3 records | License recorded in v2.3 |
|---|---|---|---:|---|
| health | OpenMed/MedDialog | https://huggingface.co/datasets/OpenMed/MedDialog | 3,793 | unknown |
| health | lavita/ChatDoctor-HealthCareMagic-100k | https://huggingface.co/datasets/lavita/ChatDoctor-HealthCareMagic-100k | 3,707 | unknown |
| general | HuggingFaceH4/ultrachat_200k | https://huggingface.co/datasets/HuggingFaceH4/ultrachat_200k | 2,377 | MIT |
| general | OpenAssistant/oasst1 | https://huggingface.co/datasets/OpenAssistant/oasst1 | 470 | Apache-2.0 |
| general | OpenAssistant/oasst2 | https://huggingface.co/datasets/OpenAssistant/oasst2 | 903 | Apache-2.0 |
| coding | ise-uiuc/Magicoder-OSS-Instruct-75K | https://huggingface.co/datasets/ise-uiuc/Magicoder-OSS-Instruct-75K | 2,771 | MIT |
| coding | codeparrot/apps | https://huggingface.co/datasets/codeparrot/apps | 174 | MIT |
| coding | HuggingFaceH4/stack-exchange-preferences | https://huggingface.co/datasets/HuggingFaceH4/stack-exchange-preferences | 805 | CC-BY-SA-4.0 |

## Health Sources

The v2.3 release conservatively records both health sources as license unknown. Earlier local documentation observed an Apache-2.0 declaration for an OpenMed/MedDialog dataset card, but that license was not normalized into the final release metadata and has not been treated as sufficient clearance for the derivative release. The ChatDoctor-HealthCareMagic dataset card did not provide a resolved license in the construction audit.

Health questions are real-world-style medical text and may contain inaccurate, outdated, unsafe, personal, or sensitive information. Quality control does not establish medical truth, complete de-identification, or redistribution permission.

## General And Coding Sources

The release preserves the dataset identifier, split, source ID, license field, and available source metadata for general and coding records. Dataset-level MIT or Apache metadata does not automatically resolve all rights in underlying conversations, code, questions, answers, or derivative transformations.

Magicoder instructions are synthesized from open-source code seeds, and APPS contains programming-problem material. Public release requires a separate provenance review of underlying content, not only the dataset-card license field.

## Stack Exchange Attribution

Stack Exchange-derived records are marked CC-BY-SA-4.0 in the release metadata. Admission required complete attribution enrichment. All 805 selected records retain the available author/source metadata; 67 strict candidates with incomplete attribution were excluded before source admission.

Any public redistribution or adaptation must preserve the applicable attribution, notice, link, and share-alike obligations after legal review. MemCalib's transformation and aggregation do not waive upstream terms.

## Release Restriction

This repository and the v2.3 handoff package are restricted to private coauthor research review and controlled internal experimentation. No repository-wide code license or data license is granted. Public release remains blocked pending:

1. source-by-source redistribution and derivative-rights confirmation;
2. Stack Exchange attribution and share-alike compliance review;
3. PII, sensitive-content, medical-safety, and code-provenance review;
4. final author approval of the public artifact, documentation, and licensing terms.

All trademarks, dataset names, source content, and author contributions remain subject to their respective owners and upstream terms.

Historical v0.1, v2.0, v2.1, v2.2, and pilot notices remain relevant only to their archived release packages; the counts and source usage in this document are the current MemCalib v2.3 release state.
