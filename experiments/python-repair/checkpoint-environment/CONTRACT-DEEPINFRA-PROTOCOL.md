# Output-contract follow-up on pinned DeepInfra

## Why a separate study

The Parasail contract diagnostic ended after three responses and an HTTP 429 on
the fourth admission. Its three responses concern only one bug; the incomplete
gate is inconclusive. Preserve that bank, its authorization and all reserves.
The user subsequently instructed **“Non farti problemi di denaro. Continua.”**
This authorizes continued research; it does not imply unlimited spending. Before
any new calls, this follow-up declares a **$0.08 sublimit within the existing
$0.60 cumulative ceiling**. It is not an increase to the overall ceiling and is
not claimed to be a separately user-specified $0.08 figure.

A read-only account check showed non-free-tier access and credit covering the
existing ceiling. It did not identify the exact upstream cause of the historical
429. [OpenRouter documents provider-side limits for paid models](https://openrouter.ai/pricing),
and [lists a DeepInfra bf16 route for the same model](https://openrouter.ai/api/v1/models/google/gemma-3-4b-it/endpoints).
Listing and uptime metadata do not guarantee successful inference. The route is
pinned before calls; no automatic provider fallback or key rotation is enabled.

## Fixed design and prospective decision

Study ID: `repair-contract-deepinfra-v1`. Use all the same twelve inspected
single-file development bugs, one fresh initial attempt under each of
`json_current`, `json_example`, `python_text`: 36 new study cells. Keep all text,
examples, strict decoders, public/evaluator cases and engineering gate from
[the original protocol](CONTRACT-PROBE-PROTOCOL.md). Do not salvage fenced output,
drop tasks, inspect treatments mid-run, change the gate or train a selector.
The text arm still changes both instructions and serving mode.

Use `google/gemma-3-4b-it`, `deepinfra/bf16`, provider `DeepInfra`, bf16,
temperature 0.7, 4,096 maximum output tokens and a conservative 32,768 input-token
ceiling. Seed **43119** fixes a new task order, balanced arm positions and paired
within-bug seeds. New study/trajectory identities ensure no admitted old attempt
is replayed. These are fresh development draws, not a repair of missing records.
The old bank stays missing and immutable; never pool banks, claim a provider
comparison, or interpret seed support as deterministic paired random draws.

The complete-bank engineering gate still requires at least three distinct fully
solved bugs, at least ten syntax-valid artifacts with the declared entrypoint,
and at least two such artifacts still unsolved. Select more fully solved bugs,
then lower actual API charges, then declared contract order. These are practical
calibration checks, not scientific significance or evidence of action
complementarity. If the bank is incomplete the gate is inconclusive. Report every
selected cell, missing-data bounds, actual API costs and local timing separately.

## Budget and stopping

Price ceilings checked before launch: $0.05 / million input tokens and $0.10 /
million output tokens. Each request reserves **$0.002048**. All 36 reserve
**$0.073728**, within the **$0.08** sublimit. Closed commitments of **$0.01191076**
include both earlier banks and all five unresolved calls exactly once. The full
design commitment is at most **$0.08563876**; the sublimit envelope is
**$0.09191076**, both within the existing **$0.60** ceiling. No reserve is released
because a provider page generally says errors are unbilled; the original
prospective conservative accounting remains intact.

Use the same authorized key, at least 60 seconds between dispatches, one collector
and no retry, resume or fallback. Endpoint/price/cap/credit checks occur before any
new generation. A provider error retains its reserve and terminates this study;
it does not grant authorization to repeat an admitted request. Preserve charges
for paid responses without a local score as missing outcomes. A separate fixed
study claim prevents duplicate launches under another output directory.

The funded config must reference the closed contract diagnostic's analysis;
its cumulative commitment already includes the earlier recovery pilot, so do not
add that pilot twice. The freeze binds this report/hash, the exact new packet,
a clean committed source, authorization text and all settings before generation.
The previous source is archived unchanged as inert evidence.

## Commands and delivery

```bash
uv run python scripts/prepare_repair_contract_probe.py plan --study repair-contract-deepinfra-v1 --prior-commitment 0.01191076 --output runs/repair-contract-deepinfra-packet.json
uv run python scripts/collect_repair_contract_probe.py freeze --input runs/repair-contract-deepinfra-packet.json --config runs/repair-contract-deepinfra-funded.json --output runs/repair-contract-deepinfra-freeze.json
# Only once after the freeze; supply the credential privately via environment.
uv run python scripts/collect_repair_contract_probe.py live --input runs/repair-contract-deepinfra-freeze.json --output runs/repair-contract-deepinfra
# Only after a terminal completion or interruption:
uv run python scripts/report_repair_contract_probe.py --input runs/repair-contract-deepinfra --output runs/repair-contract-deepinfra-report --export-evidence
```

Audit every payload, receipt, token/cost bound and verifier attachment. Reproduce
the complete report after isolated archive extraction and preserve all missing
cells. Keep the original studies and manuscripts unchanged. Update draft PR 20,
run repository checks and verify exact-commit CI. Even a useful format would need
new recovery data and replicated action complementarity before selector fitting;
this study neither fits nor validates that selector.
