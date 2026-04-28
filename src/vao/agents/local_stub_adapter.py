"""Deterministic mock backend for tests and smoke experiments."""

from __future__ import annotations

import json
from pathlib import Path

from vao.agents.base import AgentState
from vao.logging_utils import sha256_file, sha256_text
from vao.schemas import CandidateProposal, ModeDistribution
from vao.taxonomy import MODES, validate_mode


class LocalStubAdapter:
    def __init__(self, model_id: str = "local-stub-v1", **_: object) -> None:
        self.model_id = model_id

    def propose_mode_distribution(self, state: AgentState) -> ModeDistribution:
        if state.step % 2 == 0:
            probs = {
                "layout": 0.17,
                "indexing": 0.34,
                "topk": 0.11,
                "caching": 0.16,
                "summaries": 0.17,
                "micro": 0.05,
            }
        else:
            probs = {
                "layout": 0.12,
                "indexing": 0.22,
                "topk": 0.10,
                "caching": 0.31,
                "summaries": 0.20,
                "micro": 0.05,
            }
        ranking = sorted(MODES, key=lambda mode: probs[mode], reverse=True)
        parsed = {
            "mode_probs": probs,
            "mode_ranking": ranking,
            "mode_rationales": {mode: f"Stub rationale for {mode}." for mode in MODES},
        }
        raw = json.dumps(parsed, sort_keys=True)
        return ModeDistribution(raw_text=raw, parsed_json=parsed, **parsed)

    def propose_step_batch(self, state: AgentState, branch_dirs: dict[str, Path]) -> tuple[ModeDistribution, dict[str, CandidateProposal]]:
        """Deterministic batched interface used to test the orchestrator path."""
        distribution = self.propose_mode_distribution(state)
        distribution.parsed_json = {
            **(distribution.parsed_json or {}),
            "candidate_generation": "batched_local_stub",
        }
        proposals = {mode: self.propose_edit_for_mode(state, mode, branch_dirs[mode]) for mode in MODES}
        for proposal in proposals.values():
            proposal.parsed_output_json = {
                **(proposal.parsed_output_json or {}),
                "candidate_generation": "batched_local_stub",
                "batch_usage_accounted_on_distribution": True,
            }
        return distribution, proposals

    def propose_step_single(self, state: AgentState, branch_dirs: dict[str, Path]) -> tuple[ModeDistribution, CandidateProposal]:
        distribution = self.propose_mode_distribution(state)
        selected_mode = distribution.top_mode
        one_hot = {
            mode: (1.0 if mode == selected_mode else 0.0)
            for mode in MODES
        }
        single_distribution = ModeDistribution(
            mode_probs=one_hot,
            mode_ranking=[selected_mode, *[mode for mode in MODES if mode != selected_mode]],
            mode_rationales={mode: ("selected by local stub" if mode == selected_mode else "") for mode in MODES},
            raw_text=distribution.raw_text,
            parsed_json={
                **(distribution.parsed_json or {}),
                "candidate_generation": "single_local_stub",
                "selected_mode": selected_mode,
            },
        )
        proposal = self.propose_edit_for_mode(state, selected_mode, branch_dirs[selected_mode])
        proposal.parsed_output_json = {
            **(proposal.parsed_output_json or {}),
            "candidate_generation": "single_local_stub",
            "usage_accounted_on_distribution": True,
        }
        return single_distribution, proposal

    def propose_edit_for_mode(self, state: AgentState, mode: str, branch_dir: Path) -> CandidateProposal:
        validate_mode(mode)
        parent_path = branch_dir / "parent_solution.py"
        proposed_path = branch_dir / "proposed_solution.py"
        source = SOURCE_BY_MODE[mode]
        proposed_path.write_text(source, encoding="utf-8")
        parsed = {
            "mode": mode,
            "edited_file": "proposed_solution.py",
            "changed": sha256_file(parent_path) != sha256_file(proposed_path),
            "rationale": f"Deterministic {mode} candidate from local_stub.",
        }
        raw = json.dumps(parsed, sort_keys=True)
        return CandidateProposal(
            branch_index=MODES.index(mode),
            primary_mode=mode,
            secondary_modes=[],
            declared_mode=mode,
            source_hash=sha256_file(proposed_path),
            source_parent_hash=sha256_file(parent_path),
            file_path=str(proposed_path),
            raw_output_text=raw,
            parsed_output_json=parsed,
            prompt_hash=sha256_text(
                json.dumps(
                    {
                        "run_id": state.run_id,
                        "step": state.step,
                        "profile_id": state.profile_id,
                        "mode": mode,
                        "current_hash": sha256_text(state.current_solution_source),
                    },
                    sort_keys=True,
                )
            ),
            changed=bool(parsed["changed"]),
        )


class LeakageProbeAdapter(LocalStubAdapter):
    """Deterministic adapter for anti-leakage tests.

    It always routes top-1 to caching, while reusing the same candidate sources
    as the local stub. On normal workloads the indexing branch is often the best
    counterfactual, making this adapter useful for proving that promotion follows
    q_t rather than the verifier result.
    """

    def __init__(self, model_id: str = "leakage-probe-v1", **kwargs: object) -> None:
        super().__init__(model_id=model_id, **kwargs)

    def propose_mode_distribution(self, state: AgentState) -> ModeDistribution:
        probs = {
            "layout": 0.10,
            "indexing": 0.20,
            "topk": 0.05,
            "caching": 0.45,
            "summaries": 0.15,
            "micro": 0.05,
        }
        ranking = sorted(MODES, key=lambda mode: probs[mode], reverse=True)
        parsed = {
            "mode_probs": probs,
            "mode_ranking": ranking,
            "mode_rationales": {mode: f"Leakage probe rationale for {mode}." for mode in MODES},
            "visible_history_snapshot": state.visible_history,
        }
        raw = json.dumps(parsed, sort_keys=True)
        return ModeDistribution(raw_text=raw, parsed_json=parsed, **parsed)


LAYOUT_SOURCE = '''"""Layout-mode candidate: dictionary-backed point operations."""

from __future__ import annotations


class CandidateQueryEngine:
    def __init__(self, items: dict[int, int] | None = None):
        self._values: dict[int, int] = {int(key): int(value) for key, value in (items or {}).items()}

    def put(self, key: int, value: int) -> None:
        self._values[int(key)] = int(value)
        return None

    def delete(self, key: int) -> None:
        self._values.pop(int(key), None)
        return None

    def get(self, key: int) -> int | None:
        return self._values.get(int(key))

    def range_sum(self, lo: int, hi: int) -> int:
        lo = int(lo)
        hi = int(hi)
        if lo > hi:
            return 0
        return sum(value for key, value in self._values.items() if lo <= key <= hi)

    def aggregate_count(self, lo: int, hi: int) -> int:
        lo = int(lo)
        hi = int(hi)
        if lo > hi:
            return 0
        return sum(1 for key in self._values if lo <= key <= hi)

    def top_k(self, lo: int, hi: int, k: int) -> list[tuple[int, int]]:
        lo = int(lo)
        hi = int(hi)
        k = int(k)
        if lo > hi or k <= 0:
            return []
        rows = [(key, value) for key, value in self._values.items() if lo <= key <= hi]
        rows.sort(key=lambda item: (-item[1], item[0]))
        return rows[:k]
'''


INDEXING_SOURCE = '''"""Indexing-mode candidate: dictionary plus sorted-key range access."""

from __future__ import annotations

import bisect


class CandidateQueryEngine:
    def __init__(self, items: dict[int, int] | None = None):
        self._values: dict[int, int] = {int(key): int(value) for key, value in (items or {}).items()}
        self._keys: list[int] = sorted(self._values)

    def put(self, key: int, value: int) -> None:
        key = int(key)
        if key not in self._values:
            bisect.insort(self._keys, key)
        self._values[key] = int(value)
        return None

    def delete(self, key: int) -> None:
        key = int(key)
        if key not in self._values:
            return None
        del self._values[key]
        index = bisect.bisect_left(self._keys, key)
        if index < len(self._keys) and self._keys[index] == key:
            self._keys.pop(index)
        return None

    def get(self, key: int) -> int | None:
        return self._values.get(int(key))

    def range_sum(self, lo: int, hi: int) -> int:
        left, right = self._range_bounds(lo, hi)
        return sum(self._values[key] for key in self._keys[left:right])

    def aggregate_count(self, lo: int, hi: int) -> int:
        left, right = self._range_bounds(lo, hi)
        return max(0, right - left)

    def top_k(self, lo: int, hi: int, k: int) -> list[tuple[int, int]]:
        left, right = self._range_bounds(lo, hi)
        k = int(k)
        if left >= right or k <= 0:
            return []
        rows = [(key, self._values[key]) for key in self._keys[left:right]]
        rows.sort(key=lambda item: (-item[1], item[0]))
        return rows[:k]

    def _range_bounds(self, lo: int, hi: int) -> tuple[int, int]:
        lo = int(lo)
        hi = int(hi)
        if lo > hi:
            return 0, 0
        return bisect.bisect_left(self._keys, lo), bisect.bisect_right(self._keys, hi)
'''


TOPK_SOURCE = '''"""Top-k-mode candidate: list layout with heap-based top_k."""

from __future__ import annotations

import heapq


class CandidateQueryEngine:
    def __init__(self, items: dict[int, int] | None = None):
        self._items: list[tuple[int, int]] = []
        if items:
            for key, value in items.items():
                self.put(key, value)

    def put(self, key: int, value: int) -> None:
        key = int(key)
        value = int(value)
        for index, (existing_key, _) in enumerate(self._items):
            if existing_key == key:
                self._items[index] = (key, value)
                return None
        self._items.append((key, value))
        return None

    def delete(self, key: int) -> None:
        key = int(key)
        self._items = [(existing_key, value) for existing_key, value in self._items if existing_key != key]
        return None

    def get(self, key: int) -> int | None:
        key = int(key)
        for existing_key, value in self._items:
            if existing_key == key:
                return value
        return None

    def range_sum(self, lo: int, hi: int) -> int:
        lo = int(lo)
        hi = int(hi)
        if lo > hi:
            return 0
        return sum(value for key, value in self._items if lo <= key <= hi)

    def aggregate_count(self, lo: int, hi: int) -> int:
        lo = int(lo)
        hi = int(hi)
        if lo > hi:
            return 0
        return sum(1 for key, _ in self._items if lo <= key <= hi)

    def top_k(self, lo: int, hi: int, k: int) -> list[tuple[int, int]]:
        lo = int(lo)
        hi = int(hi)
        k = int(k)
        if lo > hi or k <= 0:
            return []
        rows = ((key, value) for key, value in self._items if lo <= key <= hi)
        return heapq.nsmallest(k, rows, key=lambda item: (-item[1], item[0]))
'''


CACHING_SOURCE = '''"""Caching-mode candidate: sorted index with conservative result cache."""

from __future__ import annotations

import bisect
import heapq


class CandidateQueryEngine:
    def __init__(self, items: dict[int, int] | None = None):
        self._values: dict[int, int] = {int(key): int(value) for key, value in (items or {}).items()}
        self._keys: list[int] = sorted(self._values)
        self._cache: dict[tuple, object] = {}

    def put(self, key: int, value: int) -> None:
        key = int(key)
        if key not in self._values:
            bisect.insort(self._keys, key)
        self._values[key] = int(value)
        self._cache.clear()
        return None

    def delete(self, key: int) -> None:
        key = int(key)
        if key in self._values:
            del self._values[key]
            index = bisect.bisect_left(self._keys, key)
            if index < len(self._keys) and self._keys[index] == key:
                self._keys.pop(index)
            self._cache.clear()
        return None

    def get(self, key: int) -> int | None:
        return self._values.get(int(key))

    def range_sum(self, lo: int, hi: int) -> int:
        cache_key = ("sum", int(lo), int(hi))
        if cache_key not in self._cache:
            left, right = self._range_bounds(lo, hi)
            self._cache[cache_key] = sum(self._values[key] for key in self._keys[left:right])
        return int(self._cache[cache_key])

    def aggregate_count(self, lo: int, hi: int) -> int:
        cache_key = ("count", int(lo), int(hi))
        if cache_key not in self._cache:
            left, right = self._range_bounds(lo, hi)
            self._cache[cache_key] = max(0, right - left)
        return int(self._cache[cache_key])

    def top_k(self, lo: int, hi: int, k: int) -> list[tuple[int, int]]:
        cache_key = ("top_k", int(lo), int(hi), int(k))
        if cache_key not in self._cache:
            left, right = self._range_bounds(lo, hi)
            rows = ((key, self._values[key]) for key in self._keys[left:right])
            self._cache[cache_key] = heapq.nsmallest(int(k), rows, key=lambda item: (-item[1], item[0])) if int(k) > 0 else []
        return list(self._cache[cache_key])

    def _range_bounds(self, lo: int, hi: int) -> tuple[int, int]:
        lo = int(lo)
        hi = int(hi)
        if lo > hi:
            return 0, 0
        return bisect.bisect_left(self._keys, lo), bisect.bisect_right(self._keys, hi)
'''


SUMMARIES_SOURCE = '''"""Summaries-mode candidate: sorted keys with lazily rebuilt prefix sums."""

from __future__ import annotations

import bisect
import heapq


class CandidateQueryEngine:
    def __init__(self, items: dict[int, int] | None = None):
        self._values: dict[int, int] = {int(key): int(value) for key, value in (items or {}).items()}
        self._keys: list[int] = sorted(self._values)
        self._prefix: list[int] = [0]
        self._dirty = True

    def put(self, key: int, value: int) -> None:
        key = int(key)
        if key not in self._values:
            bisect.insort(self._keys, key)
        self._values[key] = int(value)
        self._dirty = True
        return None

    def delete(self, key: int) -> None:
        key = int(key)
        if key not in self._values:
            return None
        del self._values[key]
        index = bisect.bisect_left(self._keys, key)
        if index < len(self._keys) and self._keys[index] == key:
            self._keys.pop(index)
        self._dirty = True
        return None

    def get(self, key: int) -> int | None:
        return self._values.get(int(key))

    def range_sum(self, lo: int, hi: int) -> int:
        left, right = self._range_bounds(lo, hi)
        if left >= right:
            return 0
        self._ensure_prefix()
        return self._prefix[right] - self._prefix[left]

    def aggregate_count(self, lo: int, hi: int) -> int:
        left, right = self._range_bounds(lo, hi)
        return max(0, right - left)

    def top_k(self, lo: int, hi: int, k: int) -> list[tuple[int, int]]:
        left, right = self._range_bounds(lo, hi)
        k = int(k)
        if left >= right or k <= 0:
            return []
        rows = ((key, self._values[key]) for key in self._keys[left:right])
        return heapq.nsmallest(k, rows, key=lambda item: (-item[1], item[0]))

    def _range_bounds(self, lo: int, hi: int) -> tuple[int, int]:
        lo = int(lo)
        hi = int(hi)
        if lo > hi:
            return 0, 0
        return bisect.bisect_left(self._keys, lo), bisect.bisect_right(self._keys, hi)

    def _ensure_prefix(self) -> None:
        if not self._dirty:
            return
        total = 0
        prefix = [0]
        for key in self._keys:
            total += self._values[key]
            prefix.append(total)
        self._prefix = prefix
        self._dirty = False
'''


MICRO_SOURCE = '''"""Micro-mode candidate: list baseline with local expression simplifications."""

from __future__ import annotations


class CandidateQueryEngine:
    def __init__(self, items: dict[int, int] | None = None):
        self._items: list[tuple[int, int]] = []
        for key, value in (items or {}).items():
            self.put(key, value)

    def put(self, key: int, value: int) -> None:
        key = int(key)
        value = int(value)
        for index, row in enumerate(self._items):
            if row[0] == key:
                self._items[index] = (key, value)
                return None
        self._items.append((key, value))
        return None

    def delete(self, key: int) -> None:
        key = int(key)
        self._items = [row for row in self._items if row[0] != key]
        return None

    def get(self, key: int) -> int | None:
        key = int(key)
        return next((value for existing_key, value in self._items if existing_key == key), None)

    def range_sum(self, lo: int, hi: int) -> int:
        lo = int(lo)
        hi = int(hi)
        if lo > hi:
            return 0
        return sum(value for key, value in self._items if lo <= key <= hi)

    def aggregate_count(self, lo: int, hi: int) -> int:
        lo = int(lo)
        hi = int(hi)
        if lo > hi:
            return 0
        return sum(1 for key, _ in self._items if lo <= key <= hi)

    def top_k(self, lo: int, hi: int, k: int) -> list[tuple[int, int]]:
        lo = int(lo)
        hi = int(hi)
        k = int(k)
        if lo > hi or k <= 0:
            return []
        rows = [(key, value) for key, value in self._items if lo <= key <= hi]
        return sorted(rows, key=lambda item: (-item[1], item[0]))[:k]
'''


SOURCE_BY_MODE = {
    "layout": LAYOUT_SOURCE,
    "indexing": INDEXING_SOURCE,
    "topk": TOPK_SOURCE,
    "caching": CACHING_SOURCE,
    "summaries": SUMMARIES_SOURCE,
    "micro": MICRO_SOURCE,
}
