# Does escalating after failure beat a cheap feedback-only retry?

Research-note / blog draft, 2026-10-22. Collection is complete. This study is
separate from the [earlier failed-code transfer study](when-to-keep-failed-code.md)
and its empirical manuscript; their task counts and protocols are not pooled.

## Question and result

When a coding model fails public tests, should an agent pay for a larger model
or keep retrying the cheaper one with the latest test feedback? We compared
four executable fixed policies on 157 previously unqueried BigCodeBench tasks.
Each policy had a $0.006 API-dollar admission ceiling per task, including its
initial attempt. All 628 policy outcomes were observed.

The prespecified primary intervention, immediate escalation from Qwen 3.5 9B
to 27B after public failure, solved 98 tasks. Repeated 9B solved 102. The paired
difference is **−2.55 percentage points**, with a 95% task-bootstrap interval
of **[−7.01, +1.27]**. The declared positive-intervention gate did not pass.
We have no established success gain and no basis for claiming equivalence.
We did not train another selector.

The study also exposes two constraints of this particular experiment:
conservative token reservations often leave the larger model's task budget
unused, and public examples can stop a policy on an incorrect program. These
are measured diagnostics of the evaluated system, not validated new remedies.

## Design fixed before model calls

The [frozen protocol](../../experiments/bigcodebench/feedback-only-routing/PROTOCOL.md)
and [precollection funding amendment](../../experiments/bigcodebench/feedback-only-routing/PRECOLLECTION-AMENDMENT.md)
were committed before inference. Eligibility did not use model outcomes.
From 1,140 BigCodeBench tasks we required standard-library dependencies, public
doctests, and successful execution of the official reference solution against
the public examples and unmodified full suite under two fixed RNG seeds.
A lexical screen removed close prompt overlap with prior project benchmarks
and within the new pool. The exact 157 tasks and every exclusion are retained
in the [qualification manifest](../../experiments/bigcodebench/feedback-only-routing/data/manifest.json).

This is a reference-qualified standard-library subset, not an estimate for all
BigCodeBench or production agents. “New” means never queried in this project;
it does not establish absence from model pretraining data.

We evaluated Qwen 3.5 9B and 27B through the same SiliconFlow FP8 provider,
temperature 0.6, a 1,536-token completion ceiling, no reasoning mode, fallback,
provider seed or automatic retry. There was one replicate per task. The three
small-start policies shared the same initial 9B response, charged to each
deployment policy but paid only once during collection. The direct-27B control
had its own initial response. Dispatch and policy order used frozen shuffles.

After failure, each request received the original task and only the latest
public doctest feedback, limited to 1,200 characters. It received no previous
solution, full conversation, reference code or hidden diagnostics. Feedback
came from the actual preceding response, rather than a substituted trajectory.
All policies stopped on their first public pass, even if the full-suite
evaluation subsequently failed. Hidden tests never triggered another call.

## All four policies

| Policy | Full-suite successes | Success rate | Mean API USD / task | Mean / median API seconds |
| --- | ---: | ---: | ---: | ---: |
| Retry 9B with feedback | 102/157 | 65.0% | $0.000766 | 88.90 / 13.10 |
| Immediate 9B → 27B | 98/157 | 62.4% | $0.000446 | 17.13 / 12.97 |
| Two 9B attempts, then 27B | 105/157 | 66.9% | $0.000418 | 21.61 / 13.27 |
| Direct 27B, retry 27B | 100/157 | 63.7% | $0.001018 | 13.00 / 11.50 |

The primary analysis uses paired task-cluster bootstrap intervals, 10,000 draws
and the frozen seed. The three secondary comparisons use 98.333% intervals:
delayed minus retry is +1.91 pp [−3.18, +7.01]; direct 27B minus retry is
−1.27 pp [−9.55, +6.37]; immediate escalation minus direct 27B is −1.27 pp
[−8.92, +6.37]. All span zero. Delayed escalation's highest observed rate
cannot replace the failed primary comparison or establish a winning strategy.

![Final policy comparison](../../experiments/bigcodebench/feedback-only-routing/results/fixed-policies-20261022/fixed-policy-comparison.png)

The API seconds above sum requests within a policy. They exclude collection
queue time and local verification. The long retry tail raises mean 9B latency;
its median is close to the two escalation policies. A ratio of means would
misrepresent the speedup experienced on a typical task.

## Why a smaller bill does not establish equal-quality savings

All policies share a ceiling, not equal realized spend. Before each request,
the runner reserves the frozen worst-case input/output charge. This is
$0.0010496 for 9B and $0.00512 for 27B. A call is refused when that amount
does not fit, even if its eventual actual receipt might have been cheaper.

The resulting admission asymmetry is substantial. Among budget-stopped tasks,
retry 9B spent a mean 83.5% of the cap (17 tasks). Immediate escalation spent
20.8% (27 tasks), delayed escalation 25.3% (19), and direct 27B 22.5% (29).
The larger-model policies frequently terminate with most of the cap unused.
This rule was frozen and is part of the primary policy being tested. We retain
it rather than retrospectively repairing the experiment. It limits any claim
about the intrinsic value of escalation or the cost frontier under another
admission mechanism. No noninferiority margin or cost-saving success criterion
was prespecified, so these lower bills do not demonstrate equal-quality savings.

## Public tests can end recovery too early

Of the 157 shared initial 9B responses, 105 passed the public examples but only
80 passed the official full suite. Thus **25 initial public false positives**
terminated all three small-start policies before any escalation could occur.

Terminal public false positives numbered 38 for retry 9B, 32 for immediate
escalation, 33 for delayed escalation and 28 for direct 27B. Every such task
remains a failure in the reported denominator. This finding motivates testing
a stronger observable verifier, but does not measure the effect of adding one.
Exposing hidden tests after seeing these results would change the experiment.

![Admission utilization and verifier outcomes](../../experiments/bigcodebench/feedback-only-routing/results/fixed-policies-20261022/admission-and-verification.png)

## Audit, transparency and limits

The completed bank contains **1,492 model responses** and no missing outcomes,
unknown charges or unresolved reservations. Known collection charges total
**$0.38896675**, below the study's $4 cap within the separately authorized $5.
Shared initial responses mean collection cost is different from the sum of
four separately deployed policies. Local verifier compute is recorded in
seconds and is not included in API dollars.

We repeated the offline checks under the same frozen sandbox and RNG seed:
29 format errors were reproduced, all 1,463 parseable solutions' public checks
were rerun, and all 326 originally executed full-suite checks were rerun.
There were zero pass/fail discrepancies. Original labels were retained;
agreement under the same tests is not proof of semantic correctness beyond them.

After the freeze, the user requested one descriptive interim look at the 83
tasks then complete under all four policies. Faster/easier completion could
bias that subset. The [disclosure](../../experiments/bigcodebench/feedback-only-routing/INTERIM-DISCLOSURE.md)
and exact record preserve all included call IDs, policy keys and journal-prefix
checksums. No interim confidence interval, p-value, gate, tuning, efficacy
stopping or collection change followed. Final inference uses the original
comparison and all 157 tasks; the interim read is explicitly disclosed.

Other limits include one replicate, one provider/precision, one budget point,
the reference-validity filter, lexical overlap screening, public benchmark
contamination and limited power for modest effects. All four policies use
feedback, so this study **cannot establish that feedback helps relative to
receiving no feedback**. No claim is made about adaptive selection, retained
code, hidden reasoning state or a production-ready controller.

## Reproduce and decide what comes next

From the repository root, verify receipts, prompt projection, checksums, frozen
source snapshots, primary/secondary statistics, descriptive accounting and
the unchanged original interim prefix without credentials or candidate execution:

```bash
uv sync --dev --frozen
uv run python scripts/verify_feedback_evidence.py \
  --input experiments/bigcodebench/feedback-only-routing/results/fixed-policies-20261022
```

The [complete report](../../experiments/bigcodebench/feedback-only-routing/results/fixed-policies-20261022/report.md)
contains the numerical artifact and inert source snapshots. Existing empirical
manuscripts remain separate. This result supports reporting a negative fixed
escalation test and its implementation constraints; it does not support building
a selector around a presumed gain. Any next study should first prespecify an
admission/verifier intervention, use these now-observed tasks only for development,
and reserve independent tasks for its evaluation. No such study has started.
