# Exploratory Bottleneck-Mode Pilot

This note preserves the unique protocol history formerly embedded in
`paper/neurips-submission/archive/main_3_local.tex`. It is not part of the
promoted three-worker result.

## Scope

Before the promoted fixed executable-setting panel, an exploratory
AutoResearch branch used six bottleneck modes and four workers. The branch was
not promoted because the regularization-sensitive construction was too hard at
the frozen threshold and the final router validation was cleaner on the
narrower panel. It nevertheless established conventions later retained by the
paper:

- full-horizon trajectory logging;
- first-passage deployment loss;
- occupancy as a persistence audit;
- probe-only pre-deployment signals;
- explicit handling of failed structured edits.

An instance was represented as

```text
x = (train.py_0, r, u, B, V)
```

where `train.py_0` is the editable starting program, `r` is the data/training
regime, `u` is a nuisance draw such as a seed or subset realization, `B` is the
fixed experimental budget, and `V` maps candidate artifacts to validation loss
and success. Each trajectory used one routed model for a maximum horizon `H`.
Runs continued after first success so first-passage resource, final quality,
threshold occupancy, and cost through the full horizon could be reconstructed
from the same trace.

## Mode Taxonomy

| Mode | Bottleneck intuition | Pilot status | Construction sketch | Restricted pre-run probe signature |
| --- | --- | --- | --- | --- |
| `lr-sensitive` | Small local hyperparameter errors dominate early progress. | viable | Clean regime with mis-scaled learning rate and a 128-step verifier budget. | High baseline loss despite normal parameter count and cheap-probe runtime. |
| `regularization-sensitive` | Noise or overfitting dominates the next improvement. | stress test | Label-noise regime with weak dropout or weight decay under a 128-step budget. | Weak baseline improvement; zero threshold hits at the operating threshold. |
| `optimizer-sensitive` | Gradient dynamics and optimizer family dominate. | viable | Stiff-optimization regime with a poor optimizer choice under a 128-step budget. | Under-performance relative to parameter count and cheap-probe wall profile. |
| `data-skew-sensitive` | Sampling and coverage dominate progress. | viable | Imbalanced regime with weak skew handling under a 128-step budget. | Depressed validation accuracy relative to loss and parameter count. |
| `capacity-sensitive` | The model class is too small or poorly structured. | viable | Under-sized architecture under a 512-step budget. | Low parameter count plus plateauing probe loss. |
| `schedule-sensitive` | Longer-horizon coordination matters more than local tweaks. | viable | A 512-step budget with a missing or poor learning-rate schedule, warmup, or decay policy. | Moderate immediate loss improvement but low sustained occupancy without scheduler-aware edits. |

The worker menu was GPT-5.4 Mini, GPT-5.3 Codex, GPT-5.3 Codex Spark, and
Claude Sonnet.

## Signal and Threshold

The routed signal was restricted to a cheap baseline-only probe of the
unmodified program:

- validation loss;
- validation accuracy;
- training seconds;
- total wall-clock seconds;
- parameter count;
- optimizer steps.

Template-level knobs and regime metadata were removed after the restricted
probe matched the leaky feature set on the 30-run multi-seed baseline probe:
both `probe-only` and `probe+budget` reached macro accuracy `0.933`, while
`budget-only` reached `0.333`.

The relative-improvement success threshold was frozen at `delta = 0.05`:

```text
V_succ(x, y) = 1[(L_base(x) - L(x, y)) / L_base(x) >= delta].
```

At this threshold, the 24-cell early-stop sweep retained broad entry coverage;
higher thresholds collapsed important long-horizon modes. Persistence was
tracked separately as

```text
O_i^delta(H) = (1 / H) sum_h 1[(L_base(x_i) - L_i,h) / L_base(x_i) >= delta].
```

Occupancy was an audit diagnostic, not a replacement for first-passage
competence.

## Frozen Decisions

| Decision | Evidence | Consequence |
| --- | --- | --- |
| Verifier budgets | Fixed overhead dominated extremely short 2--128 and 64--512 inner-step probes. | Use materially informative verifier budgets rather than extremely short probes. |
| Success threshold | Entry success remained broad through `delta=0.05` and dropped sharply at `0.10` and `0.15`. | Keep `delta=0.05` as the operating first-passage threshold. |
| Horizon policy | No-stop `H=8` was too short; `H=16` was informative but incomplete for optimizer and schedule persistence. | Record full trajectories and report horizon sensitivity rather than stopping at first hit. |
| Router signal | Probe-only records matched the previous leaky feature set; budget-only records were weak. | Charge and report baseline-probe signals separately from deployment trajectories. |
| Mode scope | Five modes showed useful entry or occupancy structure; regularization-sensitive had zero hits. | Treat unstable bottleneck modes as stress tests, not promoted claims. |
| Failure handling | Long-horizon reruns exposed invalid structured edits that could abort a trajectory. | Log irrecoverable single-edit failures as unsuccessful no-op steps. |

The promoted experiment inherited these protocol decisions while replacing the
exploratory mode and worker menu with the fixed executable-setting panel
documented by the surrounding bundle.
