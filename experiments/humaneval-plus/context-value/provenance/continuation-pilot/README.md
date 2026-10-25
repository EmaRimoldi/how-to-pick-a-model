# Initial continuation-pilot provenance

The initial 24-task development pilot is archived as a standalone experiment.
Only two initial checkpoints failed public tests; it supports no held-out
controller-gain claim. The later context-value study supersedes its prominence.

This directory retains the original configuration, manifest, task IDs/prompt
hashes, receipt/budget journals, scored observations, outcomes and summaries so
historical charges and task exclusions remain auditable. All eight data/config
files are byte-for-byte copies, indexed by `checksums.json`. No missing outcomes
or unknown charges are reclassified by this move. The full protocol, engineering
attempts and old presentation plot remain under the
[provenance tag](../../../../../docs/history-merge.md).
Dataset/task licensing is in [NOTICE.md](../../../NOTICE.md).

Read `manifest.json` for the 24 development-only task IDs; these are observed
tasks and must not be recycled as a fresh holdout. The retained `audit.json` is
a historical description, not another primary experiment or independent sample.

Audit the retained records without modifying them or contacting a provider:

```bash
uv run python - <<'PYTHON'
from pathlib import Path
from scripts.analyze_continuation_pilot import audit
print(audit(Path("experiments/humaneval-plus/context-value/provenance/continuation-pilot")))
PYTHON
```

The legacy collector and shared verification/accounting primitives remain
covered by runtime tests. This archive does not authorize resuming collection.
