from agent_workflow.doctor import format_checks, run_checks


def test_doctor_reports_missing_required_files(tmp_path):
    checks = run_checks(tmp_path)
    required_failures = [check for check in checks if check.required and not check.ok]

    assert required_failures
    assert "src/agent_workflow is missing" in format_checks(checks)


def test_doctor_accepts_minimal_repo_shape(tmp_path):
    (tmp_path / "src" / "agent_workflow").mkdir(parents=True)
    (tmp_path / "autoresearch").mkdir()
    (tmp_path / "autoresearch" / "train.py").write_text("", encoding="utf-8")
    (tmp_path / "autoresearch" / "program.md").write_text("", encoding="utf-8")
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "experiment.yaml").write_text("experiment_id: test\n", encoding="utf-8")

    checks = run_checks(tmp_path)
    by_name = {check.name: check for check in checks}

    assert by_name["python package"].ok
    assert by_name["autoresearch task"].ok
    assert by_name["default config"].ok
