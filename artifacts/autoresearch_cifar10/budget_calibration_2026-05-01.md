# Budget calibration notes (2026-05-01)

## Inner-loop throughput diagnostics
- Across all modes at 2 training steps: median wall 10.66s, median pure training 9.41s.
- Across all modes at 8 training steps: median wall 10.61s, median pure training 0.20s.
- Across all modes at 32 training steps: median wall 11.53s, median pure training 0.60s.
- Across all modes at 128 training steps: median wall 13.74s, median pure training 2.20s.

The fixed per-run overhead dominates very short verifier budgets; increasing inner training steps therefore costs much less than linearly in wall-clock.

## Long-budget sweep
- lr-sensitive: 64 steps -> loss 2.2228, wall 14.13s, 128 steps -> loss 2.1056, wall 16.07s, 256 steps -> loss 1.9368, wall 19.51s, 512 steps -> loss 1.7536, wall 27.22s
- regularization-sensitive: 64 steps -> loss 1.9909, wall 12.61s, 128 steps -> loss 1.8330, wall 14.32s, 256 steps -> loss 1.7516, wall 18.37s, 512 steps -> loss 1.5782, wall 24.73s
- schedule-sensitive: 64 steps -> loss 1.7964, wall 13.01s, 128 steps -> loss 1.5973, wall 14.89s, 256 steps -> loss 1.4889, wall 16.92s, 512 steps -> loss 1.3175, wall 23.33s

## Provisional protocol decision
- Short verifier budget: **128 training steps** for lr/regularization/optimizer/data-skew modes.
- Long verifier budget: **512 training steps** for capacity/schedule modes.
- Main outer AutoResearch horizon: **H=24** with ablation **H in {8, 16, 32}**.

Rationale: these budgets are much more stable than the earlier 2/6-step verifier, remain cheap on CPU once data are cached, and push the protocol closer to a meaningful optimization surface while keeping the campaign feasible.