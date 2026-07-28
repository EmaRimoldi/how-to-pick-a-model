# n=20 confirmation appendix figures

These figures were regenerated from the official confirmation/holdout raw runs only.
The missing 90 pilot runs are excluded.

Worker run count: `180` total = 20 runs per mode-worker cell.

- `mlp_flat/gpt_5_3_codex`: 20 runs
- `mlp_flat/gpt_5_4`: 20 runs
- `mlp_flat/gpt_5_4_mini`: 20 runs
- `cnn_compact/gpt_5_3_codex`: 20 runs
- `cnn_compact/gpt_5_4`: 20 runs
- `cnn_compact/gpt_5_4_mini`: 20 runs
- `resnet_micro/gpt_5_3_codex`: 20 runs
- `resnet_micro/gpt_5_4`: 20 runs
- `resnet_micro/gpt_5_4_mini`: 20 runs

Router negative-control plots reuse processed router decisions from `/Users/emanuelerimoldi/Documents/agentops-lab-public/experiments/05_autoresearch_model_routing/results/accounting/threeworker_final_analysis.json` and recompute mode-worker losses from the n=20 confirmation frontier.

`diag_z_signal_ablation` is regenerated from `/Users/emanuelerimoldi/Documents/agentops-lab-public/experiments/05_autoresearch_model_routing/results/accounting/z_signal_ablation_partial.json`. That diagnostic uses its available aggregate input, not the 180 worker-run panel.

Accounting outputs: `/Users/emanuelerimoldi/Documents/agentops-lab-public/experiments/05_autoresearch_model_routing/results/accounting_n20_confirmation`.
