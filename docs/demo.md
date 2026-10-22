# Offline Demo

```bash
uv run agent-workflow demo   --output-dir /tmp/how-to-pick-a-model-demo   --experiment-id readme_demo
```

The baseline CLI writes deterministic fixture data, a Workflow Card, CSV/JSON
summaries, and an HTML report. It uses no live model, GPU, Slurm, or provider
quota. This demonstrates the reporting format; it does not measure real policy
performance or implement the planned continuation controller.

For empirical evidence, read `experiments/README.md` and the relevant bundle.
For the next experiment, read `docs/decision-protocol.md`. Safe regeneration of
three AutoResearch figures is available through `make paper-figures-autoresearch`.
