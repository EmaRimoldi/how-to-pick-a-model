from __future__ import annotations

import math

from vao.estimators import gain, jsd, productive_mode_proxy, routing_regret
from vao.taxonomy import MODES


def test_gain_and_regret() -> None:
    gains = {mode: 0.0 for mode in MODES}
    gains["indexing"] = gain(1.0, 0.7, True, -1.0)
    gains["topk"] = gain(1.0, math.inf, False, -1.0)
    assert gains["indexing"] > 0
    assert gains["topk"] == -1.0
    assert routing_regret(gains, "layout") == gains["indexing"] - gains["layout"]


def test_productive_mode_proxy_and_jsd() -> None:
    gains = {mode: -1.0 for mode in MODES}
    gains["caching"] = 2.0
    pstar = productive_mode_proxy(gains)
    assert pstar["caching"] == 1.0
    uniform = {mode: 1 / 6 for mode in MODES}
    assert jsd(uniform, pstar) >= 0
