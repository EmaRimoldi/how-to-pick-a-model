"""Compatibility exports for the canonical swarm blackboard.

The implementation lives in :mod:`agent_workflow.communication.blackboard`.
This module remains so older swarm imports and copied workspace tools continue
to resolve without carrying a second blackboard implementation.
"""

from agent_workflow.communication.blackboard import (
    DEFAULT_CLAIM_TTL,
    DUPLICATE_THRESHOLD,
    ENTRY_BEST,
    ENTRY_CLAIM,
    ENTRY_CLAIM_RELEASE,
    ENTRY_HYPOTHESIS,
    ENTRY_INSIGHT,
    ENTRY_RESULT,
    ENTRY_STATUS,
    SharedMemory,
)

__all__ = [
    "DEFAULT_CLAIM_TTL",
    "DUPLICATE_THRESHOLD",
    "ENTRY_BEST",
    "ENTRY_CLAIM",
    "ENTRY_CLAIM_RELEASE",
    "ENTRY_HYPOTHESIS",
    "ENTRY_INSIGHT",
    "ENTRY_RESULT",
    "ENTRY_STATUS",
    "SharedMemory",
]
