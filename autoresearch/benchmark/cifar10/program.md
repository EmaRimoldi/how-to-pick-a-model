# AutoResearch CIFAR-10 program

You are given a single editable Python file `train.py` that trains a compact
CIFAR-10 model under a **fixed-step verifier budget**.

The file defines a compact CNN plus its optimizer and scheduler. Your task is to
rewrite only the marked hyperparameter section and helper functions so that
validation loss improves under the benchmark's fixed evaluation budget.

The verifier runs the edited program as a short training job on the same task
instance. The active protocol uses three workload modes under the same
**256-step** verifier budget:

- `cnn_compact`: compact convolutional CIFAR-10 training;
- `mlp_flat`: flattened-image MLP training;
- `resnet_micro`: micro residual CIFAR-10 training.

The evaluation signal is the final validation loss, together with a thresholded
success event defined relative to the unedited starting script.
