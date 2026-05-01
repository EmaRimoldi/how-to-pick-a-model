"""Select and certify a richer oracle latent-mode set from workload families."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from benchmarks.stateful_query_engine.generators.workload_gen import ALL_FAMILIES, generate_trace
from vao.estimators import gains_by_mode
from vao.records import load_records_from_roots
from vao.task_modes import trace_observable_summary
from vao.taxonomy import MODES


OBSERVABLE_KEYS = [
    "query_ratio",
    "update_ratio",
    "get_ratio",
    "put_ratio",
    "delete_ratio",
    "range_sum_ratio",
    "aggregate_count_ratio",
    "topk_ratio",
    "mean_range_width",
    "mean_topk_k",
    "mean_center_jump",
]


def analyze_latent_modes(
    *,
    out_dir: Path,
    roots: list[Path] | None,
    profile: str,
    families: list[str],
    select_k: int,
    traces_per_family: int,
    trace_length: int,
    initial_size: int,
    key_space: int,
    value_max: int,
    base_seed: int,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    family_summary = _build_family_summary(
        profile=profile,
        families=families,
        traces_per_family=traces_per_family,
        trace_length=trace_length,
        initial_size=initial_size,
        key_space=key_space,
        value_max=value_max,
        base_seed=base_seed,
    )
    observable_distances = _distance_matrix(
        family_summary.set_index("family"),
        keys=OBSERVABLE_KEYS,
    )
    response_summary = _response_summary(roots or [])
    response_distances = _response_distance_matrix(response_summary)
    combined_distances = _combine_distances(observable_distances, response_distances)
    selected_families = _farthest_point_selection(combined_distances, k=min(select_k, len(families)))

    family_summary.to_csv(out_dir / "family_observable_summary.csv", index=False)
    observable_distances.to_csv(out_dir / "observable_distance_matrix.csv")
    if not response_summary.empty:
        response_summary.to_csv(out_dir / "family_response_summary.csv", index=False)
        response_distances.to_csv(out_dir / "response_distance_matrix.csv")
    combined_distances.to_csv(out_dir / "combined_distance_matrix.csv")

    _plot_heatmap(observable_distances, path=out_dir / "observable_distance_heatmap.png", title="Observable latent-mode distances")
    if not response_summary.empty:
        _plot_heatmap(response_distances, path=out_dir / "response_distance_heatmap.png", title="Response-signature distances")
    _plot_heatmap(combined_distances, path=out_dir / "combined_distance_heatmap.png", title="Combined latent-mode distances")

    result = {
        "profile": profile,
        "families": families,
        "observable_keys": OBSERVABLE_KEYS,
        "selection_metric": "combined" if not response_summary.empty else "observable_only",
        "selected_families": selected_families,
        "selection_k": select_k,
        "traces_per_family": traces_per_family,
        "trace_length": trace_length,
        "initial_size": initial_size,
        "key_space": key_space,
        "value_max": value_max,
        "base_seed": base_seed,
        "observable_min_pairwise_distance": _selected_min_distance(observable_distances, selected_families),
        "combined_min_pairwise_distance": _selected_min_distance(combined_distances, selected_families),
    }
    (out_dir / "latent_mode_selection.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    _write_report(result, family_summary, observable_distances, response_summary, combined_distances, out_dir / "report.md")
    return result


def _build_family_summary(
    *,
    profile: str,
    families: list[str],
    traces_per_family: int,
    trace_length: int,
    initial_size: int,
    key_space: int,
    value_max: int,
    base_seed: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for family_index, family in enumerate(families):
        summaries: list[dict[str, Any]] = []
        for trace_index in range(traces_per_family):
            seed = base_seed + family_index * 10_000 + trace_index
            trace = generate_trace(
                family=family,
                seed=seed,
                length=trace_length,
                initial_size=initial_size,
                key_space=key_space,
                value_max=value_max,
                profile=profile,
            )
            summaries.append(trace_observable_summary(trace))
        row = {"family": family, "trace_count": traces_per_family}
        for key in OBSERVABLE_KEYS:
            row[key] = statistics.fmean(float(summary[key]) for summary in summaries)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("family")


def _distance_matrix(frame: pd.DataFrame, *, keys: list[str]) -> pd.DataFrame:
    normalized = frame.copy()
    for key in keys:
        series = normalized[key].astype(float)
        std = float(series.std(ddof=0))
        if std <= 0:
            normalized[key] = 0.0
        else:
            normalized[key] = (series - float(series.mean())) / std
    families = list(normalized.index)
    values = []
    for family_left in families:
        row = []
        left = normalized.loc[family_left, keys].to_numpy(dtype=float)
        for family_right in families:
            right = normalized.loc[family_right, keys].to_numpy(dtype=float)
            row.append(float(np.linalg.norm(left - right)))
        values.append(row)
    return pd.DataFrame(values, index=families, columns=families)


def _response_summary(roots: list[Path]) -> pd.DataFrame:
    if not roots:
        return pd.DataFrame()
    records = load_records_from_roots(roots)
    rows: list[dict[str, Any]] = []
    for record in records:
        if record.task_mode_true is None:
            continue
        gains = gains_by_mode(record)
        positive = {mode: max(float(gains[mode]), 0.0) for mode in MODES}
        total = sum(positive.values())
        normalized = {mode: (positive[mode] / total if total > 0 else 1.0 / len(MODES)) for mode in MODES}
        row = {
            "family": str(record.task_mode_true),
            "model_id": record.model_id,
            "step": int(record.step),
        }
        for mode in MODES:
            row[f"gain_{mode}"] = float(gains[mode])
            row[f"productive_{mode}"] = normalized[mode]
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    aggregations = {f"gain_{mode}": "mean" for mode in MODES} | {f"productive_{mode}": "mean" for mode in MODES}
    return frame.groupby("family", as_index=False).agg(aggregations).sort_values("family")


def _response_distance_matrix(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()
    summary = summary.set_index("family")
    keys = [f"productive_{mode}" for mode in MODES]
    return _distance_matrix(summary, keys=keys)


def _combine_distances(observable: pd.DataFrame, response: pd.DataFrame) -> pd.DataFrame:
    if response.empty:
        return observable.copy()
    aligned = response.reindex(index=observable.index, columns=observable.columns).fillna(0.0)
    max_observable = float(observable.to_numpy().max()) or 1.0
    max_response = float(aligned.to_numpy().max()) or 1.0
    combined = 0.5 * (observable / max_observable) + 0.5 * (aligned / max_response)
    return combined


def _farthest_point_selection(distances: pd.DataFrame, *, k: int) -> list[str]:
    families = list(distances.index)
    if not families or k <= 0:
        return []
    start = max(families, key=lambda family: float(distances.loc[family].mean()))
    selected = [start]
    remaining = [family for family in families if family != start]
    while remaining and len(selected) < k:
        next_family = max(remaining, key=lambda family: min(float(distances.loc[family, chosen]) for chosen in selected))
        selected.append(next_family)
        remaining.remove(next_family)
    return selected


def _selected_min_distance(distances: pd.DataFrame, families: list[str]) -> float:
    if len(families) < 2:
        return math.nan
    values = [
        float(distances.loc[left, right])
        for index, left in enumerate(families)
        for right in families[index + 1 :]
    ]
    return min(values) if values else math.nan


def _plot_heatmap(frame: pd.DataFrame, *, path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 6.5))
    image = ax.imshow(frame.to_numpy(dtype=float), aspect="auto", cmap="viridis")
    ax.set_xticks(range(len(frame.columns)), frame.columns, rotation=30, ha="right")
    ax.set_yticks(range(len(frame.index)), frame.index)
    ax.set_title(title)
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _write_report(
    result: dict[str, Any],
    family_summary: pd.DataFrame,
    observable_distances: pd.DataFrame,
    response_summary: pd.DataFrame,
    combined_distances: pd.DataFrame,
    path: Path,
) -> None:
    lines = [
        "# Oracle-Family Latent-Mode Selection",
        "",
        f"- Selection metric: `{result['selection_metric']}`",
        f"- Selected families: `{', '.join(result['selected_families'])}`",
        f"- Observable min pairwise distance: `{result['observable_min_pairwise_distance']:.3f}`",
        f"- Combined min pairwise distance: `{result['combined_min_pairwise_distance']:.3f}`",
        "",
        "## Observable Summaries",
        "",
    ]
    for _, row in family_summary.iterrows():
        lines.append(
            f"- `{row['family']}`: "
            f"topk_ratio={row['topk_ratio']:.3f}, range_sum_ratio={row['range_sum_ratio']:.3f}, "
            f"aggregate_count_ratio={row['aggregate_count_ratio']:.3f}, update_ratio={row['update_ratio']:.3f}, "
            f"mean_range_width={row['mean_range_width']:.1f}, mean_topk_k={row['mean_topk_k']:.1f}"
        )
    if not response_summary.empty:
        lines += [
            "",
            "## Response Signatures",
            "",
        ]
        for _, row in response_summary.iterrows():
            dominant = max(MODES, key=lambda mode: float(row[f"productive_{mode}"]))
            lines.append(f"- `{row['family']}`: dominant productive action mode=`{dominant}`")
    lines += [
        "",
        "## Selected Pairwise Distances",
        "",
    ]
    for index, left in enumerate(result["selected_families"]):
        for right in result["selected_families"][index + 1 :]:
            lines.append(
                f"- `{left}` vs `{right}`: observable=`{float(observable_distances.loc[left, right]):.3f}`, "
                f"combined=`{float(combined_distances.loc[left, right]):.3f}`"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--runs", nargs="*", default=None)
    parser.add_argument("--profile", default="hard_optimization")
    parser.add_argument("--families", default=",".join(ALL_FAMILIES))
    parser.add_argument("-k", "--select-k", type=int, default=4)
    parser.add_argument("--traces-per-family", type=int, default=6)
    parser.add_argument("--trace-length", type=int, default=200)
    parser.add_argument("--initial-size", type=int, default=200)
    parser.add_argument("--key-space", type=int, default=2000)
    parser.add_argument("--value-max", type=int, default=1000)
    parser.add_argument("--base-seed", type=int, default=7000)
    args = parser.parse_args(argv)
    result = analyze_latent_modes(
        out_dir=Path(args.out_dir),
        roots=[Path(item) for item in (args.runs or [])],
        profile=args.profile,
        families=[item.strip() for item in args.families.split(",") if item.strip()],
        select_k=args.select_k,
        traces_per_family=args.traces_per_family,
        trace_length=args.trace_length,
        initial_size=args.initial_size,
        key_space=args.key_space,
        value_max=args.value_max,
        base_seed=args.base_seed,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
