from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

from vao.agents.base import AgentState
from vao.agents.openai_responses_adapter import OpenAIResponsesAdapter, _extract_responses_text
from vao.taxonomy import MODES
from vao.workspaces import create_step_branches


class FakeOpenAIResponsesAdapter(OpenAIResponsesAdapter):
    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__(
            model_id="gpt-5.3-codex",
            api_key="test-key",
            timeout_seconds=1,
            allow_batch_repair=False,
        )
        self.payload = payload

    def _complete(self, prompt: str, schema: dict[str, Any], max_tokens: int) -> tuple[str, dict[str, Any]]:
        return json.dumps(self.payload, sort_keys=True), {
            "transport": "openai_responses",
            "usage": {"input_tokens": 11, "output_tokens": 22},
            "model": self.model_id,
            "elapsed_wall_seconds": 0.01,
        }


def test_openai_responses_batched_structured_edits_materialize_candidates(tmp_path: Path) -> None:
    parent_source = Path("benchmarks/stateful_query_engine/solution_template.py").read_text(encoding="utf-8")
    run_dir = tmp_path / "run"
    workspace = run_dir / "workspace" / "solution.py"
    workspace.parent.mkdir(parents=True)
    workspace.write_text(parent_source, encoding="utf-8")
    branch_dirs = create_step_branches(run_dir, 0, workspace, MODES)
    adapter = FakeOpenAIResponsesAdapter(_batch_payload())

    distribution, proposals = adapter.propose_step_batch(_state(workspace, parent_source), branch_dirs)

    assert distribution.top_mode == "indexing"
    assert distribution.parsed_json["transport"] == "openai_responses"
    assert set(proposals) == set(MODES)
    for mode, proposal in proposals.items():
        assert proposal.declared_mode == mode
        assert proposal.parsed_output_json["edit_protocol"] == "structured_edits"
        assert proposal.parsed_output_json["candidate_generation"] == "batched_structured_edits"
        assert "OpenAI smoke" in Path(proposal.file_path).read_text(encoding="utf-8")


def test_openai_responses_http_body_uses_json_schema(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "model": "gpt-5.4",
                    "output_text": "{\"ok\": true}",
                    "usage": {"input_tokens": 3, "output_tokens": 4},
                }
            ).encode("utf-8")

    def fake_urlopen(request: urllib.request.Request, timeout: int) -> FakeResponse:
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))  # type: ignore[union-attr]
        captured["headers"] = dict(request.header_items())
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    adapter = OpenAIResponsesAdapter(
        model_id="gpt-5.4",
        api_key="test-key",
        reasoning_effort="medium",
        timeout_seconds=123,
    )

    text, meta = adapter._complete("prompt", {"type": "object", "properties": {}}, 99)

    assert text == "{\"ok\": true}"
    assert meta["transport"] == "openai_responses"
    assert captured["url"].endswith("/responses")
    assert captured["timeout"] == 123
    assert captured["body"]["model"] == "gpt-5.4"
    assert captured["body"]["max_output_tokens"] == 99
    assert captured["body"]["text"]["format"]["type"] == "json_schema"
    assert captured["body"]["reasoning"] == {"effort": "medium"}
    assert captured["headers"]["Authorization"] == "Bearer test-key"


def test_extract_responses_text_from_output_items() -> None:
    payload = {
        "output": [
            {
                "content": [
                    {"type": "output_text", "text": "{\"ok\":"},
                    {"type": "output_text", "text": " true}"},
                ]
            }
        ]
    }
    assert _extract_responses_text(payload) == "{\"ok\": true}"


def _state(workspace: Path, parent_source: str) -> AgentState:
    return AgentState(
        run_id="openai_test",
        profile_id="hard_optimization",
        model_id="gpt-5.3-codex",
        step=0,
        current_solution_path=workspace,
        current_solution_source=parent_source,
        visible_history=[],
        profile_summary={"profile_id": "hard_optimization"},
        residual_steps=1,
        residual_wall_seconds=300.0,
        visibility_regime="top1_only",
        metadata={},
    )


def _batch_payload() -> dict[str, Any]:
    return {
        "mode_probs": {
            "layout": 0.12,
            "indexing": 0.38,
            "topk": 0.14,
            "caching": 0.15,
            "summaries": 0.16,
            "micro": 0.05,
        },
        "mode_ranking": ["indexing", "summaries", "caching", "topk", "layout", "micro"],
        "mode_rationales": {mode: f"{mode} rationale." for mode in MODES},
        "candidates": {mode: _candidate(mode) for mode in MODES},
    }


def _candidate(mode: str) -> dict[str, Any]:
    return {
        "primary_mode": mode,
        "declared_mode": mode,
        "edit_format": "structured_edits",
        "secondary_modes": [],
        "rationale": f"Small {mode} smoke edit.",
        "target_regions": ["CandidateQueryEngine docstring"],
        "edits": [
            {
                "op": "replace_exact",
                "old": '"""Correct list-backed baseline implementation."""',
                "new": f'"""Correct list-backed baseline implementation. OpenAI smoke {mode}."""',
            }
        ],
    }
