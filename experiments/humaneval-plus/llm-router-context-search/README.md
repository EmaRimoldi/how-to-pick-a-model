# LLM Router Context Search on HumanEval+

The completed `router-search-20260712` run selects a model/context setting on a
validation split and evaluates it once on held-out test data. Validation
records, selection metadata, test records, and the confirmatory speedup
figure are co-located under `runs/`.

The `TEST_EVALUATED` and `VALIDATION_SELECTED` markers record the intended
selection boundary.

Scheduler stdout/stderr are archived in
[repository history](../../../docs/history-merge.md); they are not analysis
inputs. The split, validation selection, held-out evaluation and boundary
markers remain intact.
