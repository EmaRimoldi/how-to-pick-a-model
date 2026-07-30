# Empirical Results

The `bf16_four_term_confirmation.json` result and its associated audit and
bootstrap archive are held-out confirmatory evidence. The remaining JSON files
are development, calibration, or design-sensitivity evidence as noted below.

## Held-Out Confirmation

`bf16_four_term_confirmation.json` is the frozen BF16 A100 analysis of 175,104
physical trajectories over 768 unseen tasks. It records zero censoring, zero
wrong-shard success, a confirmation inverse-share slope of `0.9868` with 90%
interval `[0.9784, 0.9952]`, and six primary four-term contrasts. Mean residual
is `0.0100` nat, residual RMS is `0.0147` nat, and the 95% bootstrap upper bound
on RMS is `0.0350` nat. Every individual residual interval contains zero.

The four-term decision selects the same model as the held-out oracle in all six
conditions, with minimum bootstrap selection probability `1.0` and zero oracle
regret. The strict omnibus status is nevertheless
`INCONCLUSIVE_OR_FALSIFIED`: thirteen of fourteen gates pass, but the residual
slope against mismatch is `0.0377` with Holm-adjusted `p = 0.0224`. At the
largest mismatch this is a `0.0299`-nat, approximately `3.0%`, discrepancy.
This supports practical approximate closure and model choice, not an exact
identity on the tested domain.

`bf16_confirmation_artifact_audit.json` verifies the eight raw A100 runs. It
contains 87,552 trajectories per model, 175,104 unique trajectory IDs, 87,552
unique schedule seeds, 801,535 unique generation seeds, model and tokenizer
revisions, design and artifact hashes, and zero wrong-shard successes. The 7B
and 14B systems issued 455,248 and 346,287 generation slots respectively. Their
measured generation time was 20,288 and 27,433 GPU-seconds respectively.

`bf16_four_term_bootstrap_draws.json.gz` contains the 5,000 nested task-bootstrap
draws referenced by the confirmation result. Its uncompressed JSON SHA-256 is
`9800cc94c6d50f703587712308189cadb840193bb6eb09f713c1d4b5673552c4`.

`posthoc_finite_replication_bias.json` is an explicitly nonconfirmatory
diagnostic of the only failed gate. The exact negative-binomial calculation
predicts a mismatch slope of `0.0257` from taking the log of a six-repetition
sample mean, explaining `68.3%` of the observed `0.0377` slope. Subtracting this
approximate bias leaves slope `0.0119` and reduces all-comparison residual RMS
from `0.0141` to `0.0083` nat. Because it uses aggregate mode scales and was
motivated after observing the result, it cannot change the frozen outcome.

The confirmation jobs were Slurm `19281145`, `19281147`, `19281148`,
`19281149`, `19281158`, `19281159`, `19281160`, and `19281162`; all completed
on one A100 each. Artifact audit job `19283303` and analysis job `19283418`
also completed. The paper-facing plots in `figures/` are generated with:

```bash
uv run python experiments/four-term-packed-validation/scripts/plot_sai3_four_term.py \
  --analysis experiments/four-term-packed-validation/results/bf16_four_term_confirmation.json \
  --inverse-share experiments/four-term-packed-validation/results/bf16_inverse_share_development.json \
  --output-dir experiments/four-term-packed-validation/results/figures
```

## Development And Sensitivity

`mlx_development_pilot.json` records the new Apple-silicon model pilot used to
debug and select the BF16 Stage 0 candidates. It contains actual model
completions, but quantization and Apple hardware define different deployed
systems from the A100 identification arm. Closure analysis is prohibited on
this development split.

`bf16_stage0.json` records the generator-v5 eligibility scout on the final BF16
A100 serving stack. Across 576 matched completions per model, success was
`86.6%` for 7B and `99.5%` for 14B; both parsed 100%, had no zero-success task
cells, and were balanced over four task strata. Neither model succeeded on any
of 288 wrong-shard attempts. This file fixes the identification pair and
informs the pre-confirmation sample size, but it is not closure evidence.

`power_analysis.json` is a synthetic design calculation generated without
reading any empirical result in this repository.

`stage0_conditioned_power.json` is a second design-only calculation that
resamples the nonconfirmatory BF16 task counts within the four frozen strata
and simulates the exact calibration and physical confirmation protocol. With
2,000 replications, 256 tasks per mode, six trajectories per cell, and a
256-slot limit identify every required cell and pass all point closure gates
in `98.45%` of packed-null simulations. The 95th-percentile absolute mean
residual is `0.0362` nats, residual RMS is `0.0387` nats, and
maximum cell censoring is `0.456%`.

`bf16_inverse_share_development.json` records the physical IID allocation gate
on generator v5 before either final split was opened. Across 3,456 trajectories,
the expected-log estimand gives pooled slope `0.9549` with 90% bootstrap
interval `0.9286`--`0.9810`; the 14B and 7B intervals are respectively
`0.9375`--`1.0083` and `0.8984`--`0.9753`. The frozen pooled gate passes. The
7B-only interval narrowly misses the lower equivalence threshold, but this is a
preserved model-specific diagnostic, not the preregistered gate. Residual RMS is
`0.104` nat, planned-share error is `0.0051`, and censoring and off-diagonal wins
are both zero. This authorized confirmation but remains development evidence.

`bf16_calibration.json` records the frozen pre-confirmation gate over 110,592
BF16 A100 completions. No task has zero matched successes and no physical slot
or numerical seed is duplicated. Focused pass probabilities are
`0.998/0.998/0.996` for 14B and `0.843/0.865/0.850` for 7B. The largest upper
95% off-diagonal-to-matched hazard ratio is `0.000736`; both task-conditioned
attempt-index intervals include zero. Calibration passes without the optional
64-to-128 extension. It estimates competence and validates assumptions, but it
does not contain held-out closure outcomes.

`power_analysis.json` was produced with:

```bash
python experiments/four-term-packed-validation/scripts/power_analysis.py \
  --replicates 1000 \
  --sample-sizes 64 128 192 256 \
  --output experiments/four-term-packed-validation/results/power_analysis.json
```

At 256 independent trajectories per cell:

- all 36 closure residuals are simultaneously within `0.15` nats in `95.4%`
  of simulations;
- the 2.5%--97.5% packedness-slope range is `0.976`--`1.023`;
- fixed-signal held-out model selection agrees with the simulated oracle in
  `99.9%` of simulations;
- mean pairwise rank concordance over all systems is `0.947`;
- the 95th percentile residual RMS is `0.078` nats.

At 128 independent trajectories per cell, residual RMS remains below `0.115`
nats in 95% of simulations, while the stricter maximum-over-36-designs closure
criterion passes `69.0%`. The physical protocol uses 256 task clusters per mode
and six trajectories per cell, gates weighted mean and RMS over six primary
conditions, and freezes this size before creating calibration or confirmation
seeds.

The calculation assumes the inverse-share law and zero off-diagonal success.
It measures finite-sample sensitivity under the null; it does not establish
that SAI-3 or an LLM satisfies packedness. The independent packedness and
off-diagonal gates in the protocol are responsible for that empirical test.
