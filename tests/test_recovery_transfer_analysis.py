from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


def analyzer():
    spec = importlib.util.spec_from_file_location("transfer_analysis", Path("scripts/analyze_recovery_transfer.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_interval_clusters_tasks_and_is_reproducible():
    a = analyzer()
    values = [0, .5, -.5, 1]
    assert a.interval(values) == a.interval(values)
    assert a.interval(values)["estimate"] == pytest.approx(.25)
    ordinary, corrected = a.interval(values), a.interval(values, .05/8)
    assert corrected["low"] <= ordinary["low"] <= ordinary["high"] <= corrected["high"]


def test_variance_diagnostic_does_not_clip_negative_noise_estimates():
    a = analyzer()
    # Observed per-task sample means vary, despite a negative noise-corrected variance.
    draws = np.array([[1,0,-1], [0,-1,1], [1,1,-1]], dtype=float)
    assert a.variance_stat(draws) < 0
    constant = np.ones((10,3))
    assert a.variance_stat(constant) == pytest.approx(0)


def test_frozen_comparison_tolerates_roundoff_but_rejects_material_changes():
    a = analyzer()
    assert a.same({"coefficient": [.1]}, {"coefficient": [.1+1e-14]})
    assert not a.same({"coefficient": [.1]}, {"coefficient": [.11]})
    assert not a.same({"coefficient": [.1]}, {"different": [.1]})
