# AutoResearch CIFAR-10 program

You are given a single editable Python file `train.py` that trains a compact
CIFAR-10 model under a **fixed-step verifier budget**.

The file defines a compact CNN plus its optimizer and scheduler. Your task is to
rewrite only the marked hyperparameter section and helper functions so that
validation loss improves under the benchmark's fixed evaluation budget.

The verifier runs the edited program as a short training job on the same task
instance. The active protocol now uses mode-dependent budgets:

- short modes (`lr-sensitive`, `regularization-sensitive`, `optimizer-sensitive`,
  `data-skew-sensitive`) use a **128-step** verifier budget;
- long modes (`capacity-sensitive`, `schedule-sensitive`) use a **512-step**
  verifier budget.

The evaluation signal is the final validation loss, together with a thresholded
success event defined relative to the unedited starting script.
