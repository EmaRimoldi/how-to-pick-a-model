# Development And Sensitivity Results

No file in this directory is confirmatory evidence.

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
2,000 replications, 256 tasks per mode passes all point closure gates in
`95.35%` of packed-null simulations; its 95th-percentile absolute mean residual
is `0.0956` nats, residual RMS is `0.0969` nats, and maximum cell censoring is
`1.56%`.

`bf16_inverse_share_development.json` records the physical IID allocation gate
on generator v5 before either final split was opened. Across 3,456 trajectories,
the pooled slope is `0.988` with 90% bootstrap interval `0.960`--`1.013`; the
14B and 7B intervals are respectively `0.985`--`1.052` and `0.913`--`0.995`.
Residual RMS is `0.108` nats, planned-share error is `0.0051`, and censoring and
off-diagonal wins are both zero. All inverse-share gates pass. This authorizes
confirmation but is still development evidence, not held-out four-term closure.

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
and four trajectories per cell, gates weighted mean and RMS over six primary
conditions, and freezes this size before creating calibration or confirmation
seeds.

The calculation assumes the inverse-share law and zero off-diagonal success.
It measures finite-sample sensitivity under the null; it does not establish
that SAI-3 or an LLM satisfies packedness. The independent packedness and
off-diagonal gates in the protocol are responsible for that empirical test.
