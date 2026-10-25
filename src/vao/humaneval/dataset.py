from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


MODE_NAMES = ("easy", "medium", "hard")


@dataclass(frozen=True)
class DatasetBundle:
    problems: dict[str, dict[str, Any]]
    expected_outputs: dict[str, dict[str, Any]]
    dataset_hash: str
    modes: dict[str, str]
    dataset_name: str
    checker_dataset: str


def load_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def project_path(path: str | Path) -> Path:
    return Path(path)


def load_humanevalplus() -> tuple[dict[str, dict[str, Any]], dict[str, Any], str]:
    """Load HumanEval+ through EvalPlus.

    EvalPlus is used as the authoritative source because it ships the release
    metadata and the checker used later by execute.py.
    """

    from evalplus.data import get_human_eval_plus, get_human_eval_plus_hash
    from evalplus.evaluate import get_groundtruth

    problems = get_human_eval_plus()
    dataset_hash = get_human_eval_plus_hash()
    expected_outputs = get_groundtruth(problems, dataset_hash, [])
    return problems, expected_outputs, dataset_hash


def load_dataset(config: dict[str, Any]) -> DatasetBundle:
    dataset_name = config.get("dataset", "humanevalplus")
    if dataset_name != "humanevalplus":
        raise ValueError(f"Unsupported dataset {dataset_name!r}; expected 'humanevalplus'")
    problems, expected_outputs, dataset_hash = load_humanevalplus()
    checker_dataset = "humaneval"

    derived_dir = project_path(config["paths"]["derived"])
    modes = ensure_modes(
        problems=problems,
        derived_dir=derived_dir,
        proxy=config.get("mode_proxy", "ref_solution_length"),
        n_modes=int(config.get("n_modes", 3)),
        modes_filename=config.get("paths", {}).get("modes", "modes.json"),
        meta_filename=config.get("paths", {}).get("modes_meta", "modes_meta.json"),
        dataset_name=dataset_name,
    )
    return DatasetBundle(
        problems=problems,
        expected_outputs=expected_outputs,
        dataset_hash=dataset_hash,
        modes=modes,
        dataset_name=dataset_name,
        checker_dataset=checker_dataset,
    )


def metric_for_problem(problem: dict[str, Any], proxy: str) -> int:
    if proxy == "ref_solution_length":
        solution = problem.get("canonical_solution", "")
        return len(re.findall(r"\w+|[^\s\w]", solution))
    if proxy == "num_tests":
        return len(problem.get("plus_input", []))
    raise ValueError(
        f"Unsupported mode_proxy {proxy!r}; expected 'ref_solution_length' or 'num_tests'"
    )


def assign_modes(
    problems: dict[str, dict[str, Any]],
    proxy: str,
    n_modes: int,
) -> tuple[dict[str, str], dict[str, Any]]:
    if n_modes != 3:
        raise ValueError("HumanEval+ mode assignment is fixed to 3 modes")

    ranked = sorted(
        (
            metric_for_problem(problem, proxy),
            task_id,
        )
        for task_id, problem in problems.items()
    )
    n = len(ranked)
    modes: dict[str, str] = {}
    cutoffs: list[int] = []
    counts: dict[str, int] = {}

    for idx, mode_name in enumerate(MODE_NAMES):
        start = round(idx * n / n_modes)
        end = round((idx + 1) * n / n_modes)
        chunk = ranked[start:end]
        for _, task_id in chunk:
            modes[task_id] = mode_name
        counts[mode_name] = len(chunk)
        if idx < n_modes - 1 and chunk:
            cutoffs.append(chunk[-1][0])

    metadata = {
        "proxy": proxy,
        "n_modes": n_modes,
        "mode_names": list(MODE_NAMES),
        "cutoffs": cutoffs,
        "counts": counts,
        "n_problems": n,
    }
    return modes, metadata


def ensure_modes(
    problems: dict[str, dict[str, Any]],
    derived_dir: Path,
    proxy: str,
    n_modes: int,
    modes_filename: str,
    meta_filename: str,
    dataset_name: str,
) -> dict[str, str]:
    derived_dir.mkdir(parents=True, exist_ok=True)
    modes_path = derived_dir / modes_filename
    meta_path = derived_dir / meta_filename

    if modes_path.exists():
        with modes_path.open("r", encoding="utf-8") as f:
            modes = json.load(f)
        missing = set(problems) - set(modes)
        if missing:
            raise ValueError(
                f"Existing {modes_path} is missing {len(missing)} task ids; "
                "delete it intentionally to regenerate modes."
            )
        return {task_id: modes[task_id] for task_id in problems}

    modes, metadata = assign_modes(problems, proxy=proxy, n_modes=n_modes)
    metadata["dataset"] = dataset_name
    with modes_path.open("w", encoding="utf-8") as f:
        json.dump(modes, f, indent=2, sort_keys=True)
        f.write("\n")
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, sort_keys=True)
        f.write("\n")
    print(
        "Frozen modes.json "
        f"using proxy={proxy}, cutoffs={metadata['cutoffs']}, counts={metadata['counts']}"
    )
    return modes


def main() -> None:
    parser = argparse.ArgumentParser(description="Load HumanEval+ and freeze modes.")
    parser.add_argument("--config", default="experiments/humaneval-plus/qwen-model-size-frontier/configs/experiment.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    bundle = load_dataset(config)
    print(
        f"Loaded {len(bundle.problems)} {bundle.dataset_name} problems; "
        f"dataset_hash={bundle.dataset_hash}"
    )


if __name__ == "__main__":
    main()
