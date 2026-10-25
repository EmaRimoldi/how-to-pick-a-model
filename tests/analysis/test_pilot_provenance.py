"""Moving the retired pilot must preserve its receipts, exclusions and frozen audit."""

import hashlib
import json
from pathlib import Path

from vao.analysis.analyze_continuation_pilot import audit
from vao.analysis.verify_feedback_evidence import equivalent


def test_archived_pilot_remains_auditable_without_a_standalone_experiment():
    root = Path(__file__).resolve().parents[2] / "experiments/humaneval-plus/context-value/provenance/continuation-pilot"
    checksums = json.loads((root / "checksums.json").read_text())
    assert {path.name for path in root.iterdir()} == set(checksums) | {"README.md", "checksums.json"}
    for name, digest in checksums.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    manifest = json.loads((root / "manifest.json").read_text())
    assert len(set(manifest["task_ids"])) == 24
    assert json.loads((root / "config.json").read_text()) == manifest["config"]
    report = audit(root)
    equivalent(report, json.loads((root / "audit.json").read_text()))
    assert report["model_calls"] == 88 and report["receipts_reconciled"]
