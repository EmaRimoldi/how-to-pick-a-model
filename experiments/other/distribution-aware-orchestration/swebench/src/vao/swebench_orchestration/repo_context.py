"""Leakage-safe repository materialization and context extraction for SWE-bench."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vao.swebench_orchestration.schemas import SWEInstancePublic


CODE_EXTENSIONS = {
    ".cfg",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".ini",
    ".ipynb",
    ".java",
    ".js",
    ".json",
    ".md",
    ".py",
    ".pyi",
    ".pyx",
    ".rst",
    ".rs",
    ".toml",
    ".ts",
    ".txt",
    ".yaml",
    ".yml",
}
STOPWORDS = {
    "about",
    "after",
    "against",
    "also",
    "because",
    "before",
    "being",
    "between",
    "broken",
    "cannot",
    "class",
    "code",
    "could",
    "description",
    "does",
    "error",
    "fail",
    "failing",
    "from",
    "function",
    "have",
    "issue",
    "method",
    "module",
    "object",
    "problem",
    "return",
    "should",
    "test",
    "that",
    "there",
    "this",
    "traceback",
    "type",
    "using",
    "value",
    "when",
    "with",
    "without",
}
_CACHE_LOCKS: dict[str, threading.Lock] = {}
_CACHE_LOCKS_GUARD = threading.Lock()


@dataclass(frozen=True)
class RepoContextConfig:
    enabled: bool = True
    cache_dir: Path = Path("swebench/repos/cache")
    work_dir: Path | None = None
    repo_urls: dict[str, str] = field(default_factory=dict)
    max_tree_entries: int = 160
    max_search_queries: int = 12
    max_search_hits: int = 28
    max_candidate_files: int = 8
    max_snippet_chars: int = 18_000
    command_timeout_seconds: int = 120


@dataclass(frozen=True)
class RepoContext:
    repo: str
    base_commit: str | None
    status: str
    cache_path: str | None = None
    checkout_path: str | None = None
    repo_url: str | None = None
    error: str | None = None
    tree_entries: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    search_hits: list[dict[str, Any]] = field(default_factory=list)
    candidate_files: list[str] = field(default_factory=list)
    snippets: list[dict[str, Any]] = field(default_factory=list)

    def prompt_payload(self) -> dict[str, Any]:
        return {
            "repo": self.repo,
            "base_commit": self.base_commit,
            "status": self.status,
            "tree_entries": self.tree_entries,
            "search_queries": self.search_queries,
            "search_hits": self.search_hits,
            "candidate_files": self.candidate_files,
            "snippets": self.snippets,
            "context_note": (
                "Repository context was extracted from the public repo at base_commit. "
                "Gold patches, test_patch, solution fields, and hidden verifier data were not used."
            ),
        }

    def trace_payload(self) -> dict[str, Any]:
        return {
            "repo_context_status": self.status,
            "repo_cache_path": self.cache_path,
            "repo_checkout_path": self.checkout_path,
            "repo_context_error": self.error,
            "repo_context_tree_entries": len(self.tree_entries),
            "repo_context_search_queries": self.search_queries,
            "repo_context_search_hits": len(self.search_hits),
            "repo_context_candidate_files": self.candidate_files,
            "repo_context_snippet_count": len(self.snippets),
            "repo_context_snippet_chars": sum(len(str(item.get("text", ""))) for item in self.snippets),
        }


def default_work_dir(output_dir: Path, run_id: str) -> Path:
    configured = os.environ.get("SWEBENCH_REPO_WORK_DIR")
    if configured:
        return Path(configured)
    if os.environ.get("SLURM_TMPDIR"):
        return Path(os.environ["SLURM_TMPDIR"]) / "swebench_repo_work" / run_id
    if os.environ.get("SLURM_LOCAL_ROOT"):
        return Path(os.environ["SLURM_LOCAL_ROOT"]) / "repo_work" / run_id
    return output_dir / "repo_work"


def build_repository_context(
    *,
    instance: SWEInstancePublic,
    config: RepoContextConfig,
    run_id: str,
    output_dir: Path,
) -> RepoContext:
    if not config.enabled:
        return RepoContext(repo=instance.repo, base_commit=instance.base_commit, status="disabled")
    if not instance.base_commit:
        return RepoContext(repo=instance.repo, base_commit=None, status="skipped_no_base_commit")

    cache_dir = config.cache_dir
    work_dir = config.work_dir or default_work_dir(output_dir, run_id)
    repo_url = config.repo_urls.get(instance.repo) or f"https://github.com/{instance.repo}.git"
    cache_path = cache_dir / f"{_safe_name(instance.repo)}.git"
    checkout_path = work_dir / _safe_name(instance.instance_id)
    try:
        with _cache_lock(cache_path):
            _ensure_cache(repo_url=repo_url, cache_path=cache_path, base_commit=instance.base_commit, config=config)
        _ensure_checkout(
            cache_path=cache_path,
            checkout_path=checkout_path,
            base_commit=instance.base_commit,
            config=config,
        )
        extracted = _extract_context(checkout_path=checkout_path, instance=instance, config=config)
        return RepoContext(
            repo=instance.repo,
            base_commit=instance.base_commit,
            status="ready",
            cache_path=str(cache_path),
            checkout_path=str(checkout_path),
            repo_url=repo_url,
            **extracted,
        )
    except Exception as exc:  # pragma: no cover - exact git/network failures vary.
        return RepoContext(
            repo=instance.repo,
            base_commit=instance.base_commit,
            status="error",
            cache_path=str(cache_path),
            checkout_path=str(checkout_path),
            repo_url=repo_url,
            error=f"{type(exc).__name__}:{exc}",
        )


def safe_instance_payload(instance: SWEInstancePublic) -> dict[str, Any]:
    return _drop_leaky_keys(instance.model_dump(mode="json"))


def _ensure_cache(*, repo_url: str, cache_path: Path, base_commit: str, config: RepoContextConfig) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if not cache_path.exists():
        _run_git(["git", "clone", "--mirror", repo_url, str(cache_path)], timeout=config.command_timeout_seconds)
    else:
        _run_git(["git", "-C", str(cache_path), "remote", "set-url", "origin", repo_url], timeout=30)
    if not _commit_exists(cache_path, base_commit, timeout=config.command_timeout_seconds):
        _run_git(
            [
                "git",
                "-C",
                str(cache_path),
                "fetch",
                "--prune",
                "origin",
                "+refs/heads/*:refs/heads/*",
                "+refs/tags/*:refs/tags/*",
            ],
            timeout=config.command_timeout_seconds,
        )
    if not _commit_exists(cache_path, base_commit, timeout=config.command_timeout_seconds):
        _run_git(["git", "-C", str(cache_path), "fetch", "origin", base_commit], timeout=config.command_timeout_seconds)
    if not _commit_exists(cache_path, base_commit, timeout=config.command_timeout_seconds):
        raise RuntimeError(f"base_commit {base_commit} is not available in {repo_url}")


def _cache_lock(cache_path: Path) -> threading.Lock:
    key = str(cache_path.resolve())
    with _CACHE_LOCKS_GUARD:
        lock = _CACHE_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _CACHE_LOCKS[key] = lock
        return lock


def _ensure_checkout(*, cache_path: Path, checkout_path: Path, base_commit: str, config: RepoContextConfig) -> None:
    checkout_path.parent.mkdir(parents=True, exist_ok=True)
    if not (checkout_path / ".git").exists():
        if checkout_path.exists() and any(checkout_path.iterdir()):
            raise RuntimeError(f"checkout path exists and is not a git checkout: {checkout_path}")
        _run_git(
            ["git", "clone", "--shared", "--no-checkout", str(cache_path), str(checkout_path)],
            timeout=config.command_timeout_seconds,
        )
    _run_git(
        ["git", "-C", str(checkout_path), "checkout", "--force", base_commit],
        timeout=config.command_timeout_seconds,
    )
    _run_git(["git", "-C", str(checkout_path), "reset", "--hard", base_commit], timeout=config.command_timeout_seconds)
    _run_git(["git", "-C", str(checkout_path), "clean", "-fdx"], timeout=config.command_timeout_seconds)


def _extract_context(*, checkout_path: Path, instance: SWEInstancePublic, config: RepoContextConfig) -> dict[str, Any]:
    tree_entries = _repo_files(checkout_path, timeout=config.command_timeout_seconds)
    tree_set = set(tree_entries)
    explicit_files = [
        resolved
        for raw in _explicit_file_mentions(instance.problem_statement)
        if (resolved := _resolve_repo_path(raw, tree_set)) is not None
    ]
    queries = _search_queries(instance.problem_statement, limit=config.max_search_queries)
    hits = _search_repo(
        checkout_path,
        queries=queries,
        max_hits=config.max_search_hits,
        timeout=config.command_timeout_seconds,
    )
    scored: dict[str, int] = {}
    for path in explicit_files:
        scored[path] = scored.get(path, 0) + 20
    for hit in hits:
        path = str(hit.get("path", ""))
        if path in tree_set:
            scored[path] = scored.get(path, 0) + _search_hit_score(hit)
    for entry in tree_entries:
        lowered = entry.lower()
        for query in queries[:5]:
            if query.lower() in lowered:
                scored[entry] = scored.get(entry, 0) + 2

    high_signal_hit_files = _dedupe(
        str(hit.get("path", ""))
        for hit in hits
        if str(hit.get("path", "")) in tree_set
        and _is_context_file(str(hit.get("path", "")))
        and _is_high_signal_query(str(hit.get("query", "")))
    )
    candidate_files = [
        path
        for path in _dedupe(
            high_signal_hit_files
            + [path for path, _score in sorted(scored.items(), key=lambda item: (-item[1], item[0]))]
        )
        if _is_context_file(path)
    ][: max(config.max_candidate_files, 0)]
    snippet_files = candidate_files or explicit_files[: max(config.max_candidate_files, 0)]
    snippets = _snippets(
        checkout_path=checkout_path,
        files=snippet_files,
        hits=hits,
        max_chars=max(config.max_snippet_chars, 0),
    )
    return {
        "tree_entries": _tree_sample(tree_entries, limit=config.max_tree_entries),
        "search_queries": queries,
        "search_hits": hits,
        "candidate_files": candidate_files,
        "snippets": snippets,
    }


def _run_git(cmd: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def _commit_exists(repo_path: Path, commit: str, *, timeout: int) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "cat-file", "-e", f"{commit}^{{commit}}"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return result.returncode == 0


def _repo_files(checkout_path: Path, *, timeout: int) -> list[str]:
    result = _run_git(["git", "-C", str(checkout_path), "ls-tree", "-r", "--name-only", "HEAD"], timeout=timeout)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _explicit_file_mentions(text: str) -> list[str]:
    pattern = re.compile(
        r"(?:[~./\w-]+/)?[\w.-]+(?:/[\w.-]+)+"
        r"\.(?:py|pyi|pyx|c|cc|cpp|h|hpp|js|ts|java|rs|toml|cfg|ini|yaml|yml|rst|md|txt)"
    )
    return _dedupe(match.group(0).strip("`'\".,:;()[]{}") for match in pattern.finditer(text))


def _resolve_repo_path(raw_path: str, tree_entries: set[str]) -> str | None:
    normalized = raw_path.replace("\\", "/").lstrip("./")
    parts = [part for part in normalized.split("/") if part and part != "~"]
    for start in range(len(parts)):
        suffix = "/".join(parts[start:])
        if suffix in tree_entries:
            return suffix
    basename_matches = [entry for entry in tree_entries if entry.endswith("/" + parts[-1]) or entry == parts[-1]]
    if len(basename_matches) == 1:
        return basename_matches[0]
    return None


def _search_queries(text: str, *, limit: int) -> list[str]:
    raw_tokens: list[str] = []
    raw_tokens.extend(match.group(1) for match in re.finditer(r"`([^`\n]{3,120})`", text))
    raw_tokens.extend(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{2,}(?:\.[A-Za-z_][A-Za-z0-9_]{2,})*\b", text))
    tokens: list[str] = []
    for token in raw_tokens:
        cleaned = token.strip().strip("'\".,:;()[]{}")
        if "\n" in cleaned or len(cleaned) < 3 or len(cleaned) > 80:
            continue
        lowered = cleaned.lower()
        if lowered in STOPWORDS or lowered.startswith("http"):
            continue
        tokens.append(cleaned)
        if "." in cleaned:
            tokens.append(cleaned.rsplit(".", 1)[-1])
    ranked = sorted(_dedupe(tokens), key=lambda item: (-_query_score(item), item.lower()))
    return ranked[: max(limit, 0)]


def _query_score(token: str) -> int:
    score = min(len(token), 30)
    if "." in token:
        score += 8
    if "_" in token:
        score += 4
    if any(char.isupper() for char in token):
        score += 3
    return score


def _search_hit_score(hit: dict[str, Any]) -> int:
    query = str(hit.get("query", ""))
    score = 4
    if _is_high_signal_query(query):
        score += 16
    if len(query) >= 12:
        score += 4
    if str(hit.get("text", "")).find(query) >= 0:
        score += 2
    return score


def _is_high_signal_query(query: str) -> bool:
    stripped = query.strip()
    if len(stripped) < 4:
        return False
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", stripped):
        return False
    return any(not char.isalnum() and char not in {"_", "."} for char in stripped) or any(
        char.isdigit() for char in stripped
    )


def _search_repo(checkout_path: Path, *, queries: list[str], max_hits: int, timeout: int) -> list[dict[str, Any]]:
    if max_hits <= 0 or not queries:
        return []
    if shutil.which("rg") is None:
        return _search_repo_python(checkout_path, queries=queries, max_hits=max_hits)
    hits: list[dict[str, Any]] = []
    per_query = max(2, max_hits // max(len(queries), 1))
    for query in queries:
        result = subprocess.run(
            [
                "rg",
                "-n",
                "--fixed-strings",
                "--max-count",
                str(per_query),
                "--glob",
                "!.git",
                "--",
                query,
                ".",
            ],
            cwd=checkout_path,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        if result.returncode not in (0, 1):
            continue
        for line in result.stdout.splitlines():
            parsed = _parse_rg_line(line, query=query)
            if parsed is not None:
                hits.append(parsed)
                if len(hits) >= max_hits:
                    return hits
    return hits


def _search_repo_python(checkout_path: Path, *, queries: list[str], max_hits: int) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    query_lowers = [(query, query.lower()) for query in queries]
    for path in sorted(checkout_path.rglob("*")):
        if len(hits) >= max_hits or not path.is_file() or ".git" in path.parts or not _is_context_file(path.name):
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        rel = path.relative_to(checkout_path).as_posix()
        for line_no, line in enumerate(lines, start=1):
            lowered = line.lower()
            for query, query_lower in query_lowers:
                if query_lower in lowered:
                    hits.append({"query": query, "path": rel, "line": line_no, "text": _preview(line, 220)})
                    break
            if len(hits) >= max_hits:
                return hits
    return hits


def _parse_rg_line(line: str, *, query: str) -> dict[str, Any] | None:
    if line.startswith("./"):
        line = line[2:]
    parts = line.split(":", 2)
    if len(parts) != 3:
        return None
    path, line_no, text = parts
    try:
        parsed_line = int(line_no)
    except ValueError:
        return None
    return {"query": query, "path": path, "line": parsed_line, "text": _preview(text, 220)}


def _snippets(
    *,
    checkout_path: Path,
    files: list[str],
    hits: list[dict[str, Any]],
    max_chars: int,
) -> list[dict[str, Any]]:
    if max_chars <= 0:
        return []
    hit_lines: dict[str, list[int]] = {}
    for hit in hits:
        path = str(hit.get("path", ""))
        line = hit.get("line")
        if isinstance(line, int):
            hit_lines.setdefault(path, []).append(line)

    snippets: list[dict[str, Any]] = []
    remaining = max_chars
    for rel_path in files:
        path = checkout_path / rel_path
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        windows = _line_windows(hit_lines.get(rel_path) or [1], total_lines=len(lines))
        for start, end in windows:
            numbered = [f"{line_no}: {lines[line_no - 1]}" for line_no in range(start, end + 1)]
            text = "\n".join(numbered)
            if len(text) > remaining:
                text = text[:remaining]
            if not text:
                continue
            snippets.append({"path": rel_path, "start_line": start, "end_line": end, "text": text})
            remaining -= len(text)
            if remaining <= 0:
                return snippets
    return snippets


def _line_windows(lines: list[int], *, total_lines: int) -> list[tuple[int, int]]:
    windows: list[tuple[int, int]] = []
    for line in sorted(set(lines))[:3]:
        start = max(1, line - 45)
        end = min(total_lines, line + 75)
        if windows and start <= windows[-1][1] + 5:
            windows[-1] = (windows[-1][0], max(windows[-1][1], end))
        else:
            windows.append((start, end))
    return windows


def _tree_sample(entries: list[str], *, limit: int) -> list[str]:
    code_entries = [entry for entry in entries if _is_context_file(entry)]
    scored = sorted(code_entries, key=lambda item: (item.count("/"), item))
    return scored[: max(limit, 0)]


def _is_context_file(path: str) -> bool:
    suffix = Path(path).suffix.lower()
    return suffix in CODE_EXTENSIONS


def _drop_leaky_keys(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in {"patch", "test_patch", "solution", "gold_patch", "fail_to_pass", "pass_to_pass"}:
                continue
            if "solution" in lowered or "gold" in lowered or "test_patch" in lowered:
                continue
            clean[key] = _drop_leaky_keys(child)
        return clean
    if isinstance(value, list):
        return [_drop_leaky_keys(item) for item in value]
    return value


def _dedupe(values: Any) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        item = str(value)
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _safe_name(value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "__", value).strip("._-")
    return f"{cleaned}_{digest}"


def _preview(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."
