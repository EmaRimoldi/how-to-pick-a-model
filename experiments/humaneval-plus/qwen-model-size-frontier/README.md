# Qwen Model-Size Frontier on HumanEval+

This completed worker study contains one 164-task JSONL log for each of
Qwen2.5-Coder 1.5B, 7B, and 32B, plus the estimated modes, success curves,
frontier, and retry thresholds.

Regenerate processed results with:

```bash
uv run python -m src.estimate --config experiments/humaneval-plus/qwen-model-size-frontier/configs/experiment.yaml
uv run python -m src.plot --config experiments/humaneval-plus/qwen-model-size-frontier/configs/experiment.yaml
```

The full and smoke launchers require Ollama and are under `scripts/`.
