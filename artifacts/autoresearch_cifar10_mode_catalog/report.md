# AutoResearch CIFAR-10 Mode Catalog

## Action Modes

- `layout`: architecture and model capacity changes
- `indexing`: optimizer-family and gradient-dynamics changes
- `topk`: learning-rate scale changes
- `caching`: regularization and robustness changes
- `summaries`: learning-rate schedule and budget-allocation changes
- `micro`: batching and local training-loop tweaks

## Latent Modes

- `lr_search_short_budget`: Clean balanced full-CIFAR regime with a tiny fixed-step budget where learning-rate scale dominates early progress.
  train_subset=50000, val_subset=10000, label_noise=0.0, imbalance_ratio=1.0, max_train_steps=2, seed=61
- `regularization_under_label_noise`: Short-horizon full-CIFAR training with synthetic label noise, making regularization choices the main lever.
  train_subset=50000, val_subset=10000, label_noise=0.25, imbalance_ratio=1.0, max_train_steps=2, seed=67
- `optimizer_for_long_tail`: Full-CIFAR long-tail regime under the same compute budget, emphasizing optimizer dynamics and class coverage.
  train_subset=50000, val_subset=10000, label_noise=0.0, imbalance_ratio=0.12, max_train_steps=2, seed=71
- `capacity_schedule_long_budget`: Clean full-CIFAR regime with a longer horizon where architecture capacity and learning-rate schedule both matter.
  train_subset=50000, val_subset=10000, label_noise=0.0, imbalance_ratio=1.0, max_train_steps=6, seed=73
