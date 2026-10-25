# Decision Gate Rationale

**Date**: 2026-04-13

## Criteria Evaluation

### Criterion 1: Architecture Effect
- **Cohen's d = +0.66 (medium)** — but in the **wrong direction** (d10 worse)
- The original gate assumed d > 0.3 means "proceed". The magnitude is there but the sign says memory hurts, not helps.
- **Assessment**: Signal detected, but it contradicts the memory-helps hypothesis

### Criterion 2: Mode Diversity
- d00: 5 categories, 5 with ≥2 runs
- d10: 5 categories, 4 with ≥2 runs
- **Assessment**: Good diversity in both cells. Not degenerate.

### Criterion 3: Sample Size
- d00: 47 runs (marginal, <50)
- d10: 69 runs (adequate, >50)
- **Assessment**: Marginal but usable

### Criterion 4 (NEW — discovered during analysis): Minimum Exploration Threshold
- Zero improvements before run 9 across all 116 runs
- 4/10 reps had <9 runs and were structurally unable to improve
- This is a confound that inflates failure rates and masks the true signal
- **Assessment**: Budget may need extension to ensure all reps reach the exploration threshold

## Why the Standard Gate Doesn't Fit

The decision matrix was designed for a simple scenario: is the signal big enough to justify the full 2×2? The calibration revealed something more interesting:

1. **The d00-d10 contrast IS detectable** (d=0.66) — just in the wrong direction
2. **The mechanism is informative**: memory stabilizes cost (κ) but creates anchoring (negative ε)
3. **Exploration diversity is the key predictor** (ρ=-0.685, p=0.029) — this is the G term
4. **Training time confound**: improvements correlate with longer training, not just better architecture
5. **The run-9 wall**: reps need ~9 iterations before ANY improvement is possible

## Decision: PROCEED to full 2×2 (with modifications)

**Rationale**: The calibration achieved its purpose — it established that architecture differences produce measurable, interpretable signals on this substrate. The signal isn't what we expected (memory hurts rather than helps), but it's informative and decomposable into BP framework terms.

The full 2×2 is now even MORE motivated because:
- **d01 (parallel, no memory)** should amplify the G term (diversity → success)
- **d11 (parallel, shared memory)** tests whether parallel diversity can overcome memory anchoring
- The interaction between parallelism and memory is the core theoretical prediction

## Modifications for Full 2×2

1. **Extend budget**: 60 minutes (from 45) to ensure more reps cross the run-9 threshold
2. **3 reps per cell** (from 5) to manage compute budget
3. **Cap MAX_STEPS**: Consider fixing MAX_STEPS=585 to eliminate the training-time confound, or alternatively accept it as a legitimate strategy and control for it in analysis
4. **Richer mode labeling**: Use code-diff-based labeling (not self-reported categories) for the full 2×2

## What we expect to see

| Cell | Prediction | BP Terms |
|------|-----------|----------|
| d00 | High variance, some great results | High φ variance, G from lucky diversity |
| d10 | Consistent but capped | Stable κ, negative ε (anchoring) |
| d01 | Best overall if parallel agents explore diverse strategies | High G (multiple independent searchers) |
| d11 | Depends on whether shared memory helps or hurts routing | All four terms active, ε sign is the key question |
