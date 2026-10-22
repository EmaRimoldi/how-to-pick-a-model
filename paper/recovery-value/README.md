# Measuring the value of failed code

A separate empirical research draft, based on the retained HumanEval+ study and
the [audited MBPP+ replication](../../experiments/mbpp-plus/context-value-transfer/results/replication-20261022/report.md).
The existing NeurIPS manuscripts and theory anchor remain separate.

The MBPP+ bank contains 2,878 observed recovery responses and two permanently
censored solver cells. All 96 selected failed tasks are retained in the data;
94 have all 30 observations. Complete-case intervals are descriptive, including
the twelve prespecified context comparisons. The primary selector advantage is
not established. All 288 prespecified API forecasts are retained with their fees.

Build from the repository root with the normal development environment and
TeX Live. Use a fresh output directory:

```bash
uv run python paper/recovery-value/build.py \
  --output /tmp/how-to-pick-a-model-recovery-paper
```

If `pdflatex` is outside `PATH`, supply its location with `--pdflatex`.
The builder audits recorded journals, compares the recomputed report with the
saved analysis, generates tables and figures, then compiles the PDF three times.
It makes no model calls, executes no candidate programs, and needs no credentials,
GPU, EvalPlus installation or historical Git objects. It refuses an unfinished
manuscript or absent final evidence.

Tables are generated from the same audited `analysis.json` as the figures.
Incomplete-bank tables require `--allow-incomplete-descriptive` and print
coverage and missing-state bounds. No generated tables or duplicate figure
copies need to be checked in.
