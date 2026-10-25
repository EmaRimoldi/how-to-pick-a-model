"""Entry point: parse args, pick mode, run experiment."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from agent_workflow.config import AgentConfig, ExperimentConfig
from agent_workflow.experiment_modes.parallel_shared_memory import run_parallel_shared_memory
from agent_workflow.experiment_modes.parallel_two_agents import run_parallel_experiment
from agent_workflow.experiment_modes.single_agent_memory import run_single_agent_memory
from agent_workflow.experiment_modes.single_agent_double_budget import run_single_long_experiment
from agent_workflow.outputs.reporter import write_final_comparison


def _repo_root() -> Path:
    return Path(__file__).parents[2]  # src/ → repo root


def _load_prompt(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text()


def _render_prompt(
    prompt: str,
    train_budget_seconds: int,
    slurm_enabled: bool,
    train_max_steps: int | None = None,
    evaluator_concurrency: str = "parallel",
    target_val_bpb: float | None = None,
) -> str:
    train_min = max(1, train_budget_seconds // 60)
    compute_device = "GPU" if slurm_enabled else "CPU worker"
    resource_metric = "VRAM" if slurm_enabled else "memory"
    if train_max_steps is None:
        evaluator_budget_description = (
            f"time-based: {train_budget_seconds}s training budget"
        )
    else:
        evaluator_budget_description = (
            f"fixed-step: exactly {train_max_steps} gradient updates "
            f"with a {train_budget_seconds}s timeout"
        )
    target_text = "not preset" if target_val_bpb is None else f"{target_val_bpb:.6f}"
    return (
        prompt.replace("{{TRAIN_TIME_BUDGET_MIN}}", str(train_min))
        .replace("{{COMPUTE_DEVICE}}", compute_device)
        .replace("{{RESOURCE_METRIC}}", resource_metric)
        .replace("{{EVALUATOR_BUDGET_DESCRIPTION}}", evaluator_budget_description)
        .replace("{{TRAIN_MAX_STEPS}}", str(train_max_steps or "none"))
        .replace("{{EVALUATOR_CONCURRENCY}}", evaluator_concurrency)
        .replace("{{TARGET_VAL_BPB}}", target_text)
    )


def _make_experiment_id(prefix: str = "exp") -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def _coerce_config_for_mode(
    config: ExperimentConfig,
    mode: str,
    n_agents: int | None = None,
) -> ExperimentConfig:
    """Normalize a loaded YAML config to the command's target mode."""
    prompt = config.agents[0] if config.agents else AgentConfig(agent_id="agent_0")

    if mode in {"single_long", "single_memory"}:
        config.mode = mode
        source = config.agents[0] if config.agents else prompt
        config.agents = [
            AgentConfig(
                agent_id=source.agent_id,
                role=source.role,
                time_budget_minutes=source.time_budget_minutes,
                train_time_budget_seconds=source.train_time_budget_seconds,
                train_max_steps=source.train_max_steps,
                cuda_device=source.cuda_device,
                model=source.model,
                temperature=source.temperature,
                use_external_memory=(source.use_external_memory or mode == "single_memory"),
                use_shared_memory=False,
                system_prompt_file=source.system_prompt_file,
                first_message_file=source.first_message_file,
            )
        ]
        return config

    desired_n = n_agents or max(len(config.agents), 2)
    if desired_n < 1:
        raise ValueError("--n-agents must be at least 1")
    existing = list(config.agents)
    if not existing:
        existing = [prompt]
    config.mode = mode
    agents: list[AgentConfig] = []
    for index in range(desired_n):
        source = existing[index] if index < len(existing) else prompt
        agents.append(
            AgentConfig(
                agent_id=source.agent_id if index < len(existing) else f"agent_{index}",
                role=source.role,
                time_budget_minutes=source.time_budget_minutes,
                train_time_budget_seconds=source.train_time_budget_seconds,
                train_max_steps=source.train_max_steps,
                cuda_device=source.cuda_device if index < len(existing) else str(index),
                model=source.model,
                temperature=source.temperature,
                use_external_memory=source.use_external_memory,
                use_shared_memory=(mode == "parallel_shared"),
                system_prompt_file=source.system_prompt_file,
                first_message_file=source.first_message_file,
            )
        )
    config.agents = agents
    return config


def _parse_csv(value: str | None) -> list[str] | None:
    if value is None:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


def _add_agent_selection_args(parser: argparse.ArgumentParser, include_n: bool) -> None:
    if include_n:
        parser.add_argument(
            "--n-agents",
            type=int,
            default=None,
            help="Number of parallel agents to spawn.",
        )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Claude model for every agent; overrides config and roster models when set.",
    )
    parser.add_argument(
        "--cuda-devices",
        type=str,
        default=None,
        help="Comma-separated CUDA devices assigned by agent order, e.g. 0,1,2.",
    )


def _apply_budget_args(config: ExperimentConfig, args) -> None:
    if getattr(args, "time_budget", None) is not None:
        config.base_time_budget_minutes = args.time_budget
        for agent in config.agents:
            agent.time_budget_minutes = args.time_budget
    if getattr(args, "train_budget", None) is not None:
        config.train_time_budget_seconds = args.train_budget
        for agent in config.agents:
            agent.train_time_budget_seconds = args.train_budget


def _apply_agent_selection_args(config: ExperimentConfig, args) -> None:
    if getattr(args, "model", None):
        for agent in config.agents:
            agent.model = args.model
    devices = _parse_csv(getattr(args, "cuda_devices", None))
    if devices is not None:
        if len(devices) < len(config.agents):
            raise ValueError(
                f"--cuda-devices requires at least {len(config.agents)} entries "
                f"for this run (got {len(devices)})"
            )
        for index, agent in enumerate(config.agents):
            agent.cuda_device = devices[index]


def _add_reviewer_grade_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--train-max-steps",
        type=int,
        default=None,
        help="Use fixed-step evaluation by setting AUTOSEARCH_MAX_STEPS.",
    )
    parser.add_argument(
        "--serialized-evaluator",
        action="store_true",
        help="Serialize train.py evaluations across agents with a shared lock.",
    )
    parser.add_argument(
        "--target-val-bpb",
        type=float,
        default=None,
        help="Pre-registered success threshold q* for certified-time analysis.",
    )
    parser.add_argument(
        "--success-confidence",
        type=float,
        default=None,
        help="Certified success confidence 1-delta for downstream analysis.",
    )


def _apply_reviewer_grade_args(config: ExperimentConfig, args) -> None:
    if args.train_max_steps is not None:
        config.train_max_steps = args.train_max_steps
        for agent in config.agents:
            agent.train_max_steps = args.train_max_steps
    if args.serialized_evaluator:
        config.evaluator_concurrency = "serialized"
    if args.target_val_bpb is not None:
        config.target_val_bpb = args.target_val_bpb
    if args.success_confidence is not None:
        config.success_confidence = args.success_confidence


def _render_prompts(repo_root: Path, config: ExperimentConfig) -> tuple[str, str]:
    system_prompt = _render_prompt(
        _load_prompt(repo_root / config.system_prompt_file),
        config.train_time_budget_seconds,
        config.slurm_enabled,
        train_max_steps=config.train_max_steps,
        evaluator_concurrency=config.evaluator_concurrency,
        target_val_bpb=config.target_val_bpb,
    )
    first_message_tmpl = _render_prompt(
        _load_prompt(repo_root / config.first_message_file),
        config.train_time_budget_seconds,
        config.slurm_enabled,
        train_max_steps=config.train_max_steps,
        evaluator_concurrency=config.evaluator_concurrency,
        target_val_bpb=config.target_val_bpb,
    )
    return system_prompt, first_message_tmpl


def main_parallel(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Run parallel-agent experiment (Mode 1)")
    parser.add_argument("--config", type=str, default=None,
                        help="Path to experiment.yaml. Command-line flags override it when provided.")
    parser.add_argument("--time-budget", type=int, default=None, help="Budget per agent (minutes)")
    parser.add_argument("--train-budget", type=int, default=None, help="Budget per training run (seconds)")
    _add_agent_selection_args(parser, include_n=True)
    parser.add_argument("--experiment-id", type=str, default=None)
    parser.add_argument("--runs-dir", type=str, default="runs")
    _add_reviewer_grade_args(parser)
    args = parser.parse_args(argv)

    repo_root = _repo_root()

    if args.config:
        config = ExperimentConfig.from_yaml(Path(args.config), repo_root=str(repo_root))
        if args.experiment_id is not None:
            config.experiment_id = args.experiment_id
        if args.time_budget is not None:
            config.base_time_budget_minutes = args.time_budget
        if args.train_budget is not None:
            config.train_time_budget_seconds = args.train_budget
        config = _coerce_config_for_mode(config, "parallel", n_agents=args.n_agents)
    else:
        experiment_id = args.experiment_id or _make_experiment_id("parallel")
        config = ExperimentConfig.make_n_parallel(
            experiment_id=experiment_id,
            n_agents=args.n_agents or 2,
            time_budget_minutes=args.time_budget or 30,
            train_time_budget_seconds=args.train_budget or 300,
            repo_root=str(repo_root),
            cuda_devices=_parse_csv(args.cuda_devices),
            train_max_steps=args.train_max_steps,
        )
    if args.config:
        _apply_budget_args(config, args)
    _apply_agent_selection_args(config, args)
    _apply_reviewer_grade_args(config, args)

    runs_dir = repo_root / (args.runs_dir if not args.config else "runs")
    experiment_dir = runs_dir / f"experiment_{config.experiment_id}"
    experiment_dir.mkdir(parents=True, exist_ok=True)

    system_prompt, first_message_tmpl = _render_prompts(repo_root, config)

    print(f"[launcher] Starting parallel experiment: {config.experiment_id}")
    print(f"[launcher] Agents: {len(config.agents)}  |  Budget: {config.base_time_budget_minutes} min  |  Train: {config.train_time_budget_seconds} s")
    print(f"[launcher] Evaluator: max_steps={config.train_max_steps or 'time-based'}  concurrency={config.evaluator_concurrency}  q*={config.target_val_bpb}")
    print(f"[launcher] SLURM: partition={config.slurm_partition}  gres={config.slurm_gres}  time={config.slurm_time}")
    print(f"[launcher] Output directory: {experiment_dir}")

    run_parallel_experiment(
        config=config,
        experiment_dir=experiment_dir,
        repo_root=repo_root,
        system_prompt=system_prompt,
        first_message_prompt=first_message_tmpl,
    )
    print(f"[launcher] Parallel experiment complete. Results: {experiment_dir}")


def main_parallel_shared(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Run parallel-agent experiment with shared memory")
    parser.add_argument("--config", type=str, default=None,
                        help="Path to experiment.yaml. Command-line flags override it when provided.")
    parser.add_argument("--time-budget", type=int, default=None, help="Budget per agent (minutes)")
    parser.add_argument("--train-budget", type=int, default=None, help="Budget per training run (seconds)")
    _add_agent_selection_args(parser, include_n=True)
    parser.add_argument("--experiment-id", type=str, default=None)
    parser.add_argument("--runs-dir", type=str, default="runs")
    _add_reviewer_grade_args(parser)
    args = parser.parse_args(argv)

    repo_root = _repo_root()

    if args.config:
        config = ExperimentConfig.from_yaml(Path(args.config), repo_root=str(repo_root))
        if args.experiment_id is not None:
            config.experiment_id = args.experiment_id
        if args.time_budget is not None:
            config.base_time_budget_minutes = args.time_budget
        if args.train_budget is not None:
            config.train_time_budget_seconds = args.train_budget
        config = _coerce_config_for_mode(config, "parallel_shared", n_agents=args.n_agents)
    else:
        experiment_id = args.experiment_id or _make_experiment_id("parallel_shared")
        config = ExperimentConfig.make_n_parallel(
            experiment_id=experiment_id,
            n_agents=args.n_agents or 2,
            time_budget_minutes=args.time_budget or 30,
            train_time_budget_seconds=args.train_budget or 300,
            repo_root=str(repo_root),
            cuda_devices=_parse_csv(args.cuda_devices),
            train_max_steps=args.train_max_steps,
        )
        config.mode = "parallel_shared"
        for agent in config.agents:
            agent.use_shared_memory = True
    if args.config:
        _apply_budget_args(config, args)
    _apply_agent_selection_args(config, args)
    _apply_reviewer_grade_args(config, args)

    runs_dir = repo_root / (args.runs_dir if not args.config else "runs")
    experiment_dir = runs_dir / f"experiment_{config.experiment_id}"
    experiment_dir.mkdir(parents=True, exist_ok=True)

    system_prompt, first_message_tmpl = _render_prompts(repo_root, config)

    print(f"[launcher] Starting parallel-shared experiment: {config.experiment_id}")
    print(f"[launcher] Agents: {len(config.agents)}  |  Budget: {config.base_time_budget_minutes} min  |  Train: {config.train_time_budget_seconds} s")
    print(f"[launcher] Evaluator: max_steps={config.train_max_steps or 'time-based'}  concurrency={config.evaluator_concurrency}  q*={config.target_val_bpb}")
    print(f"[launcher] SLURM: partition={config.slurm_partition}  gres={config.slurm_gres}  time={config.slurm_time}")
    print(f"[launcher] Output directory: {experiment_dir}")

    run_parallel_shared_memory(
        config=config,
        experiment_dir=experiment_dir,
        repo_root=repo_root,
        system_prompt=system_prompt,
        first_message_prompt=first_message_tmpl,
    )
    print(f"[launcher] Parallel-shared experiment complete. Results: {experiment_dir}")


def main_single_long(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Run single-agent-longer experiment (Mode 2)")
    parser.add_argument("--config", type=str, default=None,
                        help="Path to experiment.yaml. Command-line flags override it when provided.")
    parser.add_argument("--time-budget", type=int, default=None, help="Agent wall-clock budget (minutes)")
    parser.add_argument("--train-budget", type=int, default=None, help="Budget per training run (seconds)")
    _add_agent_selection_args(parser, include_n=False)
    parser.add_argument("--experiment-id", type=str, default=None)
    parser.add_argument("--runs-dir", type=str, default="runs")
    _add_reviewer_grade_args(parser)
    args = parser.parse_args(argv)

    repo_root = _repo_root()

    if args.config:
        config = ExperimentConfig.from_yaml(Path(args.config), repo_root=str(repo_root))
        if args.experiment_id is not None:
            config.experiment_id = args.experiment_id
        if args.time_budget is not None:
            config.base_time_budget_minutes = args.time_budget
        if args.train_budget is not None:
            config.train_time_budget_seconds = args.train_budget
        config = _coerce_config_for_mode(config, "single_long")
    else:
        experiment_id = args.experiment_id or _make_experiment_id("single")
        config = ExperimentConfig.make_single_long(
            experiment_id=experiment_id,
            time_budget_minutes=args.time_budget or 30,
            train_time_budget_seconds=args.train_budget or 300,
            repo_root=str(repo_root),
            train_max_steps=args.train_max_steps,
        )
    if args.config:
        _apply_budget_args(config, args)
    _apply_agent_selection_args(config, args)
    _apply_reviewer_grade_args(config, args)

    runs_dir = repo_root / (args.runs_dir if not args.config else "runs")
    experiment_dir = runs_dir / f"experiment_{config.experiment_id}"
    experiment_dir.mkdir(parents=True, exist_ok=True)

    system_prompt, first_message_tmpl = _render_prompts(repo_root, config)

    print(f"[launcher] Starting single-long experiment: {config.experiment_id}")
    print(f"[launcher] Evaluator: max_steps={config.train_max_steps or 'time-based'}  concurrency={config.evaluator_concurrency}  q*={config.target_val_bpb}")
    print(f"[launcher] Output directory: {experiment_dir}")

    run_single_long_experiment(
        config=config,
        experiment_dir=experiment_dir,
        repo_root=repo_root,
        system_prompt=system_prompt,
        first_message_prompt=first_message_tmpl,
    )
    print(f"[launcher] Single-long experiment complete. Results: {experiment_dir}")


def main_single_memory(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Run single-agent experiment with external memory")
    parser.add_argument("--config", type=str, default=None,
                        help="Path to experiment.yaml. Command-line flags override it when provided.")
    parser.add_argument("--time-budget", type=int, default=None, help="Agent wall-clock budget (minutes)")
    parser.add_argument("--train-budget", type=int, default=None, help="Budget per training run (seconds)")
    _add_agent_selection_args(parser, include_n=False)
    parser.add_argument("--experiment-id", type=str, default=None)
    parser.add_argument("--runs-dir", type=str, default="runs")
    _add_reviewer_grade_args(parser)
    args = parser.parse_args(argv)

    repo_root = _repo_root()

    if args.config:
        config = ExperimentConfig.from_yaml(Path(args.config), repo_root=str(repo_root))
        if args.experiment_id is not None:
            config.experiment_id = args.experiment_id
        if args.time_budget is not None:
            config.base_time_budget_minutes = args.time_budget
        if args.train_budget is not None:
            config.train_time_budget_seconds = args.train_budget
        config = _coerce_config_for_mode(config, "single_memory")
    else:
        experiment_id = args.experiment_id or _make_experiment_id("single_memory")
        config = ExperimentConfig.make_single_memory(
            experiment_id=experiment_id,
            time_budget_minutes=args.time_budget or 30,
            train_time_budget_seconds=args.train_budget or 300,
            repo_root=str(repo_root),
            train_max_steps=args.train_max_steps,
        )
    if args.config:
        _apply_budget_args(config, args)
    _apply_agent_selection_args(config, args)
    _apply_reviewer_grade_args(config, args)

    runs_dir = repo_root / (args.runs_dir if not args.config else "runs")
    experiment_dir = runs_dir / f"experiment_{config.experiment_id}"
    experiment_dir.mkdir(parents=True, exist_ok=True)

    system_prompt, first_message_tmpl = _render_prompts(repo_root, config)

    print(f"[launcher] Starting single-memory experiment: {config.experiment_id}")
    print(f"[launcher] Evaluator: max_steps={config.train_max_steps or 'time-based'}  concurrency={config.evaluator_concurrency}  q*={config.target_val_bpb}")
    print(f"[launcher] Output directory: {experiment_dir}")

    run_single_agent_memory(
        config=config,
        experiment_dir=experiment_dir,
        repo_root=repo_root,
        system_prompt=system_prompt,
        first_message_prompt=first_message_tmpl,
    )
    print(f"[launcher] Single-memory experiment complete. Results: {experiment_dir}")


MODES = {
    "single_long": main_single_long,
    "single_memory": main_single_memory,
    "parallel": main_parallel,
    "parallel_shared": main_parallel_shared,
}
