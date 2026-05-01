from __future__ import annotations

import pandas as pd

from vao.analysis.oracle_family_latent_modes import _farthest_point_selection


def test_farthest_point_selection_prefers_separated_families() -> None:
    distances = pd.DataFrame(
        [
            [0.0, 1.0, 8.0, 7.0],
            [1.0, 0.0, 7.5, 6.5],
            [8.0, 7.5, 0.0, 2.0],
            [7.0, 6.5, 2.0, 0.0],
        ],
        index=["a", "b", "c", "d"],
        columns=["a", "b", "c", "d"],
    )

    selected = _farthest_point_selection(distances, k=3)

    assert len(selected) == 3
    assert "a" in selected or "b" in selected
    assert "c" in selected or "d" in selected
