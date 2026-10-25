"""Audit frozen held-out recovery data and replay its finite budgeted policy bank.

Public CLI facade; implementation lives in vao.analysis.analyze_recovery_validation.
"""

from vao.analysis.analyze_recovery_validation import *  # Retain the published audit API.


if __name__ == "__main__":
    main()
