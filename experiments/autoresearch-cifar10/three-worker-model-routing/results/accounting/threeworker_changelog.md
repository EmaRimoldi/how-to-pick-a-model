Three-worker paper update changelog
===================================

Inputs and support
------------------

- Added `gpt_5_4_mini` to the worker action menu.
- Primary worker-frontier support is `n=35` per task-mode cell for `gpt_5_3_codex` and `gpt_5_4`, and `n=30` per task-mode cell for `gpt_5_4_mini`.
- Mini uses 10 pilot and 20 holdout valid trajectories per task mode; unfinished or invalid runs are excluded by the same filters as the existing workers.
- Added a balanced `n=30` sensitivity for all three workers.

Conclusion changes
------------------

- The primary deployment-loss frontier changes from a single two-worker recommendation to mode-conditional winners `4/m/C` at `gamma=0.05`: `gpt_5_4` for MLP-flat, `gpt_5_4_mini` for compact CNN, and `gpt_5_3_codex` for micro ResNet.
- `gpt_5_4_mini` is not dominated overall: it is the compact-CNN deployment-loss and log-effort winner.
- `gpt_5_4` is the best always-worker baseline by pooled deployment loss, but the mode oracle over the three-worker frontier is better.
- The balanced `n=30` sensitivity preserves the primary `4/m/C` winners, so the main recommendation is not driven by the 35/35/30 sample-size imbalance.

Router changes
--------------

- Reran the prompt-only router on the three-worker menu with 480 records over `Z0`, `Z1`, `Z2`, `Z3` and the same negative controls.
- The router remains biased toward `gpt_5_4` and never selects `gpt_5_4_mini` on real records.
- Richer real records reduce log-effort regret, but paired deployment gain is not robustly positive after measurement cost.
- Best mean real-signal net gain is `Z1` at `+0.005`, with a bootstrap interval crossing zero.
