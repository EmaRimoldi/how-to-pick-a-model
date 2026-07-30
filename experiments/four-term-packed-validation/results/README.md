# Development And Sensitivity Results

No file in this directory is confirmatory evidence.

`mlx_development_pilot.json` records the new Apple-silicon model pilot used to
debug and select the BF16 Stage 0 candidates. It contains actual model
completions, but quantization and Apple hardware define different deployed
systems from the A100 identification arm. Closure analysis is prohibited on
this development split.

`bf16_stage0.json` records the eligibility scout on the final BF16 A100 serving
stack. Across 576 matched completions per model, success was `62.7%` for 7B and
`96.4%` for 14B; both parsed 100%. Neither model succeeded on any of 288
wrong-shard attempts. This file fixes the identification pair and informs the
pre-confirmation sample size, but it is not closure evidence.

`power_analysis.json` is a synthetic design calculation generated without
reading any empirical result in this repository.

`stage0_conditioned_power.json` is a second design-only calculation that reads
the nonconfirmatory BF16 hazards, adds task heterogeneity, and simulates the
exact frozen calibration and physical confirmation protocol. With 2,000
replications, 96 tasks per mode passes all point closure gates in `97.4%` of
packed-null simulations; its 95th-percentile residual RMS is `0.090` nats and
maximum cell censoring is `1.04%`.

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
criterion passes `69.0%`. The physical protocol uses 64 task clusters and two
trajectories per cell, gates weighted mean and RMS over six primary conditions,
and freezes this size before creating calibration or confirmation seeds.

The calculation assumes the inverse-share law and zero off-diagonal success.
It measures finite-sample sensitivity under the null; it does not establish
that SAI-3 or an LLM satisfies packedness. The independent packedness and
off-diagonal gates in the protocol are responsible for that empirical test.
