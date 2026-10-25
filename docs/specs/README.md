# HumanEval+ Implementation Contracts

- `EXPERIMENT_SPEC.md`: original worker-frontier implementation contract.
- `ROUTER_SPEC.md`: original retry-allocation router contract.

These are historical contracts for retained baselines. Current status is governed
by `experiments/README.md` and the corresponding bundle README. Dependency setup
is governed by `pyproject.toml`, `uv.lock`, and `docs/reproducibility.md`.

The next state-conditioned action experiment is specified separately in
`docs/decision-protocol.md`; these contracts do not define that controller.
