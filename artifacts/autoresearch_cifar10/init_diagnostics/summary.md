# Init diagnostics summary

- capacity-sensitive: recommended `narrow` | target_gain=0.0078 | best_control_gain=0.0061 | margin=0.0018
- data-skew-sensitive: recommended `adam_lr5e-4_b128` | target_gain=0.0058 | best_control_gain=0.0000 | margin=0.0058
- lr-sensitive: recommended `lr_1e-5` | target_gain=0.0064 | best_control_gain=0.0019 | margin=0.0045
- optimizer-sensitive: recommended `adam_lr1e-4` | target_gain=-0.0000 | best_control_gain=0.0052 | margin=-0.0053
- regularization-sensitive: recommended `wd0_drop005` | target_gain=0.0008 | best_control_gain=0.0000 | margin=0.0008
- schedule-sensitive: recommended `nosched_lr2e-3` | target_gain=0.0000 | best_control_gain=-0.0008 | margin=0.0008