from __future__ import annotations

import pytest

from src import dataset
from src.models import make_completion_prompt


@pytest.mark.parametrize("name", ["mbppplus", "bbh", "unknown"])
def test_retired_dataset_is_rejected_before_loading_models_or_data(name: str) -> None:
    with pytest.raises(ValueError, match="Unsupported dataset"):
        dataset.load_dataset({"dataset": name})
    with pytest.raises(ValueError, match="Unsupported dataset"):
        make_completion_prompt({"prompt": "do not run"}, name)


def test_humaneval_bundle_keeps_verifier_and_mode_contract(tmp_path, monkeypatch) -> None:
    problems = {
        f"HumanEval/{i}": {"canonical_solution": "return " + "x + " * i + "x"}
        for i in range(3)
    }
    outputs = {task: {} for task in problems}
    monkeypatch.setattr(dataset, "load_humanevalplus", lambda: (problems, outputs, "fixture-hash"))
    bundle = dataset.load_dataset({"paths": {"derived": str(tmp_path)}})

    assert bundle.dataset_name == "humanevalplus"
    assert bundle.checker_dataset == "humaneval"
    assert bundle.dataset_hash == "fixture-hash"
    assert bundle.problems == problems
    assert bundle.expected_outputs == outputs
    assert set(bundle.modes) == set(problems)
    assert set(bundle.modes.values()) == {"easy", "medium", "hard"}
    assert make_completion_prompt({"prompt": "def add(a, b):"}) == (
        "Complete the following Python function for HumanEval. "
        "Return only Python code, with no Markdown fences or explanation.\n\n"
        "def add(a, b):"
    )
