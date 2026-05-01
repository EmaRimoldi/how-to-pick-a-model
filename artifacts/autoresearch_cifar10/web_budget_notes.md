# Web notes for AutoResearch budget calibration

Collected 2026-05-01 to help choose inner training budgets and outer agent horizons.

## CIFAR-10 training budgets

- The official PyTorch CIFAR-10 tutorial trains for only **2 epochs** in its teaching example (`for epoch in range(2)`), which is useful as a minimal sanity/tutorial loop but not as a strong benchmark target.
- A widely used practical CIFAR-10 reference repo (`kuangliu/pytorch-cifar`) exposes **`--epoch` with default `200`**, reflecting the much larger training budgets typically used for strong final results.

Interpretation: a rigorous AutoResearch benchmark should not confuse tutorial-length training with a solid final CIFAR training budget. Our verifier can still use much shorter runs than 200 epochs, but we should expect to need **far more than 2--6 optimizer steps** if we want inner-loop measurements that are not completely dominated by noise and startup overhead.

## Optimization / search budgets

- The Optuna first tutorial uses `study.optimize(..., n_trials=100)`, which is a practical reminder that even lightweight hyperparameter search examples often assume **tens to hundreds of trials**.

Interpretation: for the outer loop, an AutoResearch horizon in the low tens is much more plausible than `H=8` if the per-step cost is manageable.

## Agent iteration ceilings

- The OpenHands public config template exposes `max_iterations = 500`.

Interpretation: real systems often leave room for very long runs, but that is an upper ceiling rather than a recommendation. For our paper-facing protocol we likely want a much smaller fixed horizon, but one that is still meaningfully larger than 8.
