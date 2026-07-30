# Four-Term Packed Validation

Status: **BF16 Stage 0 complete; no confirmatory result is claimed yet**.

Implementation status (2026-07-30): the procedural generator, static-policy
verifier, reference/mutation audit, vLLM and Apple-MLX scout runners, physical
IID soft-allocation scheduler, inverse-share analysis, four-term held-out
analysis, and Slurm entrypoints are implemented. Development completions are
explicitly excluded from confirmatory closure evidence.

The first infrastructure smoke is intentionally smaller than Stage 0:

```bash
uv run python experiments/four-term-packed-validation/scripts/generate_sai3_tasks.py \
  --seed 20260730 --split development --tasks-per-mode 24 --difficulty scalar \
  --output runs/sai3/development.jsonl \
  --audit-output runs/sai3/development-audit.json

sbatch experiments/four-term-packed-validation/scripts/slurm_sai3_scout.sbatch \
  Qwen/Qwen2.5-Coder-7B-Instruct \
  "$PWD/runs/sai3/development.jsonl" \
  "$PWD/runs/sai3/scout-qwen25-coder-7b"
```

The smoke defaults to six tasks per mode, four matched attempts, and one
attempt per wrong shard. These counts test the runtime and locate gross
floor/ceiling behavior only; they cannot pass the statistical gates below.

The BF16 A100 Stage 0 used 24 tasks per mode, eight matched attempts, and two
attempts per wrong shard. Matched success was `0.479/0.667/0.734` by mode for
the 7B checkpoint and `0.948/0.974/0.969` for the 14B checkpoint. Both parsed
100% of outputs and each had zero wrong-shard successes in 288 trials. These
results establish eligibility and size the physical run; they are not used as
four-term evidence.

On an Apple-silicon development machine, the equivalent nonconfirmatory MLX
smoke is:

```bash
uv run --with mlx-lm==0.28.3 --with transformers==4.57.6 \
  python experiments/four-term-packed-validation/scripts/run_sai3_mlx_scout.py \
  --tasks runs/sai3/development.jsonl \
  --model mlx-community/Qwen2.5-Coder-7B-Instruct-4bit \
  --tasks-per-mode 2 --matched-attempts 2 --wrong-attempts 1 \
  --completion-batch-size 8 \
  --output runs/sai3/mlx-smoke-7b.jsonl \
  --metadata-output runs/sai3/mlx-smoke-7b.metadata.json
```

MLX is used to debug prompts, parsing, verifier behavior, and benchmark
difficulty without waiting for a cluster allocation. Quantization and Apple
hardware are part of this local system definition, so these observations are
not pooled with the BF16 A100 identification arm. Stage 0 eligibility is rerun
on the final serving stack before any confirmatory split is generated.

This bundle specifies a new experiment for testing the four-term packed
decomposition without using any existing experimental result in this
repository to choose the benchmark, models, effect sizes, or sample size. The
only reused object is the theory to be tested.

## Confirmatory Claim

For a prior-matched baseline `(M0, pi)` and a deployed system `(M, q)`, test
out of sample whether

```text
observed expected packed log-resource gain
    = unit-cost gain
    + focused-competence gain
    + mode information
    - allocation mismatch
    + residual.
```

In notation,

\[
\Delta_{\rm obs}
=
\log\frac{\kappa(M_0)}{\kappa(M)}
+\mathbb E_S\log\frac{t_0(M_0,S)}{t_0(M,S)}
+I(S;Z)
-\mathbb E_Z\mathrm{KL}(\pi_Z\|q_Z)
+R.
\]

The experiment is successful only if independently calibrated terms predict
held-out resource-to-solution and the residual satisfies the preregistered
equivalence criteria. Recomputing `T = kappa * t0 / q` and calling the equality
verified is explicitly prohibited.

The active theoretical statement is in
`paper/neurips-submission/archive/theory_anchor.tex`, theorem
`thm:four-term`. The packed law is an assumption, not a consequence of the
general definition of proper time. Therefore the empirical burden is to test
the inverse-share law and out-of-sample closure.

## Why This Setup

The design combines several useful precedents while adding the missing
identification structure:

- [Achille and Soatto](https://arxiv.org/abs/2510.12066) motivate verified
  transductive tasks and resource-to-solution as the operational object; the
  present experiment makes that resource finite, measured, and model-selective.
- [Large Language Monkeys](https://arxiv.org/abs/2407.21787) establishes
  independent repeated sampling, verifier-backed coverage, and inference-FLOP
  accounting, but does not manipulate a physical allocation `q` over latent
  modes.
- [OSCA](https://arxiv.org/abs/2410.22480) implements mixtures over sampling
  configurations, but does not separately identify information and posterior
  mismatch or test an expected-log closure identity.
- [Scaling LLM Test-Time Compute Optimally](https://arxiv.org/abs/2408.03314)
  selects compute policies on validation data and evaluates them on held-out
  prompts. This motivates the strict calibration/confirmation split.
- [EvalPlus](https://arxiv.org/abs/2305.01210),
  [BigCodeBench](https://arxiv.org/abs/2406.15877), and
  [CodeBenchGen](https://arxiv.org/abs/2404.00566) motivate mutation-tested,
  execution-based verification and fresh procedural tasks.

Existing public coding benchmarks are not the primary test because their
modes overlap, a completion generated under the "wrong" strategy can still
solve the task, and the benchmark does not expose a controlled posterior
`P(S | Z)`. Those properties make the inverse-share law unlikely to hold
closely enough to identify the four terms. A public benchmark is retained only
as an external-validity stress test after confirmation.

## Primary Benchmark: SAI-3

`SAI-3` is a procedural **sharded API-integration** benchmark.

Each task contains a small Python package and an adapter to implement. The
hidden execution environment contains one of three mutually incompatible API
contracts. The latent mode is the installed contract:

\[
S\in\{1,2,3\},\qquad P(S=s)=1/3.
\]

Three evidence shards describe the three possible contracts. A generation
stream assigned to shard `j` receives the common task plus only shard `j`.
The correct shard contains randomly generated symbol and field names required
by the installed package; the other shards contain incompatible names.
Reflection, dynamic attribute enumeration, network access, and multi-contract
fallback code are rejected by a static policy check. This makes the streams
solver-relevant and keeps off-diagonal success measurable and near zero without
giving the model the true mode.

The implementation problem remains nontrivial after the correct contract is
known. A task composes value normalization, context transformation, a derived
weight, a three-keyword API call, status handling, response post-processing,
ticket propagation, and exception translation. Randomized identifiers prevent
checkpoint memorization. All confirmation seeds are generated only after the
generator, templates, and analysis code are frozen.

### Verifier

A candidate succeeds only when all of the following pass in an isolated
container:

1. syntax and static-policy checks;
2. public smoke tests;
3. hidden differential tests against a reference adapter;
4. generated boundary and metamorphic tests;
5. timeout and resource limits.

Before model evaluation, each task must pass the reference solution, reject
each wrong-contract reference solution, achieve mutation score at least `0.95`,
and produce identical results in 20 verifier reruns. Any flaky or ambiguous
task is discarded before model inference.

## Models And Generation Slots

The dated model search, hardware tiers, candidate audit, substitutions, and
campaign-time calculation are recorded in
[`model_landscape.md`](model_landscape.md). The protocol separates a clean
identification arm from a heterogeneous current-model transport arm. Public
coding leaderboards are used only to decide what is worth scouting; model
eligibility is determined on the frozen generator-development split.

### Primary identification arm

Use two instruct checkpoints from one dense, open, same-tokenizer family:

- `Qwen/Qwen2.5-Coder-7B-Instruct`;
- `Qwen/Qwen2.5-Coder-14B-Instruct`.

The [Qwen2.5-Coder report](https://arxiv.org/abs/2409.12186) documents the
same-family 0.5B--32B series. The local development pilot rejected the 3B
system because it produced no matched success in the micro-scout. The 7B/14B
pair preserves meaningful cost and competence variation without the hardware
discontinuity of the 32B checkpoint. Eligibility is rerun in BF16 before the
pair is frozen.

These checkpoints are code-specific; the panel is not a generic-language
baseline. Its age is an advantage for identification because the serving path,
chat protocol, and non-thinking generation behavior are mature and shared.

### Current-model transport arm

After the primary analysis is frozen, repeat the practitioner decision test on
the predeclared current-model panel:

- `Qwen/Qwen3.5-4B`;
- `allenai/SERA-8B`;
- `Qwen/Qwen3.6-27B`;
- `CohereLabs/North-Mini-Code-1.0`.

This arm spans a compact current checkpoint, a compact coding-agent specialist,
a strong dense model, and a sparse coding specialist. It uses isolated
GPU-seconds and joules as its primary clocks rather than pooling dense and MoE
systems under the primary dense-FLOP closure. Runtime or formatting failure can
trigger only the substitutions frozen in `model_landscape.md`; SAI-3 rank
cannot be used to select an alternate.

Every completion is an independent fixed-format slot:

- temperature `0.8`, top-p `0.95`;
- fixed prompt-token envelope and exactly 256 decoded tokens;
- no conversation history or feedback between attempts;
- independent, logged RNG seeds;
- the first parseable patch is evaluated;
- identical serving software and BF16 precision within the primary
  identification arm.

The transport arm keeps the same sampling envelope and disables thinking when
the official chat protocol supports it. If a checkpoint cannot disable
reasoning, every reasoning token consumes the 256-token slot. Its frozen
runtime and parser are recorded as part of `M`; they are not pooled into the
same-family causal contrast.

The generator-development split may tune task complexity until focused
pass@1 is at least `0.05` for every retained model-mode cell. The lower gate
prevents excessive censoring; no upper gate is needed because near-certain
focused success still leaves inverse allocation experimentally identifiable.
Development tasks and completions are then destroyed; the generator is frozen
before fresh calibration and confirmation seeds are sampled.

Before that tuning, Stage 0 runs 24 development tasks per mode with eight
correct-shard and two-per-wrong-shard attempts for every scouted checkpoint.
It records eligibility, format, memory, throughput, energy, and verifier cost,
but never computes four-term closure or opens confirmation seeds.

Calibration generates 32 correct-shard attempts and four attempts for each
wrong shard per task and model. A correct-shard task with no success is extended
once, with frozen seeds, to 64 attempts; any remaining zero-success task cell
makes focused `t0` unidentified. Confirmation physically executes two
independent trajectories for every `(task, alpha, allocation, z)` cell, plus two
prior-baseline trajectories, with a 128-slot censoring limit.

This is 11,520 calibration completions per model. The confirmation design has
10,944 trajectories per model; using the Stage 0 hazards, its preregistered
expected load is about 70,800 slots for 7B and 44,600 for 14B, or 29.5 million
decoded tokens across both models. Including calibration, the expected Stage 1
load is about 35.4 million decoded tokens. Actual issued slots, not this
expectation, enter the ledger. Prefix caching may be used, but cached and
uncached normalized compute are both recorded.

## Physical Allocation And Signal Interventions

For signal accuracy `alpha`, use the symmetric channel

\[
P(Z=z\mid S=s)=
\begin{cases}
\alpha,&z=s,\\
(1-\alpha)/2,&z\ne s.
\end{cases}
\]

with `alpha in {1/3, 0.60, 0.80}`. Because the prior is uniform and the
channel is known, `pi_z = P(S | Z=z)` and `I(S; Z)` are exact design
quantities, not noisy mutual-information estimates.

For every signal condition, evaluate four preregistered allocations:

1. `matched`: `q_z = pi_z`, so mismatch is zero;
2. `half_prior`: `q_z = 0.5 pi_z + 0.5 pi`;
3. `prior`: `q_z = pi`, so the information gain is unused;
4. `half_anti`: `q_z = 0.5 rotate(pi_z) + 0.5 pi`.

At `alpha = 0.80`, the corresponding information is `0.460` nats and the
mismatches are approximately `0.000`, `0.121`, `0.460`, and `0.794` nats.
Thus information and mismatch vary independently over a practically visible
range while every mode keeps positive allocation.

An IID categorical soft scheduler, not a hard selector, realizes `q_z`. Before
every fixed-cost generation slot it samples one of the three evidence streams
with probabilities `q_z`, issues that prompt with a unique seed, verifies the
completion, and stops the trajectory at the first certified solution. With
matched-stream hazard `p_M(s)` and zero off-diagonal hazard, each global slot
succeeds with probability `q_z(s)p_M(s)`, so its mean first-passage count is
exactly `1/(q_z(s)p_M(s)) = t0(M,s)/q_z(s)`. The experiment tests the two
empirical premises rather than assuming them: exchangeable matched hazards and
negligible wrong-stream success.

This randomized scheduler is the discrete physical counterpart of processor
sharing. Deterministic weighted-fair scheduling is not used for the primary
test because indivisible LLM slots create first-service granularity errors when
`t0` is near one. Every primary trajectory is executed online end to end; no
post-hoc completion-pool replay is used as closure evidence.

### Practical-signal arm

After freezing the controlled analysis, train one multinomial logistic model
on calibration-only stack-trace tokens and package metadata. Its argmax
diagnostic category is a discrete practical signal `Z_practical`; its 3-by-3
confusion matrix defines a posterior and therefore a soft allocation. Estimate
that confusion matrix from five-fold out-of-fold calibration predictions, then
refit once on the full calibration split. The classifier, feature vocabulary,
regularization, and probability smoothing are frozen before confirmation. No
LLM is used as the signal classifier.

This secondary arm repeats the practitioner ranking test with calibration
estimates of `I(S; Z_practical)` and mismatch. It does not replace the
controlled channel, because estimation error in a learned signal would
otherwise be confounded with failure of the four-term law. Classifier runtime
is reported as signal-acquisition cost outside the four-term identity. It may
be omitted from the four-term score only when it is below 1% of predicted
resource-to-solution, which bounds the omitted log penalty by `log(1.01)`;
otherwise the practical decision must include an explicit acquisition-cost
term and is no longer presented as an exact four-term decomposition.

## Resource Clocks

The primary clock is additive normalized inference compute per fixed slot. For
the same-tokenizer dense identification pair, `kappa(M)` is the checkpoint's
official non-embedding parameter count multiplied by the common fixed token
envelope; the common multiplier cancels in every log ratio. The frozen values
are 6.53B for 7B and 13.1B for 14B in `configs/model_costs.json`, as reported by
the official model cards. Prompt-token and attention corrections are recorded
as diagnostics. This clock avoids batching and queueing artifacts and is
cross-checked against profiler counters.

The complete analysis is repeated with three practitioner clocks:

- isolated GPU-seconds;
- joules;
- provider-equivalent dollar cost.

Wall-clock latency under concurrent batching is secondary because it need not
be additive. A decomposition is claimed for a secondary clock only if that
clock independently passes the inverse-share gate. Signal acquisition is free
in the controlled arm. In any practical arm its measured cost must be added to
the final deployment score; it is not hidden inside the four terms.

## Estimands And Sample Splitting

Use three nonoverlapping splits, each balanced by mode:

| Split | Tasks per mode | Permitted use |
| --- | ---: | --- |
| generator development | 64 | tune task templates and difficulty; never analyze |
| calibration | 96 | estimate `t0`, off-diagonal hazard, and any practical posterior |
| confirmation | 96 | one frozen physical evaluation of closure and choice |

The primary `t0(M,s)` is the conditional **mean first-passage number of useful
fixed-cost slots** under full allocation to the correct shard. The primary
`T(M,q,s,z)` is the conditional mean total normalized resource to the first
verified solution under the physical scheduler. Estimate the cell mean first,
then take its logarithm:

\[
\widehat L(M,q)
=\sum_{s,z}\widehat P(s,z)
  \log \widehat T(M,q,s,z).
\]

Do not average per-run log times: in general
`E[log(tau)] != log(E[tau])`. A 90% first-passage quantile is reported as a
secondary proper-time diagnostic and receives a separate packedness test.

The calibration-only prediction relative to the 14B prior-matched baseline is

\[
\widehat\Delta_{4}
=\log\frac{\widehat\kappa_{14B}}{\widehat\kappa_M}
+\frac13\sum_s
  \log\frac{\widehat t_0(14B,s)}{\widehat t_0(M,s)}
+I(S;Z)-\varepsilon(q).
\]

The confirmation response is

\[
\widehat\Delta_{\rm obs}
=\widehat L(14B,\pi)-\widehat L(M,q),
\qquad
\widehat R=\widehat\Delta_{\rm obs}-\widehat\Delta_4.
\]

All uncertainty intervals use a nested cluster bootstrap over calibration and
confirmation tasks while preserving paired model, signal, and allocation
results. The controlled signal values are enumerated and weighted by the known
channel rather than estimated from random signal counts.

## Mandatory Gates And Falsification

The analysis proceeds in this order. A failed gate is a result, not a tuning
signal.

### Gate 1: verifier validity

- mutation score at least `0.95` for every task;
- zero flaky outcomes in 20 reruns;
- zero accepted wrong-contract reference patches.

### Gate 2: usable stochastic regime

- focused pass@1 at least `0.05` on the frozen calibration split;
- confirmation censoring below `5%` in every primary cell;
- no significant attempt-index trend after conditioning on task and model.

If confirmation censoring exceeds the threshold, report restricted mean
resource and do not claim exact closure.

### Gate 3: specialization and packedness

- the upper 95% confidence bound on the ratio of off-diagonal to matched
  success hazard is at most `0.02`;
- in the preregistered regression
  `log T = cell_intercept - beta log q`, the 90% equivalence interval for
  `beta` lies inside `[0.90, 1.10]`;
- requested shares and the full pre-generated, outcome-independent schedule
  shares differ by at most `0.01` absolutely after aggregation.

The hazard-ratio threshold bounds the log-time distortion from wrong-stream
success by `log(1.02) < 0.02` nats.

### Gate 4: four-term closure

- absolute weighted mean residual at most `0.10` nats;
- weighted residual RMS at most `0.15` nats;
- 95% bootstrap upper bound on residual RMS at most `0.20` nats;
- no residual slope against cost, competence, information, or mismatch after
  Holm correction at family-wise `alpha = 0.05`.

Passing Gate 4 supports the decomposition only on the tested task family and
resource clock. Failure localizes which assumption is wrong through the prior
gates and residual plots.

## Practitioner Decision Test

For an arbitrary candidate design, compute from calibration data

\[
\widehat{\mathrm{Score}}(M,q)
=
\log\widehat\kappa(M)
+\sum_s\widehat\pi(s)\log\widehat t_0(M,s)
+\widehat H(S\mid Z)
+\widehat\varepsilon(M,q).
\]

Choose the model/allocation with the smallest score before opening the
confirmation split. The practitioner claim passes when:

- Kendall rank correlation between predicted and observed designs is at least
  `0.80`;
- the selected design's observed resource is within `10%` of the confirmation
  oracle;
- nested-bootstrap probability that the selected model beats the alternatives
  is at least `0.80`.

If the probability threshold is not reached, the output is a statistically
indistinguishable candidate set rather than a forced winner. The score can be
recomputed under FLOPs, latency, energy, or dollars; model choice is explicitly
clock-dependent.

## Power Analysis

`scripts/power_analysis.py` is a design calculation, not evidence. It samples
focused pass probabilities over a conservative `[0.15, 0.65]` sensitivity regime,
simulates independent calibration and confirmation first-passage data, and
checks closure, the inverse-share slope, and held-out model choice. It reads no
repository result.

```bash
uv run python experiments/four-term-packed-validation/scripts/power_analysis.py \
  --replicates 1000 \
  --sample-sizes 64 128 192 256 \
  --output /tmp/four-term-power.json
```

The original conservative sensitivity calculation reports sizes in independent
trajectories per cell. A second analysis conditions on the BF16 Stage 0 hazards,
adds task-level logit heterogeneity, simulates 32-attempt calibration with one
extension to 64, and executes the exact censored IID schedule. It selects 96
task clusters per mode with two trajectories per `(task, z, allocation)` cell.
This size was frozen before calibration or confirmation seeds were created.
Final uncertainty is determined by the paired task bootstrap on actual
confirmation trajectories.

The checked conservative design run with 1,000 replications is summarized in
`results/README.md`. At 128 independent trajectories per cell it yields a 95th
percentile residual RMS of `0.115` nats and an inverse-share slope range of
`0.966`--`1.034`; its stricter requirement that every one of 36 simulated
design residuals be below `0.15` nats passes only 69% of the time. The primary
experiment has six conditions and gates weighted mean and RMS residuals, not
the maximum of 36 cells. These synthetic null results do not establish
packedness; the physical inverse-share and closure gates remain mandatory.

The Stage-0-conditioned calculation uses 2,000 replications. At the frozen 96
tasks per mode it identifies every focused cell, passes all point closure gates
in `97.4%` of packed-null simulations, has 95th-percentile residual RMS `0.090`
nats, and has 95th-percentile maximum cell censoring `1.04%`. This is a power
calculation under the law being tested, not evidence that the law holds.

## External-Validity Arm

After all primary decisions are frozen, repeat only the practitioner ranking
test on a stratified subset of BigCodeBench. Define modes from required library
families and let evidence streams carry family-specific API context. Because
strategies overlap and modes are not exclusive, report the packedness slope and
closure residual without expecting them to pass the strict SAI-3 gates. This
arm tests usefulness under realistic misspecification; it cannot rescue a
failed primary confirmation.

## Required Outputs

A completed bundle must contain:

- frozen generator version and task manifests for every split;
- model revisions, serving image, hardware, and tokenizer hashes;
- every prompt, seed, completion, verifier result, token count, and cost;
- requested and realized scheduler shares;
- calibration estimates and untouched confirmation records;
- packedness, off-diagonal hazard, closure, and residual tables;
- bootstrap draws and practitioner ranking/regret table;
- a machine-readable statement of every passed and failed gate.

Until the calibration and untouched confirmation artifacts exist, Stage 0 is
development evidence only and this directory does not support the paper's
four-term empirical claim.
