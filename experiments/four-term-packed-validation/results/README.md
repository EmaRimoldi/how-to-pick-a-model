# Development And Sensitivity Results

No file in this directory is confirmatory evidence.

`mlx_development_pilot.json` records the new Apple-silicon model pilot used to
debug and select the BF16 Stage 0 candidates. It contains actual model
completions, but quantization and Apple hardware define different deployed
systems from the A100 identification arm. Closure analysis is prohibited on
this development split.

`power_analysis.json` is a synthetic design calculation generated without
reading any empirical result in this repository.

`power_analysis.json` was produced with:

```bash
python experiments/four-term-packed-validation/scripts/power_analysis.py \
  --replicates 1000 \
  --sample-sizes 64 128 192 256 \
  --output experiments/four-term-packed-validation/results/power_analysis.json
```

At the frozen confirmatory size of 256 tasks per mode:

- all 36 closure residuals are simultaneously within `0.15` nats in `95.4%`
  of simulations;
- the 2.5%--97.5% packedness-slope range is `0.976`--`1.023`;
- fixed-signal held-out model selection agrees with the simulated oracle in
  `99.9%` of simulations;
- mean pairwise rank concordance over all systems is `0.947`;
- the 95th percentile residual RMS is `0.078` nats.

At 128 tasks per mode, simultaneous closure falls to `69.0%`. This is why the
protocol fixes 256 and prohibits reducing the sample size after calibration.

The calculation assumes the inverse-share law and zero off-diagonal success.
It measures finite-sample sensitivity under the null; it does not establish
that SAI-3 or an LLM satisfies packedness. The independent packedness and
off-diagonal gates in the protocol are responsible for that empirical test.
