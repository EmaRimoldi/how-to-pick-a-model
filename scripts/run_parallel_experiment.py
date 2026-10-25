#!/usr/bin/env python3
"""CLI: launch Mode 1 (2 agents × T budget)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agent_workflow.launcher import main_parallel

if __name__ == "__main__":
    main_parallel()
