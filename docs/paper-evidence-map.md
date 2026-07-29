# Paper Evidence Map

This map connects manuscript claims to the theory anchors, empirical bundles,
and safe validation commands. It is meant for an LLM agent preparing the next
paper revision.

## Intended Submission Spine

The paper should make one narrow claim:

> Model and workflow choice should be evaluated as deployment-time
> first-passage performance under task-family, signal, cost, and routing
> constraints, rather than as a single benchmark score.

The strongest current story is:

1. Define operational/certified proper time for verifiable tasks.
2. Show that routing information, model competence, cost, and allocation
   mismatch decompose deployment performance.
3. Instantiate the quantities empirically with first-hit/routing diagnostics.
4. Use completed HumanEval+ and AutoResearch evidence as the main support.
5. Mark MBPP+, BBH, SWE-bench, and incomplete smoke studies as context or future
   work unless their missing result bundles are filled in.

## Claim-To-Evidence Table

| Claim family | Theory source | Empirical support | Status |
| --- | --- | --- | --- |
| Proper time / certified proper time is the right operational quantity for verifiable deployment. | `paper/neurips-submission/main.tex`, `paper/neurips-submission/archive/theory_anchor.tex` | First-hit diagnostics in `experiments/autoresearch-cifar10/three-worker-model-routing/`; retry/routing evidence in `experiments/humaneval-plus/`. | Strong conceptual anchor; empirical realization exists. |
| Routing information can improve expected log-time when signals identify latent modes. | `main.tex` theorem `thm:ri-identity`; `theory_anchor.tex` theorem `thm:ri-identity` | `experiments/humaneval-plus/strategy-by-difficulty-grid/`; `experiments/humaneval-plus/llm-router-context-search/`; AutoResearch allocation-router outputs. | Strongest for completed HumanEval+ and AutoResearch bundles. |
| Model choice decomposes into cost, competence, information, and mismatch. | `main.tex` theorem `thm:four-term`; `theory_anchor.tex` theorem `thm:four-term` | AutoResearch three-worker accounting and router diagnostics; HumanEval+ model-size frontier and strategy routing. | Good submission spine if claims stay at accounting/decomposition level. |
| Retry depth has a cost-adjusted crossover; cheaper repeated attempts can beat stronger single attempts only in specified regimes. | `main.tex` theorem `thm:retry-crossover`; `theory_anchor.tex` retry family. | `experiments/humaneval-plus/retry-allocation-router/`; related strategy-routing figures. | Good, but avoid claiming universal retry benefit. |
| Borrowed allocations and allocation mismatch have measurable regret. | `main.tex` proposition `prop:borrowed-allocation`; `theory_anchor.tex` operational hard-router and borrowed-allocation results. | AutoResearch router selection regret and paired-gain figures. | Useful for diagnostics and appendix. |
| Approximate packedness can be tested through residual diagnostics rather than assumed exactly. | `main.tex` proposition `prop:approximation-guarantee`; `theory_anchor.tex` residual guarantees. | AutoResearch negative controls, threshold sensitivity, and z-signal ablation. | Good as empirical stress test, not as proof of exact model. |
| Multi-agent or memory-augmented workflows can outperform naive exploration when coordination reduces repeated/destructive search. | `theory_anchor.tex` multi-agent specialization threshold and agent-system design definitions. | `experiments/autoresearch-cifar10/shared-memory-ablation/`; `experiments/autoresearch-cifar10/swarm-vs-independent-agents/`. | Use narrowly; strongest evidence is shared-memory ablation, swarm is historical/partial. |

## Evidence Tiers

### Tier 1: Main Evidence

Use these for the core paper narrative:

- `experiments/humaneval-plus/strategy-by-difficulty-grid/`
- `experiments/humaneval-plus/llm-router-context-search/`
- `experiments/humaneval-plus/retry-allocation-router/`
- `experiments/autoresearch-cifar10/three-worker-model-routing/`
- `experiments/autoresearch-cifar10/shared-memory-ablation/`
- `experiments/autoresearch-cifar10/evaluation-protocol-and-compute-calibration/`

### Tier 2: Supporting Or Diagnostic Evidence

Use these for context, robustness, or appendix:

- `experiments/autoresearch-cifar10/starting-model-calibration/`
- `experiments/autoresearch-cifar10/swarm-vs-independent-agents/`
- `experiments/humaneval-plus/qwen-model-size-frontier/`
- `experiments/mbpp-plus/qwen-model-size-frontier/`
- `experiments/bbh/qwen-model-size-frontier/`

### Tier 3: Future Work Or Scaffold

Do not cite as completed support without adding missing result bundles:

- `experiments/humaneval-plus/verifier-guided-dag-induction-smoke/`
- `experiments/mbpp-plus/two-model-retry-router/`
- `experiments/mbpp-plus/category-router-smoke/`
- `experiments/bbh/family-and-subtask-router/`
- `experiments/swebench-verified/neutral-100-meta-design-scaffold/`
- `experiments/swebench-verified/open-source-orchestration-scaffold/`

## Safe Validation Commands

Regenerate agent-facing indexes:

```bash
python scripts/build_repo_inventory.py --output docs/audits/repo-inventory.md
python scripts/build_knowledge_index.py --output docs/audits/knowledge-index.md
python scripts/validate_agent_readiness.py
```

Run local tests:

```bash
uv run pytest tests -q
```

Regenerate main AutoResearch paper figures from processed evidence:

```bash
uv run python -m autoresearch.scripts.reproduce_main_figures_from_processed \
  --input experiments/autoresearch-cifar10/three-worker-model-routing/results/accounting/threeworker_final_analysis.json \
  --out-dir /tmp/how_to_pick_a_model_autoresearch
```

Inspect non-AutoResearch trace bundles:

```bash
uv run python -m src.load_traces --config experiments/humaneval-plus/retry-allocation-router/configs/router.yaml
uv run python -m src.load_traces --config experiments/mbpp-plus/two-model-retry-router/configs/router.yaml
uv run python -m src.load_traces --config experiments/bbh/family-and-subtask-router/configs/router_experiment_bbh.yaml
```

## Revision Protocol For The Next Agent

Use `docs/paper-revision-playbook.md` as the operational workflow. The short
protocol is:

1. Start with `paper/neurips-submission/main.tex` for compact submission edits.
2. Use `paper/neurips-submission/arxiv.tex` for longer AutoResearch material.
3. Use `paper/neurips-submission/archive/theory_anchor.tex` only as a validated
   theory source, not as the active manuscript.
4. Check `docs/audits/knowledge-index.md` for formal object line numbers.
5. Check `docs/audits/theory-consolidation.md` before promoting an archived
   theorem.
6. Check the relevant experiment README before citing any result.
7. Keep claims aligned with the evidence tier above.

## Current Paper Risk Register

- Do not imply that all experiments are complete; several bundles are partial
  or scaffolds.
- Do not claim exact packedness as an empirical fact; use approximate/residual
  language unless a diagnostic supports the stronger statement.
- Do not claim memory or multi-agent coordination is universally beneficial;
  the strongest evidence is substrate-specific.
- Do not treat archive PDFs as active source text; use them for provenance.
- Do not cite generated paper figures as independent evidence; cite the
  experiment bundle and accounting tables.
