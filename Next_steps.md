# Next Steps for Framework Validation and Final Paper

This document defines the remaining work needed to validate the framework and turn the current draft into a final NeurIPS submission. It intentionally avoids treating preliminary runs as paper evidence. The current repository should be used as a pilot implementation and analysis scaffold, while the final empirical campaign should be designed around the theoretical claims.

## Core Position

The paper should not be framed around a single existing benchmark. The main claim is broader:

> In verifiable agentic systems, model choice is not a scalar leaderboard decision. It is a decomposable performance-accounting problem involving per-step cost, mode-specific competence, routing information, and routing mismatch.

The empirical campaign must therefore test whether this decomposition is measurable, predictive, and useful for model selection across controlled and realistic settings.

## What Must Be Validated

### 1. Theoretical Contract

Clarify exactly what Assumption 1 buys us and where it may fail.

Required tasks:

- State the packed latent-mode assumption as a modeling contract, not as a universal empirical law.
- Separate theorem-level assumptions from empirical approximations.
- Define the observable estimands corresponding to each theoretical term:
  - model cost;
  - mode-specific success probability;
  - information about the latent mode;
  - routing mismatch;
  - certified effort or cost-adjusted time-to-verification.
- Decide whether the main theorem remains in the body or whether proof details move to the appendix.
- Add a short limitations paragraph explaining that real trajectories may have state, memory, and non-geometric retry behavior.

Definition of done:

- A reader can identify which claims are exact mathematical identities and which claims are empirical hypotheses.
- The paper does not oversell Assumption 1 as a realistic description of all agentic systems.

### 2. Empirical Plausibility of Latent Modes

The framework requires task instances to be meaningfully grouped into modes. The final campaign should test this directly.

Required tasks:

- Build a controlled latent-mode benchmark where the true mode is known by construction.
- Build a semi-natural benchmark where modes are not directly given and must be inferred from observable features, traces, or verifier feedback.
- Measure whether modes are separable before solving, during solving, and after observing failures.
- Compare oracle modes against learned/discovered modes.

Candidate mode families:

- algorithmic optimization;
- API/tool-use repair;
- long-context retrieval;
- debugging hidden state;
- multi-file code repair;
- data transformation;
- numerical reasoning;
- adversarial edge cases.

Primary diagnostics:

- mode separability from task metadata;
- mode separability from early agent traces;
- stability of learned modes across random seeds and task samples;
- performance degradation when replacing oracle modes with discovered modes.

Definition of done:

- The paper can show that the latent-mode abstraction is not merely a post-hoc explanation.
- If discovered modes are weak, the paper can state this honestly and use the result as a limitation or negative diagnostic.

### 3. Mode-Specific Model Competence

The central empirical hypothesis is that different models are best on different task modes after accounting for cost.

Required tasks:

- Run each candidate model on each task mode under the same harness and verifier.
- Estimate per-mode success probabilities and uncertainty intervals.
- Measure whether the model-by-mode interaction is stronger than a scalar global ranking.
- Include cheap, mid-tier, and strong models so that cost-competence tradeoffs are visible.
- Test whether retry depth changes the recommended model.

Candidate model menu:

- cheap/fast model;
- medium model;
- strong/slow model;
- optional specialized coding model;
- optional open-weight baseline if infrastructure permits.

Primary diagnostics:

- model-by-mode success heatmap;
- cost-adjusted competence heatmap;
- crossover curves by retry depth;
- interaction test: does the best model depend on task mode?

Definition of done:

- The campaign demonstrates either a nontrivial routing regime or a principled negative result where one model dominates after cost adjustment.

### 4. Retry and Time-to-Success Model

Assumption 1 uses a memoryless per-attempt success abstraction. This is mathematically clean, but it must be stress-tested.

Required tasks:

- Run repeated attempts per model/mode/instance.
- Estimate empirical time-to-verification curves.
- Compare geometric retry predictions against observed survival curves.
- Check whether attempts are independent enough for the theorem to be a useful approximation.
- If memoryless retry fails, decide whether to:
  - keep the theorem as a clean baseline and report deviation;
  - add an appendix extension using empirical hazards;
  - replace per-attempt probability with depth-dependent success curves.

Primary diagnostics:

- empirical survival curves;
- predicted vs observed time-to-success;
- hazard by attempt index;
- calibration error of the geometric surrogate.

Definition of done:

- The paper can defend the use of the certified-effort surrogate or clearly state when it breaks.

### 5. Cost Model

The decomposition treats model cost as a measurable term. The final paper must avoid hiding cost variability.

Required tasks:

- Log wall-clock time, token count, API cost, and verifier/runtime overhead separately.
- Report results under at least two cost metrics:
  - wall-clock latency;
  - dollar or token-normalized cost.
- Estimate whether cost is mostly model-specific or strongly mode-specific.
- Include harness overhead in the accounting.

Primary diagnostics:

- cost distribution by model and mode;
- model-only cost approximation error;
- sensitivity of recommendations to cost metric.

Definition of done:

- The recommendation does not depend on an arbitrary or underreported cost convention.

### 6. Routing Information and Mismatch

The most distinctive part of the paper is not only that models differ, but that routing can use or waste information.

Required tasks:

- Define at least three routing policies:
  - single-model baseline;
  - oracle-mode router;
  - learned router from task features or early traces.
- Add a deliberately weak router as a negative control.
- Estimate information gain and mismatch for learned routers.
- Test whether low mismatch predicts near-oracle selection performance.

Primary diagnostics:

- oracle vs learned router objective;
- routing mismatch curve vs pilot sample size;
- information gain from metadata vs early traces vs verifier feedback;
- failure examples where useful information exists but the router misallocates compute.

Definition of done:

- The paper can show that the decomposition diagnoses why a model-selection policy succeeds or fails.

### 7. Selection Sample Efficiency

The paper should compare decomposition-guided selection against naive end-to-end racing.

Required tasks:

- Define a fixed design menu: models, retry depths, and routers.
- Compare:
  - full end-to-end racing;
  - scalar model leaderboard;
  - decomposition-guided selection;
  - oracle upper bound.
- Vary pilot sample size.
- Measure how many task runs are needed to select a near-optimal design.

Primary diagnostics:

- selected design regret vs pilot budget;
- probability of selecting a near-optimal design;
- total experimental cost to reach a decision;
- robustness to mode prior shift.

Definition of done:

- The paper demonstrates a practical reason to use the decomposition instead of only racing all candidate systems.

## Publication-Ready Experimental Campaign

The final campaign should be large enough to support paper-level empirical claims, but small enough to finish under deadline pressure. The recommended target is a four-model main campaign with optional fifth-model appendix runs.

### Recommended Main Model Set

Use four primary models:

| Role | Repo alias | Reason |
| --- | --- | --- |
| Cheap/fast generalist | `gpt_5_4_mini` | Provides the low-cost baseline needed to test whether cheap retries can beat stronger single attempts. |
| Strong generalist | `gpt_5_4` | Provides a frontier general model with stronger reasoning and tool-use capability. |
| Coding-specialized model | `gpt_5_3_codex` | Tests whether specialization for agentic coding changes the per-mode competence profile. |
| Cross-provider balanced/strong model | `claude_sonnet` | Adds provider diversity with a serious non-OpenAI competitor, reducing the risk that the paper is only an OpenAI-internal ladder. |

Optional fifth model:

| Role | Repo alias | When to include |
| --- | --- | --- |
| Cross-provider cheap model | `claude_haiku` | Include if we want a second cheap/fast point and stronger cost-scaling evidence. |
| Upper-capability Anthropic model | `claude_opus_4_6` | Include only in appendix or focused subsets if budget permits. |

Models not recommended for the main campaign:

- `claude_opus_4_6`: useful as an upper-capability appendix point, but likely too expensive for the full campaign.
- `gpt_5_2_codex`: useful for backward comparison, but less central than the current Codex-specialized model.
- `qwen_coder`: useful as an open/local appendix baseline only if the local serving stack is stable and throughput is acceptable.
- local stubs: useful for infrastructure tests only, not publication evidence.

### Main Run Budget

The target publication-ready campaign should be long-horizon. The unit of experimental assignment is a trajectory run: one model, one task instance, one maximum horizon. The unit of compute is a model-step call. A trajectory with maximum horizon `H=8` can consume up to eight model-step calls, but it stops early once the verifier certifies success.

Horizon policy:

- Main setting: `H=8`.
- Short-horizon baseline: `H=1`.
- Medium-horizon diagnostic: `H=3`.
- Long-horizon stress subset: `H=16`.
- Primary time-to-success variable: `tau`, the first step at which the verifier certifies success.
- If the prompt does not reveal the maximum horizon, `H=16` trajectories can be truncated post hoc to estimate `H in {1,3,8,16}`. If the model sees the horizon, the horizon-ablation subset should be run separately.

| Block | Purpose | Design | Trajectory runs | Max model-step calls |
| --- | --- | --- | --- | --- |
| Controlled latent-mode validation | Test the decomposition when the packed-mode abstraction is closest to true. | 4 models x 6 modes x 30 tasks, `H=8` | 720 | 5,760 |
| Semi-synthetic coding/tool-use validation | Test designed but realistic modes under a verifier. | 4 models x 6 modes x 20 tasks, `H=8` | 480 | 3,840 |
| Naturalistic agent benchmark | Test external validity with discovered or weakly supervised modes. | 3 models x 150 tasks, `H=8` | 450 | 3,600 |
| Horizon/time-to-success ablation | Test survival curves, hazards, geometric approximation, and retry-depth crossovers. | 4 models x 6 modes x 10 tasks x extra horizons `{1,3,16}`; reuse `H=8` subset from main runs | 720 extra | 4,800 extra |
| Negative controls and routing stress tests | Test trivial routing, weak routers, corrupted modes, and cost dominance. | 150-250 trajectories, usually `H=8` | 150-250 | 1,200-2,000 |

Recommended target:

- Main campaign: 2,520-2,620 trajectory runs before failed-run reruns.
- Worst-case upper bound: about 19,200-20,000 model-step calls.
- Expected completed model-step calls with early stopping: about 10,000-15,000.
- Practical budget including failed runs and reruns: about 3,000 trajectory runs, or 12,000-18,000 completed model-step calls.
- Optional fifth-model appendix: add 300-500 trajectories, focused on controlled and semi-synthetic settings only; budget 2,400-3,600 max model-step calls.

### Smaller Submission-Safe Campaign

If time or API budget becomes tight, use the following minimum:

| Block | Design | Trajectory runs | Max model-step calls |
| --- | --- | --- | --- |
| Controlled latent-mode validation | 4 models x 5 modes x 20 tasks, `H=8` | 400 | 3,200 |
| Semi-synthetic validation | 4 models x 5 modes x 12 tasks, `H=8` | 240 | 1,920 |
| Naturalistic stress test | 3 models x 80 tasks, `H=8` | 240 | 1,920 |
| Horizon/time-to-success subset | 4 models x 5 modes x 5 tasks x extra horizons `{1,3,16}`; reuse `H=8` subset | 300 extra | 2,000 extra |
| Negative controls | Reserve | 0-100 | 0-800 |

Minimum credible total:

- 1,180-1,280 trajectory runs.
- 9,000-9,800 worst-case model-step calls.
- This is enough for a submission, but uncertainty intervals, long-horizon hazard estimates, and mode-by-model interaction claims will be weaker.

### Runtime and Compute Estimate

Assume hosted API models and a local orchestrator.

Sequential time estimate:

- 10,000 completed model-step calls at 60 seconds per step: about 167 sequential hours.
- 15,000 completed model-step calls at 120 seconds per step: about 500 sequential hours.
- 18,000 completed model-step calls at 180 seconds per step: about 900 sequential hours.

Parallel wall-clock estimate:

- 8-way parallelism: about 21-113 hours of pure runtime, depending on step latency and early stopping.
- 16-way parallelism: about 11-57 hours of pure runtime.
- Realistic elapsed time with rate limits, failures, reruns, and analysis: 4-8 days.

Local machine requirements:

- 8-16 CPU cores;
- 32GB RAM;
- 50-100GB disk for logs and artifacts;
- stable network;
- robust retry and checkpointing;
- rate-limit aware scheduler.

GPU requirements:

- No GPU is required if the main campaign uses hosted API models.
- GPU is only needed for optional local/open-weight baselines such as Qwen.

### Publication-Ready Evidence Standard

The final paper should not report preliminary tables as evidence. A result becomes publication-ready only if:

- the model menu is locked before the final campaign;
- the horizon policy is locked before the final campaign;
- task modes and splits are locked before the final campaign;
- verifier logic is frozen;
- cost metric conventions are frozen;
- failed-run handling is documented;
- `tau` and per-step logs are recorded for every trajectory;
- uncertainty intervals are reported for all primary comparisons;
- learned-router results are evaluated on held-out tasks;
- all main claims pass the claim-promotion gates below.

## Recommended Experimental Structure

### Experiment A: Controlled Latent-Mode Validation

Purpose:

- Test the theorem in the cleanest possible regime.

Design:

- Construct task families with known modes.
- Run all models under the same verifier.
- Compare oracle routing, learned routing, and single-model baselines.

Expected figures:

- model-by-mode competence heatmap;
- router allocation heatmap;
- predicted vs realized cost-adjusted effort;
- retry-depth crossover curves.

### Experiment B: Semi-Synthetic Coding and Tool-Use Tasks

Purpose:

- Test whether the framework survives more realistic agentic structure while retaining enough control for clean evaluation.

Design:

- Use coding/tool tasks where modes are designed but not directly exposed to the router.
- Infer modes from metadata, early traces, or verifier feedback.
- Compare true-mode router against learned-mode router.

Expected figures:

- mode recovery matrix;
- routing mismatch vs pilot budget;
- decomposition terms by model and router;
- examples of mode confusion.

### Experiment C: Naturalistic Agent Benchmark

Purpose:

- Test external validity.

Design:

- Use real or realistic tasks such as repository repair, notebook fixing, data-analysis agents, or benchmark subsets with verifiable success.
- Discover modes from traces.
- Treat mode labels as latent clusters rather than ground truth.

Expected figures:

- discovered mode taxonomy;
- selection regret vs budget;
- cost-normalized success frontier;
- decomposition residuals showing where the theory is approximate.

### Experiment D: Negative Controls and Stress Tests

Purpose:

- Show that the framework is falsifiable.

Design:

- Include settings where routing should be trivial.
- Include noisy or intentionally misleading mode labels.
- Include routers with insufficient information.
- Include tasks where cost dominates competence.

Expected figures:

- trivial-routing detection;
- degradation under corrupted mode labels;
- mismatch increase under weak routers;
- sensitivity to cost metric and success threshold.

## Paper Revision Plan

### Main Paper

Immediate edits:

- Remove preliminary numerical results from main tables.
- Replace result tables with experiment-design tables and placeholders.
- Reframe the current repository results as pilot evidence or omit them from the main paper until the final campaign is complete.
- Present Assumption 1 as a clean theoretical regime.
- Emphasize that empirical sections are designed to test, not assume, the packed-mode abstraction.

Main sections to target:

1. Introduction.
2. Verifiable model selection.
3. Packed latent-mode decomposition.
4. Decomposition-guided model selection.
5. Experimental protocol.
6. Planned empirical validation.
7. Related work.
8. Discussion targets and limitations.

### Appendix

Appendix material:

- full theorem proofs;
- estimator definitions;
- retry-depth extensions;
- router objective derivations;
- sample-size calculations;
- benchmark generation details;
- additional plots;
- implementation details.

## Concrete Work Queue

### Phase 1: Framework Cleanup

- Finalize the exact statement of Assumption 1.
- Decide whether to add a non-memoryless extension.
- Define all empirical estimators.
- Define primary and secondary metrics.
- Remove preliminary-result values from the draft.

### Phase 2: Benchmark Design

- Specify controlled modes.
- Specify semi-synthetic coding/tool modes.
- Choose the naturalistic benchmark.
- Define verifier logic for each benchmark.
- Define task sampling and train/pilot/holdout splits.

### Phase 3: Experimental Infrastructure

- Generalize the current analysis scripts beyond the existing query-engine setting.
- Add router interfaces:
  - oracle router;
  - feature router;
  - trace router;
  - weak/noisy router.
- Add repeated-attempt support.
- Add survival-curve and hazard analysis.
- Add early stopping on verifier-certified success and log `tau`.
- Decide whether the model prompt can see the maximum horizon; this determines whether horizon curves can be estimated by truncating `H=16` trajectories.
- Add cost logging for wall time, tokens, dollars, and verifier overhead.

### Phase 4: Pilot and Power Analysis

- Run a small pilot only to estimate variance and feasibility.
- Use pilot variance to determine final sample sizes.
- Lock the design menu before running the final campaign.
- Define claim-promotion gates before looking at final results.

### Phase 5: Final Campaign

- Run the controlled benchmark.
- Run the semi-synthetic benchmark.
- Run the naturalistic benchmark.
- Run negative controls.
- Freeze final artifacts and random seeds.

### Phase 6: Paper Finalization

- Fill result tables only after the final campaign.
- Replace figure placeholders with final plots.
- Move secondary plots to the appendix.
- Write discussion from actual outcomes.
- Complete NeurIPS checklist with exact compute, data, and reproducibility details.

## Claim-Promotion Gates

The paper should only make a strong empirical claim if the corresponding gate is passed.

| Claim | Required gate |
| --- | --- |
| Modes are meaningful | Modes are separable or recoverable better than chance on held-out tasks. |
| Model choice is mode-dependent | Best cost-adjusted model differs across modes or retry depths. |
| Routing helps | Learned routing beats single-model baselines under held-out evaluation. |
| Decomposition is predictive | Decomposition-guided selection has lower regret or lower sample cost than scalar racing. |
| Assumption 1 is empirically useful | The certified-effort surrogate predicts observed time-to-success within acceptable error. |
| Framework is diagnostic | Failure cases correspond to interpretable terms: low information, high mismatch, weak competence, or high cost. |

## Open Decisions

- Should the main theorem stay in the body, or should only the decomposition identity stay in the body?
- Should the final benchmark be coding-only, or should it include non-coding verifiable agent tasks?
- Should the router observe only task metadata, early traces, verifier feedback, or all three?
- Should retry depth be part of the main model-selection menu?
- Which cost metric is primary: wall-clock, dollars, or tokens?
- Which naturalistic benchmark is feasible before the deadline?

## Immediate Next Actions

1. Revise the Overleaf draft to remove preliminary numerical result claims from the main paper.
2. Convert the empirical section into a protocol-first section.
3. Choose the controlled latent-mode benchmark design.
4. Choose the naturalistic benchmark.
5. Define the exact model menu and cost convention.
6. Freeze the long-horizon policy: main `H=8`, ablation `H in {1,3,8,16}`.
7. Implement repeated-attempt logging, `tau`, early stopping, and survival-curve analysis.
8. Run a small pilot for variance estimation only.
9. Lock claim-promotion gates before the final campaign.
