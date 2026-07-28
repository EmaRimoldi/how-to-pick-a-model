"""Wrapper around the official SWE-bench evaluation harness."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EvaluationResult:
    manifest: dict[str, Any]
    returncode: int | None


BACKENDS = {"local", "docker", "modal"}


def build_command(
    *,
    dataset_name: str,
    split: str,
    predictions_path: Path,
    run_id: str,
    max_workers: int,
    timeout: int,
    instance_ids: list[str] | None = None,
    modal: bool = False,
    force_rebuild: bool = False,
    cache_level: str = "env",
    clean: bool = False,
    namespace: str | None = "swebench",
    rewrite_reports: bool = False,
    report_dir: Path | None = None,
) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "swebench.harness.run_evaluation",
        "--dataset_name",
        dataset_name,
        "--split",
        split,
        "--predictions_path",
        str(predictions_path),
        "--run_id",
        run_id,
        "--max_workers",
        str(max_workers),
        "--timeout",
        str(timeout),
        "--force_rebuild",
        str(force_rebuild).lower(),
        "--cache_level",
        cache_level,
        "--clean",
        str(clean).lower(),
        "--namespace",
        "none" if namespace is None else namespace,
        "--rewrite_reports",
        str(rewrite_reports).lower(),
        "--modal",
        str(modal).lower(),
    ]
    if instance_ids:
        command.extend(["--instance_ids", *instance_ids])
    if report_dir is not None:
        command.extend(["--report_dir", str(report_dir)])
    return command


def _normalize_backend(backend: str | None, *, modal: bool) -> str:
    selected = backend or ("modal" if modal else "local")
    if modal and selected != "modal":
        raise ValueError("--modal is only compatible with backend='modal'")
    if selected not in BACKENDS:
        raise ValueError(f"Unknown evaluation backend {selected!r}; expected one of {sorted(BACKENDS)}")
    return selected


def _load_predictions(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".jsonl":
        with path.open("r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = list(payload.values())
        if not isinstance(payload, list):
            raise ValueError("Predictions JSON must be list[prediction] or dict[instance_id, prediction].")
        if not all(isinstance(item, dict) for item in payload):
            raise ValueError("Every prediction must be a JSON object.")
        return payload
    raise ValueError("Predictions path must end with .jsonl or .json.")


def _validate_predictions(path: Path) -> dict[str, Any]:
    predictions = _load_predictions(path)
    missing_required: list[dict[str, Any]] = []
    duplicate_ids: list[str] = []
    seen: set[str] = set()
    instance_ids: list[str] = []
    model_names: list[str] = []
    model_name_by_instance: dict[str, str] = {}
    empty_patch_ids: list[str] = []
    patch_chars: list[int] = []

    for row_index, payload in enumerate(predictions, start=1):
        missing = [key for key in ("instance_id", "model_patch", "model_name_or_path") if key not in payload]
        if missing:
            missing_required.append({"row": row_index, "missing": missing})
            continue
        instance_id = str(payload["instance_id"])
        if instance_id in seen:
            duplicate_ids.append(instance_id)
        seen.add(instance_id)
        instance_ids.append(instance_id)
        model_name = str(payload["model_name_or_path"])
        model_names.append(model_name)
        model_name_by_instance[instance_id] = model_name
        patch = payload.get("model_patch")
        patch_text = "" if patch is None else str(patch)
        patch_chars.append(len(patch_text))
        if not patch_text:
            empty_patch_ids.append(instance_id)

    return {
        "rows": len(predictions),
        "missing_required_fields": len(missing_required),
        "missing_required": missing_required,
        "duplicate_instance_ids": sorted(set(duplicate_ids)),
        "empty_patch_ids": empty_patch_ids,
        "nonempty_patch_count": len(predictions) - len(empty_patch_ids) - len(missing_required),
        "instance_ids": instance_ids,
        "model_names": sorted(set(model_names)),
        "model_name_by_instance": model_name_by_instance,
        "first_model_name": model_names[0] if model_names else None,
        "patch_chars_min": min(patch_chars) if patch_chars else 0,
        "patch_chars_max": max(patch_chars) if patch_chars else 0,
    }


def _expected_report_path(*, output_dir: Path, validation: dict[str, Any], run_id: str) -> Path | None:
    model_name = validation.get("first_model_name")
    if not model_name:
        return None
    return output_dir / f"{str(model_name).replace('/', '__')}.{run_id}.json"


def _modal_token_configured() -> bool:
    if importlib.util.find_spec("modal") is None:
        return False
    return (Path.home() / ".modal.toml").exists()


def _docker_socket_available() -> bool:
    if importlib.util.find_spec("docker") is None:
        return False
    try:
        import docker

        client = docker.from_env()
        client.ping()
    except Exception:
        return False
    return True


def _preview(text: str, limit: int = 800) -> str:
    compact = "\n".join(line.rstrip() for line in text.strip().splitlines())
    return compact[:limit]


def _extract_error_summary(log_text: str) -> str | None:
    markers = [
        ">>>>> Patch Apply Failed:",
        "ResourceExhaustedError:",
        "EvaluationError:",
        "Error in evaluating model",
        "SandboxTimeoutError",
        "Traceback (most recent call last):",
    ]
    lower_bound = -1
    for marker in markers:
        index = log_text.rfind(marker)
        if index > lower_bound:
            lower_bound = index
    if lower_bound < 0:
        return None
    return _preview(log_text[lower_bound:], 1200)


def _collect_instance_results(*, output_dir: Path, validation: dict[str, Any], run_id: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    first_model_name = validation.get("first_model_name")
    model_name_by_instance = validation.get("model_name_by_instance") or {}
    if not first_model_name and not model_name_by_instance:
        return results
    base_log_dir = output_dir / "logs" / "run_evaluation" / run_id
    for instance_id in validation["instance_ids"]:
        model_name = model_name_by_instance.get(instance_id, first_model_name)
        candidate_dirs: list[Path] = []
        if model_name:
            candidate_dirs.append(base_log_dir / str(model_name).replace("/", "__") / instance_id)
        if base_log_dir.exists():
            candidate_dirs.extend(base_log_dir.glob(f"*/{instance_id}"))

        seen_dirs: set[str] = set()
        unique_dirs: list[Path] = []
        for candidate in candidate_dirs:
            key = str(candidate)
            if key not in seen_dirs:
                seen_dirs.add(key)
                unique_dirs.append(candidate)

        log_dir = unique_dirs[0] if unique_dirs else base_log_dir / str(instance_id)
        for candidate in unique_dirs:
            if (
                (candidate / "report.json").exists()
                or (candidate / "test_output.txt").exists()
                or (candidate / "run_instance.log").exists()
            ):
                log_dir = candidate
                break

        report_path = log_dir / "report.json"
        test_output_path = log_dir / "test_output.txt"
        run_log_path = log_dir / "run_instance.log"
        result: dict[str, Any] = {
            "instance_id": instance_id,
            "model_name_or_path": model_name,
            "log_dir": str(log_dir),
            "report_path": str(report_path),
            "report_exists": report_path.exists(),
            "report_bytes": report_path.stat().st_size if report_path.exists() else 0,
            "test_output_path": str(test_output_path),
            "test_output_bytes": test_output_path.stat().st_size if test_output_path.exists() else 0,
            "run_instance_log_path": str(run_log_path),
            "run_instance_log_exists": run_log_path.exists(),
        }
        if report_path.exists() and report_path.stat().st_size:
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
                result["resolved"] = bool(report.get(instance_id, {}).get("resolved", False))
            except json.JSONDecodeError:
                result["report_parse_error"] = "invalid_json"
        if run_log_path.exists():
            log_text = run_log_path.read_text(encoding="utf-8", errors="replace")
            result["patch_apply_failed"] = ">>>>> Patch Apply Failed" in log_text
            result["error_summary"] = _extract_error_summary(log_text)
        results.append(result)
    return results


def _fresh_log_path(output_dir: Path, filename: str) -> Path:
    path = output_dir / filename
    if not path.exists():
        return path
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = path.stem
    suffix = path.suffix
    return output_dir / f"{stem}_{timestamp}{suffix}"


def _safe_model_name(model_name: str | None) -> str:
    return str(model_name or "None").replace("/", "__")


def _venv_env(venv_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["VIRTUAL_ENV"] = str(venv_dir)
    env["PATH"] = f"{venv_dir / 'bin'}{os.pathsep}{env.get('PATH', '')}"
    env.setdefault("PYTHONNOUSERSITE", "1")
    return env


def _run_logged(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None,
    log,
    timeout: int | None = None,
) -> int:
    log.write("\n$ " + " ".join(shlex.quote(part) for part in command) + "\n")
    log.flush()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        log.write(f"\nTimeout after {timeout}s\n")
        log.flush()
        return 124
    return int(completed.returncode)


def _local_script_lines(lines: list[str], *, repo_dir: Path) -> list[str]:
    rewritten: list[str] = []
    skip_prefixes = (
        "source /opt/miniconda",
        "conda ",
        "mamba ",
        "micromamba ",
    )
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(skip_prefixes):
            continue
        rewritten.append(raw_line.replace("/testbed", str(repo_dir)))
    return rewritten


def _write_local_script(path: Path, lines: list[str], *, repo_dir: Path, exit_on_error: bool) -> None:
    header = ["#!/usr/bin/env bash", "set -uxo pipefail"]
    if exit_on_error:
        header = ["#!/usr/bin/env bash", "set -euxo pipefail"]
    path.write_text("\n".join(header + _local_script_lines(lines, repo_dir=repo_dir)) + "\n", encoding="utf-8")
    path.chmod(0o755)


def _ensure_local_venv(venv_dir: Path, *, python_executable: str, log, cwd: Path) -> Path:
    python_path = venv_dir / "bin" / "python"
    if not python_path.exists():
        venv_dir.parent.mkdir(parents=True, exist_ok=True)
        code = _run_logged([python_executable, "-m", "venv", str(venv_dir)], cwd=cwd, env=None, log=log)
        if code:
            raise RuntimeError(f"local_venv_create_failed:{code}")
    code = _run_logged(
        [str(python_path), "-m", "pip", "install", "-U", "pip", "setuptools", "wheel"],
        cwd=cwd,
        env=_venv_env(venv_dir),
        log=log,
    )
    if code:
        raise RuntimeError(f"local_venv_bootstrap_failed:{code}")
    return python_path


def _apply_prediction_patch(repo_dir: Path, patch_path: Path, *, log) -> tuple[bool, str | None]:
    commands = [
        ["git", "apply", "--verbose", str(patch_path)],
        ["git", "apply", "--verbose", "--reject", str(patch_path)],
        ["patch", "--batch", "--fuzz=5", "-p1", "-i", str(patch_path)],
    ]
    last_code: int | None = None
    for command in commands:
        last_code = _run_logged(command, cwd=repo_dir, env=None, log=log)
        if last_code == 0:
            return True, None
        _run_logged(["git", "reset", "--hard"], cwd=repo_dir, env=None, log=log)
        _run_logged(["git", "clean", "-fd"], cwd=repo_dir, env=None, log=log)
    return False, f">>>>> Patch Apply Failed:\nlast_exit_code={last_code}"


def _manual_report_for_unapplied_patch(instance_id: str, *, prediction: dict[str, Any]) -> dict[str, Any]:
    return {
        instance_id: {
            "patch_is_None": prediction.get("model_patch") is None,
            "patch_exists": prediction.get("model_patch") is not None,
            "patch_successfully_applied": False,
            "resolved": False,
        }
    }


def _manual_report_for_applied_patch(instance_id: str, *, prediction: dict[str, Any]) -> dict[str, Any]:
    return {
        instance_id: {
            "patch_is_None": prediction.get("model_patch") is None,
            "patch_exists": prediction.get("model_patch") is not None,
            "patch_successfully_applied": True,
            "resolved": False,
        }
    }


def _run_local_instance(
    *,
    instance: dict[str, Any],
    prediction: dict[str, Any],
    test_spec: Any,
    output_dir: Path,
    run_id: str,
    timeout: int,
    python_executable: str,
    keep_workdir: bool,
) -> dict[str, Any]:
    from swebench.harness.grading import get_eval_report

    instance_id = str(instance["instance_id"])
    model_name = _safe_model_name(prediction.get("model_name_or_path"))
    log_dir = output_dir / "logs" / "run_evaluation" / run_id / model_name / instance_id
    repo_dir = log_dir / "testbed"
    venv_dir = log_dir / ".venv"
    patch_path = log_dir / "patch.diff"
    test_output_path = log_dir / "test_output.txt"
    report_path = log_dir / "report.json"
    run_log_path = log_dir / "run_instance.log"
    log_dir.mkdir(parents=True, exist_ok=True)

    if report_path.exists() and report_path.stat().st_size:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        return {"completed": True, "resolved": bool(report.get(instance_id, {}).get("resolved", False))}

    completed = False
    resolved = False
    report: dict[str, Any] = _manual_report_for_unapplied_patch(instance_id, prediction=prediction)
    if not str(prediction.get("model_patch") or "").strip():
        log_dir.mkdir(parents=True, exist_ok=True)
        run_log_path.write_text("local_backend=venv\nempty_patch=true\n", encoding="utf-8")
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        return {"completed": False, "resolved": False, "empty_patch": True}
    try:
        with run_log_path.open("w", encoding="utf-8") as log:
            log.write("local_backend=venv\n")
            log.write("docker_required=false\nmodal_required=false\n")
            log.write(f"python_executable={python_executable}\n")
            log.write(f"repo={instance['repo']}\nbase_commit={instance['base_commit']}\n")

            if repo_dir.exists():
                shutil.rmtree(repo_dir)
            clone_url = f"https://github.com/{instance['repo']}"
            code = _run_logged(["git", "clone", clone_url, str(repo_dir)], cwd=log_dir, env=None, log=log)
            if code:
                raise RuntimeError(f"local_git_clone_failed:{code}")
            for command in (
                ["git", "reset", "--hard", str(instance["base_commit"])],
                ["git", "remote", "remove", "origin"],
                ["git", "config", "user.email", "local@swebench.invalid"],
                ["git", "config", "user.name", "SWE-bench local"],
                ["git", "config", "--global", "--add", "safe.directory", str(repo_dir)],
            ):
                _run_logged(command, cwd=repo_dir, env=None, log=log)

            patch_path.write_text(str(prediction.get("model_patch") or ""), encoding="utf-8")
            applied, patch_error = _apply_prediction_patch(repo_dir, patch_path, log=log)
            if not applied:
                log.write((patch_error or ">>>>> Patch Apply Failed:") + "\n")
                report = _manual_report_for_unapplied_patch(instance_id, prediction=prediction)
                report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
                return {"completed": False, "resolved": False}
            report = _manual_report_for_applied_patch(instance_id, prediction=prediction)

            _ensure_local_venv(venv_dir, python_executable=python_executable, log=log, cwd=log_dir)
            env = _venv_env(venv_dir)
            env_script = log_dir / "setup_env_local.sh"
            _write_local_script(env_script, test_spec.env_script_list, repo_dir=repo_dir, exit_on_error=True)
            code = _run_logged(["bash", str(env_script)], cwd=repo_dir, env=env, log=log)
            if code:
                raise RuntimeError(f"local_env_setup_failed:{code}")
            code = _run_logged([str(venv_dir / "bin" / "python"), "-m", "pip", "install", "-e", "."], cwd=repo_dir, env=env, log=log)
            if code:
                raise RuntimeError(f"local_repo_install_failed:{code}")

            eval_script = log_dir / "eval_local.sh"
            _write_local_script(eval_script, test_spec.eval_script_list, repo_dir=repo_dir, exit_on_error=False)

        with test_output_path.open("w", encoding="utf-8") as test_log:
            _run_logged(["bash", str(eval_script)], cwd=repo_dir, env=_venv_env(venv_dir), log=test_log, timeout=timeout)

        report = get_eval_report(
            test_spec=test_spec,
            prediction=prediction,
            test_log_path=str(test_output_path),
            include_tests_status=True,
        )
        completed = True
        resolved = bool(report.get(instance_id, {}).get("resolved", False))
    except Exception as exc:
        with run_log_path.open("a", encoding="utf-8") as log:
            log.write(f"\nEvaluationError:{type(exc).__name__}:{exc}\n")
        completed = False
        resolved = False
    finally:
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        if not keep_workdir:
            shutil.rmtree(repo_dir, ignore_errors=True)
            shutil.rmtree(venv_dir, ignore_errors=True)
    return {"completed": completed, "resolved": resolved, "workdir_kept": keep_workdir}


def _run_local_evaluation(
    *,
    dataset_name: str,
    split: str,
    predictions: list[dict[str, Any]],
    requested_instance_ids: list[str],
    output_dir: Path,
    run_id: str,
    timeout: int,
    python_executable: str | None,
    keep_workdir: bool,
    expected_report_path: Path | None,
) -> dict[str, Any]:
    from swebench.harness.test_spec.test_spec import make_test_spec
    from swebench.harness.utils import load_swebench_dataset

    python_executable = python_executable or sys.executable
    prediction_by_id = {str(row["instance_id"]): row for row in predictions if "instance_id" in row}
    missing_predictions = sorted(set(requested_instance_ids) - set(prediction_by_id))
    if missing_predictions:
        raise SystemExit(f"Missing predictions for local backend instance ids: {missing_predictions}")

    dataset = load_swebench_dataset(dataset_name, split)
    instance_by_id = {str(row["instance_id"]): row for row in dataset}
    missing_instances = sorted(set(requested_instance_ids) - set(instance_by_id))
    if missing_instances:
        raise SystemExit(f"Instance ids not present in dataset: {missing_instances}")

    aggregate_report: dict[str, Any] = {}
    run_results: dict[str, dict[str, Any]] = {}
    for instance_id in requested_instance_ids:
        instance = instance_by_id[instance_id]
        prediction = prediction_by_id[instance_id]
        result = _run_local_instance(
            instance=instance,
            prediction=prediction,
            test_spec=make_test_spec(instance, namespace=None),
            output_dir=output_dir,
            run_id=run_id,
            timeout=timeout,
            python_executable=python_executable,
            keep_workdir=keep_workdir,
        )
        run_results[instance_id] = result
        report_path = (
            output_dir
            / "logs"
            / "run_evaluation"
            / run_id
            / _safe_model_name(prediction.get("model_name_or_path"))
            / instance_id
            / "report.json"
        )
        if report_path.exists() and report_path.stat().st_size:
            aggregate_report.update(json.loads(report_path.read_text(encoding="utf-8")))

    if expected_report_path is not None:
        expected_report_path.write_text(json.dumps(aggregate_report, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "backend": "local",
        "local_backend": "venv",
        "python_executable": python_executable,
        "run_results": run_results,
        "report": aggregate_report,
        "completed": all(item.get("completed") for item in run_results.values()),
    }


def run_evaluation(
    *,
    dataset_name: str,
    split: str,
    predictions_path: Path,
    run_id: str,
    max_workers: int,
    timeout: int,
    execute: bool,
    output_dir: Path,
    instance_ids: list[str] | None = None,
    modal: bool = False,
    force_rebuild: bool = False,
    cache_level: str = "env",
    clean: bool = False,
    namespace: str | None = "swebench",
    rewrite_reports: bool = False,
    backend: str | None = None,
    local_python: str | None = None,
    keep_local_workdir: bool = False,
) -> EvaluationResult:
    backend = _normalize_backend(backend, modal=modal)
    modal = backend == "modal"
    predictions_path = predictions_path.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir = output_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    validation = _validate_predictions(predictions_path)
    requested_instance_ids = instance_ids or validation["instance_ids"]
    command = None
    if backend in {"docker", "modal"}:
        command = build_command(
            dataset_name=dataset_name,
            split=split,
            predictions_path=predictions_path,
            run_id=run_id,
            max_workers=max_workers,
            timeout=timeout,
            instance_ids=requested_instance_ids,
            modal=modal,
            force_rebuild=force_rebuild,
            cache_level=cache_level,
            clean=clean,
            namespace=namespace,
            rewrite_reports=rewrite_reports,
            report_dir=report_dir,
        )
    expected_report_path = _expected_report_path(output_dir=output_dir, validation=validation, run_id=run_id)
    manifest: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_name": dataset_name,
        "split": split,
        "predictions_path": str(predictions_path),
        "run_id": run_id,
        "output_dir": str(output_dir),
        "report_dir": str(report_dir),
        "logs_dir": str(output_dir / "logs" / "run_evaluation" / run_id),
        "expected_report_path": str(expected_report_path) if expected_report_path else None,
        "prediction_validation": validation,
        "command": command,
        "backend": backend,
        "execute": execute,
        "modal": modal,
        "docker_required": backend == "docker",
        "modal_required": backend == "modal",
        "modal_installed": importlib.util.find_spec("modal") is not None,
        "modal_token_configured": _modal_token_configured(),
        "swebench_installed": importlib.util.find_spec("swebench") is not None,
        "docker_socket_available": _docker_socket_available() if backend == "docker" else None,
        "local_python": local_python or sys.executable,
        "keep_local_workdir": keep_local_workdir,
    }
    manifest["instance_results"] = _collect_instance_results(
        output_dir=output_dir,
        validation=validation,
        run_id=run_id,
    )

    manifest_path = output_dir / "evaluation_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    if validation["missing_required_fields"] or validation["duplicate_instance_ids"]:
        raise SystemExit(json.dumps(manifest, indent=2, sort_keys=True))
    if not execute:
        return EvaluationResult(manifest=manifest, returncode=None)
    if not manifest["swebench_installed"]:
        command_hint = " ".join(command or [])
        raise SystemExit("The `swebench` package is not installed. Command:\n" + command_hint)
    if backend == "docker" and not manifest["docker_socket_available"]:
        raise SystemExit("Docker backend selected, but Docker is not reachable. Use --backend local for the no-Docker verifier.")
    if backend == "modal" and not manifest["modal_token_configured"]:
        raise SystemExit("Modal token is not configured. Run `python -m modal token set --verify` first.")
    if backend == "local":
        local_result = _run_local_evaluation(
            dataset_name=dataset_name,
            split=split,
            predictions=_load_predictions(predictions_path),
            requested_instance_ids=requested_instance_ids,
            output_dir=output_dir,
            run_id=run_id,
            timeout=timeout,
            python_executable=local_python,
            keep_workdir=keep_local_workdir,
            expected_report_path=expected_report_path,
        )
        manifest.update(local_result)
        manifest["returncode"] = 0 if local_result["completed"] else 1
        manifest["expected_report_exists"] = bool(expected_report_path and expected_report_path.exists())
        manifest["instance_results"] = _collect_instance_results(
            output_dir=output_dir,
            validation=validation,
            run_id=run_id,
        )
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        return EvaluationResult(manifest=manifest, returncode=int(manifest["returncode"]))

    stdout_path = _fresh_log_path(output_dir, "stdout.log")
    stderr_path = _fresh_log_path(output_dir, "stderr.log")
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        proc = subprocess.run(command, cwd=output_dir, text=True, stdout=stdout, stderr=stderr)
    manifest["returncode"] = proc.returncode
    manifest["stdout_path"] = str(stdout_path)
    manifest["stderr_path"] = str(stderr_path)
    stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace")
    stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
    manifest["stdout_bytes"] = len(stdout_text.encode("utf-8"))
    manifest["stderr_bytes"] = len(stderr_text.encode("utf-8"))
    stderr_summary = _extract_error_summary(stderr_text)
    if stderr_summary:
        manifest["stderr_error_summary"] = stderr_summary
    elif proc.returncode:
        manifest["stderr_error_summary"] = _preview(stderr_text[-1200:], 1200)
    manifest["expected_report_exists"] = bool(expected_report_path and expected_report_path.exists())
    manifest["instance_results"] = _collect_instance_results(
        output_dir=output_dir,
        validation=validation,
        run_id=run_id,
    )
    if expected_report_path and expected_report_path.exists():
        try:
            manifest["report"] = json.loads(expected_report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest["report_parse_error"] = "invalid_json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return EvaluationResult(manifest=manifest, returncode=proc.returncode)


def _parse_namespace(value: str) -> str | None:
    return None if value == "none" else value


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-name", default="princeton-nlp/SWE-Bench_Verified")
    parser.add_argument("--split", default="test")
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--run-id", default="swebench_orchestration_eval")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--instance-ids", nargs="+", default=None)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--backend", choices=sorted(BACKENDS), default="local")
    parser.add_argument("--modal", action="store_true", help="Deprecated alias for --backend modal.")
    parser.add_argument("--local-python", default=None, help="Python executable used to create local verifier venvs.")
    parser.add_argument("--keep-local-workdir", action="store_true", help="Keep local checkout and venv after evaluation.")
    parser.add_argument("--force-rebuild", action="store_true")
    parser.add_argument("--cache-level", choices=["none", "base", "env", "instance"], default="env")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--namespace", default="swebench")
    parser.add_argument("--rewrite-reports", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir) if args.output_dir else Path("swebench/studies/ad_hoc/evaluations") / args.run_id
    result = run_evaluation(
        dataset_name=args.dataset_name,
        split=args.split,
        predictions_path=Path(args.predictions),
        run_id=args.run_id,
        max_workers=args.max_workers,
        timeout=args.timeout,
        execute=args.execute,
        output_dir=output_dir,
        instance_ids=args.instance_ids,
        modal=args.modal,
        force_rebuild=args.force_rebuild,
        cache_level=args.cache_level,
        clean=args.clean,
        namespace=_parse_namespace(args.namespace),
        rewrite_reports=args.rewrite_reports,
        backend="modal" if args.modal else args.backend,
        local_python=args.local_python,
        keep_local_workdir=args.keep_local_workdir,
    )
    print(json.dumps(result.manifest, indent=2, sort_keys=True))
    if result.returncode is not None:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
