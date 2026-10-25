"""Audit and analyze fixed feedback-only trajectories without making model calls.

Public CLI facade; implementation lives in vao.analysis.analyze_feedback_routing.
"""

from vao.analysis.analyze_feedback_routing import *  # Retain the published audit API.


if __name__ == "__main__":
    main()
