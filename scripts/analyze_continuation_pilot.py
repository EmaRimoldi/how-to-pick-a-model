"""Audit saved pilot receipts/outcomes and render an exploratory cost/success plot.

Public CLI facade; implementation lives in vao.analysis.analyze_continuation_pilot.
"""

from vao.analysis.analyze_continuation_pilot import *  # Retain the published audit API.


if __name__ == "__main__":
    main()
