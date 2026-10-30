# Diagnostic acquisition: information timing and a nearby selector precedent

This review was prepared offline while the contrastive collector was active,
without reading treatment outcomes. It is published after independent terminal
replay. The [completed study](results/contrastive-calibration-20261026/README.md)
failed its fixed development screen; this review does not amend that protocol,
authorize calls, select new bugs, train a policy or change the user goal.

## What the current experiment actually supplies

The frozen source commit is `3846e157c0a8c2ef6992f85a52b724c6b6de1a6b`.
`src/vao/repair/diagnostics.py:project` includes the current files, every declared
public case (including expected values) and the full existing public feedback in
the common prompt. `contrastive_diagnostics.py:project` extends that same prompt
with observed runtime records. `contrastive_study.py:planned_requests` uses these
projections for the three fixed arms.

Therefore the current question is whether bounded execution evidence helps a
solver **given already available public tests and their outcomes**. It is not a
test of deciding to purchase a new labeled example or query an unobserved test.
This distinction does not imply that the current diagnostic is redundant: the
intermediate runtime values were not in the base prompt, even when they could in
principle be computed from code and inputs. Their practical value is the
empirical question. The completed development screen did not establish repeatable
benefit; it cannot identify why the intervention missed its criterion.

The accompanying [information map](results/contrastive-calibration-20261026/information-map.json) records the source hashes, static code
locations, access distinctions and inference limits. It contains no run outcomes
or newly inspected benchmark tasks.

## Primary-source follow-up

Sources inspected 2026-10-26 local / 2026-10-27 UTC. Claims below describe the
authors' results, not replications in this repository. This is a targeted review,
not a proof that all relevant papers have been found.

| Source | Finding relevant to our next decision |
| --- | --- |
| [VeruSteer, arXiv v1, 21 October 2026](https://arxiv.org/html/2610.29755v1) | Learns the next reported error type to repair from program, diagnostics and history. On 1,270 stored test trees, verified outcomes rise from 185 to 194: 12 gained, three lost, +0.71 percentage points. Tasks are split across training/validation/test; replay reuses sampled transitions. This is a close sequential-selection precedent, but its action is a repair target, not diagnostic acquisition. |
| [Experimental Settings in LLM-Based Program Repair, September 2026](https://arxiv.org/html/2609.17993v1) | Separates stored benchmark artifacts, initial exposure, allowed actions and returned observations from evaluator-only validation. Changing which tests are initially visible changes the experimental task. Its source-level manifest motivates an explicit information contract for any future revision. |
| [EviACT, May 2026](https://arxiv.org/html/2605.27238v1) | Coordinates retrieval, compilation and targeted-test checks before full regression. It supplies another direct precedent for execution evidence controlling repair stages. A staged fixed strategy should be considered before attributing value to a learned selector. Its reported cross-system API-cost reductions are not our equal-total-resource comparison. |
| [LEARN2FIX, author-hosted paper](https://mpi-softsec.github.io/papers/TSE24-learn2fix.pdf) | Selects queries to a human bug oracle under a limited labeling budget. Its repair experiments obtain expected outputs for the selected failing inputs. This establishes a precedent for costly information acquisition and also makes the source of correct labels an explicit experimental assumption. |
| [Chen et al., ACL 2025](https://aclanthology.org/2025.acl-long.881/) | Reports that self-generated test expectations can bias repair feedback. A generated assertion is not automatically a trusted diagnostic oracle. This strengthens the need to declare where expected answers originate. |

Our methodological inference: report overall task success, gains and losses,
costs and missingness. Conditional recovery on cases with a favorable alternative
cannot replace the all-task comparison. A new learned choice based on repair
history is not by itself a novelty claim. The VeruSteer results also do not
certify fresh-sample deployment performance or our Python acquisition policy.

## Conditional candidate for a later, separately frozen study

Only if the current results justify revising acquisition, consider comparing a
repair now with a request for **an additional trusted diagnostic test** before
repair. This remains a proposal, not the selected next experiment.

| Channel | Initial visibility | Access after a decision | Final evaluator use |
| --- | --- | --- | --- |
| Bug report, editable code and initial failure | Available to every strategy | Preserved in history | Provenance only |
| Additional development/regression tests | Declared catalog or access policy, without unpaid outcome access | Explicit permitted test action, with selection/execution/reading costs | Never silently relabeled as private evaluation |
| Private evaluator cases and reference repair | Never available to the agent or selector | No acquisition action | Used only after the policy is sealed |

This would require a credible deployment reason for staged access. Existing
public test files in a readable workspace cannot be described as hidden, nor can
their known expected values be sold back as new evidence. Artificially withholding
cheap, available tests just to favor the selector would not establish utility.
For the small function-level adapters, running the whole suite may be so cheap
that acquisition selection has no meaningful advantage; feasibility must be
shown rather than assumed.

A useful future comparison must include repair immediately, a fixed focused-test
strategy, and running all permitted regression tests before repair, with all
resource costs charged. A test chosen adaptively must earn its selection cost.
Trustworthy additional tests must be declared before outcomes, with independent
validation retained; no current private case can be retroactively moved into the
acquisition channel. If expected values need human input, that cost and the human
oracle assumption must be explicit. No generated expected answer is treated as
ground truth merely because a model wrote it.

## Decision order remains unchanged

1. The 72-request contrastive bank is complete and independently audited under
   its original primary comparison, screen and missingness rules. The screen failed.
2. If its screen passes, first replicate the same useful intervention on separate
   development sources. Do not swap to this proposed intervention to chase a
   different story.
3. If it does not pass, inspect the terminal evidence and compare concrete
   revisions. This information-access proposal is one candidate, with its own
   feasibility burden; it is not a reinterpretation of the current result.
4. Require a new task/information contract, protocol, source freeze and bounded
   allocation before any new collection. Only after repeatable utility should a
   selector be trained and evaluated on untouched, grouped bugs at common total
   resources against the strongest development-selected fixed strategy.

The closed collector, task set, prompts, budgets and decision gate remain
unchanged. No new benchmark contents were inspected for this review.
