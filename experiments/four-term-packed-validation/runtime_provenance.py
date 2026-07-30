"""Compact provenance fingerprints for SAI-3 model runs."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import subprocess
from pathlib import Path
from typing import Any


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tokenizer_fingerprint(tokenizer: Any) -> str:
    digest = hashlib.sha256()
    descriptor = {
        "class": f"{type(tokenizer).__module__}.{type(tokenizer).__qualname__}",
        "chat_template": getattr(tokenizer, "chat_template", None),
        "special_tokens_map": getattr(tokenizer, "special_tokens_map", {}),
    }
    digest.update(json.dumps(descriptor, sort_keys=True, ensure_ascii=True).encode())
    for token, token_id in sorted(tokenizer.get_vocab().items()):
        digest.update(token.encode("utf-8", errors="surrogatepass"))
        digest.update(b"\0")
        digest.update(str(token_id).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def package_versions(names: tuple[str, ...] = ("vllm", "transformers", "torch")) -> dict[str, str]:
    versions = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "unavailable"
    return versions


def git_commit(bundle: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(bundle), "rev-parse", "HEAD"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def collect_runtime_provenance(
    *,
    bundle: Path,
    tokenizer: Any,
    tasks: Path,
    design: Path | None = None,
    runtime_model: Any = None,
) -> dict[str, Any]:
    init_kwargs = getattr(tokenizer, "init_kwargs", {})
    hf_config = getattr(
        getattr(getattr(runtime_model, "llm_engine", None), "model_config", None),
        "hf_config",
        None,
    )
    revision = (
        init_kwargs.get("_commit_hash")
        or getattr(tokenizer, "_commit_hash", None)
        or getattr(hf_config, "_commit_hash", None)
        or "unavailable"
    )
    result = {
        "code_git_commit": git_commit(bundle),
        "model_revision": revision,
        "tokenizer_sha256": tokenizer_fingerprint(tokenizer),
        "tasks_sha256": sha256_path(tasks),
        "package_versions": package_versions(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
    }
    if design is not None:
        result["design_sha256"] = sha256_path(design)
    return result
