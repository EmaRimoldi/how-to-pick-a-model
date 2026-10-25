"""Tests for log_parser.py."""

import tempfile
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agent_workflow.utils.log_parser import (
    parse_val_bpb,
    parse_training_seconds,
    parse_total_seconds,
    parse_total_steps,
    parse_evaluator_mode,
    parse_train_time_budget,
    parse_train_max_steps,
    parse_peak_vram_mb,
    training_completed,
    training_crashed,
)

REAL_LOG = """\
step 00349 (99.7%) | loss: 1.345678 | lrm: 0.50 | dt: 142ms | tok/sec: 182,000 | mfu: 39.1% | epoch: 1 | remaining: 1s
---
val_bpb:          1.102075
training_seconds: 300.1
total_seconds:    325.9
peak_vram_mb:     45060.2
mfu_percent:      39.80
total_tokens_M:   499.6
num_steps:        350
num_params_M:     50.3
depth:            12
total_steps:       1170
evaluator_mode:    fixed_steps
train_time_budget: 300
train_max_steps:   1170
"""

CRASH_LOG = """\
step 00010 (2.8%) | loss: 14.000000 ...
FAIL: NaN loss detected at step 10
Traceback (most recent call last):
  ...RuntimeError: NaN detected
"""

EMPTY_LOG = ""


def test_parse_val_bpb_from_real_log():
    with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
        f.write(REAL_LOG)
        path = Path(f.name)
    try:
        result = parse_val_bpb(path)
        assert result is not None
        assert abs(result - 1.102075) < 1e-6
    finally:
        path.unlink()


def test_parse_training_seconds():
    with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
        f.write(REAL_LOG)
        path = Path(f.name)
    try:
        result = parse_training_seconds(path)
        assert result == pytest.approx(300.1)
    finally:
        path.unlink()


def test_parse_fixed_step_evaluator_metrics():
    with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
        f.write(REAL_LOG)
        path = Path(f.name)
    try:
        assert parse_total_seconds(path) == pytest.approx(325.9)
        assert parse_total_steps(path) == 1170
        assert parse_evaluator_mode(path) == "fixed_steps"
        assert parse_train_time_budget(path) == 300
        assert parse_train_max_steps(path) == 1170
    finally:
        path.unlink()


def test_parse_peak_vram_mb():
    with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
        f.write(REAL_LOG)
        path = Path(f.name)
    try:
        result = parse_peak_vram_mb(path)
        assert result == pytest.approx(45060.2)
    finally:
        path.unlink()


def test_returns_none_on_crash_log():
    with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
        f.write(CRASH_LOG)
        path = Path(f.name)
    try:
        assert parse_val_bpb(path) is None
        assert training_crashed(path) is True
        assert training_completed(path) is False
    finally:
        path.unlink()


def test_returns_none_on_empty_file():
    with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
        f.write(EMPTY_LOG)
        path = Path(f.name)
    try:
        assert parse_val_bpb(path) is None
        assert training_completed(path) is False
        # Empty file is not a crash — no content to indicate failure
        assert training_crashed(path) is False
    finally:
        path.unlink()


def test_returns_none_on_missing_file():
    path = Path("/tmp/definitely_does_not_exist_12345.log")
    assert parse_val_bpb(path) is None
    assert parse_training_seconds(path) is None
    assert parse_peak_vram_mb(path) is None
    assert training_completed(path) is False
    assert training_crashed(path) is False


def test_training_completed_requires_val_bpb():
    with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
        f.write("step 0001 (0.1%) | loss: 2.0\n")
        path = Path(f.name)
    try:
        assert training_completed(path) is False
    finally:
        path.unlink()
