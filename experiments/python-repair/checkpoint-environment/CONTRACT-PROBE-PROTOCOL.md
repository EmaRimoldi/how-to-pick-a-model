# Output-contract diagnostic — offline preparation, not authorized collection

The closed recovery pilot has no observed recovery success and 17 empty JSON
objects. A post hoc structural audit also finds 41/67 valid artifacts have the
same AST as the supplied files and 6/15 observed checkpoints have AST-identical
continue/restart inputs. Preserve the original report and all observations;
none of these diagnostics selects exclusions or establishes semantic equivalence.

The next development question is narrower than policy learning: **can this
Gemma 3 4B configuration produce useful code changes under a clearer output
contract, or does failure persist when output encoding changes?** This diagnostic
cannot yet answer when to preserve work. It prepares that necessary prerequisite.

## Fixed design

All twelve already inspected single-file development bugs remain included.
Each gets one fresh initial attempt under each of three contracts (36 calls).
There is no recovery branch, prefix progression, retry or task replacement.
These are new independently identified study attempts, not retries or completion
of unknown calls in the closed bank. No calls have been sent for this study.

| Contract | Instruction | Provider response mode |
| --- | --- | --- |
| `json_current` | Existing strict filename-to-source JSON instruction | `json_object` |
| `json_example` | Same instruction plus every-filename requirement and one unrelated syntax-only example | `json_object` |
| `python_text` | Complete Python source, no JSON wrapper or Markdown fence | response-format parameter omitted |

The text arm changes both instructions and constrained serving mode. Any effect
belongs to that contract bundle, not demonstrably to wording or parsing alone.
The example contains no solution, tests or domain hints for the study tasks.
All arm instructions and deterministic decoders live in `vao.repair.contracts`.
Do not add dynamic repair, Markdown stripping, inferred filenames from output,
extra questions or parser salvage after observing responses.

Task, original files, task specification, public cases and initial public
feedback are byte-identical across arms. The original files must fail the public
suite; an unexpected pass aborts preparation rather than silently removing the
task. Evaluator cases, reference fixes, history and outcomes never enter a request.

Keep the same pinned Gemma 3 4B / Parasail bf16 configuration, temperature 0.7,
4,096 output-token cap and 32,768-token conservative input ceiling. A new fixed
study seed, 43118, pairs the provider seed across arms of a task. API seed support
does not establish deterministic or common random draws. Task order is fixed;
all six arm permutations are used twice across twelve tasks, balancing position.
The packet records every exact provider payload before any authorization.

## Outcomes and development decision

For every cell retain the raw response, finish reason, receipt, cost, decoding,
syntax status, top-level declared entrypoint, public and evaluator results.
Correctness is a full pass of both test suites, not model self-assessment.

Container validity differs across output encodings. For example, `{}` is a valid
Python expression but does not declare `solve`. Report container validity,
syntax and declared entrypoint separately; none proves correct execution. Execute
accepted file artifacts only through the existing sandbox, including candidates
whose tests fail. Empty, truncated and unparseable responses stay paid failures.
An uncertain provider response remains missing and reserved, not a model failure.

Show all twelve paired task rows and missing-cell bounds. With one draw on twelve
inspected bugs, avoid confirmatory p-values, equivalence claims or generalization.
Use no held-out terminology and fit no selector. Report actual costs and local
verification separately: equal per-call allowance does not imply equal spending.

An engineering candidate for further recovery calibration must solve at least
three distinct bugs, produce syntactically valid source with the declared entrypoint
on at least ten bugs, and still leave at least two valid-but-unsolved bugs. These
are prospective practical checks, not powered scientific thresholds or evidence
of action complementarity. Prefer more fully solved bugs, then lower measured
API cost, then the declared contract order. Report every contract, including
null results. If none meets the checks, reconsider task/solver calibration in a
new protocol rather than fabricating a successful selector or changing this run.

## Budget and operational boundary

At the previously verified price ceilings, each call reserves $0.00151552;
36 calls reserve **$0.05455872**. The proposed per-study cap is **$0.06**, including
uncertain requests. The closed repair pilot retains **$0.01011411** committed;
maximum design commitments together would be **$0.06467283**, or **$0.07011411**
if the whole proposed cap were spent. Historical $2/$5 campaigns remain separate.

The existing continuation approval covered only never-started trajectories of
the closed pilot. It does not launch this changed-protocol study. The packet has
`live_calls_enabled: false` and `monetary_authorization_usd: null`. Preparation
and the scripted demo cannot dispatch a network request. Before any collection,
finish and validate the dedicated collector, review a clean source/packet freeze,
record authorization for this new cap and contract comparison, verify current
endpoint identity/prices/credit, and claim the study once. Do not spend based on
this proposed cap or unused funds from a closed campaign.

If authorized later, use at least 60 seconds between distinct requests. A provider
error retains its reserve and stops the study; no automatic resume, retry, fallback
or credential rotation. Rate limiting persisted even with that pacing in the old
bank, so this is an operational precaution, not an availability guarantee.

## Offline commands

```bash
uv run python scripts/prepare_repair_contract_probe.py plan \
  --output runs/repair-contract-probe-draft.json
uv run python scripts/prepare_repair_contract_probe.py audit \
  --input runs/repair-contract-probe-draft.json
uv run python scripts/prepare_repair_contract_probe.py demo \
  --input runs/repair-contract-probe-draft.json \
  --output runs/repair-contract-probe-scripted
```

The demo copies the known buggy source. Its outputs check format handling,
private/public separation and real sandbox verification, with zero API calls;
they are not model efficacy evidence. The source packet may contain evaluator
data for subsequent local scoring, but each exact API payload is independently
projected without it. Inspect payloads rather than forwarding the whole packet.
