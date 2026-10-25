"""Offline finite-domain development tasks and matched recovery projections.

This module has no provider, training, or Python-code execution path. Candidate
expressions are interpreted through a bounded, typed AST whitelist.
"""

from __future__ import annotations

import ast
import hashlib
import json
import operator
import random
from dataclasses import dataclass


DOMAIN = tuple((x, y) for x in range(16) for y in range(16))
MAX_CHARS = 2048
MAX_NODES = 128
MAX_DEPTH = 16
GRAMMAR = (
    "Return only one Python expression in x and y, with integer output 0..15. "
    "Allowed: integer constants 0..31; +, -, *, ^, %; parentheses; and "
    "A if C else B, where C is one integer comparison (<, <=, ==, !=, >=, >). "
    "Every % divisor must be a literal integer 1..31. No calls, imports, "
    "attributes, strings, assignments, loops or code fences. "
    f"At most {MAX_CHARS} characters, {MAX_NODES} AST nodes, depth {MAX_DEPTH}."
)
BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
          ast.BitXor: operator.xor, ast.Mod: operator.mod}
CMPOPS = {ast.Lt: operator.lt, ast.LtE: operator.le, ast.Eq: operator.eq,
          ast.NotEq: operator.ne, ast.GtE: operator.ge, ast.Gt: operator.gt}


def digest(value: object) -> str:
    """Stable content identity; never used as a predictive feature."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class Task:
    """Fully specified synthetic function, not a withheld-example guessing task."""

    modulus: int
    threshold: int
    a: int
    b: int
    c: int
    mask: int
    e: int
    f: int

    def __post_init__(self):
        bounds = ((self.modulus, 3, 9), (self.threshold, 1, self.modulus - 1),
                  (self.a, 1, 7), (self.b, 1, 7), (self.c, 0, 15),
                  (self.mask, 0, 15), (self.e, 1, 7), (self.f, 0, 15))
        if any(type(v) is not int or not lo <= v <= hi for v, lo, hi in bounds):
            raise ValueError("Invalid task parameters")

    def answer(self, x: int, y: int) -> int:
        # Independent ordinary-Python oracle, never evaluated from model text.
        if (x + y) % self.modulus < self.threshold:
            return (self.a * x + self.b * y + self.c) % 16
        return ((x ^ self.mask) + self.e * y + self.f) % 16

    @property
    def task_id(self) -> str:
        # Semantically equivalent specifications share one task/split group.
        return digest([self.answer(x, y) for x, y in DOMAIN])

    def specification(self) -> str:
        return (
            "Inputs x and y are integers from 0 through 15 inclusive. "
            f"Compute the remainder of x + y divided by {self.modulus}. "
            f"If that remainder is less than {self.threshold}, return the remainder "
            f"of ({self.a} times x plus {self.b} times y plus {self.c}) divided by 16. "
            f"Otherwise, take the bitwise XOR of x and {self.mask}, add "
            f"{self.e} times y and {self.f}, and return the remainder divided by 16."
        )

    def reference_expression(self) -> str:
        """Engineering oracle fixture; must never enter a solver payload."""
        return (f"({self.a}*x+{self.b}*y+{self.c})%16 if (x+y)%{self.modulus}"
                f"<{self.threshold} else ((x^{self.mask})+{self.e}*y+{self.f})%16")


def development_tasks(seed: int = 20261025, count: int = 8) -> list[Task]:
    """Generate only development fixtures; there is no evaluation split here."""
    if type(count) is not int or not 1 <= count <= 256:
        raise ValueError("Development count must be in 1..256")
    rng = random.Random(seed)
    tasks: dict[str, Task] = {}
    for _ in range(count * 100):
        modulus = rng.randint(3, 9)
        task = Task(modulus, rng.randrange(1, modulus), rng.randint(1, 7),
                    rng.randint(1, 7), rng.randrange(16), rng.randrange(16),
                    rng.randint(1, 7), rng.randrange(16))
        tasks.setdefault(task.task_id, task)
        if len(tasks) == count:
            return list(tasks.values())
    raise ValueError("Could not produce enough semantically unique tasks")


def parse_candidate(source: str) -> ast.AST:
    """Validate every branch before interpreting any input; never call eval/exec."""
    if not isinstance(source, str) or not source.strip() or len(source) > MAX_CHARS:
        raise ValueError("Expression must contain 1..2048 characters")
    try:
        node = ast.parse(source.strip(), mode="eval").body
    except (SyntaxError, RecursionError) as exc:
        raise ValueError("Invalid expression syntax") from exc
    if sum(1 for _ in ast.walk(node)) > MAX_NODES:
        raise ValueError("Expression exceeds AST node limit")

    def check(n: ast.AST, depth: int = 1) -> str:
        if depth > MAX_DEPTH:
            raise ValueError("Expression exceeds depth limit")
        child = lambda v: check(v, depth + 1)
        if isinstance(n, ast.Constant) and type(n.value) is int and 0 <= n.value <= 31:
            return "int"
        if isinstance(n, ast.Name) and n.id in {"x", "y"}:
            return "int"
        if isinstance(n, ast.BinOp) and type(n.op) in BINOPS:
            if child(n.left) != "int" or child(n.right) != "int":
                raise ValueError("Arithmetic requires integers")
            if isinstance(n.op, ast.Mod) and not (
                isinstance(n.right, ast.Constant) and type(n.right.value) is int
                and 1 <= n.right.value <= 31
            ):
                raise ValueError("Remainder requires a nonzero literal divisor")
            return "int"
        if isinstance(n, ast.Compare) and len(n.ops) == 1 and type(n.ops[0]) in CMPOPS:
            if child(n.left) == child(n.comparators[0]) == "int":
                return "bool"
        if isinstance(n, ast.IfExp):
            kinds = (child(n.test), child(n.body), child(n.orelse))
            if kinds == ("bool", "int", "int"):
                return "int"
        raise ValueError("Expression contains an unsupported construct or type")

    if check(node) != "int":
        raise ValueError("Expression must return an integer")
    return node


def interpret(node: ast.AST, x: int, y: int) -> int | bool:
    """Interpret a previously validated tree with bounded arithmetic."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return {"x": x, "y": y}[node.id]
    if isinstance(node, ast.BinOp):
        return BINOPS[type(node.op)](interpret(node.left, x, y), interpret(node.right, x, y))
    if isinstance(node, ast.Compare):
        return CMPOPS[type(node.ops[0])](interpret(node.left, x, y), interpret(node.comparators[0], x, y))
    if isinstance(node, ast.IfExp):
        branch = node.body if interpret(node.test, x, y) else node.orelse
        return interpret(branch, x, y)
    raise ValueError("Unsupported node")


def verify(task: Task, candidate: str) -> dict:
    """Exact acceptance over all 256 inputs; public feedback exposes one example.

    A format error is distinct from 256 semantic failures: its count is None.
    Out-of-range outputs count as failures, not silently normalized answers.
    """
    try:
        tree = parse_candidate(candidate)
    except ValueError as exc:
        return {"status": "format_error", "passed": False, "domain_size": len(DOMAIN),
                "failed_inputs": None, "first_counterexample": None, "error": str(exc)}
    failed = 0
    first = None
    for x, y in DOMAIN:
        actual, expected = interpret(tree, x, y), task.answer(x, y)
        if actual != expected:
            failed += 1
            if first is None:
                first = {"x": x, "y": y, "expected": expected, "actual": actual}
    return {"status": "pass" if failed == 0 else "semantic_failure", "passed": failed == 0,
            "domain_size": len(DOMAIN), "failed_inputs": failed,
            "first_counterexample": first, "error": None}


@dataclass(frozen=True)
class Attempt:
    """Observable candidate and known incremental API charge in nanodollars."""

    candidate: str
    cost_nanousd: int


def checkpoint(task: Task, attempts: list[Attempt], total_budget_nanousd: int) -> dict:
    """Build audited state; no outcomes from unobserved actions are invented."""
    if not attempts or type(total_budget_nanousd) is not int or total_budget_nanousd <= 0:
        raise ValueError("A checkpoint needs attempts and a positive budget")
    if any(type(a.cost_nanousd) is not int or a.cost_nanousd < 0 for a in attempts):
        raise ValueError("Charges must be nonnegative integer nanodollars")
    spent = sum(a.cost_nanousd for a in attempts)
    if spent >= total_budget_nanousd:
        raise ValueError("No remaining budget at checkpoint")
    feedback = [verify(task, a.candidate) for a in attempts]
    if any(f["passed"] for f in feedback):
        raise ValueError("A successful trajectory must stop; only failures can branch")
    baseline = {
        "specification": task.specification(), "current_candidate": attempts[-1].candidate,
        "latest_feedback": feedback[-1], "attempts_so_far": len(attempts),
        "spent_nanousd": spent, "remaining_nanousd": total_budget_nanousd - spent,
    }
    # No earlier code, counterexamples or oracle answers in the history increment.
    history = [{"status": f["status"], "failed_inputs": f["failed_inputs"],
                "cost_nanousd": a.cost_nanousd} for a, f in zip(attempts, feedback)]
    identity = {"task_id": task.task_id, "baseline": baseline, "progress_history": history}
    return {"checkpoint_id": digest(identity), **identity}


def branch_pair(state: dict) -> dict[str, dict]:
    """Two stateless request projections with identical task and latest feedback.

    Continuation preserves the current expression; restart discards it. Neither
    solver sees the earlier progress history. Metadata is not a model message.
    """
    baseline = state["baseline"]
    shared = {"specification": baseline["specification"], "feedback": baseline["latest_feedback"]}
    branches = {}
    for action in ("continue", "restart"):
        payload = dict(shared)
        if action == "continue":
            payload["current_candidate"] = baseline["current_candidate"]
        messages = [
            {"role": "system", "content": GRAMMAR + " Correct the task using the feedback. "
             "You may revise a candidate when one is provided."},
            {"role": "user", "content": json.dumps(payload, sort_keys=True)},
        ]
        branches[action] = {"checkpoint_id": state["checkpoint_id"], "action": action,
                            "remaining_nanousd": baseline["remaining_nanousd"],
                            "messages": messages, "prompt_sha256": digest(messages)}
    return branches
