"""Compatibility namespace for published ``python -m src.<module>`` commands.

Canonical implementations live in ``vao.humaneval``.
"""

from pathlib import Path

__path__.append(str(Path(__file__).parent / "vao" / "humaneval"))
