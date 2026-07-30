"""Compile active paper TeX sources into an out-of-tree build directory."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_SOURCES = ("arxiv.tex",)


def run_command(
    args: list[str],
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def ensure_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"required tool not found on PATH: {name}")
    return path


def has_bibliography(aux_path: Path) -> bool:
    if not aux_path.exists():
        return False
    text = aux_path.read_text(encoding="utf-8", errors="replace")
    return "\\bibdata" in text


def compile_source(paper_dir: Path, source: str, output_root: Path) -> dict[str, object]:
    pdflatex = ensure_tool("pdflatex")
    bibtex = shutil.which("bibtex")
    source_path = paper_dir / source
    if not source_path.exists():
        raise FileNotFoundError(source_path)

    stem = source_path.stem
    out_dir = output_root / stem
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pdflatex_cmd = [
        pdflatex,
        "-interaction=nonstopmode",
        "-halt-on-error",
        f"-output-directory={out_dir}",
        source,
    ]
    passes: list[dict[str, object]] = []
    for pass_name in ("pdflatex-1",):
        result = run_command(pdflatex_cmd, cwd=paper_dir)
        passes.append({"name": pass_name, "returncode": result.returncode})
        if result.returncode != 0:
            return build_result(source, out_dir, passes, result)

    aux_path = out_dir / f"{stem}.aux"
    if has_bibliography(aux_path):
        if not bibtex:
            raise RuntimeError("bibtex is required for bibliography-bearing paper sources")
        env = os.environ.copy()
        env["BIBINPUTS"] = f"{paper_dir}{os.pathsep}" + env.get("BIBINPUTS", "")
        env["BSTINPUTS"] = f"{paper_dir}{os.pathsep}" + env.get("BSTINPUTS", "")
        result = run_command([bibtex, stem], cwd=out_dir, env=env)
        passes.append({"name": "bibtex", "returncode": result.returncode})
        if result.returncode != 0:
            return build_result(source, out_dir, passes, result)

    for pass_name in ("pdflatex-2", "pdflatex-3"):
        result = run_command(pdflatex_cmd, cwd=paper_dir)
        passes.append({"name": pass_name, "returncode": result.returncode})
        if result.returncode != 0:
            return build_result(source, out_dir, passes, result)

    return build_result(source, out_dir, passes, None)


def build_result(
    source: str,
    out_dir: Path,
    passes: list[dict[str, object]],
    failed_result: subprocess.CompletedProcess[str] | None,
) -> dict[str, object]:
    stem = Path(source).stem
    pdf = out_dir / f"{stem}.pdf"
    result: dict[str, object] = {
        "source": source,
        "output_dir": str(out_dir),
        "pdf": str(pdf),
        "pdf_exists": pdf.exists(),
        "pdf_bytes": pdf.stat().st_size if pdf.exists() else 0,
        "passes": passes,
        "ok": failed_result is None and pdf.exists() and pdf.stat().st_size > 0,
    }
    if failed_result is not None:
        result["stdout_tail"] = failed_result.stdout[-4000:]
        result["stderr_tail"] = failed_result.stderr[-2000:]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument(
        "--output-root",
        default="/tmp/how_to_pick_a_model_paper_build",
        help="Directory for out-of-tree TeX build artifacts.",
    )
    parser.add_argument(
        "--source",
        action="append",
        dest="sources",
        help="TeX source filename under paper/neurips-submission. Repeatable.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    paper_dir = root / "paper" / "neurips-submission"
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    sources = args.sources or list(DEFAULT_SOURCES)

    try:
        results = [compile_source(paper_dir, source, output_root) for source in sources]
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    ok = all(bool(result["ok"]) for result in results)
    print(json.dumps({"ok": ok, "results": results}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
