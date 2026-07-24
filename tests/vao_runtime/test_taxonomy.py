from __future__ import annotations

import pytest

from vao.taxonomy import MODES, normalize_mode_probs, validate_mode


def test_validate_modes() -> None:
    assert validate_mode("layout") == "layout"
    with pytest.raises(ValueError):
        validate_mode("other")


def test_normalize_mode_probs() -> None:
    probs = normalize_mode_probs({mode: 2 for mode in MODES})
    assert set(probs) == set(MODES)
    assert abs(sum(probs.values()) - 1.0) < 1e-12


def test_normalize_mode_probs_rejects_missing() -> None:
    with pytest.raises(ValueError):
        normalize_mode_probs({"layout": 1.0})
