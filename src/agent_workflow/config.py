"""Experiment and agent configuration dataclasses."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class AgentConfig:
    """Per-agent configuration."""
    agent_id: str
    role: str = ""
    time_budget_minutes: int = 30
    train_time_budget_seconds: int = 300
    train_max_steps: Optional[int] = None
    cuda_device: str = "0"
    model: str = "claude-sonnet-4-6"
    temperature: Optional[float] = None
    use_external_memory: bool = False
    use_shared_memory: bool = False
    system_prompt_file: str = "prompts/agent_system_prompt.md"
    first_message_file: str = "prompts/agent_first_message.md"

    @classmethod
    def from_json(cls, path: Path) -> "AgentConfig":
        data = json.loads(path.read_text())
        # Map old-style fields
        if "google_model" in data:
            data.pop("google_model", None)
        if "provider" in data:
            data.pop("provider", None)
        if "thinking" in data:
            data.pop("thinking", None)
        if "prompt_file" in data:
            data.pop("prompt_file", None)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExperimentConfig:
    """Full experiment configuration."""
    experiment_id: str
    mode: str  # "parallel" | "single_long" | "parallel_capacity_benchmark" | "merge_search"
    base_time_budget_minutes: int = 30
    train_time_budget_seconds: int = 300
    train_max_steps: Optional[int] = None
    evaluator_concurrency: str = "parallel"  # "parallel" | "serialized"
    target_val_bpb: Optional[float] = None
    success_confidence: float = 0.80
    llm_token_price: float = 1.0
    evaluator_hour_price: float = 0.0
    autoresearch_dir: str = "autoresearch"
    results_root: str = "results"
    agents: list[AgentConfig] = field(default_factory=list)
    repo_root: str = ""
    # SLURM settings (threaded through to create_workspace)
    slurm_enabled: bool = True
    slurm_partition: str = "pi_tpoggio"
    slurm_gres: str = "gpu:1"
    slurm_time: str = "00:10:00"
    # Prompt file paths (relative to repo root)
    system_prompt_file: str = "prompts/agent_system_prompt.md"
    first_message_file: str = "prompts/agent_first_message.md"

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def make_parallel(
        cls,
        experiment_id: str,
        time_budget_minutes: int,
        train_time_budget_seconds: int,
        repo_root: str,
        train_max_steps: Optional[int] = None,
    ) -> "ExperimentConfig":
        agents = [
            AgentConfig(
                agent_id="agent_0",
                time_budget_minutes=time_budget_minutes,
                train_time_budget_seconds=train_time_budget_seconds,
                train_max_steps=train_max_steps,
                cuda_device="0",
            ),
            AgentConfig(
                agent_id="agent_1",
                time_budget_minutes=time_budget_minutes,
                train_time_budget_seconds=train_time_budget_seconds,
                train_max_steps=train_max_steps,
                cuda_device="1",
            ),
        ]
        return cls(
            experiment_id=experiment_id,
            mode="parallel",
            base_time_budget_minutes=time_budget_minutes,
            train_time_budget_seconds=train_time_budget_seconds,
            train_max_steps=train_max_steps,
            repo_root=repo_root,
            agents=agents,
        )

    @classmethod
    def make_n_parallel(
        cls,
        experiment_id: str,
        n_agents: int,
        time_budget_minutes: int,
        train_time_budget_seconds: int,
        repo_root: str,
        cuda_devices: Optional[list[str]] = None,
        train_max_steps: Optional[int] = None,
    ) -> "ExperimentConfig":
        """Create config for N independent parallel agents.

        If cuda_devices is not provided, agents are assigned devices 0..N-1.
        For SLURM-based training this device assignment controls CUDA_VISIBLE_DEVICES
        within each agent's environment.
        """
        if n_agents < 1:
            raise ValueError("n_agents must be at least 1")
        if cuda_devices is None:
            cuda_devices = [str(i) for i in range(n_agents)]
        if len(cuda_devices) < n_agents:
            raise ValueError(
                f"Provide at least {n_agents} CUDA device strings "
                f"(got {len(cuda_devices)})."
            )
        agents = [
            AgentConfig(
                agent_id=f"agent_{i}",
                time_budget_minutes=time_budget_minutes,
                train_time_budget_seconds=train_time_budget_seconds,
                train_max_steps=train_max_steps,
                cuda_device=cuda_devices[i],
            )
            for i in range(n_agents)
        ]
        return cls(
            experiment_id=experiment_id,
            mode="parallel",
            base_time_budget_minutes=time_budget_minutes,
            train_time_budget_seconds=train_time_budget_seconds,
            train_max_steps=train_max_steps,
            repo_root=repo_root,
            agents=agents,
        )

    @classmethod
    def make_single_long(
        cls,
        experiment_id: str,
        time_budget_minutes: int,
        train_time_budget_seconds: int,
        repo_root: str,
        train_max_steps: Optional[int] = None,
    ) -> "ExperimentConfig":
        agents = [
            AgentConfig(
                agent_id="agent_0",
                time_budget_minutes=time_budget_minutes * 2,
                train_time_budget_seconds=train_time_budget_seconds,
                train_max_steps=train_max_steps,
                cuda_device="0",
            ),
        ]
        return cls(
            experiment_id=experiment_id,
            mode="single_long",
            base_time_budget_minutes=time_budget_minutes,
            train_time_budget_seconds=train_time_budget_seconds,
            train_max_steps=train_max_steps,
            repo_root=repo_root,
            agents=agents,
        )

    @classmethod
    def make_single_memory(
        cls,
        experiment_id: str,
        time_budget_minutes: int,
        train_time_budget_seconds: int,
        repo_root: str,
        train_max_steps: Optional[int] = None,
    ) -> "ExperimentConfig":
        config = cls.make_single_long(
            experiment_id=experiment_id,
            time_budget_minutes=time_budget_minutes,
            train_time_budget_seconds=train_time_budget_seconds,
            repo_root=repo_root,
            train_max_steps=train_max_steps,
        )
        config.mode = "single_memory"
        config.agents[0].use_external_memory = True
        return config

    @classmethod
    def from_yaml(cls, path: Path, repo_root: str = "") -> "ExperimentConfig":
        """Load ExperimentConfig from an experiment.yaml file.

        The YAML schema is documented in configs/experiment.yaml.
        """
        import yaml

        raw = yaml.safe_load(path.read_text())
        exp   = raw.get("experiment", {})
        ag    = raw.get("agents", {})
        eval_ = raw.get("evaluator", {})
        slurm = raw.get("slurm", {})
        tmpl  = raw.get("prompts", {})

        mode     = exp.get("mode", "parallel")
        budget   = int(ag.get("time_budget_minutes", 30))
        train_s  = int(ag.get("train_time_budget_seconds", 300))
        train_max_steps = _optional_int(
            ag.get("train_max_steps", eval_.get("train_max_steps"))
        )
        n_agents = int(ag.get("n", 2))
        if n_agents < 1:
            raise ValueError("agents.n must be at least 1")
        model    = ag.get("model", "claude-haiku-4-5-20251001")
        temp     = ag.get("temperature", None)
        use_external_memory = bool(ag.get("use_external_memory", False))
        use_shared_memory = bool(ag.get("use_shared_memory", False))
        devices  = ag.get("cuda_devices", None)
        roster = ag.get("roster", None)
        if roster == []:
            roster = None
        overrides: dict[str, dict] = {
            o["agent_id"]: o for o in ag.get("overrides", []) if "agent_id" in o
        }

        if roster is not None:
            if not isinstance(roster, list) or not roster:
                raise ValueError("agents.roster must be a non-empty list when provided")
            n_agents = len(roster)
        if devices is None:
            devices = [str(i) for i in range(n_agents)]
        devices = [str(d) for d in devices]
        if len(devices) < n_agents:
            raise ValueError(
                f"agents.cuda_devices must contain at least {n_agents} entries "
                f"when provided (got {len(devices)})"
            )

        experiment_id = exp.get("id") or f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        evaluator_concurrency = str(eval_.get("concurrency", "parallel"))
        if evaluator_concurrency not in {"parallel", "serialized"}:
            raise ValueError(
                "evaluator.concurrency must be 'parallel' or 'serialized' "
                f"(got {evaluator_concurrency!r})"
            )

        # Build per-agent configs, applying explicit roster entries first, then
        # lightweight overrides for the compact n-agent schema.
        if roster is not None:
            agent_list = [
                _agent_from_roster_entry(
                    entry=entry,
                    index=index,
                    default_time_budget=budget,
                    default_train_seconds=train_s,
                    default_train_max_steps=train_max_steps,
                    default_cuda_device=devices[index],
                    default_model=model,
                    default_temperature=temp,
                    default_external_memory=use_external_memory,
                    default_shared_memory=use_shared_memory,
                )
                for index, entry in enumerate(roster)
            ]
            if mode in {"single_long", "single_memory"}:
                first_agent = agent_list[0]
                first_agent.use_external_memory = (
                    first_agent.use_external_memory or mode == "single_memory"
                )
                first_agent.use_shared_memory = False
                agent_list = [first_agent]
        elif mode in {"single_long", "single_memory"}:
            single_agent_overrides = overrides.get("agent_0", {})
            agent_list = [
                AgentConfig(
                    agent_id="agent_0",
                    role=single_agent_overrides.get("role", ""),
                    time_budget_minutes=budget,
                    train_time_budget_seconds=train_s,
                    train_max_steps=_optional_int(
                        single_agent_overrides.get("train_max_steps", train_max_steps)
                    ),
                    cuda_device=devices[0],
                    model=single_agent_overrides.get("model", model),
                    temperature=single_agent_overrides.get("temperature", temp),
                    use_external_memory=bool(
                        single_agent_overrides.get(
                            "use_external_memory",
                            use_external_memory or mode == "single_memory",
                        )
                    ),
                    use_shared_memory=bool(
                        single_agent_overrides.get("use_shared_memory", use_shared_memory)
                    ),
                )
            ]
        else:
            agent_list = []
            for i in range(n_agents):
                aid = f"agent_{i}"
                ov  = overrides.get(aid, {})
                agent_list.append(AgentConfig(
                    agent_id=aid,
                    role=ov.get("role", ""),
                    time_budget_minutes=int(ov.get("time_budget_minutes", budget)),
                    train_time_budget_seconds=int(ov.get("train_time_budget_seconds", train_s)),
                    train_max_steps=_optional_int(ov.get("train_max_steps", train_max_steps)),
                    cuda_device=str(ov.get("cuda_device", devices[i])),
                    model=ov.get("model", model),
                    temperature=ov.get("temperature", temp),
                    use_external_memory=bool(
                        ov.get("use_external_memory", use_external_memory)
                    ),
                    use_shared_memory=bool(
                        ov.get("use_shared_memory", use_shared_memory)
                    ),
                ))

        return cls(
            experiment_id=experiment_id,
            mode=mode,
            base_time_budget_minutes=budget,
            train_time_budget_seconds=train_s,
            train_max_steps=train_max_steps,
            evaluator_concurrency=evaluator_concurrency,
            target_val_bpb=_optional_float(eval_.get("target_val_bpb")),
            success_confidence=float(eval_.get("success_confidence", 0.80)),
            llm_token_price=float(eval_.get("llm_token_price", 1.0)),
            evaluator_hour_price=float(eval_.get("evaluator_hour_price", 0.0)),
            repo_root=repo_root,
            agents=agent_list,
            slurm_enabled=bool(slurm.get("enabled", True)),
            slurm_partition=slurm.get("partition", "pi_tpoggio"),
            slurm_gres=slurm.get("gres", "gpu:1"),
            slurm_time=slurm.get("time", "00:10:00"),
            system_prompt_file=tmpl.get("system_prompt", "prompts/agent_system_prompt.md"),
            first_message_file=tmpl.get("first_message", "prompts/agent_first_message.md"),
        )


def _optional_int(value) -> Optional[int]:
    if value in (None, "", "null"):
        return None
    return int(value)


def _optional_float(value) -> Optional[float]:
    if value in (None, "", "null"):
        return None
    return float(value)


def _agent_from_roster_entry(
    entry: dict,
    index: int,
    default_time_budget: int,
    default_train_seconds: int,
    default_train_max_steps: Optional[int],
    default_cuda_device: str,
    default_model: str,
    default_temperature: Optional[float],
    default_external_memory: bool,
    default_shared_memory: bool,
) -> AgentConfig:
    if not isinstance(entry, dict):
        raise ValueError("Each agents.roster entry must be a mapping")
    agent_id = str(entry.get("agent_id", entry.get("id", f"agent_{index}")))
    if not re.fullmatch(r"[A-Za-z0-9_-]+", agent_id):
        raise ValueError(
            "agents.roster agent ids may only contain letters, numbers, "
            f"underscore, and dash (got {agent_id!r})"
        )
    return AgentConfig(
        agent_id=agent_id,
        role=str(entry.get("role", "")),
        time_budget_minutes=int(entry.get("time_budget_minutes", default_time_budget)),
        train_time_budget_seconds=int(
            entry.get("train_time_budget_seconds", default_train_seconds)
        ),
        train_max_steps=_optional_int(
            entry.get("train_max_steps", default_train_max_steps)
        ),
        cuda_device=str(entry.get("cuda_device", default_cuda_device)),
        model=entry.get("model", default_model),
        temperature=entry.get("temperature", default_temperature),
        use_external_memory=bool(
            entry.get("use_external_memory", default_external_memory)
        ),
        use_shared_memory=bool(entry.get("use_shared_memory", default_shared_memory)),
        system_prompt_file=entry.get("system_prompt", "prompts/agent_system_prompt.md"),
        first_message_file=entry.get("first_message", "prompts/agent_first_message.md"),
    )
