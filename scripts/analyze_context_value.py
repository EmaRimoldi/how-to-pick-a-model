"""Audit prospective context-value records and compare matched outcomes by task cluster.

Public CLI facade; implementation lives in vao.analysis.analyze_context_value.
"""

from vao.analysis.analyze_context_value import *  # Retain the published audit API.


if __name__ == "__main__":
    main()
