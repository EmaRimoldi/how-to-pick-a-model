# Coding-solver compatibility control, v1

Status: prospective development protocol, fixed before any model call in this
study. Identity: `repair-solver-compatibility-v1`. It is not a continuation of
either interrupted study and cannot fill their missing outcomes.

## Question and scope

Can one coding-oriented model repeatedly repair the existing failed checkpoints
with the original public information and response contract? The preceding
[interface control](results/interface-stopped-20261026/README.md) produced no
complete repair among 44 received answers and remains statistically inconclusive.
This positive-control attempt checks practical solver/task compatibility. A
positive outcome is not assumed, and a null result must be retained.

Use all twelve `json_current` candidates from the complete Gemma 27B archive,
SHA-256 `f2a3b228425ee98a8a5bbc0422f6bdb486d44eeb1a2a86d4cabeba309103c913`.
The same eight public failures receive four fresh draws each: **32 requests**.
Four public passes remain in provenance without intervention. Eligibility never
uses evaluator scores. These are exposed development bugs; ten of the twelve
original bugs come from youtube-dl. None becomes a fresh holdout.

The sole condition is `direct_repair`: original `json_current` instruction,
original failed artifact including its provenance comment, raw public tests and
preceding feedback. Message content must exactly match the original condition
of the interface study. No extra helper permission, focused repetition, trace,
reference patch, fault location, evaluator input or expected hidden value is added.
The task, evaluator, decoding and complete-pass criterion remain unchanged.

## Model, exact requests and operational boundary

Pin `qwen/qwen3-coder-next`, endpoint `parasail/bf16`, provider Parasail, BF16,
temperature 0.7, JSON object response, at most 4096 output tokens and a conservative
32768 input-token admission bound. Price ceilings are **$0.12/$0.80 per million
input/output tokens**. The [endpoint review](SOLVER-ENDPOINT-REVIEW-20261026.json)
records the public metadata and checked alternatives. The
[official model card](https://huggingface.co/Qwen/Qwen3-Coder-Next) describes the
coding-oriented model; no advertised benchmark gain is treated as our evidence.

The cheaper checked Qwen3-Coder-30B endpoint did not advertise seed support.
Coder-Next provides the required seed, JSON and explicit precision controls at
a lower reservation than the other inspected coding endpoints meeting the
generation-parameter requirements. This is not an exhaustive cheapest-model
claim. Report the actual pinned provider price, not a catalog minimum from a
different endpoint. Endpoint availability/uptime snapshots do not predict this run.

Seed base 43128 deterministically shuffles the 32 task/draw cells and generates
distinct request seeds. All request identities and provider bodies are frozen
and checked against every old planned body, including uncertain and never-sent
requests. Provider seeds do not guarantee deterministic generation.

This is one model configuration, not a concurrent controlled Gemma comparison:
model, provider, precision, seed and collection time differ from historical
banks. Do not infer a causal specialization effect, parameter-count effect or
scaling law. Do not pool the old and new draws as independent bugs.

Use the same authorized key, **no rotation, no fallback**, and at least **60 seconds
between admissions**. Read-only account review found enough credit for this cap,
but neither it nor public metadata identifies the cause of earlier HTTP 429s or
proves that a limit has reset. OpenRouter's [rate-limit explanation](https://openrouter.ai/pricing)
does not diagnose an individual failure. No generation health check is allowed.
The new model is a scientific compatibility control, not a resumed old request.

Live preflight must independently reconfirm endpoint identity, all required
parameters, context limits, price ceilings and credit before admission. A
single-use study claim prevents a duplicate launch. Any request error or uncertain
charge stops the collection and retains its full reserve. No retry, resumption,
successor, model change or ad hoc replacement task is authorized by this protocol.
Until termination inspect only integrity, progress and accounting. Keep sources
unchanged while the collector runs.

## Separate declared allocation

The [allocation](SOLVER-AUTHORIZED.json) declares **$0.24** under the user's standing
instruction to continue and latest goal amendment. This is an agent-declared
bounded allocation, not a newly user-typed amount or unlimited spending.
Carry **$0.05126739** exactly once, including eight unresolved historical calls,
under the retained **$0.60 cumulative ceiling**. Closed study caps remain unchanged.

The reserve per new request is $0.00720896. Maximum 32-call reservations total
$0.23068672; maximum design cumulative commitment is $0.28195411. Even committing
the whole new cap would total $0.29126739. Report known receipts, uncertainty,
prefix counterfactual costs, local verification time and provider latency
separately. Each deployed draw bears one prefix cost; the prefix is not newly
billed into the research ledger. Pacing is an operational precaution, not a
policy's action cost. Equal call limits do not establish equal total resource use.

## Prespecified analysis and engineering screen

Primary outcome: full public-plus-evaluator pass on each of the 32 cells. Report
all twelve retained source records and all planned cells, plus usable source,
public passes, false public acceptance, public-score improvements/regressions,
syntax-edit categories, API cost and verification time. A public pass alone is
not a successful repair; syntax changes do not establish semantic improvement.

For a sealed complete bank, report mean full success and a descriptive bug-cluster
bootstrap interval (10000 resamples, seed 43129) using eight per-bug four-draw
means. Eight selected clusters do not support confirmatory population inference.
For an incomplete bank, retain finite selected-cell worst/best success bounds,
null mean/bootstrap fields and an inconclusive screen. Missing responses are
unknown, not failures. Report bounds on the number of repeatedly solved bugs.

The engineering screen requires a complete bank, no accounting overrun, and
**at least three distinct eligible bugs each solved in both draw halves**
`{0,1}` and `{2,3}` (at least two successes per such bug). Concentrating two
successes in the same half does not pass. This threshold is fixed before calls,
not selected from their outcomes. False acceptances and regressions remain
visible even if the compatibility screen passes.

A pass permits only a separately frozen intervention calibration comparing
direct repair and costed diagnostic acquisition. It does not demonstrate action
complementarity, policy benefit or correctness on all possible inputs, and never
automatically enables selector fitting. A failure requires reconsidering the
task/solver setup without rewriting this screen or historical results.

## Delivery and reproduction

```bash
.venv/bin/python scripts/prepare_repair_solver_study.py \
  --output runs/repair-solver-packet.json

.venv/bin/python scripts/report_repair_solver_study.py \
  --input runs/repair-solver-live \
  --output runs/repair-solver-report --export-evidence

.venv/bin/python scripts/verify_repair_contract_evidence.py \
  --input runs/repair-solver-report --output runs/repair-solver-replay.json
```

Preparation, reporting and verification never call a model. Live launch requires
the separately funded config, exact request review, clean committed source,
passing offline workflow and CI, and a single-use freeze. At termination audit
every receipt and projection, preserve inert frozen sources, independently replay
all saved evaluation inputs, and publish all results including nulls/missingness.
Update the draft PR and pause the dedicated monitor after delivery.
