"""Tests for reasoning_trace.py — trace appending, updating, and summarising."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agent_workflow.instrumentation.reasoning_trace import (
    ReasoningEntry,
    ReasoningTracer,
    collect_all_traces,
    summarize_all_traces,
)


def _entry(step: int, agent_id: str = "agent_0", **kwargs) -> ReasoningEntry:
    return ReasoningEntry(
        step_index=step,
        timestamp=datetime.now(timezone.utc).isoformat(),
        agent_id=agent_id,
        **kwargs,
    )


@pytest.fixture
def tracer(tmp_path):
    return ReasoningTracer(tmp_path / "reasoning", "agent_0")


class TestReasoningTracer:
    def test_append_creates_file(self, tracer):
        tracer.append(_entry(0))
        assert (tracer.reasoning_dir / "trace.jsonl").exists()

    def test_read_all_empty(self, tracer):
        assert tracer.read_all() == []

    def test_append_and_read(self, tracer):
        tracer.append(_entry(0, hypothesis="test A"))
        tracer.append(_entry(1, hypothesis="test B"))
        entries = tracer.read_all()
        assert len(entries) == 2
        assert entries[0].hypothesis == "test A"
        assert entries[1].hypothesis == "test B"

    def test_update_step_modifies_last_matching(self, tracer):
        tracer.append(_entry(0, hypothesis="H0"))
        tracer.append(_entry(1, hypothesis="H1"))
        tracer.update_step(0, confirmed="confirmed", val_bpb_after=1.23)
        entries = tracer.read_all()
        step0 = next(e for e in entries if e.step_index == 0)
        assert step0.confirmed == "confirmed"
        assert step0.val_bpb_after == pytest.approx(1.23)

    def test_update_step_does_not_affect_other_steps(self, tracer):
        tracer.append(_entry(0))
        tracer.append(_entry(1, confirmed="confirmed"))
        tracer.update_step(0, confirmed="falsified")
        entries = tracer.read_all()
        step1 = next(e for e in entries if e.step_index == 1)
        assert step1.confirmed == "confirmed"  # unchanged

    def test_update_nonexistent_step_is_noop(self, tracer):
        tracer.append(_entry(0))
        tracer.update_step(99, confirmed="crash")  # should not raise
        entries = tracer.read_all()
        assert len(entries) == 1

    def test_confirmed_steps_filter(self, tracer):
        tracer.append(_entry(0, confirmed="confirmed"))
        tracer.append(_entry(1, confirmed="falsified"))
        tracer.append(_entry(2, confirmed="confirmed"))
        assert len(tracer.confirmed_steps()) == 2

    def test_falsified_steps_filter(self, tracer):
        tracer.append(_entry(0, confirmed="falsified"))
        tracer.append(_entry(1, confirmed="confirmed"))
        assert len(tracer.falsified_steps()) == 1

    def test_summarize_counts(self, tracer):
        tracer.append(_entry(0, confirmed="confirmed", val_bpb_after=1.3))
        tracer.append(_entry(1, confirmed="falsified", val_bpb_after=1.4))
        tracer.append(_entry(2, confirmed="crash"))
        summary = tracer.summarize()
        assert summary["total_steps"] == 3
        assert summary["confirmed_hypotheses"] == 1
        assert summary["falsified_hypotheses"] == 1
        assert summary["crashes"] == 1

    def test_summarize_best_bpb(self, tracer):
        for i, bpb in enumerate([1.4, 1.2, 1.3]):
            tracer.append(_entry(i, val_bpb_after=bpb))
        summary = tracer.summarize()
        assert summary["best_val_bpb"] == pytest.approx(1.2)

    def test_summarize_empty(self, tracer):
        summary = tracer.summarize()
        assert summary["total_steps"] == 0


class TestCollectAndSummarise:
    def _make_agent_trace(self, mode_dir: Path, agent_id: str, entries: list):
        agent_dir = mode_dir / agent_id
        (agent_dir / "reasoning").mkdir(parents=True)
        trace_path = agent_dir / "reasoning" / "trace.jsonl"
        with open(trace_path, "w") as f:
            for e in entries:
                f.write(json.dumps(e.to_dict()) + "\n")

    def test_collect_all_traces(self, tmp_path):
        exp_dir = tmp_path / "exp"
        mode_dir = exp_dir / "mode_parallel"
        self._make_agent_trace(mode_dir, "agent_0", [
            _entry(0, agent_id="agent_0", confirmed="confirmed", hypothesis="H1"),
        ])
        self._make_agent_trace(mode_dir, "agent_1", [
            _entry(0, agent_id="agent_1", confirmed="falsified", hypothesis="H2"),
        ])
        traces = collect_all_traces(exp_dir, "parallel")
        assert "agent_0" in traces
        assert "agent_1" in traces
        assert traces["agent_0"][0].hypothesis == "H1"

    def test_collect_missing_agent_returns_empty(self, tmp_path):
        exp_dir = tmp_path / "exp"
        (exp_dir / "mode_parallel").mkdir(parents=True)
        traces = collect_all_traces(exp_dir, "parallel")
        assert traces == {}

    def test_summarize_finds_independently_confirmed(self, tmp_path):
        exp_dir = tmp_path / "exp"
        mode_dir = exp_dir / "mode_parallel"
        self._make_agent_trace(mode_dir, "agent_0", [
            _entry(0, agent_id="agent_0", confirmed="confirmed", hypothesis="lower LR"),
        ])
        self._make_agent_trace(mode_dir, "agent_1", [
            _entry(0, agent_id="agent_1", confirmed="confirmed", hypothesis="lower LR"),
        ])
        traces = collect_all_traces(exp_dir, "parallel")
        summary = summarize_all_traces(traces)
        independently = summary["independently_confirmed_hypotheses"]
        assert any(x["hypothesis"] == "lower LR" for x in independently)
