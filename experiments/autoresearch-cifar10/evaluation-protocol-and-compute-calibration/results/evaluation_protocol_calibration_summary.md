# Evaluation Protocol Calibration Summary

**Status**: Archived
**Period**: April 2026 (first experiment)
**Objective**: show why parallel agent evaluations need fixed-step evaluation or explicit compute accounting before claims about agent quality.

---

## Main Finding

The first 2x2 agent pilot was not a clean test of parallel agent quality because
parallel training jobs shared the same CPU. Under fixed-time evaluation, more
concurrent training workers complete fewer optimizer updates and produce worse
validation loss. Under fixed-step evaluation, validation loss stays fixed because
every worker completes the same number of updates; the cost appears as
additional wall-clock latency.

This experiment therefore supports a protocol rule used by later experiments:

> Compare agent workflows under fixed-step evaluation, or report compute
> allocation explicitly. Do not interpret fixed-time CPU-parallel runs as pure
> evidence about agent decision quality.

## Paper Figures

![Fixed-time compute loss](figures/figure-01-fixed-time-compute-loss.png)

**Figure 1** shows the fixed-time confound directly: increasing concurrent
training workers reduces optimizer updates per worker, and validation loss
worsens at the same time.

![Fixed-step latency cost](figures/figure-02-fixed-step-latency-cost.png)

**Figure 2** shows the fixed-step control: all workers complete 300 optimizer
updates and reach the same validation loss. Parallelism changes wall-clock time,
not quality.

![Throughput efficiency](figures/figure-03-throughput-efficiency.png)

**Figure 3** shows the capacity curve: throughput rises sublinearly and parallel
efficiency falls as workers contend for CPU.

## Research Question

Can we empirically measure how parallelism and memory affect autonomous LLM
agents without confusing agent behavior with compute allocation? Secondarily,
can the BP framework's mathematical decomposition explain the observed
differences?

**Background**: Beneventano and Poggio proposed a theoretical framework that decomposes the performance gain (or loss) of an agent configuration relative to a baseline into four interpretable terms:

```
Delta = log(kappa_0 / kappa) + phi + G - epsilon
```

Each term has a specific empirical estimator used in this pilot:

- **log(kappa_0 / kappa)** — cost efficiency. kappa is the mean cost per LLM turn, measured in two units:
  - *Token axis*: kappa_token = mean tokens per turn (input + output). Tokens are read from the Claude API `usage` response; if unavailable, estimated as total_characters / 4, calibrated against turns that do have API counts (median ratio correction).
  - *Wall-clock axis*: kappa_wall = mean wall-clock seconds per turn.
  - The ratio kappa_0/kappa compares the baseline cell (d00) to the design cell. log > 0 means the design cell is cheaper per turn.

- **phi** — prior alignment. Estimated via mode-conditional attempts-to-first-success: for each edit category (optimizer, lr_schedule, architecture, batch_data), count how many turns until the first accepted change. phi = weighted sum of log(baseline_steps / design_steps) across categories, weighted by the global prior (relative frequency of each category across all cells). phi > 0 means the design cell finds improvements faster.

- **G** — information gain. Estimated as KL(pi_D || pi_global), where pi_D is the distribution of accepted edit categories in the design cell and pi_global is the pooled distribution across all cells. G > 0 means the design cell specializes differently from the population average — it has learned to focus on certain categories. Uses Laplace smoothing (1e-6) to avoid division by zero.

- **epsilon** — coordination mismatch. Estimated as KL(pi_D || q_D), where pi_D is the distribution of *accepted* edit categories and q_D is the distribution of *proposed* edit categories (including rejected ones). epsilon > 0 means the agent wastes effort proposing changes in categories that don't get accepted — it routes exploration poorly.

**Why phi, G, epsilon were near-zero in the pilot**: The mode labeling system classifies each agent edit into categories, but in the pilot most edits fell into the same category ("optimizer"), yielding near-uniform distributions. With so little category diversity, the KL divergences collapse to zero and the attempts-to-first-success ratios are uninformative. This is a measurement resolution problem, not a theoretical one.

This decomposition was developed for theoretical analysis. The question is whether it produces measurable terms when applied to real LLM agents running real ML tasks.

**Experimental approach**: We use a 2x2 factorial design crossing parallelism (1 vs 2 agents) with memory (none vs external/shared), where the agents autonomously train CNNs on CIFAR-10. The baseline cell d00 (single agent, no memory) anchors the decomposition: each other cell's performance is decomposed into the four terms relative to d00.

**Goal**: Build the full instrumentation pipeline (token tracking, mode labeling, decomposition computation) and run a minimal pilot (3 reps per cell) to check whether (a) the infrastructure works end-to-end, (b) the decomposition terms are measurable above noise, and (c) any of six pre-registered hypotheses about parallelism and memory show consistent direction. This is explicitly a feasibility experiment, not a confirmatory experiment.

**Six pre-registered hypotheses**:
- **H1**: Parallelism helps wall-clock efficiency but not token efficiency (agents run faster but don't use fewer tokens)
- **H2**: Memory helps on both axes (fewer tokens and less wall-clock time per improvement)
- **H3**: Shared memory lowers coordination mismatch epsilon (agents avoid duplicating work)
- **H4**: Parallelism is sensitive to coordination — epsilon exceeds log(2) when agents lack shared info
- **H5**: Context pressure is the dominant cost driver — kappa increases monotonically as the agent's context fills up
- **H6**: d11 (parallel + shared memory) dominates d00 on both token and wall-clock axes

## Experimental Design

The pilot tested the 2x2 factorial design:

|              | No Memory (0) | Memory (1)     |
|--------------|---------------|----------------|
| **Single (0)** | d00 (baseline) | d10            |
| **Parallel (1)** | d01           | d11            |

### Task, model, and metrics

**Task**: Each LLM agent (claude-haiku-4-5) is given a git repository containing a CIFAR-10 image classification problem. The agent autonomously reads and edits `train.py`, choosing hyperparameters and architecture modifications, then runs training. After each training attempt, the agent observes the result and decides what to try next.

**Model being trained**: A configurable CNN (`CIFAR10Net`) for CIFAR-10 (32x32 RGB images, 10 classes). Default architecture: 3 convolutional blocks (Conv2d + BatchNorm + ReLU + Dropout + MaxPool), followed by a fully connected classifier (128 hidden units). ~357K parameters. All training runs on CPU (no GPU available in this environment).

**What the agent optimizes**: Across successive training attempts within a single experiment, the LLM agent modifies `train.py` to change:
- **Optimizer**: type (Adam, AdamW, SGD), learning rate, weight decay, momentum, betas
- **Schedule**: warmup epochs, LR decay factor, decay milestones
- **Architecture**: depth (number of conv blocks), base channels, channel multiplier, dropout rate, FC hidden width, batch norm on/off
- **Data**: batch size

The agent follows a one-change-per-turn strategy, guided by its memory of previous attempts.

**val_bpb metric**: Despite the name "bits per byte", this is simply the **cross-entropy loss** on the CIFAR-10 test set (10,000 images). It is printed as `val_bpb` in the training output but is identical to `val_loss`. Lower is better. Typical range: 0.73-0.90 for well-tuned models, ~1.9 for untrained/short runs.

**Why initial val_bpb differs across runs**: The "initial val_bpb" in the table is the result of the **first training attempt** — but the LLM agent modifies `train.py` *before* launching that first attempt. The agent is non-deterministic (Claude's sampling temperature), so two runs of the same cell will make different first edits to the hyperparameters, producing different first val_bpb values. For example, d01/rep1's agent happened to choose poor initial hyperparameters (initial val_bpb = 0.900, worst in the table), while d10/rep2's agent got lucky (0.761, close to the final best). The underlying `train.py` is deterministic (SEED=42, deterministic PyTorch), so given the same code the same val_bpb is always produced — all variance comes from the LLM's non-deterministic code edits. This is an inherent feature of the experimental design (the agent's choices ARE the experiment), not a bug.

**Tokens consumed**: This counts **Claude API tokens** (input + output) used by the LLM agent during its autonomous loop — how much "thinking" the agent did. It is NOT related to training data tokens. Counted from the API usage response when available, or estimated as characters/4 as fallback. Parallel cells consume roughly 2x more tokens because two agents run simultaneously.

### Memory configurations

The 2x2 design tests two types of memory, both injected as text prepended to the agent's input message at each turn:

**External memory (d10 — single agent)**:
A private experiment log table built from `training_runs.jsonl`. The agent sees a compact markdown table of all its previous training attempts:

```
# Experiment Log
| # | change                  | bpb    | delta   | best |
|---|-------------------------|--------|---------|------|
| 1 | increase BASE_CHANNELS  | 0.8271 | —       | ✓    |
| 2 | lower LR to 5e-4       | 0.8004 | -0.0267 | ✓    |
| 3 | add dropout 0.1         | 0.8312 | +0.0308 |      |
```

This gives the agent a structured history of what it tried and what worked, replacing the implicit memory that would otherwise accumulate (and degrade) in the growing conversation context. The table is rebuilt from the monitoring log at each turn, so it is always complete and accurate.

**Shared memory (d11 — parallel agents)**:
A cross-agent experiment log built from `shared_results_log.jsonl`. Both agents write to the same JSONL file (with file locking) after each training run, and both read it before each turn:

```
# Shared Experiment Log (all agents)
| agent | # | change                  | bpb    | kept |
|-------|---|-------------------------|--------|------|
| ag_0  | 1 | lower LR to 5e-4       | 0.8012 | ✓    |
| ag_1  | 1 | increase depth to 4     | 0.8449 | ✗    |
| ag_0  | 2 | add weight decay 5e-4   | 0.7962 | ✓    |
```

This lets each agent see what the other has tried, ideally reducing duplicated exploration. The shared log is stored as a symlink inside each agent's git worktree, pointing to the experiment-level shared file.

**No memory (d00, d01)**: The agent receives only its current budget status and task description. Previous attempts are visible only through the growing conversation context, which degrades as the context window fills up.

The archived evidence now has four bundles: the original 2x2 agent pilot,
exploratory runs, a fixed-time compute-allocation benchmark, and a fixed-step
pair benchmark.

### 1. Pilot 2x2 feasibility — 12 runs (4 cells x 3 reps)

Each agent is an LLM (claude-haiku-4-5) that autonomously writes and trains small neural networks. The **base time budget** is 30 minutes (1800s) per experiment: the agent has 30 minutes of wall-clock time to iterate on code and launch training runs. Each individual **training attempt** is capped at 120 seconds. Within the 30-minute window, the agent decides how many training attempts to make — typically 2-9 for single-agent cells, 9-18 for parallel cells (because two agents run independently).

### 2. Exploratory config iteration — 8 runs

Same 4 modes as the pilot, but with a shorter **10-minute budget** (600s) and 120s per training attempt. All configs use claude-haiku-4-5. The 8 runs are: 5x single-long (no memory, 1 agent), 1x single-memory (external memory, 1 agent), 1x parallel (2 agents, no memory), 1x parallel-shared (2 agents, shared memory). The purpose was rapid iteration to explore different hyperparameter choices before committing to the full pilot.

### 3. Fixed-Time Compute-Allocation Scaling — N=1..8

In the pilot, parallel cells (d01/d11) showed worse val_bpb than single cells (d00/d10). But is that because parallelism itself is unhelpful, or because two training processes running simultaneously on the same CPU compete for compute and each one gets fewer gradient steps done?

To answer this, we remove the LLM agent entirely and run **only the training script** (`train.py`) directly, with a fixed 2-second training budget. This isolates the pure hardware contention effect: same code, same hyperparameters, same seed — the only variable is how many copies run at the same time on the 10-core CPU machine.

The experiment launches N identical `train.py` processes simultaneously (N=1,2,4,8) and measures: (a) how many gradient steps each process completes in 2 seconds, (b) the resulting val_bpb, (c) total wall time and throughput. Two thread policies are tested: **default** (PyTorch's OpenMP uses all available cores per process, so N processes fight over the same 10 cores) and **partitioned** (CPU affinity pins 10/N cores to each process, eliminating thread contention).

Note: the val_bpb values here (~1.9) are much worse than the pilot (~0.8) because the training budget is 2 seconds vs 120 seconds — only ~19 gradient steps vs hundreds. The absolute values don't matter; what matters is the **relative degradation** as N increases.

### 4. Fixed-Step CPU Pair Benchmark — N=2

A later follow-up benchmark was added to answer the complementary question that the fixed-time scaling experiment could not answer: if every `train.py` process is forced to complete the same number of gradient updates, does CPU parallelism still hurt validation quality, or does it only make each evaluation slower?

This matters because the 2x2 agent design can be run with either fixed-time or fixed-step evaluators. Under a fixed-time evaluator, parallel jobs can produce worse results simply because each job completes fewer gradient steps in the same wall-clock budget. Under a fixed-step evaluator, the gradient-update count is equalized, so any remaining contention appears as wall-clock overhead instead of a direct quality penalty.

The follow-up used the deterministic calibration-design training workspace, CPU-only execution, and `MAX_STEPS = 300` for every worker. Results are stored in `fixed_step_cpu_pair_benchmark/`.

| Condition | Group wall time | Mean worker time | Steps | Mean val_bpb |
|-----------|-----------------|------------------|-------|--------------|
| 1 process, 4 threads | 86.99s | 85.88s | 300 | 1.267963 |
| 2 sequential processes, 4 threads each | 172.44s | 85.10s | 300, 300 | 1.267963 |
| 2 parallel processes, 4 threads each | 98.48s | 97.15s | 300, 300 | 1.267963 |
| 2 parallel processes, 2 threads each | 125.86s | 124.60s | 300, 300 | 1.267963 |

Interpretation: fixed-step CPU parallelism at N=2 did not reduce validation quality because all runs completed the same 300 gradient updates and reached the same val_bpb. It did introduce wall-clock contention. The best tested setting was two concurrent processes with four threads each: it finished the two evaluations 1.75x faster than running them sequentially, but each worker was 14.2% slower. Limiting each process to two threads was worse on this workload, giving only 1.37x group speedup and a 46.4% per-worker slowdown.

---

## Key Results

### 1. Pilot 2x2 (primary experiment)

**Per-cell per-rep breakdown** (training runs = number of train attempts the agent made within its 30-min budget):

| Cell | Rep | Training runs | Initial val_bpb | Best val_bpb | Tokens consumed |
|------|-----|---------------|-----------------|-------------|-----------------|
| d00  | 1   | 4             | 0.828           | 0.827       | 36,416          |
| d00  | 2   | 2             | 0.800           | 0.800       | 48,104          |
| d00  | 3   | 9             | 0.801           | 0.799       | 38,402          |
| d10  | 1   | 3             | 0.829           | 0.829       | 47,170          |
| d10  | 2   | 9             | 0.761           | 0.761       | 35,136          |
| d10  | 3   | 4             | 0.831           | 0.755       | 43,200          |
| d01  | 1   | 11            | 0.900           | 0.811       | 91,803          |
| d01  | 2   | 9             | 0.802           | 0.802       | 92,684          |
| d01  | 3   | 18            | 0.837           | 0.837       | 70,693          |
| d11  | 1   | 9             | 0.845           | 0.801       | 90,053          |
| d11  | 2   | 17            | 0.844           | 0.804       | 67,685          |
| d11  | 3   | 14            | 0.796           | 0.796       | 69,146          |

**Summary statistics**:

| Cell | Mode              | Mean training runs | Mean best val_bpb | Std   | N reps |
|------|-------------------|--------------------|---------------------|-------|--------|
| d00  | Single / No Memory | 5.0 +/- 2.9       | 0.809               | 0.016 | 3      |
| d10  | Single / Memory    | 5.3 +/- 2.6       | 0.782               | 0.041 | 3      |
| d01  | Parallel / No Mem  | 12.7 +/- 3.9      | 0.817               | 0.018 | 3      |
| d11  | Parallel / Memory  | 13.3 +/- 3.3      | 0.800               | 0.004 | 3      |

Note: parallel cells (d01, d11) produce ~2.5x more training attempts because two agents run independently, but this does not translate into better final quality — it reflects the resource contention problem.

**Observations**:
- Memory improves single-agent performance (d10 < d00 by ~0.027 bpb), but with high variance (std 0.041).
- Parallel agents without memory (d01) perform *worse* than baseline, suggesting resource contention degrades training quality.
- Parallel + memory (d11) partially recovers quality and shows the lowest variance (std 0.004), hinting at a stabilizing effect.
- None of the six pre-registered hypotheses (H1-H6) were fully supported at this sample size.
- Linear fit R^2(best_val_bpb ~ total_tokens) = 0.32 — token budget is a weak predictor of final quality.

![Pilot 2x2 comparison](figures/fig01_pilot_2x2_comparison.png)

**Figure 1 interpretation**: The error bars and scatter points reveal that d10 (memory) has the lowest mean but also the widest spread — two reps cluster near 0.755-0.761 while a third sits at 0.829, suggesting a bimodal outcome where memory either "clicks" and produces a large gain or fails to help at all. In contrast, d11 (parallel + memory) shows remarkably tight clustering (all 3 reps within 0.796-0.804), but its mean is not lower than d00. This hints that memory's benefit in d10 may depend on lucky initialization rather than a robust mechanism. The d01 bar sits above the d00 baseline, confirming that parallelism alone hurts — but the scatter shows one rep at 0.802 (comparable to d00) and another at 0.837, so the damage is also inconsistent. With only 3 points per cell, none of these differences would survive a significance test; the figure is best read as generating hypotheses, not confirming them.

![Best-so-far curves](figures/fig05_best_so_far_curves.png)

**Figure 5 interpretation**: The optimization trajectories (averaged across 3 reps) show best val_bpb as a function of cumulative Claude API tokens. d10 (memory, teal) improves fastest and reaches the lowest plateau (~0.782) with the fewest tokens (~10K). d00 (baseline, dark blue) plateaus early at ~0.809 with ~15K tokens. Both parallel cells (d01 red, d11 gold) consume 2-3x more tokens (60-90K) due to two agents running simultaneously, but d01 never drops below d00 — the extra tokens are wasted on contention-degraded training. d11 eventually drops below d00 (~0.800) but only after ~35K tokens, suggesting shared memory helps but slowly. The key insight: token efficiency (val_bpb improvement per token) is highest for d10, not for parallel cells — more agents does not mean faster convergence when hardware is constrained.

### 2. Exploratory Runs

All exploratory runs use claude-haiku-4-5, 10-minute budget, 120s per training attempt.

| Run                  | Mode             | Agents | Memory   | Shared | Best val_bpb |
|----------------------|------------------|--------|----------|--------|-------------|
| single-long (run1)   | single_long      | 1      | no       | no     | no data     |
| single-long (run2)   | single_long      | 1      | no       | no     | 0.762       |
| single-long (run3)   | single_long      | 1      | no       | no     | no data     |
| single-long (run4)   | single_long      | 1      | no       | no     | no data     |
| single-long (run5)   | single_long      | 1      | no       | no     | 0.816       |
| single-memory (run1) | single_memory    | 1      | **yes**  | no     | **0.739**   |
| parallel (run1)      | parallel         | 2      | no       | no     | 0.824       |
| parallel-shared (run1)| parallel_shared | 2      | no       | **yes**| 0.830       |

3 of 5 single-long runs produced no usable metrics (agent failed to complete a training run within budget).

**Observations**:
- The best result across the feasibility pilot was a single-agent + memory run (0.739), substantially beating the pilot mean.
- Parallel configurations consistently underperformed single-agent setups, reinforcing the resource contention finding.
- 3/8 exploratory runs produced no data, highlighting infrastructure fragility at shorter budgets.

![Exploratory comparison](figures/fig03_exploratory_comparison.png)

**Figure 3 interpretation**: The standout is single-memory at 0.739, well left of the d00 pilot baseline (dashed line). However, this is a single unreplicated run — it could be an outlier. The two successful single-long runs bracket the baseline (0.762 and 0.816), showing high variance even within the same configuration. Both parallel modes sit to the right of the baseline, reinforcing the contention penalty. A critical limitation: the 3 missing single-long runs introduce survivorship bias — we only see results from runs where the agent happened to produce valid training output. The true single-long distribution may be worse than shown.

### 3. Fixed-Time Compute-Allocation Scaling

This benchmark isolates compute allocation by running identical 2-second
training tasks, not the full agent loop. On a 10-core CPU machine, it measures
how throughput, optimizer updates, and validation loss change as N concurrent
processes share CPU resources.

| N agents | Policy      | Wall time (s) | Speedup | Efficiency | Mean steps | Mean val_bpb |
|----------|-------------|---------------|---------|------------|------------|-------------|
| 1        | sequential  | 9.34          | 1.00x   | 100%       | 19.0       | 1.945       |
| 1        | parallel    | 10.08         | 0.93x   | 93%        | 21.0       | 1.947       |
| 2        | default     | 11.18         | 1.69x   | 85%        | 17.0       | 1.986       |
| 2        | partitioned | 10.16         | 1.86x   | 93%        | 19.0       | 1.945       |
| 4        | default     | 14.28         | 2.63x   | 66%        | 12.0       | 2.059       |
| 4        | partitioned | 14.26         | 2.63x   | 66%        | 15.0       | 2.018       |
| 8        | default     | 23.54         | 3.15x   | 39%        | 7.1        | 2.207       |
| 8        | partitioned | 22.58         | 3.29x   | 41%        | 10.0       | 2.113       |

**Observations**:
- Speedup is strictly sublinear: N=8 yields only ~3.2x throughput (ideal would be 8x).
- Training quality degrades monotonically with N: val_bpb worsens by ~13% from N=1 to N=8 (default policy). Each agent completes fewer gradient steps in the same wall-clock budget.
- Partitioned thread policy (dividing cores equally: 5 per agent at N=2, 1 per agent at N=8) provides modest quality improvements at N=2 (no degradation) but the advantage diminishes at higher N.
- This is the key confound for the 2x2 design: parallel cells (d01, d11)
  receive a different effective compute allocation than single cells (d00,
  d10). Any quality difference between parallel and single cells conflates the
  workflow effect with the compute-allocation effect.

The current presentation figures for this result are
[`figure-01-fixed-time-compute-loss.png`](figures/figure-01-fixed-time-compute-loss.png)
and
[`figure-03-throughput-efficiency.png`](figures/figure-03-throughput-efficiency.png).
The older `fig02_resource_contention.png` plot is retained only as historical
provenance.

**Fixed-step follow-up**: A later N=2 benchmark held gradient updates fixed at 300 steps per worker. In that setting, two concurrent CPU training jobs reached the same val_bpb as sequential jobs, but each worker slowed down. The best tested setting, 2 parallel processes with 4 threads each, gave a 1.75x group-level speedup over two sequential evaluations while slowing each worker by 14.2%. This clarifies the fixed-time result: under fixed-time evaluation, parallelism hurts quality because it reduces completed steps; under fixed-step evaluation, it mainly increases evaluation latency.

### 4. Edit Category Distribution

The decomposition terms phi, G, and epsilon depend on classifying each agent edit into categories (optimizer, regularization, architecture, data_pipeline, other). The mode labeling script analyzes the git diff and the agent's stated hypothesis to assign a category. Here is the distribution across all pilot runs:

| Cell | Total proposed | optimizer | regularization | architecture | data_pipeline | other | Total accepted |
|------|---------------|-----------|----------------|--------------|---------------|-------|---------------|
| d00  | 6             | 0         | 0              | 4            | 2             | 0     | 0             |
| d10  | 12            | 2         | 6              | 2            | 0             | 2     | 0             |
| d01  | 20            | 4         | 12             | 4            | 0             | 0     | 6             |
| d11  | 16            | 10        | 6              | 0            | 0             | 0     | 0             |

![Mode distribution](figures/fig04_mode_distribution.png)

**Figure 4 interpretation**: This figure explains why the KL divergence terms (G and epsilon) collapsed to zero. Two problems are visible:

1. **Low category diversity**: Each cell is dominated by 1-2 categories. d11 is 63% optimizer, d01 is 60% regularization, d10 is 50% regularization. When distributions are this concentrated, the KL divergence between them is small — there isn't enough "spread" across categories for information-theoretic measures to detect differences.

2. **Near-zero acceptance rate**: Only d01 had any accepted edits (6 out of 20 proposed), and the other three cells had zero acceptances. The epsilon estimator compares accepted vs proposed distributions — with 0 acceptances, it is undefined (falls back to 0). The phi estimator requires accepted edits in both the baseline and design cell — with d00 having 0 acceptances, phi is undefined for every comparison.

**Root cause**: The agents mostly explored a narrow hyperparameter subspace (learning rate and regularization tweaks), and the 120-second training budget was often too short for changes to produce measurable improvements — hence few acceptances. The mode labeling system works correctly, but the experiment did not generate enough diverse, successful edits to feed the decomposition estimators.

## Answers to the Research Question

**Can the BP decomposition produce measurable terms?** Partially. The cost term log(kappa_0/kappa) was measurable but noisy. The phi, G, and epsilon terms were all zero or near-zero in the pilot — the instrumentation for mode labeling and information gain did not produce enough signal at this scale (see Figure 4: near-zero acceptance rates and low category diversity). The decomposition reduced to a single-term approximation (cost only), which is too simple to be useful.

**Hypothesis verdicts** (out of 3 reps supporting each):
- H1 (parallelism helps wall-clock only): **1/3** — inconsistent
- H2 (memory helps both axes): **1/3** — inconsistent
- H3 (shared memory lowers epsilon): **0/3** — no support
- H4 (parallelism sensitive to coordination): **0/3** — no support
- H5 (context pressure dominant): **0/3** — no support (kappa data was sparse)
- H6 (d11 dominates d00): **0/3** — no support

**Negative result criterion**: R^2 = 0.32 for best_val_bpb ~ total_tokens, so the single-scalar fit does NOT explain the data. This means the decomposition is not redundant — there IS structure beyond "more tokens = better" — but the pilot was too noisy to extract it.

## Conclusions

1. **Memory is the strongest single factor**: Adding memory to a single agent produced the best val_bpb (0.739 exploratory, 0.782 pilot mean), consistently outperforming no-memory counterparts. This aligns with H2's direction but was not statistically robust.

2. **Parallelism introduces CPU contention**: On shared-CPU hardware, parallel agents compete for resources. Under fixed-time evaluation, this degrades individual training quality because each worker completes fewer gradient steps. The fixed-step follow-up shows the complementary behavior: when every worker completes the same 300 steps, quality is equalized but the parallel workers are slower. This is a confound that must be controlled before any claim about parallelism can be made.

3. **The 2x2 design is viable but underpowered**: With only 3 reps per cell, variance is too high to draw inferential conclusions. The factorial structure is sound, but needs more repetitions and confound control.

4. **d11 shows a stabilizing pattern**: Parallel + memory had the lowest variance (0.004), suggesting memory may help coordinate parallel agents, though the mechanism is unclear.

5. **Infrastructure validated**: The full pipeline works end-to-end: agent runner, token tracking, mode labeling, decomposition computation, and aggregation. Key issues found: resource contention not controlled, initial val_bpb not standardized across runs, phi/G/epsilon terms not yet producing signal.

## Implications for Later Experiments

- A separate theory/protocol audit addressed the theoretical decomposition framework.
- The calibration design experiment introduced phased execution and config routing.
- The probe ablation experiment redesigned the 2x2 with confound controls: fixed seeds, CPU-aware execution, and a calibrated starting model.
