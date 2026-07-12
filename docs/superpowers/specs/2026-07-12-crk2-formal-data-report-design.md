# CRK-2 Formal Dataset Statistical Report Design

## Objective

Produce a polished, self-contained HTML report for the complete formal CRK-2 benchmark. The report must support both paper writing and internal data-quality review. All quantitative claims must be recomputed from the final benchmark JSONL rather than copied from an earlier summary.

## Audience And Delivery

- Primary audience: benchmark authors and technical reviewers.
- Secondary use: figures and tables that can be adapted for the paper or appendix.
- Delivery: one offline, self-contained HTML file plus a compact machine-readable analysis snapshot.
- Analysis runtime: `/Users/zhaofanyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`; Conda must not be used.

## Source Of Truth

- Formal benchmark: `med_rpeval_pipeline/data/crk2_canonical_memory_benchmark_en_15528.jsonl`.
- Construction rejects: `med_rpeval_pipeline/data/crk2_canonical_memory_benchmark_en_15528.rejected.jsonl`.
- Run lineage: `med_rpeval_pipeline/data/crk2_canonical_generation_run_en_15577.lock.json`.
- Existing summary is used only for reconciliation, not as the analytical input.

## Report Structure

1. Technical summary with benchmark scale, atomic-memory scale, label mix, and final QC status.
2. Construction funnel from the 30,000-record semantic-QC pool to the 15,528-record formal benchmark.
3. Source and topic coverage, including concentration and source balance.
4. Memory structure and atomization, including parent blocks, atomic memories, atoms per parent, and mixed-label parents.
5. A/B/C distributions overall and crossed with topic, source dataset, and memory type.
6. Hard-A family distribution and synthetic-memory footprint.
7. Text and rubric complexity distributions, including robust quantiles and long-tail cases.
8. Paper-ready tables with exact counts, shares, denominators, and metric definitions.
9. Quality findings, limitations, robustness checks, and concrete next validation steps.
10. Reproducibility metadata with source paths, hashes, filters, and generation time.

## Analytical Definitions

- Sample grain: one benchmark record.
- Parent-memory grain: one `memory_blocks[]` item.
- Atomic-memory grain: one `memories[]` item.
- Atomization ratio: atomic-memory count divided by parent-memory count.
- Mixed parent: a parent whose linked atoms contain more than one A/B/C label.
- Synthetic footprint: atomic memories with `source = synthetic_hard_a` divided by all atomic memories.
- Topic/source shares: count divided by all formal samples.
- Label shares: atomic label count divided by all atomic memories.
- Length metrics: Unicode character counts on generated question, stored-memory text, and serialized judge-rubric natural-language fields. Source evidence is measured separately.
- Distribution summaries: minimum, median, mean, p90, p95, p99, and maximum where useful. The report makes descriptive claims only.

## Visual Design

- Light technical-report surface with high-contrast charcoal text.
- Restrained palette: blue for primary distributions, gold for secondary comparison, pink for risks, olive for QC/context, and neutral greys.
- Chart types: ranked bars, 100% stacked bars, histograms, distribution summaries, and topic-label heatmaps.
- Charts use zero baselines for absolute magnitude and direct labels where feasible.
- The reading path remains report-like rather than dashboard-like; there are no filters or operational controls.
- Layout must remain readable on laptop and narrow mobile widths.

## Reproducibility And QA

- A dedicated analysis script streams the 276 MB JSONL and writes bounded aggregate datasets.
- Aggregates must reconcile with the final summary for sample, memory, label, source, and memory-type counts.
- The canonical report artifact must pass the Data Analytics artifact validator.
- The portable HTML packager must pass structural and browser verification without network requests.
- Final QA checks title/section visibility, chart count, table count, overflow, source affordances, and exact embedded artifact equality.

## Explicit Limitations

- Both current source datasets are health-domain datasets, so topic diversity is intra-domain rather than general-dialogue diversity.
- Hard-A memories are synthetic and therefore require separate interpretation from extracted B/C memories.
- Automatic construction QC does not replace stratified human audit, counterfactual response testing, or judge calibration.
- Free-form subtype values are descriptive and must not be treated as a controlled benchmark taxonomy.

## Outputs

- `med_rpeval_pipeline/24_analyze_crk2_formal_benchmark.py`
- `med_rpeval_pipeline/data/crk2_formal_benchmark_analysis.snapshot.json`
- `med_rpeval_pipeline/data/crk2_formal_benchmark_analysis.artifact.json`
- `med_rpeval_pipeline/data/crk2_formal_benchmark_analysis_report.html`
