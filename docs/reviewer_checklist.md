# Evidence Review Checklist

- Is the task/verifier, success threshold, model version, and budget declared?
- Are first-hit outcomes distinguished from final quality and full-horizon cost?
- Are failures, censoring, abstention, and budget exhaustion included?
- Is all context, routing, model, and verifier usage accounted for?
- Are measured costs distinguished from estimates and latency?
- Are policy fitting/tuning separated from held-out tasks?
- Are continuation actions compared from matched observable checkpoints?
- Are unsupported counterfactuals labeled as unavailable rather than replayed?
- Are state-dependent forecasts calibrated against outcomes rather than verbal confidence?
- Do conclusions stay within the recorded protocol and coverage?

Current data supplies baseline and matched development evidence. The context-value
diagnostic adds prospective forecasts; learned policies and their validation
remain planned in `docs/decision-protocol.md`. `uv run python scripts/maintenance/workflow.py check` verifies
structure and unit behavior, not the scientific validity of new policy claims.
