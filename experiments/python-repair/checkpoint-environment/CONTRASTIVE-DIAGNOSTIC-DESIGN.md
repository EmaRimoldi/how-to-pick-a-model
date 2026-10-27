# Revised information intervention: a public failing/passing contrast

Status: **offline development preparation, not a frozen funded collection**.
This follows the complete trace study's failed screen and its
[post hoc audit](results/information-independent-posthoc-20261026/README.md).
The final objective is unchanged: a prospective acquisition policy that beats
the best fixed strategy on untouched bugs under a common total resource envelope.

## Hypothesis and controls

An execution of a failing example shows what happened but may leave the model
without a concrete comparison for behavior that must survive its edit. The
working hypothesis is that a bounded pair of failing and passing public
executions can improve complete repair, beyond the same feedback and a single
trace. The current bank does not establish this mechanism or prospective benefit.

The proposed calibration has three concurrent conditions, using fresh requests:

1. **Focused feedback:** current code, full public tests and observations, first
   failure highlighted; no new execution evidence.
2. **Single trace:** identical core prompt plus one bounded failure trace with
   the v2 lossless representation.
3. **Paired traces:** identical core prompt and identical first trace, plus one
   bounded trace of a selected already-passing public test.

Paired versus focused feedback is the primary efficacy comparison. Paired versus
single trace measures the incremental contrast; single versus focused diagnoses
the representation variant. Do not substitute a favorable secondary comparison
for the primary. All source candidates, unavailable diagnostics, failed replies,
false acceptances and regressions remain in the denominator. Complete repair
requires the frozen public and evaluator suites, not one corrected example.

An efficacy screen must be declared before new responses; there is no fitted
selector or changed historical gate. The eight exposed bugs can only support
development. Before an equal-budget policy study, freeze grouped evaluation bugs
that have not been inspected or used to design this intervention.

## Implemented public-only acquisition

`vao.repair.contrastive_diagnostics` accepts only the existing public task schema,
current files and bound public feedback. It uses the first public failure and
selects one already-passing input, preferring the same recursive JSON type shape,
then minimum recursively averaged normalized Levenshtein distance. Strings are
bounded to their first 256 characters; ties preserve public order. Case names,
expected outputs, provenance, private tests and reference code do not rank inputs.
This heuristic is not a semantic-distance claim or a learned selector.

Each selected case is rerun normally and traced in fresh existing OS sandboxes.
Both observations must agree with recorded public feedback. Single acquisition
costs two executions; paired acquisition costs four. No public failure means no
probe. No passing case or any mismatch yields an explicit unavailable diagnostic,
with spent executions retained. It does not synthesize a passing test or infer an
expected answer from the buggy program.

The v2 representation retains every saved event and all value/truncation markers.
It delta-encodes adjacent reported local snapshots only when the canonical UTF-8
JSON becomes shorter; otherwise it preserves the raw representation. Expansion
reproduces the retained trace exactly. It does not reconstruct dropped events,
inspect omitted regex objects, identify a causal slice or claim token savings.
Old worker, verifier and v1 acquisition implementations remain unchanged.

The [offline qualification](results/contrastive-preparation-20261026/README.md)
retains all twelve sources. Both variants are available for all eight triggered
sources. It contains zero model calls and no repair efficacy evidence.

## Prior work and novelty boundary

Primary sources checked on 2026-10-26 (local date):

- [ContrastRepair, §3.2](https://arxiv.org/html/2403.01971) already pairs failing
  tests with similar passing tests and uses existing or generated passing cases.
  Our bounded existing-test heuristic and runtime-pair adapter are inspired by
  that idea; they are not a reproduction of its mutation or conversation system.
- [Haque et al., KnowledgeNLP 2025](https://aclanthology.org/2025.knowledgenlp-1.17/)
  find that naive trace inclusion does not consistently help. This motivates
  controlling representation and keeping negative results, not predicting a gain.
- [Maniple, §III-B](https://arxiv.org/html/2404.05520) studies fact selection and
  includes runtime facts and reference-derived angelic values. The latter are
  excluded here: our passing observations come from existing public tests.
- [TraceRepair, §3.2](https://arxiv.org/html/2604.02647) selects runtime probes and
  uses their observations in multi-strategy repair. Targeted diagnosis alone is
  prior art; its additional model calls would need full cost accounting.
- [To Run or Not to Run](https://arxiv.org/html/2606.26978) directly studies the
  cost and uneven benefit of execution in repair agents, including quota and
  budget-guided conditions. Its reported nonsignificant differences do not prove
  equivalence. Its main prohibition is prompt-level, with additional constrained
  checks. We must compare against simple acquisition quotas, not claim that
  recognizing execution cost is new.

No novelty claim follows from contrasting traces, choosing facts or counting
execution costs. The remaining research target is measurable prospective benefit
over the strongest fixed policy under enforced total resources on unseen bugs.

## Before any new paid experiment

Freeze a clean source commit, exact request schedule/seeds/provider contract,
fresh request identities, selected development sources, primary analysis and
stopping/missingness rules. Declare a separate sublimit under the unchanged
$0.60 ceiling, carrying $0.16495655 once including thirteen historical uncertain
reservations. No allocation or model launch is created by this document.

Charge acquisition, prompt tokens, every generation attempt, selection and
public verification. Keep evaluator-only research cost separate. Equal output
caps alone are not an equal-total-budget comparison. Only after repeatable
intervention benefit should we integrate the resource-bounded fixed-policy
runner, establish useful action headroom, and fit a prospective selector on
development data. Qualification success is not permission to skip these stages.
