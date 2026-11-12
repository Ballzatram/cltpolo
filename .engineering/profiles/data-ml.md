# Data, notebooks and machine learning

Extends DATA-01, TEST-01/02, BUILD-01 and AI-01.

- MUST define data provenance, schema, access, classification, retention and quality checks. Keep raw sensitive data and credentials out of Git and fixtures.
- MUST separate reproducible transformations from notebook exploration. Clear sensitive/oversized notebook outputs; make maintained workflows executable from a clean environment.
- MUST version code, configuration, dependency environment and input/model references. Record seeds and nondeterminism limits; do not promise exact reproducibility when the platform cannot provide it.
- MUST test schema drift, nulls, duplicates, boundary values, invalid records, empty batches and reruns. Define reconciliation, quarantine and recovery from partial loads.
- For models, MUST separate training/validation/test data appropriately, test leakage and document metrics, evaluation sets, limitations and rollback. Evaluate relevant privacy, bias and abuse risks.
- For model/LLM integrations, MUST test prompt/tool boundaries, untrusted input, failure behavior, evaluation regressions and latency/cost budgets. Treat outputs as untrusted; do not grant a model unchecked authority over protected operations.
- MUST monitor data quality and model/inference behavior in production, with ownership and a fallback/retraining procedure as appropriate.

Evidence: data contract tests, reproducible run record, lineage, evaluation report, recovery checks and monitoring. Code coverage alone says little about model quality.
