# Unified NeurIPS Paper Plan

Working title: **How to Pick the Model: Decomposable Performance Accounting for Agentic Systems**

## Diagnostic Summary

`final_paper.tex` is the broader and more ambitious manuscript. It contains the full "decomposition engine" framing, packed latent-mode assumption, routing-information identity, four-term decomposition, graph-depth/crossover theory, sample-complexity and Bernstein results, routing-triviality diagnostics, related work, limitations, and appendices. Its main weakness for NeurIPS is scope: too many theory extensions, synthetic validations, scoping remarks, and practitioner material compete for the nine-page main text.

`neurips.tex` is a tighter NeurIPS-style manuscript. It has a clearer three-pillar narrative: decompose, decide, reuse. Its strongest components are the concise abstract/introduction, the decomposition-guided design-selection algorithm, evaluation-complexity analysis, transfer theory, and compact experimental tables. Its weaknesses are that several empirical claims are still synthetic or semi-synthetic, the transfer story may be too much for the main paper, and the experimental section needs a clearer narrative about metrics, rankings, robustness, and evidence limits.

The unified paper should be about model/design selection for agentic systems under a packed latent-mode abstraction. It should not drift into the Turing-ordering paper; the Turing project was used only as the source of the NeurIPS checklist.

## NeurIPS 2026 Constraints

Official 2026 guidance is available. Main-track submissions have nine content pages including figures and tables. References, acknowledgements, optional technical appendices, and the mandatory checklist do not count toward the content limit. The paper must use the current `neurips_2026.sty`; old styles or style-file tweaks risk desk rejection. The submission PDF should include paper, references, appendix, and checklist in one file. Code/data may be submitted separately as anonymized supplementary material. The checklist is mandatory and visible to reviewers. Use of agents/LLMs as part of the methodology must be disclosed in the experimental setup when non-standard or central.

Planning consequence: the main paper should be one focused theory-plus-evidence argument. Full proofs, extended synthetic experiments, transfer proof details, practitioner flowcharts, and long related-work discussion belong in the appendix.

## Central Thesis

The defensible thesis is:

> Choosing a model or agent design is not a scalar benchmark race. Under a packed latent-mode model of verifiable tasks, the performance gap between designs decomposes into interpretable and separately estimable terms: cost, competence, routing information, and routing mismatch. This decomposition yields practical design rules, a sample-efficient selection algorithm, and diagnostics for when routing or transfer is worth engineering.

Main claim scope:

- The four-term identity is exact under the packed latent-mode and geometric-trials assumptions.
- The decomposition is performance accounting, not a Lagrangian dual decomposition.
- The algorithmic value is that a shared structured pilot can score many candidate designs without racing each one end-to-end.
- Empirical evidence should be presented as validation of the framework's internal predictions and as initial practical evidence, not as proof that all real agent tasks satisfy the assumptions.

## Proposed Table of Contents

1. Introduction
2. Setup: Verifiable Agent Design Under Latent Modes
3. Four-Term Decomposition
4. Decomposition-Guided Design Selection
5. Experiments
6. Transfer and Reuse
7. Related Work
8. Discussion, Limitations, and Future Directions
9. Appendix
10. NeurIPS Checklist

## Section-by-Section Plan

### 1. Introduction

- Start from the builder's problem: given a task family, a menu of models, routing policies, retries/depth, and costs, which design should be deployed?
- Contrast with benchmark racing: easy, assumption-light, but opaque and evaluation-expensive as the design menu grows.
- State the paper's core move: decompose the performance gap into cost, competence, information gain, and mismatch.
- Preview the practical consequences: crossover depth, routing-triviality pre-check, decomposition-guided selection, transfer trichotomy.
- Source: both. TO DEVELOP: sharpen the contribution list around one main theorem, one algorithm, and one experimental validation story.

### 2. Setup: Verifiable Agent Design Under Latent Modes

- Define budgeted transductive/verifiable tasks: instance, solution, verifier, budget.
- Define model/agent design: model, depth/retries, routing policy, per-step cost, verification protocol.
- Define task modes and the packed latent-mode family assumption.
- Clarify what is observable in experiments: oracle workload family or proxy mode, not necessarily discovered latent structure.
- Source: both, especially `sections/preliminaries.tex` and `sections_n/decomposition.tex`.
- Appendix: residual outside the packed family, formal notation variants.

### 3. Four-Term Decomposition

- State the routing-information identity only if it directly helps the main theorem.
- State the four-term model-aware decomposition as the main mathematical result.
- Explain each term operationally: cost, competence, information gain, mismatch.
- Include the Lagrangian non-connection as a compact remark/proposition: the terms are primal accounting terms, not shadow prices.
- Include the crossover formula as the main actionable corollary.
- Source: both, strongest from `sections/act2_decomposition.tex`, `sections/act3_extensions.tex`, and `sections_n/decomposition.tex`.
- Appendix: full proof, Lagrangian proof, expectation-vs-quantile discussion, Kelly-Cover interpretation.

### 4. Decomposition-Guided Design Selection

- Present the algorithm: structured pilot, analytical scoring, confirmation on top candidates.
- Define the ranking/objective used to order designs.
- Explain there may not be a universally correct ranking metric: expected log certified time, cost-adjusted success, regret, and quantile objectives are all defensible under different deployment goals.
- The main paper should use one primary metric and include sensitivity analysis for alternatives.
- State near-optimality and evaluation-complexity guarantees.
- Source: `neurips.tex`/`sections_n/algorithm.tex` plus `final_paper.tex` sample-complexity material.
- Appendix: tightness example, full sample-complexity cascade, Bernstein derivation.

### 5. Experiments

- Experimental setup: task family/modes, design menu, models, costs, depth grid, randomization, validation split, pilot/confirmation budgets.
- Conditions/protocols: synthetic packed-family validation, end-to-end selection experiments, transfer grid, real or semi-real benchmark diagnostics.
- Models: list model tiers or abstract model set; if using live LLM agents, report exact versions and costs.
- Metrics: expected log objective, regret, savings factor, pairwise model terms, crossover depth, routing information gain, routing mismatch, transfer regret.
- Ranking construction: rank candidate designs by the primary decomposition score, then report how rankings change under alternative metrics.
- Main results: sample-efficient design selection, crossover predictions, routing-triviality diagnosis, transfer savings.
- Robustness/sensitivity: pilot budget split, Bernstein vs Hoeffding, threshold/cost-ratio variation, model-cost perturbations, mode-prior shifts.
- Qualitative transcript/log analysis: if live agent transcripts are included, use short snippets/log traces to show why specific modes trigger different design choices; otherwise move this to appendix or omit.
- Limitations of experimental evidence: synthetic/semi-synthetic assumptions, limited live runs, closed-model nondeterminism, mode labels may be oracle families rather than discovered latent modes.
- Source: both. TO DEVELOP: replace placeholder real-benchmark section with actual query-engine/autoresearch evidence or clearly mark as future work.

### 6. Transfer and Reuse

- Keep the main transfer story concise: post-training equivalence vs orchestration equivalence; plug-and-play, re-route, start over.
- Include the two divergences only if page budget allows.
- Present transfer as a secondary contribution after decomposition-guided selection.
- Source: `sections_n/transfer.tex` plus shorter version in `sections/act3_extensions.tex`.
- Appendix: independence constructions, transfer proof, full transfer grid.

### 7. Related Work

- Compound AI systems and routing: RouteLLM, FrugalGPT, routing/cascade systems.
- Test-time compute scaling and repeated sampling.
- Algorithm selection, portfolios, racing, successive halving, Bayesian optimization.
- Domain adaptation and transferability estimation.
- Information-theoretic search/time views: Kelly, Cover, Levin/Solomonoff, Achille/Soatto-style time-centric frameworks.
- Source: both, especially `sections_n/related_discussion.tex` for concise NeurIPS fit.

### 8. Discussion, Limitations, and Future Directions

- Explain what is foundational: model choice becomes a measurable design-accounting problem rather than a leaderboard race.
- State when the framework should not be used: single-mode tasks, no pilot data, trivial routing, rapidly shifting distributions, tiny design menus.
- Explicitly list open research questions:
  - How should latent modes be discovered rather than supplied by oracle families?
  - How does the decomposition degrade under non-geometric certified-time distributions?
  - How should one choose between expectation, quantile, and cost-adjusted ranking metrics?
  - Can the pilot/confirmation split be optimized theoretically?
  - When does transfer reuse work in real agent deployments?
  - How should the framework extend to continuous design spaces and multi-step dependent agents?
- Source: both, especially `sections/discussion.tex` and checklist constraints.

## Mapping Table

| Unified section | Main source | Use in main text | Move to appendix |
|---|---|---|---|
| Introduction | both | Builder problem, benchmark racing critique, contributions | Long folklore discussion |
| Setup | both | Verifiable task, design tuple, packed modes | Residual outside packed family |
| Four-term decomposition | both | Main theorem, term interpretation, crossover | Full proofs, Kelly analogy, Lagrangian details |
| Design-selection algorithm | `neurips.tex` | Algorithm, near-optimality, O(1)-in-k evaluation argument | Tightness proof, full cascade |
| Experiments | both | Setup, metrics, main quantitative results, robustness | Extra synthetic experiments, full tables |
| Transfer | `neurips.tex` | Short secondary contribution | Independence and full transfer proofs |
| Related work | both | Concise NeurIPS positioning | Long citation discussion |
| Discussion/limitations | both | Scope, non-use cases, open questions | Practitioner guide |
| Checklist | copied from Turing project | Required after appendix | N/A |

## Material to Move to Appendix

- Full theorem proofs.
- Lagrangian non-connection proof.
- Full sample-complexity and Bernstein derivations.
- Transfer independence constructions and transfer bounds.
- Extended synthetic experiments EXP1--EXP15.
- Practitioner decision flowchart and pilot-sizing table.
- Full experiment configs, code commands, compute/cost reporting.
- Alternative ranking metrics and complete sensitivity tables.
- Any qualitative logs/transcripts not essential to the main empirical argument.

## Missing Pieces

- Decide the primary ranking/objective metric for the main paper.
- Decide which experiments are real/live enough for main text versus appendix.
- Compute or extract confidence intervals/error bars for main experimental claims.
- Add Bayesian optimization or clearly scope it as missing.
- Replace placeholder real-benchmark validation with current query-engine/autoresearch evidence if intended.
- Define exact model names, costs, versions, and budgets.
- Write a concise NeurIPS abstract that does not overclaim beyond assumptions.
- Complete checklist answers and reproducibility details.
- Ensure the main paper fits nine content pages.

