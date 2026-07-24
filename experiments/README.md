# Experiments

Experiments are split by benchmark family. No AutoResearch evidence is mixed
with the other evaluation tracks.

## AutoResearch

[`autoresearch/`](autoresearch/) contains the CIFAR-10 edit--verify studies:

1. baseline calibration;
2. evaluation-protocol calibration;
3. agent-memory ablation;
4. swarm baselines;
5. model-routing and deployment accounting.

The runnable substrate lives at the repository root in `autoresearch/`,
`src/agent_workflow/`, and `src/vao/`.

## Other experiments

[`other/`](other/) contains:

- completed strategy-routing and router-search runs;
- MBPP category-routing smoke figures;
- the SWE-bench experimental scaffold.

The tracked HumanEval+, MBPP+, and BBH worker logs remain in `data/` because the
legacy `config/` and `src/*.py` pipeline addresses them directly. They are
non-AutoResearch evidence and are documented by `other/README.md`.
