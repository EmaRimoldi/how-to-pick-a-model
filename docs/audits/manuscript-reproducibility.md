# Manuscript reproducibility audit

## Scope

Audited artifact: the historical
[submitted manuscript](https://github.com/EmaRimoldi/how-to-pick-a-model/blob/d98e3f2209c6e470885e748aafb0a41ea6395291/paper/neurips-submission/archive/submitted-manuscript.pdf).
The October 2026 cleanup removed this PDF from the working tree after the
text-layer anomaly below was independently confirmed. This audit retains the
historical findings. For current PDFs from active sources, run
`uv run python scripts/maintenance/workflow.py paper-build`.

The manuscript source and all twelve paper-facing AutoResearch figures were
located in `paper/neurips-submission/` and in the imported Overleaf history. The
runtime, processed evidence, and available raw traces were located in
`autoresearch/` and
`experiments/autoresearch-cifar10/three-worker-model-routing/`.

## Main accounting discrepancy

The manuscript declares the primary first-passage deployment loss

```text
deployment_loss = failure + cost_to_first_hit_or_horizon
```

but the published frontier values were produced by the historical composite
implementation

```text
failure
+ 0.25 * (1 - threshold_occupancy)
+ 0.25 * (1 - final_relative_improvement)
+ full_horizon_wall_seconds / 1800
```

The historical implementation is preserved in
`autoresearch/analysis/autoresearch_cifar10_deployment_accounting.py`. The
corrected first-passage implementation is in
`autoresearch/scripts/analyze_autoresearch_threeworker_final.py`.

Under the declared loss, the mature two-worker winners are GPT-5.4 for MLP-flat
and compact CNN, and GPT-5.3 Codex for micro ResNet. The later three-worker
analysis selects GPT-5.4, GPT-5.4 Mini, and GPT-5.3 Codex respectively.

## Archived evidence coverage

The coverage below describes the verified pre-retirement snapshot. Current
CIFAR-10 code/data are archived in [provenance](../history-merge.md); embedded
manuscript figures remain available for compilation.

- Historical two-worker panel: 210 processed trajectories; 150 raw holdout
  traces present; 60 pilot traces missing.
- Balanced three-worker panel: 270 processed trajectories; 180 raw traces
  present; 90 pilot traces missing.
- The main processed-figure command reads the separate 300-record pooled JSON
  (35/35/30 trials per workload across the three workers), not the balanced
  270-record sensitivity table. These are distinct recorded analyses.
- Router: processed rows for the later three-worker rerun are present; the
  original two-worker router-decision JSONL used by the submitted manuscript is
  not present.
- Signal ablation: aggregate output is present; the underlying diagnostic
  records are not.

## PDF text-layer anomaly

The supplied PDF contains a non-visible text-layer instruction on pages 2 and
35 that asks an automated output to include three specific review phrases. It
is absent from the located LaTeX source and is not executable JavaScript. The
PDF should be regenerated from source before redistribution.
