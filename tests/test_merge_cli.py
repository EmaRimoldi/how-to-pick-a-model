"""The installed merge command must use the packaged runtime and preserve options."""

import builtins
from types import SimpleNamespace

import pytest

from agent_workflow.cli import main
from agent_workflow.modes import merge


def test_merge_help_does_not_import_repository_scripts(monkeypatch, capsys):
    original = builtins.__import__

    def installed_import(name, *args, **kwargs):
        if name == "scripts" or name.startswith("scripts."):
            raise ModuleNotFoundError(name)
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", installed_import)
    with pytest.raises(SystemExit) as result:
        main(["merge", "--help"])
    assert result.value.code == 0
    assert "--evaluation-workspace" in capsys.readouterr().out


@pytest.mark.parametrize("explicit_benchmark", [False, True])
def test_merge_cli_forwards_options_to_single_runtime(tmp_path, monkeypatch, explicit_benchmark):
    from importlib.resources import files
    from pathlib import Path
    observed = {}

    class FixtureMerger:
        def __init__(self, **kwargs):
            observed.update(kwargs)

        def run(self, **kwargs):
            observed.update(kwargs)
            return SimpleNamespace(best_individual_agent="fixture", best_individual_val_bpb=1,
                                   merge_val_bpb=1, merge_won=False, delta_val_bpb=0)

    monkeypatch.setattr(merge, "MergeOrchestrator", FixtureMerger)
    args = ["merge", "--experiment-dir", str(tmp_path), "--source-mode", "parallel-shared",
            "--evaluation-workspace", str(tmp_path / "evaluation"), "--deterministic"]
    if explicit_benchmark:
        args += ["--autoresearch-dir", str(tmp_path / "benchmark")]
    main(args)
    benchmark = tmp_path / "benchmark" if explicit_benchmark else Path(str(files("autoresearch")))
    assert observed == {"experiment_dir": tmp_path, "autoresearch_dir": benchmark,
                        "mode": "parallel-shared", "evaluation_workspace": tmp_path / "evaluation",
                        "agent_based": False, "agent_model": "claude-opus-4-6"}
