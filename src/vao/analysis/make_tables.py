"""Create simple Markdown tables from estimator CSV files."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--estimators", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    frame = pd.read_csv(args.estimators)
    columns = [
        "model_id",
        "profile_id",
        "best_loss",
        "success",
        "mean_routing_regret",
        "mean_jsd",
        "invalid_rate",
    ]
    table = _to_markdown(frame[columns])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(table + "\n", encoding="utf-8")
    print(str(out))


def _to_markdown(frame: pd.DataFrame) -> str:
    headers = list(frame.columns)
    rows = []
    rows.append("| " + " | ".join(headers) + " |")
    rows.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for _, row in frame.iterrows():
        rows.append("| " + " | ".join(_format_value(row[column]) for column in headers) + " |")
    return "\n".join(rows)


def _format_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


if __name__ == "__main__":
    main()
