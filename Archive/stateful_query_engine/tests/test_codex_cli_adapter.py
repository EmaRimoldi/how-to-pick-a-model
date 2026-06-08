from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from vao.agents.codex_cli_adapter import CodexCliAdapter, _parse_codex_stdout_usage


def test_codex_cli_complete_uses_output_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_which(name: str) -> str | None:
        assert name == "codex"
        return "/usr/local/bin/codex"

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        captured["timeout"] = kwargs["timeout"]
        schema_path = Path(cmd[cmd.index("--output-schema") + 1])
        output_path = Path(cmd[cmd.index("--output-last-message") + 1])
        captured["schema"] = json.loads(schema_path.read_text(encoding="utf-8"))
        output_path.write_text('{"ok": true}', encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="tokens used\n12.5\n", stderr="")

    monkeypatch.setattr("vao.agents.codex_cli_adapter.shutil.which", fake_which)
    monkeypatch.setattr("vao.agents.codex_cli_adapter.subprocess.run", fake_run)
    adapter = CodexCliAdapter(
        model_id="gpt-5.4-mini",
        timeout_seconds=123,
        reasoning_effort="medium",
        use_output_schema=True,
    )

    text, meta = adapter._complete("prompt", {"type": "object", "properties": {}}, 77)

    assert text == '{"ok": true}'
    assert meta["transport"] == "codex_cli"
    assert meta["usage"] == {"total_tokens_reported": 12.5}
    assert meta["model"] == "gpt-5.4-mini"
    assert meta["max_tokens_requested"] == 77
    assert captured["timeout"] == 123
    assert captured["schema"] == {"type": "object", "properties": {}}
    assert captured["cmd"][:2] == ["codex", "exec"]
    assert "-c" in captured["cmd"]
    assert 'model_reasoning_effort="medium"' in captured["cmd"]


def test_codex_cli_complete_uses_absolute_working_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    monkeypatch.setattr("vao.agents.codex_cli_adapter.shutil.which", lambda _: "/usr/local/bin/codex")

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        captured["cwd"] = kwargs["cwd"]
        output_path = Path(cmd[cmd.index("--output-last-message") + 1])
        output_path.write_text('{"ok": true}', encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("vao.agents.codex_cli_adapter.subprocess.run", fake_run)
    adapter = CodexCliAdapter(model_id="gpt-5.4-mini", working_dir=tmp_path)

    adapter._complete("prompt", {"type": "object"}, 10)

    cd_path = Path(captured["cmd"][captured["cmd"].index("-C") + 1])
    assert cd_path.is_absolute()
    assert cd_path == tmp_path.resolve()
    assert Path(captured["cwd"]) == tmp_path.resolve()


def test_codex_cli_complete_reports_cli_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vao.agents.codex_cli_adapter.shutil.which", lambda _: "/usr/local/bin/codex")

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="unsupported model")

    monkeypatch.setattr("vao.agents.codex_cli_adapter.subprocess.run", fake_run)
    adapter = CodexCliAdapter(model_id="gpt-5.2-codex")

    with pytest.raises(RuntimeError, match="codex_cli_failed:1:unsupported model"):
        adapter._complete("prompt", {"type": "object"}, 10)


def test_parse_codex_stdout_usage() -> None:
    assert _parse_codex_stdout_usage("tokens used\n10.033\n") == {"total_tokens_reported": 10.033}
    assert _parse_codex_stdout_usage("tokens used\nnot-a-number\n") == {"tokens_used_raw": "not-a-number"}
    assert _parse_codex_stdout_usage("no usage") == {}
