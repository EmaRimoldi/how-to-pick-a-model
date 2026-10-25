# LLM Router Context Search on HumanEval+

The completed `router-search-20260712` run selects a model/context setting on a
validation split and evaluates it once on held-out test data. Validation
records, selection metadata, test records, logs, and the confirmatory speedup
figure are co-located under `runs/`.

The `TEST_EVALUATED` and `VALIDATION_SELECTED` markers record the intended
selection boundary.
