"""Estimate reviewer-facing T_wall and T_cost from experiment logs.

This module treats each mode directory as one independent replicate. Within a
replicate it pools all agents and asks: at what elapsed critical-path wall time
did the system first produce a candidate whose latent-loss proxy crossed q*?

The estimator is intentionally conservative:
- no target q* means no certified-time estimate;
- if require_reevaluation is set, single-shot wins do not count;
- if fewer than ceil(confidence * N) replicates hit the target, the certified
  estimate is reported as not certified rather than extrapolated.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional


@dataclass
class TrainingEvent:
    replicate_id: str
    experiment_id: str
    mode: str
    agent_id: str
    run_index: int
    turn: int
    candidate_id: Optional[str]
    finished_at: float
    wall_elapsed_seconds: float
    val_bpb: float
    latent_loss_proxy: float
    reevaluation_count: int
    is_reevaluation: bool
    cumulative_tokens: float
    cumulative_evaluator_wall_seconds: float
    cumulative_cost_proxy: float


@dataclass
class ReplicateEstimate:
    replicate_id: str
    experiment_id: str
    mode: str
    event_count: int
    hit: bool
    hit_wall_seconds: Optional[float] = None
    hit_cost_proxy: Optional[float] = None
    hit_run_index: Optional[int] = None
    hit_agent_id: Optional[str] = None
    hit_candidate_id: Optional[str] = None
    hit_val_bpb: Optional[float] = None
    hit_latent_loss_proxy: Optional[float] = None


@dataclass
class CertifiedModeEstimate:
    mode: str
    target_val_bpb: float
    confidence: float
    replicate_count: int
    required_hits: int
    hit_count: int
    certified: bool
    t_wall_seconds: Optional[float]
    t_cost_proxy: Optional[float]
    warning: Optional[str] = None
    replicates: list[ReplicateEstimate] = field(default_factory=list)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for raw_line in path.read_text().splitlines():
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _parse_iso_epoch(value: object) -> Optional[float]:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _float_or_none(value: object) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_zero(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _mode_dirs(paths: Iterable[Path]) -> list[Path]:
    found: list[Path] = []
    for raw_path in paths:
        path = raw_path.expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        if path.is_dir() and path.name.startswith("mode_"):
            found.append(path)
        elif path.is_dir():
            found.extend(sorted(p for p in path.glob("mode_*") if p.is_dir()))
            found.extend(sorted(p for p in path.glob("experiment_*/mode_*") if p.is_dir()))
        else:
            raise ValueError(f"Expected an experiment or mode directory, got file: {path}")
    return sorted(set(found))


def _replicate_start_epoch(mode_dir: Path) -> float:
    starts: list[float] = []
    run_starts: list[float] = []
    for agent_dir in sorted(mode_dir.glob("agent_*")):
        meta_path = agent_dir / "results" / "metadata.json"
        if meta_path.exists():
            try:
                metadata = json.loads(meta_path.read_text())
                start_epoch = _parse_iso_epoch(metadata.get("start_time"))
                if start_epoch is not None:
                    starts.append(start_epoch)
            except json.JSONDecodeError:
                pass
        for row in _read_jsonl(agent_dir / "results" / "training_runs.jsonl"):
            start = _float_or_none(row.get("started_at"))
            if start is not None:
                run_starts.append(start)
    if starts:
        return min(starts)
    if run_starts:
        return min(run_starts)
    return 0.0


def _turn_token_events(agent_dir: Path) -> list[tuple[float, int, float]]:
    events: list[tuple[float, int, float]] = []
    for row in _read_jsonl(agent_dir / "results" / "turns.jsonl"):
        timestamp = _float_or_none(row.get("timestamp"))
        if timestamp is None:
            continue
        events.append(
            (
                timestamp,
                _int_or_zero(row.get("turn")),
                float(row.get("total_tokens") or 0.0),
            )
        )
    return sorted(events, key=lambda item: (item[0], item[1]))


def _tokens_up_to(
    token_events_by_agent: dict[str, list[tuple[float, int, float]]],
    *,
    agent_id: str,
    turn: int,
    finished_at: float,
) -> float:
    total = 0.0
    for other_agent, token_events in token_events_by_agent.items():
        for timestamp, turn_index, tokens in token_events:
            # Same-agent turn indices are the most reliable alignment because
            # turn timestamps are written after the Claude invocation returns.
            if other_agent == agent_id and turn_index <= turn:
                total += tokens
            elif other_agent != agent_id and timestamp <= finished_at:
                total += tokens
    return total


def collect_training_events(
    mode_dir: Path,
    *,
    llm_token_price: float = 1.0,
    evaluator_hour_price: float = 0.0,
) -> list[TrainingEvent]:
    """Collect sorted training events for one mode directory."""
    mode = mode_dir.name.removeprefix("mode_")
    experiment_id = mode_dir.parent.name.removeprefix("experiment_")
    replicate_id = f"{mode_dir.parent.name}/{mode_dir.name}"
    start_epoch = _replicate_start_epoch(mode_dir)

    token_events_by_agent: dict[str, list[tuple[float, int, float]]] = {}
    raw_events: list[tuple[Path, dict]] = []
    for agent_dir in sorted(mode_dir.glob("agent_*")):
        agent_id = agent_dir.name
        token_events_by_agent[agent_id] = _turn_token_events(agent_dir)
        for row in _read_jsonl(agent_dir / "results" / "training_runs.jsonl"):
            raw_events.append((agent_dir, row))

    raw_events.sort(
        key=lambda item: (
            _float_or_none(item[1].get("finished_at")) or float("inf"),
            str(item[0]),
            _int_or_zero(item[1].get("run_index")),
        )
    )

    events: list[TrainingEvent] = []
    cumulative_evaluator_wall_seconds = 0.0
    for agent_dir, row in raw_events:
        val_bpb = _float_or_none(row.get("val_bpb"))
        finished_at = _float_or_none(row.get("finished_at"))
        if val_bpb is None or finished_at is None:
            continue

        wall_seconds = _float_or_none(row.get("evaluator_wall_seconds"))
        if wall_seconds is None:
            wall_seconds = _float_or_none(row.get("wall_seconds")) or 0.0
        cumulative_evaluator_wall_seconds += wall_seconds

        agent_id = str(row.get("agent_id") or agent_dir.name)
        turn = _int_or_zero(row.get("turn"))
        cumulative_tokens = _tokens_up_to(
            token_events_by_agent,
            agent_id=agent_id,
            turn=turn,
            finished_at=finished_at,
        )
        cumulative_cost_proxy = (
            llm_token_price * cumulative_tokens
            + evaluator_hour_price * (cumulative_evaluator_wall_seconds / 3600.0)
        )

        latent_loss_proxy = _float_or_none(row.get("candidate_mean_val_bpb_after"))
        if latent_loss_proxy is None:
            latent_loss_proxy = val_bpb

        events.append(
            TrainingEvent(
                replicate_id=replicate_id,
                experiment_id=experiment_id,
                mode=mode,
                agent_id=agent_id,
                run_index=_int_or_zero(row.get("run_index")),
                turn=turn,
                candidate_id=row.get("candidate_id"),
                finished_at=finished_at,
                wall_elapsed_seconds=max(finished_at - start_epoch, 0.0),
                val_bpb=val_bpb,
                latent_loss_proxy=latent_loss_proxy,
                reevaluation_count=_int_or_zero(row.get("candidate_eval_count_after")),
                is_reevaluation=bool(row.get("is_reevaluation")),
                cumulative_tokens=cumulative_tokens,
                cumulative_evaluator_wall_seconds=cumulative_evaluator_wall_seconds,
                cumulative_cost_proxy=cumulative_cost_proxy,
            )
        )
    return events


def estimate_replicate(
    mode_dir: Path,
    *,
    target_val_bpb: float,
    require_reevaluation: bool = False,
    min_evaluations: int = 2,
    llm_token_price: float = 1.0,
    evaluator_hour_price: float = 0.0,
) -> ReplicateEstimate:
    events = collect_training_events(
        mode_dir,
        llm_token_price=llm_token_price,
        evaluator_hour_price=evaluator_hour_price,
    )
    mode = mode_dir.name.removeprefix("mode_")
    experiment_id = mode_dir.parent.name.removeprefix("experiment_")
    replicate_id = f"{mode_dir.parent.name}/{mode_dir.name}"

    for event in events:
        enough_evaluations = (
            not require_reevaluation or event.reevaluation_count >= min_evaluations
        )
        if enough_evaluations and event.latent_loss_proxy <= target_val_bpb:
            return ReplicateEstimate(
                replicate_id=replicate_id,
                experiment_id=experiment_id,
                mode=mode,
                event_count=len(events),
                hit=True,
                hit_wall_seconds=event.wall_elapsed_seconds,
                hit_cost_proxy=event.cumulative_cost_proxy,
                hit_run_index=event.run_index,
                hit_agent_id=event.agent_id,
                hit_candidate_id=event.candidate_id,
                hit_val_bpb=event.val_bpb,
                hit_latent_loss_proxy=event.latent_loss_proxy,
            )

    return ReplicateEstimate(
        replicate_id=replicate_id,
        experiment_id=experiment_id,
        mode=mode,
        event_count=len(events),
        hit=False,
    )


def estimate_certified_times(
    mode_dirs: Iterable[Path],
    *,
    target_val_bpb: float,
    confidence: float = 0.80,
    require_reevaluation: bool = False,
    min_evaluations: int = 2,
    llm_token_price: float = 1.0,
    evaluator_hour_price: float = 0.0,
) -> dict[str, CertifiedModeEstimate]:
    """Estimate empirical certified T_wall/T_cost per mode."""
    if not 0.0 < confidence <= 1.0:
        raise ValueError("confidence must be in (0, 1]")

    by_mode: dict[str, list[ReplicateEstimate]] = {}
    for mode_dir in mode_dirs:
        estimate = estimate_replicate(
            mode_dir,
            target_val_bpb=target_val_bpb,
            require_reevaluation=require_reevaluation,
            min_evaluations=min_evaluations,
            llm_token_price=llm_token_price,
            evaluator_hour_price=evaluator_hour_price,
        )
        by_mode.setdefault(estimate.mode, []).append(estimate)

    results: dict[str, CertifiedModeEstimate] = {}
    for mode, replicates in sorted(by_mode.items()):
        n = len(replicates)
        required_hits = math.ceil(confidence * n) if n else 0
        hits = [rep for rep in replicates if rep.hit]
        certified = len(hits) >= required_hits and required_hits > 0
        t_wall = None
        t_cost = None
        warning = None
        if certified:
            wall_values = sorted(float(rep.hit_wall_seconds) for rep in hits)
            cost_values = sorted(float(rep.hit_cost_proxy) for rep in hits)
            t_wall = wall_values[required_hits - 1]
            t_cost = cost_values[required_hits - 1]
        else:
            warning = (
                f"not certified: {len(hits)}/{n} replicates hit q*="
                f"{target_val_bpb:.6f}; need {required_hits}"
            )
        if n < 5:
            small_n = f"only {n} replicate(s); treat as pilot, not confirmatory"
            warning = f"{warning}; {small_n}" if warning else small_n
        results[mode] = CertifiedModeEstimate(
            mode=mode,
            target_val_bpb=target_val_bpb,
            confidence=confidence,
            replicate_count=n,
            required_hits=required_hits,
            hit_count=len(hits),
            certified=certified,
            t_wall_seconds=t_wall,
            t_cost_proxy=t_cost,
            warning=warning,
            replicates=replicates,
        )
    return results


def _write_markdown(path: Path, estimates: dict[str, CertifiedModeEstimate]) -> None:
    lines = [
        "# Certified-Time Analysis",
        "",
        "| mode | reps | hits | certified | T_wall_seconds | T_cost_proxy | warning |",
        "| --- | ---: | ---: | --- | ---: | ---: | --- |",
    ]
    for estimate in estimates.values():
        lines.append(
            "| {mode} | {reps} | {hits}/{required} | {certified} | {wall} | {cost} | {warning} |".format(
                mode=estimate.mode,
                reps=estimate.replicate_count,
                hits=estimate.hit_count,
                required=estimate.required_hits,
                certified="yes" if estimate.certified else "no",
                wall=(
                    f"{estimate.t_wall_seconds:.2f}"
                    if estimate.t_wall_seconds is not None
                    else ""
                ),
                cost=(
                    f"{estimate.t_cost_proxy:.2f}"
                    if estimate.t_cost_proxy is not None
                    else ""
                ),
                warning=estimate.warning or "",
            )
        )
    lines.append("")
    lines.append("Replicate-level hits:")
    lines.append("")
    lines.append("| replicate | mode | hit | wall_seconds | cost_proxy | candidate | latent_loss_proxy |")
    lines.append("| --- | --- | --- | ---: | ---: | --- | ---: |")
    for estimate in estimates.values():
        for rep in estimate.replicates:
            lines.append(
                "| {replicate} | {mode} | {hit} | {wall} | {cost} | {candidate} | {loss} |".format(
                    replicate=rep.replicate_id,
                    mode=rep.mode,
                    hit="yes" if rep.hit else "no",
                    wall=(
                        f"{rep.hit_wall_seconds:.2f}"
                        if rep.hit_wall_seconds is not None
                        else ""
                    ),
                    cost=(
                        f"{rep.hit_cost_proxy:.2f}"
                        if rep.hit_cost_proxy is not None
                        else ""
                    ),
                    candidate=rep.hit_candidate_id or "",
                    loss=(
                        f"{rep.hit_latent_loss_proxy:.6f}"
                        if rep.hit_latent_loss_proxy is not None
                        else ""
                    ),
                )
            )
    path.write_text("\n".join(lines) + "\n")


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Estimate T_wall/T_cost from AutoResearch experiment logs."
    )
    parser.add_argument("paths", nargs="+", help="Experiment dirs or mode dirs.")
    parser.add_argument("--target-val-bpb", type=float, required=True, help="q* threshold.")
    parser.add_argument("--confidence", type=float, default=0.80, help="1-delta.")
    parser.add_argument("--require-reevaluation", action="store_true")
    parser.add_argument("--min-evaluations", type=int, default=2)
    parser.add_argument("--llm-token-price", type=float, default=1.0)
    parser.add_argument("--evaluator-hour-price", type=float, default=0.0)
    parser.add_argument("--out", type=str, default=None, help="Output JSON path.")
    args = parser.parse_args(argv)

    mode_dirs = _mode_dirs(Path(p) for p in args.paths)
    estimates = estimate_certified_times(
        mode_dirs,
        target_val_bpb=args.target_val_bpb,
        confidence=args.confidence,
        require_reevaluation=args.require_reevaluation,
        min_evaluations=args.min_evaluations,
        llm_token_price=args.llm_token_price,
        evaluator_hour_price=args.evaluator_hour_price,
    )
    payload = {mode: asdict(estimate) for mode, estimate in estimates.items()}

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2))
        _write_markdown(out_path.with_suffix(".md"), estimates)
        print(f"Wrote {out_path}")
        print(f"Wrote {out_path.with_suffix('.md')}")
    else:
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
