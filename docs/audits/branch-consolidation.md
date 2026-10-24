# Branch consolidation — 24 October 2026

The review started from `main` at `244eb4fe8293c4396a6e05c8df495b5527cb6121`.
Every remote topic branch was compared by ancestry, changed files, implementation
and evidence contracts, rather than treating an old branch as automatically newer.

## Decisions

| Branch and reviewed head | Assessment and disposition |
| --- | --- |
| `codex/unify-how-to-pick-a-model` — `f122673a646710f967bca59c0c0713ea731c873b` | Original package/history unification. Already merged in PR #1 and an ancestor of main. Retain the maintained package; remove the branch. |
| `codex/merge-neurips-2026` — `d1640c397d4fbc8faeccbbe5e517f233da1b19b2` | Cluster manuscript and experiment history, already merged in PR #2. Later scope reductions are deliberate; do not restore retired copies. Remove the branch. |
| `codex/include-all-source-artifacts` — `4b797ee9037070b1e1f8a1a5a94db889b33a0af6` | Source provenance archives, already merged in PR #3. Keep the retained archives and subsequent cleanup. Remove the branch. |
| `codex/recovery-validation` — `3af4fb6ca6cae5caa2f588de4608a44505b8804c` | Recovery selectors, matched context conditions, cost receipts and declared producer transfer. Squash-merged in PR #8: its tree is **identical** to `cb6caa32d7aad2d3fdfe63ea1d31526f01e9801e` (tree `88df7aca44fd5d204e6a5e26ea58b4b63cbcb89e`). Preserve the original commit ancestry with a history-only merge; do not apply its older tree over later changes. Remove the branch. |
| `codex/cross-benchmark-recovery` — `1f653780aebf8ac6fc29e90ca48059c1f2a5e593` | Frozen MBPP+ replication, forecast controls, offline reconstruction and separate empirical paper. Already merged in PR #9. Keep the declared censoring and transfer boundaries. Remove the branch. |
| `codex/continuation-test-scheduling` — `64809add6f8bcf9fbc49e4407f09f21e12560555` | Concurrent shutdown must preserve the provider transport-stop reason. Already merged in PR #10. Keep the fix and its regression test. Remove the branch. |
| `codex/feedback-only-fixed-policies` — `ee36d90a1b121f27620553b3a17c476b37c0cc41` | Five new commits, compatible with current main: complete 157-task BigCodeBench fixed-policy bank, public/evaluator separation, conservative admission, evidence checks, reports and explicit negative primary result. Integrate this implementation and evidence with the maintenance fixes below; resolve PR #11. Remove the branch after validation. |
| `codex/four-term-packed-validation` — `b8f57d74e2dc8b36aff94a53e48ed4ca5921d320` | Separate July/August theory and SAI-3 benchmark line, 71 unique commits. Retire its working-tree changes for the reasons below. Preserve its complete ancestry with an explicitly **history-only** merge. Remove the branch; no scientific assets are lost from Git. |

## Why the older theory line is not the maintained implementation

The useful self-contained components are a procedural task generator, bounded
verifier, deterministic schedule/seeding, censored first-passage estimators,
artifact audits, bootstrap analyses and plots. Its 32 offline tests pass, including
synthetic analysis and checked confirmation/follow-up bundle consistency. Those
checks do not rerun its vLLM/MLX, Slurm or A100 experiments.

This is a different experimental intervention from failed-code recovery or
feedback-only escalation. Its physical confirmation reports 13 of 14 passing
gates, with the overall closure gate failing; the high-repetition follow-up does
not establish a universal exact decomposition. The complete raw physical runs
are external to the repository. The later theoretical revisions change the
estimand and tool-allocation formulation again; they are not an implemented
continuation controller.

Merging that tree wholesale would replace the current `main.tex`, revise the
protected theory anchor, introduce a second manuscript/proof pair, reinstate a
separate benchmark family and bring obsolete inventory expectations. It also
removes `main.tex` from canonical-source checks and the default paper build.
These changes conflict with the subsequent, deliberate scope reduction on main.
No shared current-runtime bug fix was found there that needs porting independently.

The historical generator, results, figures, drafts and all 71 commits remain
reachable through main's merge ancestry. Browse the
[reviewed snapshot](https://github.com/EmaRimoldi/how-to-pick-a-model/tree/b8f57d74e2dc8b36aff94a53e48ed4ca5921d320),
or inspect a file with:

```bash
git show b8f57d74e2dc8b36aff94a53e48ed4ca5921d320:experiments/four-term-packed-validation/README.md
```

The history-only merge deliberately retains main's files; it is **not** a claim
that this theory or its experiments were incorporated into the active paper.
The same ancestry technique for PR #8 records the original squash-merged commits
without replaying a superseded tree. A verified full Git bundle and the initial
branch/PR metadata were also saved locally before cleanup.

## Reconciled design and fixes

- Current task studies share VAO provider/accounting and verification primitives;
  historical `agent_workflow` modes remain the baseline CLI. Replace the obsolete
  architecture document that described the baseline runner as the only runtime.
- Hash historical collection source **snapshots**, not the current working-tree
  implementations, when verifying saved evidence. Continue to reconstruct every
  frozen statistical/accounting field and validate all published checksums.
- Resolve the recorded BigCodeBench task bundle relative to the checkout, so
  analysis works from another working directory. Plan-only inspection reports
  current source drift; actual collection still rejects it before provider access.
- Move the merge CLI into `agent_workflow.modes.merge`, with the old script as a
  compatibility wrapper. The installed command no longer imports an unpackaged
  `scripts` namespace, and both entry points use the same runtime. Resolve the
  default benchmark through the installed package instead of source-tree depth.
- Run Makefile Python targets through `uv` by default, so the documented
  `make check` uses the locked environment without manual activation.
- Respect optional dependencies: the macOS BigCodeBench sandbox test requires
  EvalPlus, matching the existing continuation-test convention. The base install
  skips that integration test; it is exercised separately with the pinned extra.
- Mark the BigCodeBench campaign as completed, retain its failed primary gate,
  and distinguish its historical budget from the separate $2 recovery campaign.
  Frozen results, manifests, sources and manuscript files are not rewritten.

## Validation

The initial main passed **241 tests, 4 skipped**. The retired theory line passed
**32 offline tests** in a detached worktree. The consolidated base environment passed **259 tests, 5 skipped**; all **89 runtime
tests** passed in a separate environment with the pinned EvalPlus extra, including
the macOS sandbox checks. The five base-suite skips are optional integrations.

Also verified:

- `make check`: regenerated indexes, readiness/link checks, compilation and tests.
- Full saved HumanEval+ recovery audit and MBPP+ reconstruction against its frozen
  expected analysis, including forecast controls and missing-state accounting.
- BigCodeBench: all 628 outcomes and 1,492 responses, snapshot hashes, statistics,
  receipt/prompt chains and preserved interim snapshot; zero discrepancies in the
  saved verifier-repeat diagnostic. This audit executes no historical candidates.
- Plan-only BigCodeBench inspection, plus regression coverage that execution
  rejects source drift before any provider access.
- Three AutoResearch figures regenerated from tracked processed evidence.
- Deterministic CLI demo and report generation.
- Built wheel installed in another environment with lockfile-pinned dependencies:
  all ten CLI help surfaces and the demo work outside the source checkout. The
  merge options are checked with a fixture runtime, without launching evaluation.

Paid/provider calls, full model training and cluster experiments were **not rerun**.
The historical raw-run availability and scientific limitations above remain.
Only main is retained after the verified merge; historical work is reachable
through its ancestry rather than maintained as competing branches.
