from __future__ import annotations

from typing import Any


STRATEGY_ORDER = ("mode1_direct", "mode2_structured", "mode3_robust")


STRATEGY_INSTRUCTIONS = {
    "direct": (
        "Solve the task with the shortest correct implementation. Use a direct "
        "construction and avoid unnecessary abstraction."
    ),
    "structured": (
        "Before writing code, reason internally about the specification, invariants, "
        "and boundary cases. Then implement the resulting structured solution."
    ),
    "robust": (
        "Reason internally using decomposition and adversarial edge-case analysis. "
        "Check the algorithm against representative cases before finalizing it."
    ),
}


def make_strategy_prompt(
    problem: dict[str, Any],
    strategy_kind: str,
) -> str:
    if strategy_kind not in STRATEGY_INSTRUCTIONS:
        raise ValueError(f"Unknown strategy kind: {strategy_kind}")
    instruction = STRATEGY_INSTRUCTIONS[strategy_kind]
    return (
        "Complete the following Python function for HumanEval+. "
        f"{instruction} "
        "Return only executable Python code, without Markdown fences or explanation.\n\n"
        f"{problem['prompt']}"
    )

