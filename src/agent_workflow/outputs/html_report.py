"""Static HTML report generation for Agent Workflow runs."""

from __future__ import annotations

from html import escape
from pathlib import Path

from agent_workflow.outputs.workflow_card import WorkflowCard


def write_static_report(
    card: WorkflowCard,
    trajectories: dict[str, list[float]],
    output_dir: Path,
    title: str = "Agent Workflow Report",
) -> Path:
    """Write a self-contained report.html file.

    The report intentionally uses inline CSS and SVG so it can be opened from a
    local filesystem, attached to issues, or published as a static artifact.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "report.html"
    report_path.write_text(_render_report(card, trajectories, title))
    return report_path


def _render_report(
    card: WorkflowCard,
    trajectories: dict[str, list[float]],
    title: str,
) -> str:
    best_value = card.result.get("best_value", "n/a")
    baseline_value = card.baseline.get("best_value", "n/a")
    attempts = card.result.get("attempts", "n/a")
    agent_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(agent.get('id', '?')))}</td>"
        f"<td>{escape(str(agent.get('role', '')))}</td>"
        f"<td>{escape(str(agent.get('model', '')))}</td>"
        f"<td>{escape(str(agent.get('memory', '')))}</td>"
        "</tr>"
        for agent in card.agents
    )
    limitation_items = "\n".join(
        f"<li>{escape(item)}</li>" for item in card.limitations
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #172033;
      --muted: #647084;
      --paper: #f7f9fc;
      --line: #d7e0eb;
      --accent: #0f766e;
      --code: #101828;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: var(--paper);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.55;
      letter-spacing: 0;
    }}
    header {{
      padding: 56px 24px 44px;
      color: white;
      background: #0b1020;
    }}
    main, .inner {{
      width: min(1080px, calc(100% - 36px));
      margin: 0 auto;
    }}
    h1 {{
      max-width: 820px;
      margin: 0;
      font-size: 46px;
      line-height: 1.08;
      letter-spacing: 0;
    }}
    .subtitle {{
      max-width: 760px;
      margin: 18px 0 0;
      color: #d7e5ef;
      font-size: 19px;
    }}
    section {{
      margin: 24px 0;
      padding: 26px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: white;
    }}
    h2 {{
      margin: 0 0 16px;
      font-size: 25px;
      line-height: 1.18;
      letter-spacing: 0;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }}
    .metric {{
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--paper);
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .metric strong {{
      display: block;
      margin-top: 8px;
      font-size: 28px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 15px;
    }}
    th, td {{
      padding: 11px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{ font-weight: 800; }}
    .chart-wrap {{
      overflow-x: auto;
    }}
    .chart {{
      display: block;
      width: 100%;
      min-width: 640px;
      height: auto;
    }}
    code {{
      padding: 2px 5px;
      border-radius: 5px;
      color: #dff9f4;
      background: var(--code);
    }}
    .note {{
      color: var(--muted);
    }}
    @media (max-width: 720px) {{
      h1 {{ font-size: 34px; }}
      .metrics {{ grid-template-columns: 1fr; }}
      section {{ padding: 20px; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="inner">
      <h1>{escape(title)}</h1>
      <p class="subtitle">{escape(card.claim)}</p>
    </div>
  </header>
  <main>
    <section>
      <h2>Run Summary</h2>
      <div class="metrics">
        <div class="metric"><span>Workflow</span><strong>{escape(card.workflow)}</strong></div>
        <div class="metric"><span>Attempts</span><strong>{escape(str(attempts))}</strong></div>
        <div class="metric"><span>Best {escape(card.metric)}</span><strong>{escape(str(best_value))}</strong></div>
      </div>
      <p class="note">Baseline best value: {escape(str(baseline_value))}. Source: {escape(card.source)}.</p>
    </section>

    <section>
      <h2>Agent Trajectories</h2>
      <div class="chart-wrap">
        {_trajectory_svg(trajectories)}
      </div>
      <p class="note">Lower is better. This chart is generated from the run artifact trajectories.</p>
    </section>

    <section>
      <h2>Agent Roster</h2>
      <table>
        <thead><tr><th>Agent</th><th>Role</th><th>Model</th><th>Memory</th></tr></thead>
        <tbody>{agent_rows}</tbody>
      </table>
    </section>

    <section>
      <h2>Workflow Card</h2>
      <p>Task: {escape(card.task)}</p>
      <p>Metric: <code>{escape(card.metric)}</code></p>
      <p>Evidence level: {escape(card.evidence_level)}</p>
    </section>

    <section>
      <h2>Limitations</h2>
      <ul>{limitation_items}</ul>
    </section>
  </main>
</body>
</html>
"""


def _trajectory_svg(trajectories: dict[str, list[float]]) -> str:
    width = 880
    height = 320
    pad_left = 64
    pad_right = 28
    pad_top = 40
    pad_bottom = 54
    values = [value for series in trajectories.values() for value in series]
    if not values:
        return "<p>No trajectory data available.</p>"
    y_min = min(values)
    y_max = max(values)
    if y_min == y_max:
        y_min -= 0.1
        y_max += 0.1
    max_steps = max(len(series) for series in trajectories.values())
    max_x = max(1, max_steps - 1)
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom
    colors = ["#0f766e", "#2563eb", "#c2410c", "#7c3aed", "#be123c"]

    def x_at(index: int) -> float:
        return pad_left + (index / max_x) * plot_w

    def y_at(value: float) -> float:
        return pad_top + ((y_max - value) / (y_max - y_min)) * plot_h

    lines = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="Agent trajectory chart">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>',
        f'<line x1="{pad_left}" y1="{pad_top}" x2="{pad_left}" y2="{height - pad_bottom}" stroke="#94a3b8"/>',
        f'<line x1="{pad_left}" y1="{height - pad_bottom}" x2="{width - pad_right}" y2="{height - pad_bottom}" stroke="#94a3b8"/>',
        f'<text x="{pad_left}" y="{height - 18}" fill="#647084" font-size="14">attempt</text>',
        f'<text x="12" y="22" fill="#647084" font-size="14">metric</text>',
    ]
    for tick in range(5):
        value = y_min + (tick / 4) * (y_max - y_min)
        y = y_at(value)
        lines.append(
            f'<line x1="{pad_left}" y1="{y:.1f}" x2="{width - pad_right}" y2="{y:.1f}" stroke="#e2e8f0"/>'
        )
        lines.append(
            f'<text x="12" y="{y + 5:.1f}" fill="#647084" font-size="13">{value:.3f}</text>'
        )
    for idx, (agent_id, series) in enumerate(trajectories.items()):
        color = colors[idx % len(colors)]
        points = " ".join(
            f"{x_at(i):.1f},{y_at(value):.1f}" for i, value in enumerate(series)
        )
        lines.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="3" points="{points}"/>'
        )
        for i, value in enumerate(series):
            lines.append(
                f'<circle cx="{x_at(i):.1f}" cy="{y_at(value):.1f}" r="4" fill="{color}"/>'
            )
        legend_y = pad_top + 22 + idx * 22
        lines.append(
            f'<rect x="{width - 190}" y="{legend_y - 12}" width="14" height="14" fill="{color}"/>'
        )
        lines.append(
            f'<text x="{width - 168}" y="{legend_y}" fill="#172033" font-size="14">{escape(agent_id)}</text>'
        )
    lines.append("</svg>")
    return "\n".join(lines)
