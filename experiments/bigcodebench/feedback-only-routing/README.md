# Feedback-only fixed-policy evaluation

Stage 1 is complete: **157 task clusters, 628/628 policy outcomes, 1,492 model
responses**, no missing outcomes or uncertain charges. Known collection cost is
**$0.38896675**, within the amended $4.00 cap and separate $5 authorization.
Read the [audited report and figures](results/fixed-policies-20261022/report.md).

The prespecified primary comparison, immediate 27B escalation minus repeated
9B, is **−2.55 pp**, 95% paired task-bootstrap interval **[−7.01, +1.27]**:
98 versus 102 tasks solved. The gate does not pass. Delayed escalation solves
105, direct 27B 100; all three adjusted secondary intervals include zero.
No selector was trained and no favorable secondary is promoted to primary.

Lower mean API spend under escalation does not establish equal-quality savings:
the conservative reservation rule often disallows another 27B call with most
of the $0.006 task cap unused. Public false positives also stop recovery early.
The [research note](../../../docs/blog/feedback-only-escalation.md) explains both.

After the freeze, [one human-requested descriptive look](INTERIM-DISCLOSURE.md)
used the 83 tasks then complete under all policies. Its completion bias and
immutable prefix are preserved; no fitting, stopping or experimental change
followed. The initial funding preflight admitted no model requests.
The [prospective protocol](PROTOCOL.md) fixes 157 previously unqueried,
reference-audited BigCodeBench tasks and one replicate per task. All four
policies receive only public feedback; compare repeated 9B, immediate 27B
escalation, delayed escalation and direct 27B at one API-dollar admission cap.

The exact task/qualification manifest is [data/manifest.json](data/manifest.json).
Full-suite data are evaluation only. They must never be added to solver prompts.
The filtered subset is not the full BigCodeBench benchmark. The completed MBPP+
and HumanEval+ banks remain development evidence and are not recycled here.

Preparation and reference verification are offline. The collector defaults to a
plan, requires a clean committed source freeze before `--execute`, and never
automatically resumes. A key is accepted only via an un-echoed stdin pipe.

```bash
.venv/bin/python scripts/run_feedback_routing.py \
  --config experiments/bigcodebench/feedback-only-routing/configs/evaluation.json
```

The collector is finished and must not be restarted. These 157 observed tasks
are now development evidence for any later design. No further paid collection
or selector is authorized by this completed protocol.

Reproduce the complete published artifact without credentials, model calls,
candidate execution, optional EvalPlus or the original machine:

```bash
uv run python scripts/verify_feedback_evidence.py \
  --input experiments/bigcodebench/feedback-only-routing/results/fixed-policies-20261022
```

The final offline repeat checked every response: 29 format errors reproduced,
1,463 public checks and all 326 originally executed full-suite checks repeated
under the frozen sandbox and seed, with zero pass/fail discrepancies. This is
a diagnostic; original labels remain primary, and benchmark tests are not a
complete semantic specification. The saved-data audit above executes no code.

To reproduce qualification, `scripts/prepare_feedback_routing.py` defaults to
printing the pinned download URL and SHA-256. Supply that verified Parquet with
`--parquet PATH --output NEW_DIRECTORY` to execute reference checks in the
sandbox. This needs EvalPlus 0.3.1, pandas and a Parquet engine such as pyarrow;
no API key or model is involved. The original two-seed qualification audit and
all exclusions are retained, rather than silently repaired.

`scripts/report_feedback_routing.py` publishes an audited ended bank, raw receipts,
inert frozen-source snapshots, task-level statistics and PNG/SVG figures. It
refuses an active collection. The collector source/protocol hashes stay fixed
while offline reporting is developed; its actual commit is in each run manifest.

Dataset: [BigCodeBench v0.1.4](https://huggingface.co/datasets/bigcode/bigcodebench),
Apache 2.0, original authors of [BigCodeBench](https://arxiv.org/abs/2406.15877).
Source revision and raw download checksum are pinned in the protocol. See
`data/LICENSE.dataset` for the dataset license.
