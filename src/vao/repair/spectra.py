"""Public-test spectrum feasibility; no reference patch, model or fitted selector."""
from __future__ import annotations

from fractions import Fraction
import math
import time

from .coverage_worker import EVENT_LIMIT, LINE_LIMIT, VERSION
from .diagnostics import binding, validate_public
from .environment import canonical
from .verifier import RepairVerifier


def valid_coverage(value, files):
    if not isinstance(value, dict) or set(value) != {
            "version", "lines", "line_events", "limit_reached", "intact", "event_limit", "line_limit"}:
        return False
    if (value["version"] != VERSION or value["event_limit"] != EVENT_LIMIT
            or value["line_limit"] != LINE_LIMIT or type(value["line_events"]) is not int
            or not 0 <= value["line_events"] <= EVENT_LIMIT + 1
            or any(type(value[k]) is not bool for k in ("limit_reached", "intact"))):
        return False
    rows = value["lines"]
    if not isinstance(rows, list) or len(rows) > min(LINE_LIMIT, value["line_events"]):
        return False
    for row in rows:
        if (not isinstance(row, list) or len(row) != 2 or not isinstance(row[0], str)
                or row[0] not in files or type(row[1]) is not int
                or not 1 <= row[1] <= len(files[row[0]].splitlines())):
            return False
    if rows != [list(x) for x in sorted(set(map(tuple, rows)))]:
        return False
    return value["line_events"] <= EVENT_LIMIT or value["limit_reached"]


class CoverageVerifier(RepairVerifier):
    def coverage(self, files, entrypoint, case):
        result = self._execute(files, entrypoint, case, worker="coverage_worker.py")
        if (set(result) != {"observed", "coverage"} or not isinstance(result["observed"], dict)
                or not valid_coverage(result["coverage"], files)):
            return {"available": False, "reason": "invalid_or_failed_coverage_worker", "worker_result": result}
        data = result["coverage"]
        complete = data["intact"] and not data["limit_reached"]
        return {"available": complete, "reason": None if complete else "incomplete_coverage",
                "observed": self._observation(result["observed"]), "coverage": data}


def score(case, observed):
    if "expected" in case:
        return observed.get("status") == "returned" and canonical(observed.get("value")) == canonical(case["expected"])
    return observed == {"status": "exception", "exception": case["raises"]}


def acquire_spectrum(public, stored, verifier):
    """Keep every public case, rerun ordinary and covered calls, never retry."""
    files = public["files"]
    validate_public(public, files)
    if stored["binding"] != binding(public, files):
        raise ValueError("Archived feedback belongs to different files or tests")
    expected = stored["feedback"]["cases"]
    if [c["id"] for c in public["public_cases"]] != [r["id"] for r in expected]:
        raise ValueError("Archived feedback must cover the ordered public suite")
    start = time.monotonic()
    rows = []
    for case, old in zip(public["public_cases"], expected):
        ordinary = verifier.invoke(files, public["entrypoint"], case)
        covered = verifier.coverage(files, public["entrypoint"], case)
        rows.append({"id": case["id"], "ordinary": ordinary, "coverage_result": covered,
                     "stored_observed": old["observed"], "stored_passed": old["passed"]})
    return {"binding": stored["binding"], "cases": rows, "additional_executions": 2 * len(rows),
            "seconds": time.monotonic() - start}


def analyze_spectrum(public, acquisition):
    """Rank all observed lines, retaining exact-score ties and missing records.

    Squared Ochiai as a rational supplies an exact sort/tie key. It is not a
    calibrated probability of fault. A non-flat ranking is not localization
    accuracy, a repair benefit, or a go/no-go criterion for model collection.
    """
    files = public["files"]
    validate_public(public, files)
    cases, rows = public["public_cases"], acquisition["cases"]
    if (acquisition["binding"] != binding(public, files)
            or [r["id"] for r in rows] != [c["id"] for c in cases]):
        raise ValueError("Acquisition does not match the complete public state")
    issues, labels, spectra = [], [], []
    for case, row in zip(cases, rows):
        result = row["coverage_result"]
        ordinary = row["ordinary"]
        passed = score(case, ordinary)
        valid = (result.get("available") is True and valid_coverage(result.get("coverage"), files)
                 and result["coverage"]["intact"] and not result["coverage"]["limit_reached"]
                 and canonical(ordinary) == canonical(result.get("observed")) == canonical(row["stored_observed"])
                 and type(row["stored_passed"]) is bool and passed == row["stored_passed"])
        if not valid:
            issues.append(case["id"])
        labels.append(passed)
        spectra.append(set(map(tuple, result["coverage"]["lines"])) if valid else set())
    base = {"available": not issues, "invalid_or_mismatched_cases": issues, "public_cases": len(cases),
            "additional_executions": acquisition["additional_executions"], "seconds": acquisition["seconds"]}
    if issues:
        return {**base, "ranking": None, "metrics": None}
    failures = sum(not label for label in labels)
    grouped = {}
    for location in sorted(set().union(*spectra)):
        ef = sum(not label and location in lines for label, lines in zip(labels, spectra))
        ep = sum(label and location in lines for label, lines in zip(labels, spectra))
        squared = Fraction(ef * ef, failures * (ef + ep)) if failures else Fraction(0)
        grouped.setdefault(squared, []).append({"file": location[0], "line": location[1],
                                                "failing_covered": ef, "passing_covered": ep})
    ranking, rank = [], 1
    for squared in sorted(grouped, reverse=True):
        locations = grouped[squared]
        ranking.append({"rank_min": rank, "rank_max": rank + len(locations) - 1,
                        "ochiai": math.sqrt(float(squared)),
                        "squared_exact": [squared.numerator, squared.denominator], "locations": locations})
        rank += len(locations)
    covered = rank - 1
    top = len(ranking[0]["locations"]) if ranking else 0
    failed_lines = set().union(*(lines for label, lines in zip(labels, spectra) if not label))
    positive_groups = sum(g["squared_exact"][0] > 0 for g in ranking)
    metrics = {"passing_cases": sum(labels), "failing_cases": failures, "covered_lines": covered,
               "failing_executed_lines": len(failed_lines), "score_groups": len(ranking),
               "positive_score_groups": positive_groups, "top_tie_lines": top,
               "both_outcomes_present": 0 < failures < len(cases),
               "distinguishes_failing_executed_lines": positive_groups > 1,
               "top_tie_fraction_of_failing_executed": top / len(failed_lines) if failed_lines else None}
    return {**base, "ranking": ranking, "metrics": metrics}
