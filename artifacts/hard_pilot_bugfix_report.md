# Hard Pilot Bugfix Report

Two candidate-quality issues appeared in the first hard Haiku batch pilot.

## `list.remove` Source-Validation Rejections

Fix: added a narrow deterministic parser repair. If the only source-validation error is `banned attribute call: remove`, the parser rewrites simple statement-level `container.remove(value)` calls into a list-comprehension assignment, then validates the full repaired source again.

The repair is logged in each proposal as:

- `source_repair_status`
- `source_repairs`

The two failed pilot payloads now reparse and validate with `source_repairs: ["list_remove_rewritten_to_comprehension"]`.

## `top_k` Semantic Error

Fix: hardened structured-edit prompts. They now explicitly require `top_k` to order by value descending and then key ascending, with sorting/heap semantics equivalent to `(-value, key)`.

No semantic auto-repair was added for `top_k`: changing a wrong top-k algorithm locally would create a different candidate from the model's proposed edit. The verifier remains the correctness authority and logs semantic failures as evaluated counterfactual branches.
