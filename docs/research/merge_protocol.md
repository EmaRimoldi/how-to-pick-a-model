# Merge Protocol

## Overview

After a parallel search completes, the merge orchestrator (`merger.py`) examines
every agent's search trajectory and produces a **merged train.py** candidate that
combines the best modifications discovered independently.

The merge is:
- **code-aware** — it parses hyperparameter values from train.py rather than doing
  text concatenation
- **evaluation-aware** — it uses actual val_bpb measurements to decide which values
  to keep
- **trajectory-aware** — it reads reasoning traces and snapshot metadata, not just
  final results

## Running the Merge Phase

```bash
python scripts/run_merge_phase.py \
    --experiment-dir runs/experiment_parallel_20260331_120000

# With evaluation (requires an available workspace with SLURM scripts):
python scripts/run_merge_phase.py \
    --experiment-dir runs/experiment_parallel_20260331_120000 \
    --evaluate
```

## What Gets Merged

The merge phase collects three categories of evidence:

### 1. Snapshot candidates

For each agent, the following snapshots are considered:

| Category | Description |
|---|---|
| **Best** | Snapshot with lowest `val_bpb_after` for that agent |
| **Final** | Last snapshot taken before agent stopped |
| **Informative intermediates** | Snapshots near major metric jumps (>0.002 bpb improvement in one step), up to 3 per agent |

These are copied to `mode_merge/candidates/` as named `.py` files:
- `candidate_agent_0_best.py`
- `candidate_agent_0_final.py`
- `candidate_agent_0_step003.py`
- etc.

### 2. Reasoning traces

Each agent's `reasoning/trace.jsonl` is read to extract:
- All confirmed hypotheses (where `confirmed == "confirmed"`)
- All falsified hypotheses
- Hypotheses confirmed independently by ≥2 agents (strongest signal)

Independently confirmed hypotheses get the highest weight in the merge decision.

### 3. Per-parameter improvement correlations

For each snapshot, the change in val_bpb is attributed to the modified parameter.
The merge identifies which parameters are **consistently associated with improvement**
across agents and steps.

## Merge Algorithm

```
1. Rank all candidates by val_bpb (lower is better)
2. Start from the best candidate as the base
3. For each tunable parameter in the base:
   a. Check all other candidates that have a different value for that parameter
   b. If the other candidate:
      - has val_bpb within 0.5% of the best candidate
      - AND the parameter is flagged as "likely helpful" by correlation analysis
   c. Then transplant that parameter value into the merged candidate
4. Write merged_train.py with the final combined hyperparameters
```

The algorithm is intentionally conservative: it only transplants values from
candidates that already performed nearly as well as the best. It will not combine
values from a mediocre candidate with the best unless the parameter is demonstrably
beneficial.

### Why not concatenate?

Since `train.py` contains only scalar hyperparameters, "merging" means choosing
the best value for each scalar. Text concatenation is meaningless here. The merge
is done by:
1. Extracting the hyperparameter dict from each candidate
2. Applying the chosen values to the base source file using regex substitution

This preserves all other code in the base file (comments, non-hyperparameter logic)
and only updates the identified scalar constants.

## Output Files

```
mode_merge/
    candidates/
        candidate_agent_0_best.py      # best snapshot per agent
        candidate_agent_0_final.py     # final snapshot per agent
        candidate_agent_0_step003.py   # informative intermediates
        candidate_merged.py            # final merged candidate
    merge_plan.json                    # what was decided and why
    merge_results.json                 # final comparison table
    merge_report.txt                   # human-readable summary
```

### merge_plan.json fields

```json
{
  "experiment_id": "...",
  "mode": "parallel",
  "timestamp": "...",
  "candidates": [...],          // all candidate train.py files considered
  "reasoning_summary": {...},   // cross-agent reasoning trace analysis
  "trajectory_analysis": {...}, // per-param improvement correlations
  "merge_strategy": "...",      // human description of what was merged
  "notes": "..."
}
```

### merge_results.json fields

```json
{
  "best_individual_agent": "agent_0",
  "best_individual_val_bpb": 1.1020,
  "merge_val_bpb": null,       // null if --evaluate not passed
  "merge_candidate_name": "merged",
  "merge_won": null,
  "delta_val_bpb": null,
  "candidates_evaluated": [...],
  "merge_explanation": "..."
}
```

## Reasoning Trace Usage

The merge orchestrator reads reasoning traces to:

1. **Identify independently confirmed hypotheses** — if ≥2 agents confirm the same
   hypothesis, it is given higher confidence. The hypothesis text is matched by
   string equality, so agents must record their hypotheses consistently.

2. **Identify falsified directions** — hypotheses falsified by multiple agents are
   flagged as likely poor directions. The merge avoids incorporating parameter
   values associated with falsified hypotheses.

3. **Understand trajectory dynamics** — the `evidence` field in each reasoning entry
   records what prior data motivated each change. This explains why the agent moved
   in a particular direction, which helps interpret snapshot sequences.

## Limitations

1. **Requires snapshots** — the merge phase only works if agents called
   `save_snapshot.py` and `update_snapshot.py` during their runs. If snapshots are
   absent, the merge falls back to the baseline train.py.

2. **Parameter parsing** — hyperparameter extraction uses regex matching of
   `ALL_CAPS_NAME = <float>` patterns. Parameters not matching this pattern will
   not be merged (but will be retained as-is from the base candidate).

3. **Evaluation is optional** — the merge produces a candidate but does not
   automatically evaluate it unless `--evaluate` is passed. Evaluation requires a
   pre-configured workspace with `submit_training.sh` and `check_training.sh`.

4. **Single-round merge** — the current algorithm does one round of parameter-level
   merging. It does not iterate or search the space of merged candidates. If the
   merged candidate performs worse, this is recorded in `merge_results.json` for
   analysis.
