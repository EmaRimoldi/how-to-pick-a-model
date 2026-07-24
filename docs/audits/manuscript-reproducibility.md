# Manuscript reproducibility audit

## Scope

Audited artifact: `paper/submitted-manuscript.pdf`.

The manuscript source and all twelve paper-facing AutoResearch figures were
located in `paper/neurips-submission/` and in the imported Overleaf history. The
runtime, processed evidence, and available raw traces were located in
`autoresearch/` and
`experiments/autoresearch/05_autoresearch_model_routing/`.

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

## Evidence coverage

- Historical two-worker panel: 210 processed trajectories; 150 raw holdout
  traces present; 60 pilot traces missing.
- Balanced three-worker panel: 270 processed trajectories; 180 raw traces
  present; 90 pilot traces missing.
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
