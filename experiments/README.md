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
- the original SWE-bench experimental scaffold;
- the later distribution-aware orchestration archive, Step 1 induction work,
  and SWE-bench studies imported from the cluster checkout `NeurIPS_2026`.

The cluster import is rooted at
[`other/distribution-aware-orchestration/`](other/distribution-aware-orchestration/).
Its AutoResearch code and evidence remain in the root `autoresearch/` package
and this directory's `autoresearch/` experiment family, so the non-AutoResearch
snapshot does not duplicate them.

The tracked HumanEval+, MBPP+, and BBH worker logs remain in `data/` because the
legacy `config/` and `src/*.py` pipeline addresses them directly. They are
non-AutoResearch evidence and are documented by `other/README.md`.
