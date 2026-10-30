# Post hoc structural-edit diagnostic

Added after the primary descriptive report. The original comparisons, full bank,
missing data and operational cutoff are unchanged.

Of 67 valid file artifacts, **41 have the same Python AST as their supplied input
files**, ignoring comments, formatting and source locations: 8/17 prefix outputs
and 33/50 recovery outputs. The other 26 have a different AST. All were parseable.
These counts are correlated within bugs and are not 67 independent experiments.

At **6/15 observed failed checkpoints**, the continue and restart files have the
same AST even though their bytes differ. Keep those checkpoints: wording,
comments or layout can still change an LLM response, so this is not a claim of
identical requests. AST equality also is not a general semantic-equivalence test.

This strengthens the calibration concern: many attempted repairs make no
structural change, and some action contrasts carry no distinct program structure.
It does not explain every failure or establish which output contract would help.
The remaining nine checkpoints have structurally different starting code; their
lack of observed recovery success remains part of the finding.

[All per-artifact and per-checkpoint classifications](artifact-diagnostic.json)
are generated without model calls or execution of candidate source:

```bash
python -m vao.analysis.repair_artifacts \
  --input runs/repair-gemma4b-development-final-20261026 \
  --output runs/repair-artifact-diagnostic.json
```

The same command works from a fresh evidence-archive extraction using the
installed repository environment. Compare the complete JSON with the published
file. No population, causal or action-equivalence claim is made.
