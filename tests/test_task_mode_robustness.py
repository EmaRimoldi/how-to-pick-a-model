from __future__ import annotations

from vao.analysis.task_mode_robustness import required_trials_for_wilson_half_width, wilson_interval


def test_wilson_interval_is_bounded() -> None:
    lo, hi = wilson_interval(2, 5)
    assert 0.0 <= lo <= hi <= 1.0


def test_required_trials_decreases_with_looser_half_width() -> None:
    strict = required_trials_for_wilson_half_width(0.5, 0.10)
    loose = required_trials_for_wilson_half_width(0.5, 0.20)
    assert strict >= loose
