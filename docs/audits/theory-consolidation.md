# Theoretical-manuscript consolidation audit

## Scope

This audit covers the theoretical content of:

- \`paper/neurips-submission/main.tex\`;
- \`paper/neurips-submission/arxiv.tex\`;
- \`paper/neurips-submission/archive/final_paper.tex\`;
- \`paper/neurips-submission/archive/main_1.tex\`;
- \`paper/neurips-submission/archive/main_3.tex\`;
- \`paper/neurips-submission/archive/neurips_old.tex\`;
- the retained manuscript PDFs under \`paper/neurips-submission/archive/\`.

\`next_steps.tex\` was deliberately excluded from inspection, comparison, and
editing.  The non-theoretical \`piers_macro.tex\` support file was removed during
the subsequent source cleanup.
\`Achille & Soatto.pdf\` is an external reference and is not a candidate for
content consolidation.

## Selected anchors

### Current paper anchor

\`paper/neurips-submission/main.tex\`

- Current compact paper with HumanEval+ evidence.
- 18 formal objects: 2 assumptions, 6 definitions, 3 theorems, 1 lemma,
  5 propositions, and 1 corollary.
- Contains the clean current statements of the routing-information identity,
  model-aware decomposition, model crossover, retry crossover, paired
  estimator, mode-dependent cost extension, approximate-packedness residual,
  borrowed-allocation penalty, geometric retry scale, and first-hit
  diagnostics.

### AutoResearch manuscript anchor

\`paper/neurips-submission/arxiv.tex\`

- Latest complete source in the AutoResearch manuscript branch.
- 17 formal objects and the fullest empirical discussion in that branch.
- The earlier \`arxiv_backup.tex\` snapshot had the same formal-result inventory
  and was removed after this comparison; no theoretical result was lost.
- \`submitted-manuscript.pdf\` remains the immutable record of the submitted
  layout and is not replaced by this editable source.

### Maximal theory anchor

\`paper/neurips-submission/archive/theory_anchor.tex\`

- Recovered from the maximal theory source at historical commit \`01a8e85\`.
- The historical source contained 54 formal objects and 24 proof
  environments.
- After the second quantity-level audit, the consolidated anchor contains 65
  formal objects.  The added objects preserve cellwise pilot concentration,
  operational progress/persistence losses, and the progressive-signal packed
  decomposition that had previously appeared only in draft prose or appendices.
- The consolidated source compiles cleanly to 29 pages.
- It is the editable theory companion to the historical \`BP.pdf\`, while
  preserving additional theory that was added after the PDF snapshot.

## Result-family crosswalk

### Exact packed-allocation core

The following are variants of the same mathematical spine and are retained in
the theory anchor and, in shorter form, in the current paper:

1. Budgeted/verifiable task and stochastic-solver definitions.
2. Packed latent-mode family.
3. Conditional cross-entropy decomposition.
4. Posterior-matched allocation.
5. Routing-information identity
   \(\Delta_{\log}=I(S;Z)-\mathbb E_Z\mathrm{KL}(\pi_Z\|q_Z)\).
6. Model-aware cost/competence/information/mismatch decomposition.
7. Model-selection crossover.
8. Mode-dependent-cost extension.
9. Uniform residual under approximate inverse-share log-linearity.

The statements in \`arxiv.tex\` and \`main_3.tex\`
use different symbols but do not add a distinct theorem to this core.

### Retry and first-passage family

The common content consists of the geometric certified scale and the
single-mode retry crossover.  The following distinct, valid additions were
transported into \`theory_anchor.tex\`:

- unique cost-adjusted continuously relaxed retry depth;
- multi-mode retry crossover;
- the correct expected cost for stop-at-first-success retries;
- integer deployment by checking the neighbors of the relaxed optimum.

### Model, routing, and system-design consequences

The maximal historical theory source already retained:

- benchmark-racing and model-only optimization counterexamples;
- verifier equalization;
- task-specific fine-tuning value;
- multi-agent specialization threshold;
- budget-preserving task reductions;
- post-training transfer and target-relevant side information;
- approximate orchestration-equivalence bounds;
- continuous-reward extension;
- hierarchical graph-compression, service-cost, and latency thresholds.

The exact modewise criterion for when a hard model router is useless was
transported from the archived depth/routing branch into
\`theory_anchor.tex\`.

### Operational hard-selection family

The deleted standalone operational draft used hard actions rather than packed
shares.  Its distinct algebraic content is preserved as the operational
hard-router decomposition in \`theory_anchor.tex\`: baseline improvement is
operating-resource gain plus verified-competence gain plus value of
information minus allocation regret.

### Design-selection family

\`main_1.tex\` and \`neurips_old.tex\` contained a standard uniform-score
selection lemma and an evaluation-reuse count.  Corrected, assumption-explicit
versions were transported into \`theory_anchor.tex\`:

- uniform score error implies at most \(2\delta\) selection regret;
- a confirmation stage adds at most \(2\eta\);
- when all designs are deterministic functions of shared model--mode
  estimands, pilot task evaluations are independent of the number of
  analytically scored designs.

### Second-pass quantity audit

The second audit inspected displayed quantities and estimator definitions in
addition to formal theorem environments.  It found and consolidated:

- the valid Bernoulli cell-concentration calculation from `main_1.tex`, now
  Proposition `prop:cellwise-pilot-concentration`, with an exact logarithmic
  error bound and an explicit warning that it does not control all four terms;
- first-hit CDF, survival, discrete hazard, geometric-fit discrepancy,
  persistence, occupancy loss, first-passage deployment loss, and audit loss,
  now Definition `def:operational-progress-loss`;
- the progressive-signal quantities
  `(Delta_R^log,C_R,Phi_R,G_R,M_R)`, now Proposition
  `prop:progressive-signal-decomposition`;
- the net router objective, signal-acquisition scalarization, paired gain, and
  action-shift probability, now recorded with Proposition
  `prop:paired-unbiased`;
- the empirical four-term closure residual, now recorded in the measurement
  protocol.

The obsolete evaluator-side `widehat{MM}` construction was not promoted as an
operating-resource quantity: the anchor retains posterior-allocation KL only
when a supported packed allocation is predeclared and otherwise uses held-out
hard-router allocation regret.  Occupancy remains a persistence diagnostic and
is not identified with certified proper time.

## Claims not promoted into the anchors

These items remain identifiable through Git history, but were not copied as
formal results because the archived proofs do not justify the stated claim.

### Hoeffding “all four terms” bound

\`final_paper.tex\` propagates Bernoulli success-probability error through all
four decomposition terms using a single \(1/p_{\min}\) Lipschitz constant.
This does not cover arbitrary signal-channel estimation, routing mismatch near
zero support, or non-Bernoulli cost estimation.  A valid version needs
positivity margins and a declared estimator for every term.

### Bernstein \(p_{\min}^{-1}\) improvement

The proof substitutes \(p_{\min}\) for the Bernoulli variance upper bound of
every mode.  From \(p_s\ge p_{\min}\), one cannot conclude
\(p_s(1-p_s)\le p_{\min}\).  The advertised bound therefore does not follow
without a different relative-error concentration argument.

### Proxy-validity theorem

The proof uses a second-order Jensen-gap approximation as though it were an
exact identity.  Its derivative sign is also stated incorrectly.  The
fixed-depth single-mode ranking is valid by stochastic dominance, but the
claimed optimizer-distance theorem is not established.

### “Dependence can only help” remark

Positive correlation between attempts can make retries less useful than
independent attempts.  Information reuse may help, but arbitrary dependence
does not provide a lower bound.  The archived statement is false without a
specific dependence model.

### Budget-to-regret cascade

The archived union bound omits the number of models in the logarithmic factor
and does not propagate the log-success Lipschitz constant.  The safe retained
statement is the assumption-explicit uniform-score selection guarantee.

### Three-case transfer bound

The proof found only in the former `final_paper_local.tex` snapshot:

- omits one of the two source--target objective deviations needed for
  transferred-vs-target-optimal regret;
- applies entropy continuity without its binary-entropy term;
- treats routing KL mismatch as Lipschitz without a support lower bound;
- uses prior KL alone to control posterior and routing-channel shifts.

The qualitative transfer trichotomy remains useful, but the displayed
quantitative theorem is not promoted.  The snapshot was removed after this
assessment; Git history remains its provenance record.

### Lagrangian “non-connection”

The useful observation is conceptual: decomposition terms are components of a
primal objective, not automatically shadow prices.  The archived proposition
does not define a sufficiently general constraint family to support its
strongest impossibility wording, so it is retained only as interpretation.

## Source disposition

| File | Decision | Reason |
| --- | --- | --- |
| \`main.tex\` | keep | current compact paper anchor |
| \`arxiv.tex\` | keep | latest AutoResearch manuscript anchor |
| \`archive/theory_anchor.tex\` | keep | maximal validated theory anchor |
| \`arxiv_backup.tex\` | removed | strict predecessor of \`arxiv.tex\`; same formal-result inventory |
| \`archive/main_3.tex\` | removed after second audit | packed, upper-envelope, operational-routing, retry, residual, progressive-signal, finite-horizon, and paired-estimator quantities are in \`theory_anchor.tex\`; protocol material is in \`arxiv.tex\` |
| \`archive/main_1.tex\` | removed after second audit | packed core, cellwise concentration, corrected selection, and evaluation-reuse results are in \`theory_anchor.tex\`; the selection protocol is in \`arxiv.tex\` |
| \`archive/final_paper.tex\` | retain as archive | unique valid depth/routing results consolidated; unsupported claims excluded from the anchor |
| \`archive/neurips_old.tex\` | retain as archive | core duplicates; valid selection ideas consolidated; transfer bound unsupported |
| \`archive/main_local.tex\` | removed after second audit | strict predecessor of \`main.tex\`; no distinct theoretical or empirical result |
| \`archive/main_3_local.tex\` | removed after migration | same theory as \`main_3.tex\`; its unique exploratory pilot appendix was moved to the AutoResearch experiment bundle |
| \`archive/final_paper_local.tex\` | removed after reconciliation | its valid transfer concepts are represented more rigorously in \`theory_anchor.tex\`; the exclusive quantitative bound is unsupported, and its new citation keys have no bibliography entries |
| \`archive/Beneventano_Poggio.tex\` | retain as archive | mechanical text extraction of \`BP.pdf\`, not an authoritative LaTeX source |
| \`archive/next_steps.tex\` | untouched | explicitly excluded by request |

The audit identifies redundancy and records the migration required before
historical source deletion.  Git history remains the provenance record after a
snapshot is removed from the working tree.

## Retained PDFs

- \`archive/main.pdf\`: compiled current-paper snapshot.
- \`archive/submitted-manuscript.pdf\`: immutable submitted manuscript.
- \`archive/BP.pdf\`: immutable historical theory manuscript.
- \`archive/Achille & Soatto.pdf\`: external reference, not merged into an
  authored manuscript.

PDFs are retained for provenance even when an editable anchor covers their
theoretical content.
