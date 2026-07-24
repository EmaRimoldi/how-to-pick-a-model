import json
from pathlib import Path

from agent_workflow.cli import main as cli_main
from agent_workflow.demo import generate_demo_bundle
from agent_workflow.outputs.workflow_card import WorkflowCard


def test_generate_demo_bundle_writes_reviewable_artifacts(tmp_path: Path):
    bundle = generate_demo_bundle(
        output_dir=tmp_path,
        experiment_id="unit_demo",
    )

    assert bundle.experiment_dir == tmp_path / "experiment_unit_demo"
    assert bundle.report_html.exists()
    assert bundle.report_md.exists()
    assert bundle.workflow_card_json.exists()
    assert bundle.workflow_card_md.exists()
    assert bundle.summary_json.exists()
    assert (bundle.experiment_dir / "trajectories.csv").exists()
    assert "offline_demo_fixture" in bundle.workflow_card_json.read_text()
    assert "Fixture data only" in bundle.summary_json.read_text()
    assert "Agent Workflow Offline Demo" in bundle.report_html.read_text()


def test_demo_cli_dispatches_and_writes_bundle(tmp_path: Path):
    cli_main(
        [
            "demo",
            "--output-dir",
            str(tmp_path),
            "--experiment-id",
            "cli_demo",
        ]
    )

    report = tmp_path / "experiment_cli_demo" / "report.html"
    card = tmp_path / "experiment_cli_demo" / "workflow_card.json"
    assert report.exists()
    assert card.exists()
    assert json.loads(card.read_text())["source"] == "offline_demo_fixture"


def test_workflow_card_markdown_contains_claim_and_limitations():
    card = WorkflowCard(
        experiment_id="card_unit",
        task="toy",
        workflow="parallel_shared",
        metric="toy_loss",
        agents=[{"id": "a0", "role": "search", "model": "demo", "memory": "shared"}],
        baseline={"best_value": 1.2},
        result={"best_value": 1.0},
        claim="Shared context helped on this toy fixture.",
        evidence_level="fixture",
        limitations=["not a live run"],
        source="test",
    )

    rendered = card.to_markdown()

    assert "Shared context helped" in rendered
    assert "not a live run" in rendered
    assert "`a0`" in rendered
