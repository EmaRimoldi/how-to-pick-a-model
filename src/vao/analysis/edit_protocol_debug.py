"""Compare replacement, unified-diff, and structured-edit protocol overhead."""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vao.logging_utils import write_json


DEFAULT_ROOTS = {
    "phase3_haiku_replacement": "runs/phase3_real_backend/haiku_dev",
    "phase35_haiku_patch": "runs/phase35_patch/haiku_dev",
}


def build_report(roots: dict[str, str], parent_path: Path) -> dict[str, Any]:
    observed = {}
    for name, root in roots.items():
        rows = _collect_proposals(Path(root))
        if rows:
            observed[name] = _summarize_rows(rows)
    parent_source = parent_path.read_text(encoding="utf-8")
    examples = _compact_examples(parent_source)
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "observed_logs": observed,
        "compact_examples": examples,
        "decision": (
            "Use structured_edits as the default real-model edit protocol; "
            "keep replacement and unified-diff as legacy fallbacks."
        ),
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Edit Protocol Debug Report",
        "",
        f"Generated: `{report['created_at']}`",
        "",
        "## Observed Existing Runs",
        "",
        "| dataset | proposals | mean raw chars | median raw chars | est mean output tokens | errors | validation failures |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, summary in report["observed_logs"].items():
        lines.append(
            f"| `{name}` | `{summary['proposal_count']}` | `{summary['mean_raw_chars']:.1f}` | "
            f"`{summary['median_raw_chars']}` | `{summary['estimated_mean_output_tokens_chars_over_4']:.1f}` | "
            f"`{summary['proposal_error_count']}` | `{summary['proposal_validation_failure_count']}` |"
        )
    examples = report["compact_examples"]
    lines.extend(
        [
            "",
            "## Compact Structured Edit Examples",
            "",
            "| payload | chars | ratio vs full template replacement |",
            "| --- | ---: | ---: |",
            f"| full replacement template | `{examples['replacement_template_payload_chars']}` | `1.0` |",
            f"| structured one-line edit | `{examples['structured_one_line_payload_chars']}` | `{examples['one_line_vs_replacement_ratio']:.3f}` |",
            f"| structured function replacement | `{examples['structured_function_payload_chars']}` | `{examples['function_vs_replacement_ratio']:.3f}` |",
            "",
            "## Decision",
            "",
            report["decision"],
            "",
            (
                "Reason: unified diffs reduced output length somewhat, but had high apply/repair failure rates. "
                "Structured edits avoid hunk-number/context ambiguity, reject full files, and still let the harness "
                "materialize and validate the full candidate locally."
            ),
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _collect_proposals(root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in root.rglob("proposal.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        parsed = payload.get("parsed_output_json") or {}
        raw = payload.get("raw_output_text") or ""
        rows.append(
            {
                "raw_chars": len(raw),
                "edit_chars": len(parsed.get("unified_diff") or json.dumps(parsed.get("edits") or "")),
                "errors": len(payload.get("errors") or []),
                "validation_failures": len(payload.get("validation_failures") or []),
            }
        )
    return rows


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    raw = [int(row["raw_chars"]) for row in rows]
    return {
        "proposal_count": len(rows),
        "mean_raw_chars": statistics.fmean(raw),
        "median_raw_chars": statistics.median(raw),
        "max_raw_chars": max(raw),
        "estimated_mean_output_tokens_chars_over_4": statistics.fmean(raw) / 4,
        "proposal_error_count": sum(int(row["errors"]) for row in rows),
        "proposal_validation_failure_count": sum(int(row["validation_failures"]) for row in rows),
    }


def _compact_examples(parent_source: str) -> dict[str, Any]:
    replacement_payload = json.dumps(
        {
            "primary_mode": "micro",
            "declared_mode": "micro",
            "edit_format": "replacement_file",
            "rationale": "Full replacement example.",
            "solution_py": parent_source,
        }
    )
    structured_line = json.dumps(
        {
            "primary_mode": "micro",
            "declared_mode": "micro",
            "edit_format": "structured_edits",
            "rationale": "One-line local edit.",
            "edits": [{"op": "replace_exact", "old": "        return rows[:k]", "new": "        return list(rows[:k])"}],
        },
        separators=(",", ":"),
    )
    structured_function = json.dumps(
        {
            "primary_mode": "topk",
            "declared_mode": "topk",
            "edit_format": "structured_edits",
            "rationale": "Replace only top_k.",
            "edits": [
                {
                    "op": "replace_function",
                    "function": "top_k",
                    "source": (
                        "    def top_k(self, lo: int, hi: int, k: int) -> list[tuple[int, int]]:\n"
                        "        lo = int(lo)\n        hi = int(hi)\n        k = int(k)\n"
                        "        if lo > hi or k <= 0:\n            return []\n"
                        "        rows = [(key, value) for key, value in self._items if lo <= key <= hi]\n"
                        "        rows.sort(key=lambda item: (-item[1], item[0]))\n"
                        "        return rows[:k]\n"
                    ),
                }
            ],
        },
        separators=(",", ":"),
    )
    return {
        "replacement_template_payload_chars": len(replacement_payload),
        "structured_one_line_payload_chars": len(structured_line),
        "structured_function_payload_chars": len(structured_function),
        "one_line_vs_replacement_ratio": len(structured_line) / len(replacement_payload),
        "function_vs_replacement_ratio": len(structured_function) / len(replacement_payload),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json_out", default="artifacts/edit_protocol_debug_report.json")
    parser.add_argument("--md_out", default="artifacts/edit_protocol_debug_report.md")
    parser.add_argument("--parent", default="autoresearch/benchmark/cifar10/solution_template.py")
    parser.add_argument("--root", action="append", default=[], help="name=run_root. Defaults to known protocol roots.")
    args = parser.parse_args(argv)
    roots = dict(DEFAULT_ROOTS)
    for item in args.root:
        name, root = item.split("=", 1)
        roots[name] = root
    report = build_report(roots, Path(args.parent))
    write_json(Path(args.json_out), report)
    write_markdown(report, Path(args.md_out))
    print(json.dumps({"json_out": args.json_out, "md_out": args.md_out, "observed": len(report["observed_logs"])}, indent=2))


if __name__ == "__main__":
    main()
