# Feedback-only fixed-policy evaluation

Stage 1: test a useful intervention before building another selector.
Collection is active under the amended $4.00 cap; treatment analysis waits until
the collector ends, apart from [one later human-requested descriptive look](INTERIM-DISCLOSURE.md)
on the same 83 completed tasks. No repeated readout or experimental change follows
from that snapshot. The initial funding preflight admitted no model requests.
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

New authorization: maximum $5 additional; this collection is capped at $4.00,
including unknown reservations. No paid forecaster or learned selector is run.
The reference audit is preparation, **not a model evaluation result**.

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
