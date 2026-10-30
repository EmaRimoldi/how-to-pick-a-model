"""Finite selected-cell bounds; no collection, model calls or policy fitting.

A lower screen passes only when every binary completion of missing cells would
pass the original efficacy criteria. It never imputes outcomes or changes a
closed study's complete-bank rule. Draws are nested within predeclared bugs.
"""
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class Criteria:
    repeated_bugs: int = 3
    trace_successes_per_bug: int = 2
    net_successes: int = 4


def evaluate(cells, *, bugs, draws=4, criteria=Criteria()):
    if type(draws) is not int or draws < 2 or draws % 2:
        raise ValueError('Declare a positive even draw count')
    if not bugs or len(set(bugs)) != len(bugs):
        raise ValueError('Declare unique selected bugs')
    if any(type(v) is not int or v < 1 for v in (criteria.repeated_bugs, criteria.trace_successes_per_bug, criteria.net_successes)):
        raise ValueError('Positive integer criteria required')
    expected = {(bug, draw, arm) for bug in bugs for draw in range(draws) for arm in ('focused', 'trace')}
    if set(cells) != expected or any(v is not None and type(v) is not bool for v in cells.values()):
        raise ValueError('All preselected cells and exact booleans/unknowns required')
    def extreme(favorable):
        # All efficacy components are monotone in trace success and control failure.
        completed = {k: (v if v is not None else (k[2] == 'trace') == favorable) for k, v in cells.items()}
        repeated = sum(sum(completed[(bug,d,'trace')] for d in range(draws)) >= criteria.trace_successes_per_bug for bug in bugs)
        def net(ds):
            return sum(int(completed[(bug,d,'trace')]) - int(completed[(bug,d,'focused')]) for bug in bugs for d in ds)
        difference = net(range(draws))
        halves = [net(range(0, draws//2)), net(range(draws//2, draws))]
        passed = repeated >= criteria.repeated_bugs and difference >= criteria.net_successes and all(v > 0 for v in halves)
        return {'screen_passed':passed,'net':difference,'halves':halves,'repeated':repeated}
    lower, upper = extreme(False), extreme(True)
    n = len(bugs) * draws
    missing = sum(v is None for v in cells.values())
    return {'mode':'finite_selected_cell_completion_bounds','missing':missing,
        'bounds':[Fraction(lower['net'],n),Fraction(upper['net'],n)],
        'mean':None if missing else Fraction(lower['net'],n),
        'all_completions_pass':lower['screen_passed'],
        'no_completion_passes':not upper['screen_passed'],
        'inconclusive':not lower['screen_passed'] and upper['screen_passed'],
        'lower':lower,'upper':upper,'fit_selector':False}
