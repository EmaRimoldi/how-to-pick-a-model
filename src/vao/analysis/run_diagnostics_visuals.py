"""Per-run diagnostics for mode probabilities, losses, gains, and costs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from vao.estimators import gains_by_mode, routing_regret
from vao.logging_utils import write_json
from vao.records import load_step_records
from vao.taxonomy import MODES


def summarize_run(run_dir: Path) -> dict[str, Any]:
    records = load_step_records(run_dir)
    steps = []
    for record in records:
        losses = {branch.declared_mode: float(branch.latent_loss) for branch in record.branches}
        gains = gains_by_mode(record)
        best_mode = max(MODES, key=lambda mode: gains[mode])
        selected_loss = losses.get(record.selected_mode)
        branch_wall = sum(float(branch.elapsed_wall_seconds or 0.0) for branch in record.branches)
        steps.append(
            {
                "step": record.step,
                "selected_mode": record.selected_mode,
                "selected_mode_top1": record.selected_mode_top1,
                "selection_policy": record.selection_policy,
                "verified_best_mode": best_mode,
                "mode_probs": record.mode_probs,
                "post_feedback_mode_probs": record.post_feedback_mode_probs,
                "loss_by_mode": losses,
                "gain_by_mode": gains,
                "selected_loss": selected_loss,
                "best_counterfactual_loss": min(losses.values()) if losses else None,
                "routing_regret": routing_regret(gains, record.selected_mode_top1),
                "selected_policy_regret": routing_regret(gains, record.selected_mode),
                "feedback_regret_improvement": record.feedback_regret_improvement,
                "feedback_jsd_improvement": record.feedback_jsd_improvement,
                "input_tokens": record.input_tokens,
                "output_tokens": record.output_tokens,
                "total_tokens": (record.input_tokens or 0) + (record.output_tokens or 0),
                "agent_cost_usd": record.agent_cost_usd,
                "branch_wall_seconds": branch_wall,
            }
        )
    return {
        "run_dir": str(run_dir),
        "run_id": records[0].run_id if records else run_dir.name,
        "profile_id": records[0].profile_id if records else None,
        "model_id": records[0].model_id if records else None,
        "steps": steps,
    }


def make_plots(summary: dict[str, Any], out_dir: Path, *, single_mode: str | None = None) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "mode_probs": str(out_dir / "mode_probs_by_step.png"),
        "loss_by_mode": str(out_dir / "loss_by_step_by_mode.png"),
        "best_loss": str(out_dir / "best_loss_by_step.png"),
        "gain_heatmap": str(out_dir / "gain_heatmap_by_step_mode.png"),
        "cost_per_step": str(out_dir / "cost_per_step.png"),
    }
    _plot_mode_probs(summary, Path(outputs["mode_probs"]))
    _plot_loss_by_mode(summary, Path(outputs["loss_by_mode"]))
    _plot_best_loss(summary, Path(outputs["best_loss"]))
    _plot_gain_heatmap(summary, Path(outputs["gain_heatmap"]))
    _plot_cost(summary, Path(outputs["cost_per_step"]))
    if any(step.get("post_feedback_mode_probs") for step in summary["steps"]):
        outputs["pre_post_mode_probs"] = str(out_dir / "pre_post_mode_probs_by_step.png")
        _plot_pre_post_probs(summary, Path(outputs["pre_post_mode_probs"]), mode=single_mode)
    if single_mode:
        outputs["single_mode"] = str(out_dir / f"single_mode_{single_mode}_trajectory.png")
        _plot_single_mode(summary, Path(outputs["single_mode"]), single_mode)
    return outputs


def write_markdown(summary: dict[str, Any], plots: dict[str, str], path: Path) -> None:
    lines = [
        "# Run Diagnostics",
        "",
        f"Run: `{summary['run_id']}`",
        f"Profile: `{summary['profile_id']}`",
        f"Model: `{summary['model_id']}`",
        "",
        "| step | selected | top1 | verified best | selected loss | best loss | top1 regret | policy regret | cost usd | tokens |",
        "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for step in summary["steps"]:
        lines.append(
            f"| `{step['step']}` | `{step['selected_mode']}` | `{step['selected_mode_top1']}` | "
            f"`{step['verified_best_mode']}` | `{step['selected_loss']}` | `{step['best_counterfactual_loss']}` | "
            f"`{step['routing_regret']}` | `{step['selected_policy_regret']}` | "
            f"`{step['agent_cost_usd']}` | `{step['total_tokens']}` |"
        )
    lines.extend(["", "## Plots"])
    for label, plot_path in plots.items():
        lines.append(f"- {label}: `{plot_path}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _steps(summary: dict[str, Any]) -> list[int]:
    return [int(step["step"]) for step in summary["steps"]]


def _plot_mode_probs(summary: dict[str, Any], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    xs = _steps(summary)
    for mode in MODES:
        ax.plot(xs, [step["mode_probs"][mode] for step in summary["steps"]], marker="o", label=mode)
    ax.set_ylim(0, 1)
    ax.set_xlabel("step")
    ax.set_ylabel("q_t(mode)")
    ax.set_title("Mode probability distribution by step")
    ax.legend(ncol=3)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_pre_post_probs(summary: dict[str, Any], path: Path, *, mode: str | None) -> None:
    mode = mode or "layout"
    xs = _steps(summary)
    pre = [step["mode_probs"][mode] for step in summary["steps"]]
    post = [
        (step["post_feedback_mode_probs"] or step["mode_probs"])[mode]
        for step in summary["steps"]
    ]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(xs, pre, marker="o", label=f"pre {mode}")
    ax.plot(xs, post, marker="s", label=f"post {mode}")
    ax.set_ylim(0, 1)
    ax.set_xlabel("step")
    ax.set_ylabel("probability")
    ax.set_title(f"C(b) pre/post feedback probability for {mode}")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_single_mode(summary: dict[str, Any], path: Path, mode: str) -> None:
    xs = _steps(summary)
    fig, ax1 = plt.subplots(figsize=(8, 4.5))
    ax1.plot(xs, [step["mode_probs"][mode] for step in summary["steps"]], marker="o", color="#2563eb", label="probability")
    ax1.set_ylim(0, 1)
    ax1.set_xlabel("step")
    ax1.set_ylabel("probability", color="#2563eb")
    ax2 = ax1.twinx()
    ax2.plot(xs, [step["gain_by_mode"][mode] for step in summary["steps"]], marker="s", color="#dc2626", label="gain")
    ax2.set_ylabel("verified gain", color="#dc2626")
    ax1.set_title(f"Single-mode trajectory: {mode}")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_loss_by_mode(summary: dict[str, Any], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    xs = _steps(summary)
    for mode in MODES:
        ax.plot(xs, [step["loss_by_mode"][mode] for step in summary["steps"]], marker="o", label=mode)
    ax.plot(xs, [step["selected_loss"] for step in summary["steps"]], color="black", linewidth=2.5, label="selected")
    ax.set_xlabel("step")
    ax.set_ylabel("latent loss")
    ax.set_title("Latent loss by mode and selected branch")
    ax.legend(ncol=3)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_best_loss(summary: dict[str, Any], path: Path) -> None:
    xs = _steps(summary)
    selected_losses = [step["selected_loss"] for step in summary["steps"]]
    step_best_losses = [step["best_counterfactual_loss"] for step in summary["steps"]]
    visible_best_so_far = _running_min(selected_losses)
    oracle_best_so_far = _running_min(step_best_losses)

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(xs, selected_losses, marker="o", color="#111827", alpha=0.75, label="selected loss at step")
    ax.plot(xs, step_best_losses, marker="s", color="#2563eb", alpha=0.75, label="best counterfactual at step")
    ax.plot(xs, visible_best_so_far, color="#16a34a", linewidth=2.5, label="best visible so far")
    ax.plot(xs, oracle_best_so_far, color="#dc2626", linewidth=2.5, linestyle="--", label="best counterfactual so far")
    ax.set_xlabel("step")
    ax.set_ylabel("latent loss")
    ax.set_title("Best loss trajectory")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _running_min(values: list[float | None]) -> list[float | None]:
    best: float | None = None
    out: list[float | None] = []
    for value in values:
        if value is not None:
            numeric = float(value)
            best = numeric if best is None else min(best, numeric)
        out.append(best)
    return out


def _plot_gain_heatmap(summary: dict[str, Any], path: Path) -> None:
    matrix = [[step["gain_by_mode"][mode] for mode in MODES] for step in summary["steps"]]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    image = ax.imshow(matrix, cmap="RdYlGn", aspect="auto")
    ax.set_xticks(range(len(MODES)), MODES, rotation=30, ha="right")
    ax.set_yticks(range(len(summary["steps"])), [step["step"] for step in summary["steps"]])
    ax.set_xlabel("mode")
    ax.set_ylabel("step")
    ax.set_title("Verified gain by step and mode")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_cost(summary: dict[str, Any], path: Path) -> None:
    xs = _steps(summary)
    costs = [step["agent_cost_usd"] or 0.0 for step in summary["steps"]]
    tokens = [step["total_tokens"] or 0 for step in summary["steps"]]
    fig, ax1 = plt.subplots(figsize=(8, 4.5))
    ax1.bar(xs, costs, color="#0f766e", alpha=0.8, label="USD")
    ax1.set_xlabel("step")
    ax1.set_ylabel("USD cost")
    ax2 = ax1.twinx()
    ax2.plot(xs, tokens, color="#7c3aed", marker="o", label="tokens")
    ax2.set_ylabel("tokens")
    ax1.set_title("Cost and tokens by step")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--out_dir", default=None)
    parser.add_argument("--single_mode", choices=MODES, default=None)
    args = parser.parse_args(argv)
    run_dir = Path(args.run_dir)
    out_dir = Path(args.out_dir) if args.out_dir else Path("artifacts/plots") / f"run_{run_dir.name}"
    summary = summarize_run(run_dir)
    plots = make_plots(summary, out_dir, single_mode=args.single_mode)
    write_json(out_dir / "run_diagnostics_summary.json", {**summary, "plots": plots})
    write_markdown(summary, plots, out_dir / "run_diagnostics.md")
    print(json.dumps({"run_dir": str(run_dir), "out_dir": str(out_dir), "plots": len(plots)}, indent=2))


if __name__ == "__main__":
    main()
